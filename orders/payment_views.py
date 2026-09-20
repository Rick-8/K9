import os
import uuid
from decimal import Decimal, ROUND_HALF_UP

import requests
import stripe

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .activity import log_job_activity
from .models import (
    BespokeApprovalPayment,
    BespokeOrderWorkflow,
    BespokeQuote,
    OrderCommunication,
)


# =========================================================
# CONFIGURATION
# =========================================================

def env_value(name, default=""):
    return os.environ.get(name, default).strip()


def stripe_secret_key():
    return env_value("STRIPE_SECRET_KEY")


def stripe_webhook_secret():
    return env_value("STRIPE_WEBHOOK_SECRET")


def paypal_client_id():
    return env_value("PAYPAL_CLIENT_ID")


def paypal_client_secret():
    return env_value("PAYPAL_CLIENT_SECRET")


def paypal_mode():
    return env_value(
        "PAYPAL_MODE",
        "sandbox",
    ).lower()


def paypal_base_url():
    if paypal_mode() == "live":
        return "https://api-m.paypal.com"

    return "https://api-m.sandbox.paypal.com"


# =========================================================
# SHARED HELPERS
# =========================================================

def amount_to_minor_units(amount):
    return int(
        (
            Decimal(amount)
            * Decimal("100")
        ).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )


def amount_to_string(amount):
    return (
        Decimal(amount)
        .quantize(
            Decimal("0.01")
        )
        .to_eng_string()
    )


def get_payable_approval(token):
    return get_object_or_404(
        BespokeApprovalPayment.objects
        .select_related(
            "workflow",
            "workflow__order",
            "quote",
        ),
        approval_token=token,
    )


def validate_payable_approval(approval):
    quote = approval.quote

    if not quote:
        return False

    if not approval.customer_approved:
        return False

    if quote.status != BespokeQuote.Status.ACCEPTED:
        return False

    if approval.amount_due <= Decimal("0.00"):
        return False

    return True


def finalize_successful_payment(
    approval_id,
    provider,
    payment_reference,
    checkout_reference,
    metadata=None,
):
    """
    Mark payment as paid and move the job to Step 6.

    Idempotent so Stripe webhooks/returns or repeated callbacks
    do not duplicate activity.
    """

    with transaction.atomic():

        approval = (
            BespokeApprovalPayment.objects
            .select_for_update()
            .get(pk=approval_id)
        )

        workflow = (
            BespokeOrderWorkflow.objects
            .select_for_update()
            .select_related("order")
            .get(pk=approval.workflow_id)
        )

        order = workflow.order

        if (
            approval.payment_status
            == BespokeApprovalPayment
            .PaymentStatus
            .PAID
        ):
            return approval

        approval.mark_paid(
            provider=provider,
            reference=payment_reference,
            checkout_reference=checkout_reference,
            metadata=metadata or {},
        )

        order.order_total = approval.amount_due

        order.save(
            update_fields=[
                "order_total",
                "updated_at",
            ]
        )

        workflow.current_step = (
            BespokeOrderWorkflow
            .Step
            .PRODUCTION
        )

        workflow.stage = (
            BespokeOrderWorkflow
            .Stage
            .PRODUCTION
        )

        workflow.customer_waiting = False
        workflow.customer_waiting_since = None
        workflow.next_action = (
            "Payment received. Begin production."
        )

        workflow.save(
            update_fields=[
                "current_step",
                "stage",
                "customer_waiting",
                "customer_waiting_since",
                "next_action",
                "updated_at",
            ]
        )

        OrderCommunication.objects.create(
            order=order,
            channel=(
                OrderCommunication
                .Channel
                .OTHER
            ),
            context=(
                OrderCommunication
                .Context
                .PAYMENT
            ),
            direction=(
                OrderCommunication
                .Direction
                .INCOMING
            ),
            status=(
                OrderCommunication
                .Status
                .RECEIVED
            ),
            summary=(
                "Payment received via "
                f"{approval.get_payment_provider_display()}."
            ),
            content=(
                f"Payment received: "
                f"£{approval.amount_due:.2f}\n"
                f"Provider: "
                f"{approval.get_payment_provider_display()}\n"
                f"Payment reference: "
                f"{approval.payment_reference}"
            ),
            from_address=(
                approval.approved_email
                or order.customer_email
            ),
            to_address="K9",
            thread_reference=(
                f"payment:{approval.pk}"
            ),
            occurred_at=timezone.now(),
        )

        log_job_activity(
            order=order,
            user=None,
            message=(
                f"Payment of £{approval.amount_due:.2f} "
                f"received via "
                f"{approval.get_payment_provider_display()}. "
                "Workflow automatically moved to "
                "Step 6: Production."
            ),
        )

        return approval


