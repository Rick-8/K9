from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from allauth.account.signals import user_logged_in

from .models import (
    BespokeNotificationPreference,
    BespokeRequest,
)


User = get_user_model()


# =========================================================
# GUEST BESPOKE REQUEST CLAIMING
# =========================================================

CLAIM_SESSION_KEY = "bespoke_request_to_claim"


@receiver(user_logged_in)
def claim_pending_bespoke_request(
    sender,
    request,
    user,
    **kwargs,
):
    """
    If a guest submits a bespoke request and then
    registers or logs in, link that request to their
    customer account.
    """

    bespoke_id = request.session.get(
        CLAIM_SESSION_KEY
    )

    if not bespoke_id:
        return

    bespoke_request = (
        BespokeRequest.objects
        .filter(
            pk=bespoke_id
        )
        .first()
    )

    if bespoke_request is None:

        request.session.pop(
            CLAIM_SESSION_KEY,
            None,
        )

        return

    # -----------------------------------------------------
    # Guest request has not yet been linked
    # -----------------------------------------------------

    if bespoke_request.user_id is None:

        bespoke_request.user = user

        bespoke_request.save(
            update_fields=[
                "user",
                "updated_at",
            ]
        )

    # -----------------------------------------------------
    # Already belongs to this same customer
    # -----------------------------------------------------

    elif bespoke_request.user_id == user.id:
        return

    # -----------------------------------------------------
    # Belongs to somebody else
    # -----------------------------------------------------

    else:
        return


# =========================================================
# STAFF BESPOKE NOTIFICATION PREFERENCES
# =========================================================

@receiver(post_save, sender=User)
def create_staff_bespoke_notification_preference(
    sender,
    instance,
    **kwargs,
):
    """
    Automatically creates a bespoke email notification
    preference whenever a user is marked as staff.

    Notifications default to OFF.

    A superuser can then enable them through Django Admin.
    """

    if instance.is_staff:

        BespokeNotificationPreference.objects.get_or_create(
            user=instance,
            defaults={
                "email_notifications": False,
            },
        )
