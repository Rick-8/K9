import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


def generate_bespoke_reference():
    """
    Creates a customer-friendly unique reference such as:
    K9B-A12BC34DEF
    """
    return f"K9B-{uuid.uuid4().hex[:10].upper()}"


class BespokeRequest(models.Model):

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        REVIEWING = "reviewing", "Under Review"
        MORE_INFO = "more_info", "More Information Needed"
        QUOTED = "quoted", "Quote Sent"
        ACCEPTED = "accepted", "Quote Accepted"
        IN_PROGRESS = "in_progress", "In Progress"
        READY = "ready", "Ready"
        COMPLETED = "completed", "Completed"
        DECLINED = "declined", "Unable to Fulfil"
        CANCELLED = "cancelled", "Cancelled"

    class PreferredContact(models.TextChoices):
        EMAIL = "email", "Email"
        PHONE = "phone", "Phone"
        EITHER = "either", "Either"

    class Fulfilment(models.TextChoices):
        POST = "post", "Post / Courier"
        COLLECTION = "collection", "Collection"
        DISCUSS = "discuss", "Not Sure Yet"

    # ---------------------------------------------------------
    # REQUEST INFORMATION
    # ---------------------------------------------------------

    reference = models.CharField(
        max_length=16,
        unique=True,
        default=generate_bespoke_reference,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="bespoke_requests",
        blank=True,
        null=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    current_step = models.PositiveSmallIntegerField(
        default=1,
    )

    # ---------------------------------------------------------
    # STEP 1 - THE IDEA
    # ---------------------------------------------------------

    request_title = models.CharField(
        max_length=120,
        blank=True,
    )

    # Existing field kept
    item_type = models.CharField(
        max_length=150,
        blank=True,
        help_text=(
            "For example: plaque, memorial, gift box, sign, "
            "keepsake, decoration or something completely unique."
        ),
    )

    # Existing field kept
    description = models.TextField(
        blank=True,
        help_text=(
            "Describe your idea, vision, dimensions, "
            "requirements or anything else you have in mind."
        ),
    )

    inspiration_source = models.CharField(
        max_length=200,
        blank=True,
        help_text=(
            "For example: a memory, hobby, pet, place, "
            "photograph, theme or existing item."
        ),
    )

    # ---------------------------------------------------------
    # STEP 2 - RECIPIENT & OCCASION
    # ---------------------------------------------------------

    recipient_name = models.CharField(
        max_length=120,
        blank=True,
    )

    recipient_relationship = models.CharField(
        max_length=120,
        blank=True,
    )

    recipient_age = models.CharField(
        max_length=40,
        blank=True,
        help_text="An exact age or approximate range is fine.",
    )

    occasion = models.CharField(
        max_length=120,
        blank=True,
    )

    occasion_date = models.DateField(
        blank=True,
        null=True,
    )

    recipient_interests = models.TextField(
        blank=True,
        help_text=(
            "Hobbies, interests, favourite things, "
            "personality or anything that may help with the design."
        ),
    )

    story_or_meaning = models.TextField(
        blank=True,
        help_text=(
            "Any story, memory or meaning behind the gift."
        ),
    )

    # ---------------------------------------------------------
    # STEP 3 - DESIGN
    # ---------------------------------------------------------

    style = models.CharField(
        max_length=160,
        blank=True,
    )

    theme = models.CharField(
        max_length=160,
        blank=True,
    )

    colours = models.CharField(
        max_length=200,
        blank=True,
    )

    materials = models.CharField(
        max_length=200,
        blank=True,
    )

    size_or_dimensions = models.CharField(
        max_length=120,
        blank=True,
    )

    personalisation_text = models.TextField(
        blank=True,
        help_text=(
            "Names, dates, wording, quotes or messages "
            "to appear on the finished item."
        ),
    )

    must_include = models.TextField(
        blank=True,
        help_text="Anything that absolutely must be included.",
    )

    avoid = models.TextField(
        blank=True,
        help_text="Anything the customer definitely does not want.",
    )

    finish_notes = models.TextField(
        blank=True,
        help_text=(
            "Finish, texture, mounting, display, packaging "
            "or other visual requirements."
        ),
    )

    # ---------------------------------------------------------
    # FUTURE IMAGE / FILE SUPPORT
    # ---------------------------------------------------------

    attachment_notes = models.TextField(
        blank=True,
        help_text=(
            "Reserved for notes relating to future customer attachments."
        ),
    )

    # ---------------------------------------------------------
    # STEP 4 - BUDGET & PRACTICAL DETAILS
    # ---------------------------------------------------------

    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    # Existing budget field kept for compatibility
    budget = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    budget_min = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
    )

    budget_max = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        blank=True,
        null=True,
    )

    budget_flexible = models.BooleanField(
        default=True,
    )

    needed_by = models.DateField(
        blank=True,
        null=True,
    )

    deadline_flexible = models.BooleanField(
        default=True,
    )

    fulfilment = models.CharField(
        max_length=20,
        choices=Fulfilment.choices,
        default=Fulfilment.DISCUSS,
    )

    delivery_postcode = models.CharField(
        max_length=12,
        blank=True,
    )

    practical_notes = models.TextField(
        blank=True,
    )

    # ---------------------------------------------------------
    # STEP 5 - CUSTOMER DETAILS
    # ---------------------------------------------------------

    # Existing field kept
    name = models.CharField(
        max_length=100,
        blank=True,
    )

    # Existing field kept
    email = models.EmailField(
        blank=True,
    )

    # Existing field kept
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    preferred_contact = models.CharField(
        max_length=20,
        choices=PreferredContact.choices,
        default=PreferredContact.EMAIL,
    )

    best_contact_time = models.CharField(
        max_length=120,
        blank=True,
    )

    # ---------------------------------------------------------
    # STEP 6 - AGREEMENT & SUBMISSION
    # ---------------------------------------------------------

    details_confirmed = models.BooleanField(
        default=False,
    )

    terms_accepted = models.BooleanField(
        default=False,
    )

    contact_consent = models.BooleanField(
        default=False,
    )

    # ---------------------------------------------------------
    # DATES
    # ---------------------------------------------------------

    submitted_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    # ---------------------------------------------------------
    # MODEL SETTINGS
    # ---------------------------------------------------------

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        title = self.request_title or self.item_type or "Bespoke Request"
        return f"{self.reference} - {title}"

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    @property
    def customer_name(self):
        if self.name:
            return self.name

        if self.user:
            full_name = self.user.get_full_name()

            if full_name:
                return full_name

            return self.user.get_username()

        return "Guest Customer"

    @property
    def budget_display(self):
        if self.budget_min is not None and self.budget_max is not None:
            return f"£{self.budget_min} - £{self.budget_max}"

        if self.budget_max is not None:
            return f"Up to £{self.budget_max}"

        if self.budget_min is not None:
            return f"From £{self.budget_min}"

        if self.budget:
            return self.budget

        return "Open to discussion"

    def mark_submitted(self):
        self.status = self.Status.SUBMITTED
        self.submitted_at = timezone.now()
        self.current_step = 6
        self.save()