# =========================================================
# STRIPE
# =========================================================

@require_POST
def stripe_start(request, token):

    approval = get_payable_approval(token)

    if (
        approval.payment_status
        == BespokeApprovalPayment
        .PaymentStatus
        .PAID
    ):
        return redirect(
            "customer_quote_review",
            token=approval.approval_token,
        )

    if not validate_payable_approval(approval):
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_error=not_ready"
        )

    secret_key = stripe_secret_key()

    if not secret_key:
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_error=stripe_config"
        )

    stripe.api_key = secret_key

    order = approval.workflow.order
    quote = approval.quote

    success_url = (
        request.build_absolute_uri(
            reverse(
                "stripe_return",
                kwargs={
                    "token": approval.approval_token,
                },
            )
        )
        + "?session_id={CHECKOUT_SESSION_ID}"
    )

    cancel_url = (
        request.build_absolute_uri(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
        )
        + "?payment_cancelled=stripe"
    )

    try:

        session = (
            stripe.checkout.Session.create(
                mode="payment",
                client_reference_id=(
                    order.reference_number
                ),
                customer_email=(
                    order.customer_email
                ),
                line_items=[
                    {
                        "price_data": {
                            "currency": "gbp",
                            "product_data": {
                                "name": (
                                    "K9 Bespoke Order "
                                    f"{order.reference_number}"
                                ),
                                "description": (
                                    "Accepted Quote "
                                    f"V{quote.version}"
                                ),
                            },
                            "unit_amount": (
                                amount_to_minor_units(
                                    approval.amount_due
                                )
                            ),
                        },
                        "quantity": 1,
                    },
                ],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "approval_id": str(
                        approval.pk
                    ),
                    "order_reference": (
                        order.reference_number
                    ),
                    "quote_id": str(
                        quote.pk
                    ),
                },
                payment_intent_data={
                    "metadata": {
                        "approval_id": str(
                            approval.pk
                        ),
                        "order_reference": (
                            order.reference_number
                        ),
                    }
                },
            )
        )

    except Exception:

        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_error=stripe"
        )

    approval.payment_provider = (
        BespokeApprovalPayment
        .PaymentProvider
        .STRIPE
    )

    approval.checkout_reference = session.id

    approval.payment_status = (
        BespokeApprovalPayment
        .PaymentStatus
        .PROCESSING
    )

    approval.payment_metadata = {
        "stripe_checkout_session": session.id,
    }

    approval.save(
        update_fields=[
            "payment_provider",
            "checkout_reference",
            "payment_status",
            "payment_metadata",
            "updated_at",
        ]
    )

    return redirect(session.url)


@require_GET
def stripe_return(request, token):

    approval = get_payable_approval(token)

    if (
        approval.payment_status
        == BespokeApprovalPayment
        .PaymentStatus
        .PAID
    ):
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_success=stripe"
        )

    secret_key = stripe_secret_key()

    session_id = request.GET.get(
        "session_id",
        "",
    ).strip()

    if not secret_key or not session_id:
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_error=stripe_return"
        )

    stripe.api_key = secret_key

    try:
        session = (
            stripe.checkout.Session.retrieve(
                session_id
            )
        )

    except Exception:
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_error=stripe_return"
        )

    expected_amount = amount_to_minor_units(
        approval.amount_due
    )

    metadata_approval_id = str(
        session.metadata.get(
            "approval_id",
            "",
        )
    )

    if (
        metadata_approval_id != str(approval.pk)
        or session.currency != "gbp"
        or session.amount_total != expected_amount
    ):
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_error=verification"
        )

    if session.payment_status == "paid":

        finalize_successful_payment(
            approval_id=approval.pk,
            provider=(
                BespokeApprovalPayment
                .PaymentProvider
                .STRIPE
            ),
            payment_reference=str(
                session.payment_intent
                or session.id
            ),
            checkout_reference=session.id,
            metadata={
                "stripe_session_id": session.id,
                "stripe_payment_status": (
                    session.payment_status
                ),
            },
        )

        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_success=stripe"
        )

    return redirect(
        reverse(
            "customer_quote_review",
            kwargs={
                "token": approval.approval_token,
            },
        )
        + "?payment_pending=stripe"
    )


