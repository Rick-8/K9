import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.utils import timezone

from bespoke.models import BespokeRequest


# =========================================================
# ORDER
# =========================================================

class Order(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("sent", "Sent / Complete"),
        ("cancelled", "Cancelled"),
    ]

    ORDER_TYPE_CHOICES = [
        ("bespoke", "Bespoke"),
        ("shop", "Shop"),
    ]

    reference_number = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    order_type = models.CharField(
        max_length=20,
        choices=ORDER_TYPE_CHOICES,
        default="shop",
    )

    bespoke_request = models.ForeignKey(
        BespokeRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )

    customer_name = models.CharField(
        max_length=150,
    )

    customer_email = models.EmailField()

    phone_number = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    shipping_address = models.TextField(
        blank=True,
        null=True,
    )

    order_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
    )

    tracking_number = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

    def save(self, *args, **kwargs):

        if not self.reference_number:
            self.reference_number = (
                f"K9-{uuid.uuid4().hex[:8].upper()}"
            )

        if (
            self.status == "sent"
            and not self.completed_at
        ):
            self.completed_at = timezone.now()

        elif self.status != "sent":
            self.completed_at = None

        super().save(*args, **kwargs)

    @property
    def is_bespoke(self):
        return self.order_type == "bespoke"

    def __str__(self):
        return (
            f"{self.reference_number} | "
            f"{self.customer_name}"
        )


# =========================================================
# ORDER NOTE / ACTIVITY LOG
# =========================================================

class OrderNote(models.Model):

    NOTE_TYPE_CHOICES = [
        ("internal", "Internal Staff Note"),
        ("system", "System Update"),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="notes",
    )

    note_type = models.CharField(
        max_length=20,
        choices=NOTE_TYPE_CHOICES,
        default="internal",
    )

    content = models.TextField()

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="k9_order_notes",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

    def __str__(self):
        return (
            f"{self.get_note_type_display()} | "
            f"{self.order.reference_number}"
        )


# =========================================================
# BESPOKE WORKFLOW
# =========================================================

class BespokeOrderWorkflow(models.Model):

    class Stage(models.TextChoices):
        NEW = "new", "New Job"
        REVIEW = "review", "Staff Review"

        CUSTOMER_CONTACT = (
            "customer_contact",
            "Customer Contact",
        )

        DESIGN = (
            "design",
            "Design & Specification",
        )

        QUOTE = (
            "quote",
            "Pricing & Quote",
        )

        AWAITING_CUSTOMER = (
            "awaiting_customer",
            "Awaiting Customer",
        )

        APPROVED = (
            "approved",
            "Customer Approved",
        )

        PAYMENT = (
            "payment",
            "Payment",
        )

        PRODUCTION = (
            "production",
            "Production",
        )

        READY = (
            "ready",
            "Ready",
        )

        DELIVERY = (
            "delivery",
            "Delivery / Collection",
        )

        COMPLETED = (
            "completed",
            "Completed",
        )

        ON_HOLD = (
            "on_hold",
            "On Hold",
        )

        CANCELLED = (
            "cancelled",
            "Cancelled",
        )

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Step(models.IntegerChoices):
        OVERVIEW = 1, "Job Overview"
        CONTACT = 2, "Customer Contact"
        DESIGN = 3, "Design & Specification"
        QUOTE = 4, "Pricing & Quote"
        APPROVAL = 5, "Approval & Payment"
        PRODUCTION = 6, "Production"
        DELIVERY = 7, "Completion & Delivery"
        CLOSE = 8, "Close Job"

    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="bespoke_workflow",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_bespoke_jobs",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_bespoke_jobs",
    )

    current_step = models.PositiveSmallIntegerField(
        choices=Step.choices,
        default=Step.OVERVIEW,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(8),
        ],
    )

    stage = models.CharField(
        max_length=30,
        choices=Stage.choices,
        default=Stage.NEW,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )

    staff_summary = models.TextField(
        blank=True,
    )

    next_action = models.TextField(
        blank=True,
    )

    next_action_due = models.DateTimeField(
        null=True,
        blank=True,
    )

    customer_waiting = models.BooleanField(
        default=False,
    )

    customer_waiting_since = models.DateTimeField(
        null=True,
        blank=True,
    )

    on_hold_reason = models.TextField(
        blank=True,
    )

    last_worked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recent_bespoke_jobs",
    )

    last_worked_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-updated_at",
        ]

    @property
    def reference(self):
        return self.order.reference_number

    @property
    def customer_name(self):
        return self.order.customer_name

    @property
    def bespoke_reference(self):

        if self.order.bespoke_request:
            return (
                self.order
                .bespoke_request
                .reference
            )

        return ""

    @property
    def job_title(self):

        request = self.order.bespoke_request

        if not request:
            return "Bespoke Job"

        if getattr(
            request,
            "request_title",
            None,
        ):
            return request.request_title

        if getattr(
            request,
            "item_type",
            None,
        ):
            return request.item_type

        return "Bespoke Job"

    @property
    def resume_label(self):

        return dict(
            self.Step.choices
        ).get(
            self.current_step,
            "Job Overview",
        )

    def mark_worked(
        self,
        user,
        step=None,
    ):

        now = timezone.now()

        self.last_worked_by = user
        self.last_worked_at = now

        if self.started_at is None:
            self.started_at = now

        if step is not None:
            self.current_step = step

        self.save()

    def set_customer_waiting(
        self,
        waiting,
    ):

        self.customer_waiting = waiting

        if waiting:
            self.customer_waiting_since = (
                timezone.now()
            )

        else:
            self.customer_waiting_since = None

        self.save()

    def mark_completed(
        self,
        user=None,
    ):

        now = timezone.now()

        self.stage = self.Stage.COMPLETED
        self.current_step = self.Step.CLOSE
        self.completed_at = now
        self.customer_waiting = False
        self.customer_waiting_since = None

        if user:
            self.last_worked_by = user
            self.last_worked_at = now

        self.save()

    def __str__(self):

        return (
            f"{self.order.reference_number} | "
            f"{self.job_title}"
        )


