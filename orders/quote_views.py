from django import forms
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from .activity import log_job_activity
from .models import (
    BespokeApprovalPayment,
    BespokeOrderWorkflow,
    BespokeQuote,
    OrderCommunication,
)


class CustomerQuoteApprovalForm(forms.Form):
    """
    Public confirmation form used with the secure approval token.
    """

    response_name = forms.CharField(
        max_length=150,
        label="Your Name",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "name",
            }
        ),
    )

    response_email = forms.EmailField(
        label="Your Email",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "autocomplete": "email",
            }
        ),
    )

    approval_notes = forms.CharField(
        required=False,
        label="Optional Comments",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": (
                    "Optional comments about your acceptance..."
                ),
            }
        ),
    )

    def __init__(
        self,
        *args,
        expected_email="",
        **kwargs,
    ):
        self.expected_email = (
            expected_email
            or ""
        ).strip().lower()

        super().__init__(
            *args,
            **kwargs,
        )

    def clean_response_email(self):
        email = (
            self.cleaned_data[
                "response_email"
            ]
            .strip()
            .lower()
        )

        if (
            self.expected_email
            and email
            != self.expected_email
        ):
            raise forms.ValidationError(
                (
                    "Please use the email address that this "
                    "quotation was sent to."
                )
            )

        return email


