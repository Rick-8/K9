from .models import OrderNote


def log_job_activity(
    order,
    user,
    message,
    note_type="system",
):
    """
    Add an entry to the job/order activity feed.

    Every entry automatically records:
    - the order/job
    - the staff member responsible
    - the activity/message
    - the date and time through OrderNote's timestamp field
    """

    if not message:
        return None

    return OrderNote.objects.create(
        order=order,
        author=user,
        note_type=note_type,
        content=message,
    )