# =========================================================
# CUSTOMER COMMUNICATION
# =========================================================

class OrderCommunication(models.Model):

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"
        PHONE = "phone", "Phone"
        IN_PERSON = "in_person", "In Person"
        OTHER = "other", "Other"

    class Direction(models.TextChoices):
        INCOMING = "incoming", "Incoming"
        OUTGOING = "outgoing", "Outgoing"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        RECEIVED = "received", "Received"
        LOGGED = "logged", "Logged"
        FAILED = "failed", "Failed"

    class Context(models.TextChoices):
        GENERAL = "general", "General"
        CONTACT = "contact", "Customer Contact"
        DESIGN = "design", "Design"
        QUOTE = "quote", "Quote"
        APPROVAL = "approval", "Approval"
        PAYMENT = "payment", "Payment"
        PRODUCTION = "production", "Production"
        DELIVERY = "delivery", "Delivery"

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="communications",
    )

    # Links a communication to a specific design revision.
    #
    # This is intentionally optional because most
    # communications are unrelated to a design version.
    design_version = models.ForeignKey(
        "BespokeDesignVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communications",
    )

    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.EMAIL,
    )

    context = models.CharField(
        max_length=20,
        choices=Context.choices,
        default=Context.GENERAL,
    )

    direction = models.CharField(
        max_length=20,
        choices=Direction.choices,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.LOGGED,
    )

    subject = models.CharField(
        max_length=255,
        blank=True,
    )

    from_address = models.CharField(
        max_length=255,
        blank=True,
    )

    to_address = models.CharField(
        max_length=255,
        blank=True,
    )

    summary = models.TextField(
        blank=True,
    )

    content = models.TextField(
        blank=True,
    )

    has_attachment = models.BooleanField(
        default=False,
    )

    # Actual customer files are not permanently retained
    # here. We store metadata only.
    attachment_names = models.JSONField(
        default=list,
        blank=True,
    )

    attachment_notes = models.TextField(
        blank=True,
    )

    message_id = models.CharField(
        max_length=255,
        blank=True,
    )

    thread_reference = models.CharField(
        max_length=255,
        blank=True,
    )

    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logged_order_communications",
    )

    occurred_at = models.DateTimeField(
        default=timezone.now,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-occurred_at",
            "-created_at",
        ]

    def __str__(self):

        return (
            f"{self.order.reference_number} | "
            f"{self.get_channel_display()} | "
            f"{self.get_direction_display()}"
        )


# =========================================================
# MASTER DESIGN / SPECIFICATION
# =========================================================