def quote_review(
    request,
    token,
):
    """
    Public customer quote review and acceptance page.

    The UUID token acts as a secure capability link.
    No customer login is required.
    """

    approval = get_object_or_404(
        BespokeApprovalPayment.objects
        .select_related(
            "workflow",
            "workflow__order",
            "quote",
        )
        .prefetch_related(
            "quote__lines"
        ),
        approval_token=token,
    )

    workflow = approval.workflow
    order = workflow.order
    quote = approval.quote

    quote_available = bool(
        quote
        and quote.status
        in {
            BespokeQuote.Status.SENT,
            BespokeQuote.Status.ACCEPTED,
        }
    )

    already_accepted = bool(
        quote
        and (
            approval.customer_approved
            or quote.status
            == BespokeQuote.Status.ACCEPTED
        )
    )

    form = CustomerQuoteApprovalForm(
        initial={
            "response_name": (
                order.customer_name
                or ""
            ),
            "response_email": (
                order.customer_email
                or ""
            ),
        },
        expected_email=(
            order.customer_email
            or ""
        ),
    )

    if (
        request.method == "POST"
        and quote_available
        and not already_accepted
    ):

        action = request.POST.get(
            "action",
            ""
        )

        if action == "accept":

            form = CustomerQuoteApprovalForm(
                request.POST,
                expected_email=(
                    order.customer_email
                    or ""
                ),
            )

            if form.is_valid():

                with transaction.atomic():

                    # Lock only the approval row first.
                    #
                    # Do not combine select_for_update() with
                    # select_related("quote") here because quote is
                    # nullable and PostgreSQL will reject FOR UPDATE
                    # against the resulting LEFT OUTER JOIN.
                    locked_approval = (
                        BespokeApprovalPayment.objects
                        .select_for_update()
                        .get(
                            pk=approval.pk
                        )
                    )

                    if not locked_approval.quote_id:

                        quote_available = False

                    else:

                        # Lock the quote and workflow separately.
                        # This keeps the transaction safe without
                        # locking across nullable outer joins.
                        locked_quote = (
                            BespokeQuote.objects
                            .select_for_update()
                            .get(
                                pk=locked_approval.quote_id
                            )
                        )

                        locked_workflow = (
                            BespokeOrderWorkflow.objects
                            .select_for_update()
                            .select_related(
                                "order"
                            )
                            .get(
                                pk=locked_approval.workflow_id
                            )
                        )

                        locked_order = (
                            locked_workflow.order
                        )

                        if (
                            locked_quote.workflow_id
                            != locked_workflow.pk
                        ):

                            quote_available = False

                        elif (
                            locked_quote.status
                            not in {
                                BespokeQuote.Status.SENT,
                                BespokeQuote.Status.ACCEPTED,
                            }
                        ):

                            quote_available = False

                        elif (
                            locked_approval.customer_approved
                            or locked_quote.status
                            == BespokeQuote.Status.ACCEPTED
                        ):

                            # Idempotent handling for double-clicks or
                            # repeated POSTs. Do not create duplicate
                            # activity or communication records.
                            approval = locked_approval
                            quote = locked_quote
                            workflow = locked_workflow
                            order = locked_order
                            already_accepted = True

                        else:

                            now = timezone.now()

                            locked_quote.status = (
                                BespokeQuote.Status.ACCEPTED
                            )

                            locked_quote.accepted_at = now

                            locked_quote.save(
                                update_fields=[
                                    "status",
                                    "accepted_at",
                                    "updated_at",
                                ]
                            )

                            locked_approval.customer_approved = True
                            locked_approval.approved_at = now
                            locked_approval.approved_name = (
                                form.cleaned_data[
                                    "response_name"
                                ].strip()
                            )
                            locked_approval.approved_email = (
                                form.cleaned_data[
                                    "response_email"
                                ].strip()
                            )
                            locked_approval.approval_notes = (
                                form.cleaned_data[
                                    "approval_notes"
                                ].strip()
                            )
                            locked_approval.amount_due = (
                                locked_quote.total
                            )
                            locked_approval.payment_status = (
                                BespokeApprovalPayment
                                .PaymentStatus
                                .AWAITING_PAYMENT
                            )

                            locked_approval.save(
                                update_fields=[
                                    "customer_approved",
                                    "approved_at",
                                    "approved_name",
                                    "approved_email",
                                    "approval_notes",
                                    "amount_due",
                                    "payment_status",
                                    "updated_at",
                                ]
                            )

                            locked_workflow.current_step = (
                                BespokeOrderWorkflow
                                .Step
                                .APPROVAL
                            )

                            locked_workflow.stage = (
                                BespokeOrderWorkflow
                                .Stage
                                .PAYMENT
                            )

                            locked_workflow.customer_waiting = True
                            locked_workflow.customer_waiting_since = now
                            locked_workflow.next_action = (
                                "Await customer payment."
                            )

                            locked_workflow.save(
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
                                order=locked_order,
                                channel=(
                                    OrderCommunication
                                    .Channel
                                    .OTHER
                                ),
                                context=(
                                    OrderCommunication
                                    .Context
                                    .APPROVAL
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
                                    f"Quote V{locked_quote.version} "
                                    "accepted by customer."
                                ),
                                content=(
                                    (
                                        "Customer accepted "
                                        f"Quote V{locked_quote.version}."
                                    )
                                    + (
                                        "\n\nComments:\n"
                                        + locked_approval.approval_notes
                                        if locked_approval.approval_notes
                                        else ""
                                    )
                                ),
                                from_address=(
                                    locked_approval
                                    .approved_email
                                ),
                                to_address="K9",
                                thread_reference=(
                                    f"quote:{locked_quote.pk}"
                                ),
                                occurred_at=now,
                            )

                            log_job_activity(
                                order=locked_order,
                                user=None,
                                message=(
                                    f"Quote V{locked_quote.version} "
                                    "accepted by the customer. "
                                    "Workflow automatically moved "
                                    "to Step 5: Approval & Payment."
                                ),
                            )

                            approval = locked_approval
                            quote = locked_quote
                            workflow = locked_workflow
                            order = locked_order
                            already_accepted = True

    context = {
        "approval": approval,
        "workflow": workflow,
        "order": order,
        "quote": quote,
        "form": form,
        "quote_available": quote_available,
        "already_accepted": already_accepted,
    }

    return render(
        request,
        "orders/customer_quote_review.html",
        context,
    )
