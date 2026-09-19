import logging

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from orders.models import Order, OrderNote

from .emails import (
    send_bespoke_customer_confirmation,
    send_bespoke_staff_notifications,
)
from .forms import (
    BespokeContactForm,
    BespokeDesignForm,
    BespokeIdeaForm,
    BespokePracticalForm,
    BespokeRecipientForm,
    BespokeSubmitForm,
)
from .models import BespokeRequest


logger = logging.getLogger(__name__)


# =========================================================
# SESSION KEYS
# =========================================================

WIZARD_SESSION_KEY = "bespoke_wizard_id"

CLAIM_SESSION_KEY = "bespoke_request_to_claim"

LAST_SUBMITTED_SESSION_KEY = "bespoke_last_submitted_reference"


# =========================================================
# WIZARD FORMS
# =========================================================

STEP_FORMS = {
    1: BespokeIdeaForm,
    2: BespokeRecipientForm,
    3: BespokeDesignForm,
    4: BespokePracticalForm,
    5: BespokeContactForm,
    6: BespokeSubmitForm,
}


# =========================================================
# WIZARD PAGE INFORMATION
# =========================================================

STEP_META = {
    1: {
        "title": "Your Idea",
        "eyebrow": "Start Anywhere",
        "intro": (
            "Tell us what you are imagining. "
            "It doesn't need to be fully planned or polished."
        ),
    },

    2: {
        "title": "Who Is It For?",
        "eyebrow": "Make It Personal",
        "intro": (
            "Tell us a little about the person, occasion "
            "and meaning behind the gift."
        ),
    },

    3: {
        "title": "Design The Details",
        "eyebrow": "Shape The Idea",
        "intro": (
            "Colours, themes, wording, materials and all the "
            "little details that could make it unique."
        ),
    },

    4: {
        "title": "Practical Details",
        "eyebrow": "Budget & Timing",
        "intro": (
            "Tell us about your budget, quantity, deadline "
            "and how you would like to receive the finished item."
        ),
    },

    5: {
        "title": "Your Details",
        "eyebrow": "Nearly There",
        "intro": (
            "We need a few contact details so we can discuss "
            "your bespoke request with you."
        ),
    },

    6: {
        "title": "Review & Send",
        "eyebrow": "Final Check",
        "intro": (
            "Review your idea before sending it to K9. "
            "Nothing will be charged at this stage."
        ),
    },
}


# =========================================================
# GET OR CREATE DRAFT
# =========================================================

def get_or_create_bespoke_request(request):
    """
    Finds the customer's existing wizard draft from
    the browser session.

    If there isn't one, creates a new draft.

    Guests can complete the wizard without registering.
    """

    bespoke_id = request.session.get(
        WIZARD_SESSION_KEY
    )

    bespoke_request = None

    if bespoke_id:
        bespoke_request = (
            BespokeRequest.objects
            .filter(
                pk=bespoke_id,
                status=BespokeRequest.Status.DRAFT,
            )
            .first()
        )

    # -----------------------------------------------------
    # Security
    # -----------------------------------------------------

    if (
        bespoke_request
        and bespoke_request.user_id
    ):

        if not request.user.is_authenticated:
            bespoke_request = None

        elif (
            bespoke_request.user_id
            != request.user.id
        ):
            bespoke_request = None

    # -----------------------------------------------------
    # Create new draft
    # -----------------------------------------------------

    if bespoke_request is None:

        bespoke_request = BespokeRequest.objects.create(
            user=(
                request.user
                if request.user.is_authenticated
                else None
            )
        )

        request.session[
            WIZARD_SESSION_KEY
        ] = bespoke_request.pk

    return bespoke_request


# =========================================================
# START WIZARD
# =========================================================