class BespokeDesign(models.Model):
    """
    Master design record for a bespoke job.

    This stores the overall brief and high-level information.

    Individual customer-facing design revisions are stored
    separately in BespokeDesignVersion.
    """

    workflow = models.OneToOneField(
        BespokeOrderWorkflow,
        on_delete=models.CASCADE,
        related_name="design_record",
    )

    specification = models.TextField(
        blank=True,
    )

    internal_notes = models.TextField(
        blank=True,
    )

    # These fields are retained for compatibility with
    # existing data and the current Step 3 implementation.
    # The versioned design system will gradually take over
    # customer-facing final design state.
    final_design_summary = models.TextField(
        blank=True,
    )

    final_design_ready = models.BooleanField(
        default=False,
    )

    final_design_sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_bespoke_designs",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    @property
    def accepted_version(self):
        """
        Return the accepted customer design, if one exists.
        """

        return (
            self.versions
            .filter(
                status=(
                    BespokeDesignVersion
                    .Status
                    .ACCEPTED
                )
            )
            .order_by(
                "-version"
            )
            .first()
        )

    @property
    def latest_version(self):
        """
        Return the latest design version.
        """

        return (
            self.versions
            .order_by(
                "-version"
            )
            .first()
        )

    @property
    def next_version_number(self):
        """
        Determine the next design revision number.
        """

        latest = self.latest_version

        if not latest:
            return 1

        return latest.version + 1

    def __str__(self):

        return (
            f"Design | "
            f"{self.workflow.order.reference_number}"
        )


# =========================================================
# DESIGN VERSION / REVISION
# =========================================================

