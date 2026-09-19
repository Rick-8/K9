from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from .models import BespokeNotificationPreference


# =========================================================
# CUSTOMER CONFIRMATION EMAIL
# =========================================================

def send_bespoke_customer_confirmation(bespoke_request):
    """
    Sends the customer a confirmation email after their
    bespoke request has been successfully submitted.
    """

    if not bespoke_request.email:
        return False

    subject = (
        f"K9 Bespoke Request Received - "
        f"{bespoke_request.reference}"
    )

    context = {
        "bespoke": bespoke_request,
    }

    # -----------------------------------------------------
    # Plain-text version
    # -----------------------------------------------------

    text_body = render_to_string(
        "bespoke/emails/customer_confirmation.txt",
        context,
    )

    # -----------------------------------------------------
    # HTML version
    # -----------------------------------------------------

    html_body = render_to_string(
        "bespoke/emails/customer_confirmation.html",
        context,
    )

    # -----------------------------------------------------
    # Build email
    # -----------------------------------------------------

    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[
            bespoke_request.email,
        ],
    )

    email.attach_alternative(
        html_body,
        "text/html",
    )

    email.send(
        fail_silently=False,
    )

    return True


# =========================================================
# STAFF NOTIFICATION EMAIL
# =========================================================

def send_bespoke_staff_notifications(
    bespoke_request,
    order,
):
    """
    Sends a new bespoke request notification to each
    eligible staff member.

    A staff member only receives the email when:

    - Their account is active
    - They are marked as staff
    - They have an email address
    - Their bespoke email notification preference is ON

    Each staff member receives their own email so staff
    email addresses are not exposed to other recipients.

    Returns the number of staff emails successfully sent.
    """

    # -----------------------------------------------------
    # Find staff who have notifications enabled
    # -----------------------------------------------------

    preferences = (
        BespokeNotificationPreference.objects
        .select_related("user")
        .filter(
            email_notifications=True,
            user__is_staff=True,
            user__is_active=True,
        )
        .exclude(
            user__email="",
        )
    )

    # -----------------------------------------------------
    # No recipients
    # -----------------------------------------------------

    if not preferences.exists():
        return 0

    # -----------------------------------------------------
    # Email subject
    # -----------------------------------------------------

    subject = (
        f"NEW BESPOKE REQUEST - "
        f"{bespoke_request.reference} - "
        f"{bespoke_request.customer_name}"
    )

    # -----------------------------------------------------
    # Shared template context
    # -----------------------------------------------------

    context = {
        "bespoke": bespoke_request,
        "order": order,
    }

    # -----------------------------------------------------
    # Render templates once
    # -----------------------------------------------------

    text_body = render_to_string(
        "bespoke/emails/staff_notification.txt",
        context,
    )

    html_body = render_to_string(
        "bespoke/emails/staff_notification.html",
        context,
    )

    sent_count = 0

    # -----------------------------------------------------
    # Send separately to each staff member
    # -----------------------------------------------------

    for preference in preferences:

        staff_user = preference.user

        recipient_email = (
            staff_user.email.strip()
            if staff_user.email
            else ""
        )

        if not recipient_email:
            continue

        # -------------------------------------------------
        # Replying to the staff notification can reply
        # directly to the customer.
        # -------------------------------------------------

        reply_to = []

        if bespoke_request.email:
            reply_to = [
                bespoke_request.email,
            ]

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[
                recipient_email,
            ],
            reply_to=reply_to,
        )

        email.attach_alternative(
            html_body,
            "text/html",
        )

        email.send(
            fail_silently=False,
        )

        sent_count += 1

    return sent_count