def bespoke_start(request):
    """
    Main entry point for the bespoke wizard.

    Adding ?new=1 starts a completely fresh request.
    """

    if request.GET.get("new") == "1":

        request.session.pop(
            WIZARD_SESSION_KEY,
            None,
        )

    bespoke_request = (
        get_or_create_bespoke_request(
            request
        )
    )

    step = (
        bespoke_request.current_step
        or 1
    )

    step = max(
        1,
        min(step, 6),
    )

    return redirect(
        "bespoke_step",
        step=step,
    )


# =========================================================
# WIZARD STEP
# =========================================================

def bespoke_step(request, step):

    # -----------------------------------------------------
    # Validate requested step
    # -----------------------------------------------------

    if step not in STEP_FORMS:
        raise Http404

    bespoke_request = (
        get_or_create_bespoke_request(
            request
        )
    )

    # -----------------------------------------------------
    # Prevent somebody manually skipping too far ahead
    # -----------------------------------------------------

    allowed_step = min(
        (
            bespoke_request.current_step
            or 1
        ) + 1,
        6,
    )

    if step > allowed_step:

        return redirect(
            "bespoke_step",
            step=max(
                1,
                bespoke_request.current_step,
            ),
        )

    # -----------------------------------------------------
    # Load correct form
    # -----------------------------------------------------

    form_class = STEP_FORMS[
        step
    ]

    form = form_class(
        request.POST or None,
        instance=bespoke_request,
    )

    # -----------------------------------------------------
    # PROCESS FORM SUBMISSION
    # -----------------------------------------------------

    if (
        request.method == "POST"
        and form.is_valid()
    ):

        bespoke_request = form.save(
            commit=False
        )

        # -------------------------------------------------
        # Attach logged-in user
        # -------------------------------------------------

        if (
            request.user.is_authenticated
            and bespoke_request.user_id
            is None
        ):

            bespoke_request.user = (
                request.user
            )

        # =================================================
        # STEPS 1 - 5
        # =================================================

        if step < 6:

            bespoke_request.current_step = max(
                (
                    bespoke_request.current_step
                    or 1
                ),
                step + 1,
            )

            bespoke_request.save()

            return redirect(
                "bespoke_step",
                step=step + 1,
            )

        # =================================================
        # STEP 6
        # FINAL SUBMISSION
        # =================================================

        bespoke_request.save()

        bespoke_request.mark_submitted()

        # -------------------------------------------------
        # CREATE / FIND ORDER
        # -------------------------------------------------

        order, created = (
            Order.objects.get_or_create(
                bespoke_request=bespoke_request,
                defaults={
                    "order_type": "bespoke",
                    "customer_name": (
                        bespoke_request.customer_name
                    ),
                    "customer_email": (
                        bespoke_request.email
                    ),
                    "phone_number": (
                        bespoke_request.phone
                    ),
                    "status": "pending",
                },
            )
        )

        # -------------------------------------------------
        # Existing order
        # -------------------------------------------------

        if not created:

            order.customer_name = (
                bespoke_request.customer_name
            )

            order.customer_email = (
                bespoke_request.email
            )

            order.phone_number = (
                bespoke_request.phone
            )

            order.save(
                update_fields=[
                    "customer_name",
                    "customer_email",
                    "phone_number",
                    "updated_at",
                ]
            )

        # -------------------------------------------------
        # CREATE INITIAL SYSTEM NOTE
        # -------------------------------------------------

        if created:

            OrderNote.objects.create(
                order=order,
                note_type="system",
                content=(
                    "Bespoke request received. "
                    f"Request reference: "
                    f"{bespoke_request.reference}. "
                    f"Item: "
                    f"{bespoke_request.item_type or 'Not specified'}."
                ),
            )

        # -------------------------------------------------
        # SAVE SUBMISSION TO SESSION
        # -------------------------------------------------

        request.session[
            CLAIM_SESSION_KEY
        ] = bespoke_request.pk

        request.session[
            LAST_SUBMITTED_SESSION_KEY
        ] = bespoke_request.reference

        request.session.pop(
            WIZARD_SESSION_KEY,
            None,
        )

        # =================================================
        # CUSTOMER CONFIRMATION EMAIL
        # =================================================

        try:

            email_sent = (
                send_bespoke_customer_confirmation(
                    bespoke_request
                )
            )

        except Exception:

            logger.exception(
                (
                    "Failed to send bespoke confirmation "
                    "email for request %s"
                ),
                bespoke_request.reference,
            )

            email_sent = False

        # -------------------------------------------------
        # CUSTOMER SUCCESS / WARNING MESSAGE
        # -------------------------------------------------

        if email_sent:

            messages.success(
                request,
                (
                    "Your bespoke request has been sent "
                    "successfully. We've also emailed you "
                    "a copy of your request and information "
                    "about what happens next."
                ),
            )

        else:

            messages.warning(
                request,
                (
                    "Your bespoke request has been saved "
                    "successfully, but we couldn't send the "
                    "confirmation email. Your request is "
                    "still safely recorded and a member of "
                    "the K9 team can still review it."
                ),
            )

        # =================================================
        # STAFF NOTIFICATION EMAILS
        # =================================================
        #
        # Only staff members who:
        #
        # - are active
        # - are marked as staff
        # - have an email address
        # - have bespoke email notifications ON
        #
        # will receive the notification.
        #
        # Any failure here must NOT interrupt the customer
        # submission.
        # =================================================

        try:

            staff_emails_sent = (
                send_bespoke_staff_notifications(
                    bespoke_request,
                    order,
                )
            )

            logger.info(
                (
                    "Sent %s bespoke staff notification "
                    "email(s) for request %s"
                ),
                staff_emails_sent,
                bespoke_request.reference,
            )

        except Exception:

            logger.exception(
                (
                    "Failed to send staff notifications "
                    "for bespoke request %s"
                ),
                bespoke_request.reference,
            )

        # -------------------------------------------------
        # SUCCESS PAGE
        # -------------------------------------------------

        return redirect(
            "bespoke_success",
            reference=(
                bespoke_request.reference
            ),
        )

    # =====================================================
    # DISPLAY WIZARD PAGE
    # =====================================================

    context = {
        "form": form,
        "bespoke": bespoke_request,
        "step": step,
        "total_steps": 6,
        "step_meta": STEP_META[
            step
        ],
        "previous_step": (
            step - 1
            if step > 1
            else None
        ),
        "is_review": (
            step == 6
        ),
    }

    return render(
        request,
        "bespoke/bespoke_wizard.html",
        context,
    )