class BespokeDesignVersion(models.Model):
    """
    One individual design revision.

    A bespoke job can have unlimited versions:

        V1
        V2
        V3
        ...

    Customer acceptance or rejection is recorded against
    the exact design revision they reviewed.

    Actual uploaded design files are not permanently stored.
    K9 stores metadata and a SHA-256 fingerprint instead.
    """

    class Status(models.TextChoices):

        DRAFT = (
            "draft",
            "Draft",
        )

        SENT = (
            "sent",
            "Sent to Customer",
        )

        ACCEPTED = (
            "accepted",
            "Accepted",
        )

        REJECTED = (
            "rejected",
            "Rejected / Changes Requested",
        )

        SUPERSEDED = (
            "superseded",
            "Superseded",
        )

    design = models.ForeignKey(
        "BespokeDesign",
        on_delete=models.CASCADE,
        related_name="versions",
    )

    # =====================================================
    # VERSION
    # =====================================================

    version = models.PositiveIntegerField()

    title = models.CharField(
        max_length=200,
        blank=True,
        help_text=(
            "Optional short title for this design version."
        ),
    )

    # =====================================================
    # CUSTOMER-FACING DESIGN INFORMATION
    # =====================================================

    customer_summary = models.TextField(
        help_text=(
            "Description of this design version shown "
            "to the customer."
        ),
    )

    change_summary = models.TextField(
        blank=True,
        help_text=(
            "Explain what changed from the previous version."
        ),
    )

    # =====================================================
    # STAFF-ONLY NOTES
    # =====================================================

    staff_notes = models.TextField(
        blank=True,
        help_text=(
            "Internal notes. Never shown to the customer."
        ),
    )

    # =====================================================
    # STATUS
    # =====================================================

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    # =====================================================
    # SECURE CUSTOMER RESPONSE
    # =====================================================

    response_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    # =====================================================
    # DESIGN FILE METADATA
    #
    # K9 deliberately does not use FileField here.
    #
    # The local file can be emailed directly and discarded.
    # SHA-256 lets us identify the exact file associated
    # with this revision.
    # =====================================================

    file_name = models.CharField(
        max_length=255,
        blank=True,
    )

    file_content_type = models.CharField(
        max_length=150,
        blank=True,
    )

    file_size = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    file_sha256 = models.CharField(
        max_length=64,
        blank=True,
    )

    # =====================================================
    # SENT DETAILS
    # =====================================================

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bespoke_design_versions_sent",
    )

    # =====================================================
    # CUSTOMER RESPONSE
    # =====================================================

    responded_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    response_name = models.CharField(
        max_length=200,
        blank=True,
    )

    response_email = models.EmailField(
        blank=True,
    )

    response_notes = models.TextField(
        blank=True,
        help_text=(
            "Customer comments or requested changes."
        ),
    )

    # =====================================================
    # STAFF AUDIT
    # =====================================================

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bespoke_design_versions_created",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-version",
        ]

        constraints = [

            models.UniqueConstraint(
                fields=[
                    "design",
                    "version",
                ],
                name=(
                    "unique_bespoke_design_version"
                ),
            ),

        ]

    def __str__(self):

        return (
            f"{self.design.workflow.order.reference_number} "
            f"| Design V{self.version}"
        )

    @property
    def version_label(self):

        return (
            f"Design V{self.version}"
        )

    @property
    def can_customer_respond(self):

        return (
            self.status
            == self.Status.SENT
        )

    @property
    def is_accepted(self):

        return (
            self.status
            == self.Status.ACCEPTED
        )

    @property
    def is_rejected(self):

        return (
            self.status
            == self.Status.REJECTED
        )

    @property
    def is_draft(self):

        return (
            self.status
            == self.Status.DRAFT
        )

    @property
    def has_been_sent(self):

        return bool(
            self.sent_at
        )

    def mark_sent(
        self,
        user=None,
    ):
        """
        Mark this exact design revision as sent.
        """

        self.status = (
            self.Status.SENT
        )

        self.sent_at = timezone.now()

        self.sent_by = user

        self.save(
            update_fields=[
                "status",
                "sent_at",
                "sent_by",
                "updated_at",
            ]
        )

    def mark_accepted(
        self,
        name="",
        email="",
        notes="",
    ):
        """
        Mark this exact design revision as accepted.

        Other active design revisions become superseded.

        Rejected designs stay rejected so the historical
        record remains accurate.
        """

        now = timezone.now()

        (
            self.design
            .versions
            .exclude(
                pk=self.pk
            )
            .filter(
                status__in=[
                    self.Status.DRAFT,
                    self.Status.SENT,
                    self.Status.ACCEPTED,
                ]
            )
            .update(
                status=(
                    self.Status.SUPERSEDED
                ),
                updated_at=now,
            )
        )

        self.status = (
            self.Status.ACCEPTED
        )

        self.responded_at = now

        self.response_name = (
            name
        )

        self.response_email = (
            email
        )

        self.response_notes = (
            notes
        )

        self.save(
            update_fields=[
                "status",
                "responded_at",
                "response_name",
                "response_email",
                "response_notes",
                "updated_at",
            ]
        )

    def mark_rejected(
        self,
        name="",
        email="",
        notes="",
    ):
        """
        Record that the customer rejected this version or
        requested changes.
        """

        self.status = (
            self.Status.REJECTED
        )

        self.responded_at = (
            timezone.now()
        )

        self.response_name = (
            name
        )

        self.response_email = (
            email
        )

        self.response_notes = (
            notes
        )

        self.save(
            update_fields=[
                "status",
                "responded_at",
                "response_name",
                "response_email",
                "response_notes",
                "updated_at",
            ]
        )


# =========================================================
# QUOTES
# =========================================================