# =============================================================
# FUTURE ATTACHMENTS
# =============================================================

class BespokeAttachment(models.Model):
    """
    Attachment support is being built into the database now,
    but uploads will NOT be enabled in the customer wizard yet.

    Later this can handle:
    - inspiration photos
    - sketches
    - screenshots
    - examples
    - reference images
    - other customer files
    """

    request = models.ForeignKey(
        BespokeRequest,
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    file = models.FileField(
        upload_to="bespoke/attachments/%Y/%m/",
    )

    original_name = models.CharField(
        max_length=255,
        blank=True,
    )

    caption = models.CharField(
        max_length=255,
        blank=True,
    )

    sort_order = models.PositiveSmallIntegerField(
        default=0,
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "sort_order",
            "uploaded_at",
        ]

    def __str__(self):
        return self.original_name or self.file.name

# =============================================================
# STAFF BESPOKE NOTIFICATION PREFERENCES
# =============================================================

class BespokeNotificationPreference(models.Model):
    """
    Controls whether an individual staff member receives
    email notifications when a new bespoke request arrives.

    Only a superuser will be allowed to change this setting
    through Django Admin.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bespoke_notification_preference",
    )

    email_notifications = models.BooleanField(
        default=False,
        help_text=(
            "Send this staff member an email when a new "
            "bespoke request is submitted."
        ),
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        status = (
            "ON"
            if self.email_notifications
            else "OFF"
        )

        return (
            f"{self.user.get_username()} - "
            f"Bespoke notifications {status}"
        )