# =========================================================
# SUCCESS PAGE
# =========================================================

def bespoke_success(
    request,
    reference,
):

    bespoke_request = get_object_or_404(
        BespokeRequest,
        reference=reference,
    )

    allowed = False

    # -----------------------------------------------------
    # Logged-in owner
    # -----------------------------------------------------

    if (
        request.user.is_authenticated
        and bespoke_request.user_id
        == request.user.id
    ):

        allowed = True

    # -----------------------------------------------------
    # Guest who just submitted this request
    # -----------------------------------------------------

    if (
        request.session.get(
            LAST_SUBMITTED_SESSION_KEY
        )
        == bespoke_request.reference
    ):

        allowed = True

    # -----------------------------------------------------
    # Guest waiting to register / log in
    # -----------------------------------------------------

    if (
        request.session.get(
            CLAIM_SESSION_KEY
        )
        == bespoke_request.pk
    ):

        allowed = True

    # -----------------------------------------------------
    # No permission to view request
    # -----------------------------------------------------

    if not allowed:
        raise Http404

    context = {
        "bespoke": bespoke_request,
        "can_register": (
            not request.user.is_authenticated
        ),
    }

    return render(
        request,
        "bespoke/bespoke_success.html",
        context,
    )


# =========================================================
# REGISTER AFTER SUBMISSION
# =========================================================