class BespokeQuote(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"
        SUPERSEDED = "superseded", "Superseded"
        ACCEPTED = "accepted", "Accepted"
        CANCELLED = "cancelled", "Cancelled"

    workflow = models.ForeignKey(
        BespokeOrderWorkflow,
        on_delete=models.CASCADE,
        related_name="quotes",
    )

    version = models.PositiveIntegerField(
        default=1,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    title = models.CharField(
        max_length=200,
        default="Bespoke Quote",
    )

    notes = models.TextField(
        blank=True,
    )

    # =====================================================
    # STAFF-ENTERED PRICING
    # =====================================================

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    delivery_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # =====================================================
    # VAT
    #
    # Staff controls whether VAT applies and the rate.
    # K9 only performs the calculation.
    # =====================================================

    vat_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Enable VAT calculation for this quote."
        ),
    )

    vat_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("20.00"),
        validators=[
            MinValueValidator(
                Decimal("0.00")
            ),
            MaxValueValidator(
                Decimal("100.00")
            ),
        ],
        help_text=(
            "VAT percentage entered by staff."
        ),
    )

    vat_on_delivery = models.BooleanField(
        default=True,
        help_text=(
            "Include the delivery charge when calculating VAT."
        ),
    )

    vat_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
    )

    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    # =====================================================
    # AUDIT
    # =====================================================

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_bespoke_quotes",
    )

    sent_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    accepted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-version",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "workflow",
                    "version",
                ],
                name=(
                    "unique_bespoke_quote_version"
                ),
            ),
        ]

    # =====================================================
    # TOTAL CALCULATION
    # =====================================================

    def recalculate_totals(self):
        """
        Recalculate the quotation from staff-entered prices.

        Pricing is never generated automatically.

        K9 calculates only:

        line totals
            ↓
        subtotal
            ↓
        optional delivery
            ↓
        optional VAT
            ↓
        final total
        """

        subtotal = sum(
            (
                line.line_total
                for line
                in self.lines.all()
            ),
            Decimal("0.00"),
        )

        delivery = (
            self.delivery_cost
            or Decimal("0.00")
        )

        vat_amount = Decimal("0.00")

        if self.vat_enabled:

            vat_rate = (
                self.vat_rate
                or Decimal("0.00")
            )

            taxable_amount = subtotal

            if self.vat_on_delivery:
                taxable_amount += delivery

            vat_amount = (
                taxable_amount
                * vat_rate
                / Decimal("100.00")
            ).quantize(
                Decimal("0.01")
            )

        total = (
            subtotal
            + delivery
            + vat_amount
        )

        self.subtotal = subtotal
        self.vat_amount = vat_amount
        self.total = total

        type(self).objects.filter(
            pk=self.pk
        ).update(
            subtotal=subtotal,
            vat_amount=vat_amount,
            total=total,
        )

    # =====================================================
    # DISPLAY HELPERS
    # =====================================================

    @property
    def before_vat_total(self):

        return (
            self.subtotal
            + (
                self.delivery_cost
                or Decimal("0.00")
            )
        )

    @property
    def vat_label(self):

        if not self.vat_enabled:
            return "No VAT"

        return (
            f"VAT @ {self.vat_rate:g}%"
        )

    def __str__(self):

        return (
            f"{self.workflow.order.reference_number} "
            f"| Quote V{self.version}"
        )


class BespokeQuoteLine(models.Model):

    quote = models.ForeignKey(
        BespokeQuote,
        on_delete=models.CASCADE,
        related_name="lines",
    )

    description = models.CharField(
        max_length=255,
    )

    quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("1.00"),
    )

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    sort_order = models.PositiveIntegerField(
        default=0,
    )

    class Meta:
        ordering = [
            "sort_order",
            "id",
        ]

    @property
    def line_total(self):

        return (
            self.quantity
            * self.unit_price
        )

    def save(self, *args, **kwargs):

        super().save(*args, **kwargs)

        self.quote.recalculate_totals()

    def delete(self, *args, **kwargs):

        quote = self.quote

        result = super().delete(
            *args,
            **kwargs,
        )

        quote.recalculate_totals()

        return result

    def __str__(self):

        return (
            f"{self.description} | "
            f"£{self.line_total:.2f}"
        )


# =========================================================
# CUSTOMER APPROVAL & PAYMENT
# =========================================================

