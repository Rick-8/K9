from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import (
    BespokeOrderWorkflow,
    Order,
)


# =========================================================
# AUTOMATIC BESPOKE JOB CREATION
# =========================================================

@receiver(post_save, sender=Order)
def create_bespoke_workflow_for_order(
    sender,
    instance,
    created,
    **kwargs,
):
    """
    Automatically ensure every bespoke Order has a
    BespokeOrderWorkflow job.

    This works whether the order is created:

    - from the customer bespoke request wizard
    - by staff
    - from Django Admin
    - from another part of the K9 system later

    get_or_create prevents duplicate jobs.
    """

    if instance.order_type != "bespoke":
        return

    BespokeOrderWorkflow.objects.get_or_create(
        order=instance,
    )