def bespoke_register(
    request,
    reference,
):
    """
    Guest chooses to create a K9 account AFTER
    submitting their bespoke request.
    """

    bespoke_request = get_object_or_404(
        BespokeRequest,
        reference=reference,
    )

    # -----------------------------------------------------
    # Confirm this browser/session submitted the request
    # -----------------------------------------------------

    if (
        request.session.get(
            LAST_SUBMITTED_SESSION_KEY
        )
        != bespoke_request.reference
        and request.session.get(
            CLAIM_SESSION_KEY
        )
        != bespoke_request.pk
    ):

        raise Http404

    # -----------------------------------------------------
    # Keep request waiting to be claimed
    # -----------------------------------------------------

    request.session[
        CLAIM_SESSION_KEY
    ] = bespoke_request.pk

    signup_url = reverse(
        "account_signup"
    )

    next_url = reverse(
        "bespoke_claim"
    )

    query_string = urlencode(
        {
            "next": next_url,
        }
    )

    return redirect(
        f"{signup_url}?{query_string}"
    )


# =========================================================
# LOGIN AFTER SUBMISSION
# =========================================================

def bespoke_login(
    request,
    reference,
):
    """
    Allows an existing K9 customer to log in and
    attach the guest request to their account.
    """

    bespoke_request = get_object_or_404(
        BespokeRequest,
        reference=reference,
    )

    # -----------------------------------------------------
    # Confirm this browser/session owns the request
    # -----------------------------------------------------

    if (
        request.session.get(
            LAST_SUBMITTED_SESSION_KEY
        )
        != bespoke_request.reference
        and request.session.get(
            CLAIM_SESSION_KEY
        )
        != bespoke_request.pk
    ):

        raise Http404

    # -----------------------------------------------------
    # Keep request waiting to be claimed
    # -----------------------------------------------------

    request.session[
        CLAIM_SESSION_KEY
    ] = bespoke_request.pk

    login_url = reverse(
        "account_login"
    )

    next_url = reverse(
        "bespoke_claim"
    )

    query_string = urlencode(
        {
            "next": next_url,
        }
    )

    return redirect(
        f"{login_url}?{query_string}"
    )


# =========================================================
# CLAIM REQUEST AFTER LOGIN / REGISTRATION
# =========================================================

@login_required
def bespoke_claim(request):
    """
    Links the submitted guest bespoke request to the
    newly registered or logged-in customer.
    """

    bespoke_id = request.session.get(
        CLAIM_SESSION_KEY
    )

    # -----------------------------------------------------
    # Nothing waiting to be claimed
    # -----------------------------------------------------

    if not bespoke_id:

        messages.info(
            request,
            (
                "There is no bespoke request "
                "waiting to be linked."
            ),
        )

        return redirect("/")

    bespoke_request = get_object_or_404(
        BespokeRequest,
        pk=bespoke_id,
    )

    # -----------------------------------------------------
    # Attach guest request to this user
    # -----------------------------------------------------

    if bespoke_request.user_id is None:

        bespoke_request.user = (
            request.user
        )

        bespoke_request.save(
            update_fields=[
                "user",
                "updated_at",
            ]
        )

    # -----------------------------------------------------
    # Request belongs to somebody else
    # -----------------------------------------------------

    elif (
        bespoke_request.user_id
        != request.user.id
    ):

        messages.error(
            request,
            (
                "That bespoke request is already "
                "linked to another account."
            ),
        )

        request.session.pop(
            CLAIM_SESSION_KEY,
            None,
        )

        return redirect("/")

    # -----------------------------------------------------
    # CLAIM COMPLETE
    # -----------------------------------------------------

    request.session.pop(
        CLAIM_SESSION_KEY,
        None,
    )

    messages.success(
        request,
        (
            f"{bespoke_request.reference} "
            "is now linked to your K9 account."
        ),
    )

    return redirect(
        "bespoke_success",
        reference=(
            bespoke_request.reference
        ),
    )