class BespokeApprovalPayment(models.Model):

    class PaymentStatus(models.TextChoices):

        NOT_READY = (
            "not_ready",
            "Not Ready",
        )

        AWAITING_APPROVAL = (
            "awaiting_approval",
            "Awaiting Customer Approval",
        )

        AWAITING_PAYMENT = (
            "awaiting_payment",
            "Awaiting Payment",
        )

        PROCESSING = (
            "processing",
            "Payment Processing",
        )

        PAID = (
            "paid",
            "Paid",
        )

        FAILED = (
            "failed",
            "Payment Failed",
        )

        REFUNDED = (
            "refunded",
            "Refunded",
        )

    class PaymentProvider(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        PAYPAL = "paypal", "PayPal"

    workflow = models.OneToOneField(
        BespokeOrderWorkflow,
        on_delete=models.CASCADE,
        related_name="approval_payment",
    )

    quote = models.ForeignKey(
        BespokeQuote,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_records",
    )

    approval_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )

    approval_requested_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    customer_approved = models.BooleanField(
        default=False,
    )

    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    approved_name = models.CharField(
        max_length=150,
        blank=True,
    )

    approved_email = models.EmailField(
        blank=True,
    )

    approval_notes = models.TextField(
        blank=True,
    )

    amount_due = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    payment_status = models.CharField(
        max_length=30,
        choices=PaymentStatus.choices,
        default=PaymentStatus.NOT_READY,
    )

    payment_provider = models.CharField(
        max_length=20,
        choices=PaymentProvider.choices,
        blank=True,
    )

    payment_reference = models.CharField(
        max_length=255,
        blank=True,
    )

    checkout_reference = models.CharField(
        max_length=255,
        blank=True,
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    payment_metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    @property
    def can_start_production(self):

        return (
            self.customer_approved
            and self.payment_status
            == self.PaymentStatus.PAID
        )

    def mark_approval_requested(
        self,
        quote,
    ):

        self.quote = quote
        self.amount_due = quote.total

        self.approval_requested_at = (
            timezone.now()
        )

        self.payment_status = (
            self.PaymentStatus
            .AWAITING_APPROVAL
        )

        self.customer_approved = False
        self.approved_at = None
        self.paid_at = None

        self.save()

    def mark_approved(
        self,
        name="",
        email="",
    ):

        self.customer_approved = True
        self.approved_at = timezone.now()
        self.approved_name = name
        self.approved_email = email

        if (
            self.payment_status
            != self.PaymentStatus.PAID
        ):
            self.payment_status = (
                self.PaymentStatus
                .AWAITING_PAYMENT
            )

        self.save()

    def mark_paid(
        self,
        provider,
        reference="",
        checkout_reference="",
        metadata=None,
    ):

        self.payment_provider = provider

        self.payment_reference = (
            reference
        )

        self.checkout_reference = (
            checkout_reference
        )

        self.payment_status = (
            self.PaymentStatus.PAID
        )

        self.paid_at = timezone.now()

        if metadata is not None:
            self.payment_metadata = metadata

        self.save()

    def __str__(self):

        return (
            f"{self.workflow.order.reference_number} "
            f"| {self.get_payment_status_display()}"
        )


# =========================================================
# PRODUCTION
# =========================================================

class BespokeProduction(models.Model):

    class Status(models.TextChoices):

        NOT_STARTED = (
            "not_started",
            "Not Started",
        )

        IN_PROGRESS = (
            "in_progress",
            "In Progress",
        )

        PAUSED = (
            "paused",
            "Paused",
        )

        COMPLETE = (
            "complete",
            "Complete",
        )

    workflow = models.OneToOneField(
        BespokeOrderWorkflow,
        on_delete=models.CASCADE,
        related_name="production_record",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED,
    )

    internal_notes = models.TextField(
        blank=True,
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_production_jobs",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):

        return (
            f"Production | "
            f"{self.workflow.order.reference_number}"
        )


# =========================================================
# DELIVERY / DISPATCH
# =========================================================

class BespokeDelivery(models.Model):

    class Method(models.TextChoices):
        COURIER = "courier", "Courier"
        POST = "post", "Post"

        COLLECTION = (
            "collection",
            "Customer Collection",
        )

        LOCAL_DELIVERY = (
            "local_delivery",
            "Local Delivery",
        )

    class Status(models.TextChoices):

        NOT_READY = (
            "not_ready",
            "Not Ready",
        )

        READY = (
            "ready",
            "Ready",
        )

        DISPATCHED = (
            "dispatched",
            "Dispatched",
        )

        COLLECTED = (
            "collected",
            "Collected",
        )

        DELIVERED = (
            "delivered",
            "Delivered",
        )

    workflow = models.OneToOneField(
        BespokeOrderWorkflow,
        on_delete=models.CASCADE,
        related_name="delivery_record",
    )

    method = models.CharField(
        max_length=30,
        choices=Method.choices,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_READY,
    )

    carrier = models.CharField(
        max_length=100,
        blank=True,
    )

    service = models.CharField(
        max_length=100,
        blank=True,
    )

    tracking_number = models.CharField(
        max_length=150,
        blank=True,
    )

    dispatch_notes = models.TextField(
        blank=True,
    )

    dispatched_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispatched_bespoke_jobs",
    )

    delivered_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_bespoke_deliveries",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    @property
    def is_dispatched(self):

        return self.status in {
            self.Status.DISPATCHED,
            self.Status.COLLECTED,
            self.Status.DELIVERED,
        }

    def __str__(self):

        return (
            f"Delivery | "
            f"{self.workflow.order.reference_number}"
        )