@csrf_exempt
@require_POST
def stripe_webhook(request):

    secret_key = stripe_secret_key()
    webhook_secret = stripe_webhook_secret()

    if not secret_key or not webhook_secret:
        return HttpResponse(status=400)

    stripe.api_key = secret_key

    payload = request.body

    signature = request.META.get(
        "HTTP_STRIPE_SIGNATURE",
        "",
    )

    try:
        event = stripe.Webhook.construct_event(
            payload,
            signature,
            webhook_secret,
        )

    except Exception:
        return HttpResponse(status=400)

    if event.type in {
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
    }:

        session = event.data.object

        if session.payment_status == "paid":

            approval_id = session.metadata.get(
                "approval_id"
            )

            if approval_id:

                try:
                    approval = (
                        BespokeApprovalPayment.objects
                        .get(pk=approval_id)
                    )

                except (
                    BespokeApprovalPayment
                    .DoesNotExist
                ):
                    approval = None

                if (
                    approval
                    and session.currency == "gbp"
                    and session.amount_total
                    == amount_to_minor_units(
                        approval.amount_due
                    )
                ):

                    finalize_successful_payment(
                        approval_id=approval.pk,
                        provider=(
                            BespokeApprovalPayment
                            .PaymentProvider
                            .STRIPE
                        ),
                        payment_reference=str(
                            session.payment_intent
                            or session.id
                        ),
                        checkout_reference=session.id,
                        metadata={
                            "stripe_event_id": event.id,
                            "stripe_session_id": session.id,
                            "stripe_payment_status": (
                                session.payment_status
                            ),
                        },
                    )

    return JsonResponse(
        {
            "received": True,
        }
    )


# =========================================================
# PAYPAL
# =========================================================

def paypal_access_token():

    client_id = paypal_client_id()
    client_secret = paypal_client_secret()

    if not client_id or not client_secret:
        raise RuntimeError(
            "PayPal credentials are missing."
        )

    response = requests.post(
        paypal_base_url()
        + "/v1/oauth2/token",
        auth=(
            client_id,
            client_secret,
        ),
        data={
            "grant_type": "client_credentials",
        },
        headers={
            "Accept": "application/json",
            "Accept-Language": "en_GB",
        },
        timeout=20,
    )

    response.raise_for_status()

    return response.json()[
        "access_token"
    ]


@require_POST
def paypal_start(request, token):

    approval = get_payable_approval(token)

    if (
        approval.payment_status
        == BespokeApprovalPayment
        .PaymentStatus
        .PAID
    ):
        return redirect(
            "customer_quote_review",
            token=approval.approval_token,
        )

    if not validate_payable_approval(approval):
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_error=not_ready"
        )

    order = approval.workflow.order
    quote = approval.quote

    return_url = request.build_absolute_uri(
        reverse(
            "paypal_return",
            kwargs={
                "token": approval.approval_token,
            },
        )
    )

    cancel_url = (
        request.build_absolute_uri(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
        )
        + "?payment_cancelled=paypal"
    )

    try:

        access_token = paypal_access_token()

        response = requests.post(
            paypal_base_url()
            + "/v2/checkout/orders",
            headers={
                "Authorization": (
                    f"Bearer {access_token}"
                ),
                "Content-Type": (
                    "application/json"
                ),
                "PayPal-Request-Id": (
                    str(uuid.uuid4())
                ),
            },
            json={
                "intent": "CAPTURE",
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "brand_name": "K9",
                            "user_action": "PAY_NOW",
                            "shipping_preference": (
                                "NO_SHIPPING"
                            ),
                            "return_url": return_url,
                            "cancel_url": cancel_url,
                        }
                    }
                },
                "purchase_units": [
                    {
                        "reference_id": (
                            order.reference_number
                        ),
                        "custom_id": str(
                            approval.pk
                        ),
                        "description": (
                            "K9 Bespoke Order "
                            f"{order.reference_number} "
                            f"- Quote V{quote.version}"
                        ),
                        "amount": {
                            "currency_code": "GBP",
                            "value": (
                                amount_to_string(
                                    approval.amount_due
                                )
                            ),
                        },
                    }
                ],
            },
            timeout=20,
        )

        response.raise_for_status()
        paypal_order = response.json()

    except Exception:
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_error=paypal"
        )

    paypal_order_id = paypal_order.get(
        "id",
        "",
    )

    approval_url = ""

    for link in paypal_order.get(
        "links",
        [],
    ):

        if link.get("rel") in {
            "payer-action",
            "approve",
        }:
            approval_url = link.get(
                "href",
                "",
            )
            break

    if not paypal_order_id or not approval_url:
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_error=paypal"
        )

    approval.payment_provider = (
        BespokeApprovalPayment
        .PaymentProvider
        .PAYPAL
    )

    approval.checkout_reference = (
        paypal_order_id
    )

    approval.payment_status = (
        BespokeApprovalPayment
        .PaymentStatus
        .PROCESSING
    )

    approval.payment_metadata = {
        "paypal_order_id": paypal_order_id,
        "paypal_mode": paypal_mode(),
    }

    approval.save(
        update_fields=[
            "payment_provider",
            "checkout_reference",
            "payment_status",
            "payment_metadata",
            "updated_at",
        ]
    )

    return redirect(approval_url)


@require_GET
def paypal_return(request, token):

    approval = get_payable_approval(token)

    if (
        approval.payment_status
        == BespokeApprovalPayment
        .PaymentStatus
        .PAID
    ):
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_success=paypal"
        )

    returned_order_id = (
        request.GET.get(
            "token",
            "",
        )
        .strip()
    )

    paypal_order_id = (
        approval.checkout_reference
        or returned_order_id
    )

    if (
        not paypal_order_id
        or (
            returned_order_id
            and returned_order_id
            != paypal_order_id
        )
    ):
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_error=verification"
        )

    try:

        access_token = paypal_access_token()

        response = requests.post(
            (
                paypal_base_url()
                + "/v2/checkout/orders/"
                + paypal_order_id
                + "/capture"
            ),
            headers={
                "Authorization": (
                    f"Bearer {access_token}"
                ),
                "Content-Type": (
                    "application/json"
                ),
                "PayPal-Request-Id": (
                    "k9-capture-"
                    f"{paypal_order_id}"
                ),
            },
            json={},
            timeout=20,
        )

        response.raise_for_status()
        capture_data = response.json()

    except Exception:
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_error=paypal_capture"
        )

    capture = None

    try:
        capture = (
            capture_data[
                "purchase_units"
            ][0][
                "payments"
            ][
                "captures"
            ][0]
        )

    except (
        KeyError,
        IndexError,
        TypeError,
    ):
        capture = None

    if (
        capture_data.get("status")
        != "COMPLETED"
        or not capture
        or capture.get("status")
        != "COMPLETED"
    ):
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_pending=paypal"
        )

    captured_amount = capture.get(
        "amount",
        {},
    )

    if (
        captured_amount.get(
            "currency_code"
        ) != "GBP"
        or Decimal(
            captured_amount.get(
                "value",
                "0.00",
            )
        ) != approval.amount_due
    ):
        return redirect(
            reverse(
                "customer_quote_review",
                kwargs={
                    "token": approval.approval_token,
                },
            )
            + "?payment_error=verification"
        )

    finalize_successful_payment(
        approval_id=approval.pk,
        provider=(
            BespokeApprovalPayment
            .PaymentProvider
            .PAYPAL
        ),
        payment_reference=(
            capture.get(
                "id",
                paypal_order_id,
            )
        ),
        checkout_reference=(
            paypal_order_id
        ),
        metadata={
            "paypal_order_id": (
                paypal_order_id
            ),
            "paypal_capture_id": (
                capture.get(
                    "id",
                    "",
                )
            ),
            "paypal_status": (
                capture_data.get(
                    "status",
                    "",
                )
            ),
            "paypal_mode": paypal_mode(),
        },
    )

    return redirect(
        reverse(
            "customer_quote_review",
            kwargs={
                "token": approval.approval_token,
            },
        )
        + "?payment_success=paypal"
    )
