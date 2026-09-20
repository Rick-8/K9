import hashlib
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.staticfiles import finders
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Max, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import escape

from .activity import log_job_activity
from .forms import (
    BespokeDesignForm,
    BespokeDesignMasterForm,
    BespokeDesignVersionForm,
    BespokeJobWorkflowForm,
    BespokeQuoteForm,
    BespokeQuoteLineFormSet,
    CommunicationLogForm,
    CustomerEmailForm,
    DesignCustomerEmailForm,
    DesignVersionEmailForm,
    WhatsAppMessageForm,
)
from .models import (
    BespokeDesign,
    BespokeDesignVersion,
    BespokeOrderWorkflow,
    BespokeQuote,
    BespokeApprovalPayment,
    OrderCommunication,
)
from .views import sync_bespoke_workflow_with_order


# =========================================================
# WORKFLOW CONFIGURATION
# =========================================================

WIZARD_STEPS = {

    1: {
        "title": "Job Overview",
        "short_title": "Overview",
        "description": (
            "Review the original bespoke request, customer "
            "details and current job information."
        ),
    },

    2: {
        "title": "Customer Contact",
        "short_title": "Contact",
        "description": (
            "Contact the customer by email, WhatsApp or "
            "telephone and keep a complete communication history."
        ),
    },

    3: {
        "title": "Design & Specification",
        "short_title": "Design",
        "description": (
            "Create and manage design revisions until the "
            "customer accepts a design."
        ),
    },

    4: {
        "title": "Pricing & Quote",
        "short_title": "Quote",
        "description": (
            "Create, review and send quotation versions "
            "until the final price is agreed."
        ),
    },

    5: {
        "title": "Approval & Payment",
        "short_title": "Approval",
        "description": (
            "Obtain final customer approval and confirmed "
            "payment before production can begin."
        ),
    },

    6: {
        "title": "Production",
        "short_title": "Production",
        "description": (
            "Manage production and record customer "
            "communications relating to manufacture."
        ),
    },

    7: {
        "title": "Completion & Delivery",
        "short_title": "Delivery",
        "description": (
            "Record delivery, carrier and tracking information "
            "and complete dispatch."
        ),
    },

    8: {
        "title": "Close Job",
        "short_title": "Complete",
        "description": (
            "Review the completed bespoke job and its "
            "full history."
        ),
    },
}


STEP_STAGE_MAP = {

    1: BespokeOrderWorkflow.Stage.REVIEW,

    2: BespokeOrderWorkflow.Stage.CUSTOMER_CONTACT,

    3: BespokeOrderWorkflow.Stage.DESIGN,

    4: BespokeOrderWorkflow.Stage.QUOTE,

    5: BespokeOrderWorkflow.Stage.AWAITING_CUSTOMER,

    6: BespokeOrderWorkflow.Stage.PRODUCTION,

    7: BespokeOrderWorkflow.Stage.DELIVERY,

    8: BespokeOrderWorkflow.Stage.READY,
}


CLOSED_STAGES = [
    BespokeOrderWorkflow.Stage.COMPLETED,
    BespokeOrderWorkflow.Stage.CANCELLED,
]


# =========================================================
# GENERAL HELPERS
# =========================================================

def format_user_name(user):
    """
    Return a useful display name for a staff member.
    """

    if not user:
        return "System"

    full_name = user.get_full_name().strip()

    if full_name:
        return full_name

    return user.username


def format_datetime(value):
    """
    Format a datetime for the activity trail.
    """

    if not value:
        return "Not set"

    return timezone.localtime(
        value
    ).strftime(
        "%d %b %Y %H:%M"
    )


def customer_first_name(order):
    """
    Return the customer's first name for messages.
    """

    if not order.customer_name:
        return "there"

    return (
        order.customer_name
        .strip()
        .split(" ")[0]
    )


def touch_workflow(
    workflow,
    user,
):
    """
    Record that a member of staff worked on the job.
    """

    now = timezone.now()

    fields_to_update = [
        "last_worked_by",
        "last_worked_at",
        "updated_at",
    ]

    workflow.last_worked_by = user
    workflow.last_worked_at = now

    if workflow.started_at is None:

        workflow.started_at = now

        fields_to_update.append(
            "started_at"
        )

    workflow.save(
        update_fields=fields_to_update
    )


def ensure_order_processing(
    order,
    user,
):
    """
    Move a pending order into processing once staff begin
    meaningful work.
    """

    if order.status != "pending":
        return

    order.status = "processing"

    order.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    log_job_activity(
        order=order,
        user=user,
        message=(
            "Order status changed from "
            "'Pending' to 'Processing' "
            "when staff started work."
        ),
    )


# =========================================================
# EMAIL HELPERS
# =========================================================

def default_customer_email_message(order):
    """
    Default Step 2 email message.
    """

    first_name = customer_first_name(
        order
    )

    return (
        f"Hi {first_name},\n\n"
        "Thank you for choosing K9.\n\n"
        "I'm getting in touch regarding your bespoke "
        f"order {order.reference_number}.\n\n"
    )


def default_design_version_email_message(
    order,
    design_version,
):
    """
    Default email when sending a specific design revision.
    """

    first_name = customer_first_name(
        order
    )

    message = (
        f"Hi {first_name},\n\n"
        "We've prepared a new design for your bespoke "
        f"order {order.reference_number}.\n\n"
        f"{design_version.version_label}\n\n"
    )

    if design_version.customer_summary:

        message += (
            f"{design_version.customer_summary}\n\n"
        )

    if design_version.change_summary:

        message += (
            "Changes in this version:\n"
            f"{design_version.change_summary}\n\n"
        )

    message += (
        "Please review the attached design and use the "
        "review button below to either accept this design "
        "or request changes.\n\n"
    )

    return message


def build_customer_design_review_url(
    request,
    design_version,
):
    """
    Build the secure public customer review URL.

    The URL route itself will be added in the next step.
    """

    return request.build_absolute_uri(
        (
            "/orders/design-review/"
            f"{design_version.response_token}/"
        )
    )


def build_customer_quote_review_url(
    request,
    approval_payment,
):
    """
    Build the secure public quote review URL.

    The approval token is the capability used by the customer
    to review and accept the currently active quote.
    """

    return request.build_absolute_uri(
        (
            "/orders/quote-review/"
            f"{approval_payment.approval_token}/"
        )
    )


def build_k9_email_content(
    order,
    staff_message,
    section_title="Bespoke Order",
    action_url="",
    action_label="",
):
    """
    Build professional plain-text and HTML versions
    of an outgoing K9 email.

    Optionally include a customer action button.
    """

    safe_message = escape(
        staff_message
    )

    html_message = safe_message.replace(
        "\n",
        "<br>"
    )

    reference = escape(
        order.reference_number
    )

    customer_name = escape(
        order.customer_name
        or "Customer"
    )

    safe_section_title = escape(
        section_title
    )

    action_html = ""

    if action_url and action_label:

        safe_url = escape(
            action_url
        )

        safe_label = escape(
            action_label
        )

        action_html = f"""
        <table
            width="100%"
            cellpadding="0"
            cellspacing="0"
            role="presentation"
            style="
                margin-top: 28px;
                margin-bottom: 10px;
            "
        >
            <tr>
                <td align="center">

                    <a
                        href="{safe_url}"
                        style="
                            display: inline-block;
                            background: #212529;
                            color: #ffffff;
                            text-decoration: none;
                            font-size: 15px;
                            font-weight: bold;
                            padding: 14px 24px;
                            border-radius: 8px;
                        "
                    >
                        {safe_label}
                    </a>

                </td>
            </tr>
        </table>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">

    <head>
        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>K9 Bespoke Order</title>
    </head>

    <body
        style="
            margin: 0;
            padding: 0;
            background-color: #f4f5f7;
            font-family: Arial, Helvetica, sans-serif;
            color: #212529;
        "
    >

        <table
            width="100%"
            cellpadding="0"
            cellspacing="0"
            role="presentation"
            style="
                background-color: #f4f5f7;
                padding: 30px 15px;
            "
        >

            <tr>

                <td align="center">

                    <table
                        width="100%"
                        cellpadding="0"
                        cellspacing="0"
                        role="presentation"
                        style="
                            max-width: 650px;
                            background: #ffffff;
                            border-radius: 12px;
                            overflow: hidden;
                            border: 1px solid #e5e7eb;
                        "
                    >

                        <!-- HEADER -->

                        <tr>

                            <td
                                style="
                                    background-color: #212529;
                                    color: #ffffff;
                                    padding: 28px 32px;
                                "
                            >

                                <div
                                    style="
                                        font-size: 30px;
                                        font-weight: bold;
                                    "
                                >
                                    K9
                                </div>

                                <div
                                    style="
                                        color: #ced4da;
                                        font-size: 14px;
                                        margin-top: 5px;
                                    "
                                >
                                    Handmade, personalised
                                    &amp; bespoke gifts
                                </div>

                            </td>

                        </tr>


                        <!-- REFERENCE -->

                        <tr>

                            <td
                                style="
                                    padding: 24px 32px 0 32px;
                                "
                            >

                                <table
                                    width="100%"
                                    cellpadding="0"
                                    cellspacing="0"
                                    role="presentation"
                                    style="
                                        background: #f8f9fa;
                                        border-radius: 8px;
                                    "
                                >

                                    <tr>

                                        <td
                                            style="
                                                padding: 16px;
                                            "
                                        >

                                            <div
                                                style="
                                                    color: #6c757d;
                                                    font-size: 11px;
                                                    font-weight: bold;
                                                    text-transform: uppercase;
                                                    letter-spacing: 1px;
                                                "
                                            >
                                                {safe_section_title}
                                            </div>

                                            <div
                                                style="
                                                    color: #212529;
                                                    font-size: 18px;
                                                    font-weight: bold;
                                                    margin-top: 5px;
                                                "
                                            >
                                                {reference}
                                            </div>

                                        </td>

                                    </tr>

                                </table>

                            </td>

                        </tr>


                        <!-- MESSAGE -->

                        <tr>

                            <td
                                style="
                                    padding: 30px 32px;
                                    font-size: 16px;
                                    line-height: 1.7;
                                    color: #343a40;
                                "
                            >

                                {html_message}

                                {action_html}

                                <br><br>

                                Kind regards,<br>

                                <strong>
                                    K9
                                </strong>

                            </td>

                        </tr>


                        <!-- FOOTER -->

                        <tr>

                            <td
                                style="
                                    background: #f8f9fa;
                                    border-top: 1px solid #e5e7eb;
                                    padding: 22px 32px;
                                    color: #6c757d;
                                    font-size: 12px;
                                    line-height: 1.6;
                                "
                            >

                                This email relates to your K9
                                bespoke order

                                <strong>
                                    {reference}
                                </strong>.

                                <br><br>

                                Please reply to this email if you
                                have any questions or need to provide
                                further information.

                                <br><br>

                                Customer:

                                <strong>
                                    {customer_name}
                                </strong>

                            </td>

                        </tr>

                    </table>

                </td>

            </tr>

        </table>

    </body>

    </html>
    """

    plain_content = (
        f"{staff_message}\n\n"
    )

    if action_url and action_label:

        plain_content += (
            f"{action_label}:\n"
            f"{action_url}\n\n"
        )

    plain_content += (
        "Kind regards,\n"
        "K9\n\n"
        "----------------------------------------\n"
        f"K9 Bespoke Order: {order.reference_number}\n"
        "Handmade, personalised and bespoke gifts.\n\n"
        "Please reply to this email if you have any "
        "questions or need to provide further information."
    )

    return (
        plain_content,
        html_content,
    )


def attach_uploaded_file(
    email,
    attachment,
):
    """
    Attach a temporary uploaded file without storing it.
    """

    if not attachment:
        return

    attachment.seek(0)

    email.attach(
        attachment.name,
        attachment.read(),
        (
            getattr(
                attachment,
                "content_type",
                None,
            )
            or "application/octet-stream"
        ),
    )

    attachment.seek(0)


# =========================================================
# DESIGN FILE HELPERS
# =========================================================

def calculate_file_metadata(
    attachment,
):
    """
    Calculate identifying metadata for a design attachment.

    The SHA-256 fingerprint identifies the exact bytes that
    were sent without permanently storing the file.
    """

    if not attachment:

        return {
            "file_name": "",
            "file_content_type": "",
            "file_size": None,
            "file_sha256": "",
        }

    digest = hashlib.sha256()

    attachment.seek(0)

    for chunk in attachment.chunks():

        digest.update(
            chunk
        )

    attachment.seek(0)

    return {
        "file_name": (
            attachment.name
        ),

        "file_content_type": (
            getattr(
                attachment,
                "content_type",
                "",
            )
            or ""
        ),

        "file_size": (
            attachment.size
        ),

        "file_sha256": (
            digest.hexdigest()
        ),
    }


def build_next_design_version_initial(
    design,
):
    """
    Build the starting content for the next design version.

    The previous design description is carried forward so
    staff do not need to re-enter it manually.

    If the latest design was rejected / changes requested,
    the customer's feedback is also appended to the customer
    description and copied into the change summary.

    Example:

        Original design description...

        Customer requested changes from Design V1:
        Please make the lettering larger.
    """

    if not design:
        return {}

    latest_version = (
        design.latest_version
    )

    if not latest_version:
        return {}

    customer_summary = (
        latest_version
        .customer_summary
        .strip()
    )

    change_summary = ""

    # -----------------------------------------------------
    # CUSTOMER REQUESTED CHANGES
    # -----------------------------------------------------

    if (
        latest_version.status
        == (
            BespokeDesignVersion
            .Status
            .REJECTED
        )
        and latest_version.response_notes
    ):

        requested_changes = (
            latest_version
            .response_notes
            .strip()
        )

        if customer_summary:

            customer_summary = (
                f"{customer_summary}\n\n"
                "Customer requested changes from "
                f"{latest_version.version_label}:\n"
                f"{requested_changes}"
            )

        else:

            customer_summary = (
                "Customer requested changes from "
                f"{latest_version.version_label}:\n"
                f"{requested_changes}"
            )

        change_summary = (
            requested_changes
        )

    # -----------------------------------------------------
    # RETURN PREFILLED VALUES FOR NEW VERSION FORM
    # -----------------------------------------------------

    return {
        "customer_summary": (
            customer_summary
        ),

        "change_summary": (
            change_summary
        ),
    }


def supersede_other_active_designs(
    design_version,
):
    """
    When a newer version is actually sent to the customer,
    older active versions must no longer remain actionable.

    Rejected versions remain rejected so the revision
    history stays accurate.

    Draft, sent and previously accepted versions become
    superseded when another design version takes over.
    """

    now = timezone.now()

    (
        design_version
        .design
        .versions
        .exclude(
            pk=design_version.pk
        )
        .filter(
            status__in=[
                BespokeDesignVersion
                .Status
                .DRAFT,

                BespokeDesignVersion
                .Status
                .SENT,

                BespokeDesignVersion
                .Status
                .ACCEPTED,
            ]
        )
        .update(
            status=(
                BespokeDesignVersion
                .Status
                .SUPERSEDED
            ),
            updated_at=now,
        )
    )


# =========================================================
# QUOTE HELPERS
# =========================================================

def quote_label(quote):
    """
    Return the customer/staff-facing quote version label.
    """

    return f"Quote V{quote.version}"


def format_quote_email_message(
    order,
    quote,
    staff_message,
):
    """
    Build the text used inside the branded K9 email.

    All prices and VAT settings come from staff-entered quote
    data. K9 only formats and calculates the saved values.
    """

    lines = [
        staff_message.strip(),
        "",
        "----------------------------------------",
        quote_label(quote).upper(),
        "----------------------------------------",
    ]

    for line in quote.lines.all():

        lines.append(
            f"{line.description} | "
            f"{line.quantity:g} × £{line.unit_price:.2f} "
            f"= £{line.line_total:.2f}"
        )

    lines.extend(
        [
            "",
            f"Subtotal: £{quote.subtotal:.2f}",
            f"Delivery: £{quote.delivery_cost:.2f}",
        ]
    )

    if quote.vat_enabled:

        vat_delivery_text = (
            "including delivery"
            if quote.vat_on_delivery
            else "excluding delivery"
        )

        lines.extend(
            [
                (
                    f"VAT @ {quote.vat_rate:g}% "
                    f"({vat_delivery_text}): "
                    f"£{quote.vat_amount:.2f}"
                ),
            ]
        )

    else:

        lines.append(
            "VAT: Not applied"
        )

    lines.append(
        f"TOTAL: £{quote.total:.2f}"
    )

    if quote.notes:
        lines.extend(
            [
                "",
                "Quote notes:",
                quote.notes.strip(),
            ]
        )

    lines.extend(
        [
            "",
            (
                "Please review this quotation. If anything needs "
                "changing, reply to this email or contact K9 and "
                "we can prepare a revised quote."
            ),
            "",
            (
                "When you are happy with the quotation, use the "
                "Approve Quote & Pay button in this email. Once "
                "accepted, K9 will move your order to the payment "
                "stage."
            ),
        ]
    )

    return "\n".join(lines)


def supersede_other_active_quotes(
    selected_quote,
):
    """
    Keep one customer-facing quote active at a time.

    If a revised quote is sent, any older draft, sent or
    accepted quote becomes superseded. This prevents an old
    acceptance from keeping the payment stage unlocked.
    """

    (
        selected_quote
        .workflow
        .quotes
        .exclude(pk=selected_quote.pk)
        .filter(
            status__in=[
                BespokeQuote.Status.DRAFT,
                BespokeQuote.Status.SENT,
                BespokeQuote.Status.ACCEPTED,
            ]
        )
        .update(
            status=BespokeQuote.Status.SUPERSEDED,
            updated_at=timezone.now(),
        )
    )


def clone_quote_revision(
    source_quote,
    user,
):
    """
    Create a new draft quote by copying the previous version,
    including every line item.
    """

    with transaction.atomic():

        highest_version = (
            source_quote
            .workflow
            .quotes
            .aggregate(maximum=Max("version"))
            .get("maximum")
            or 0
        )

        new_quote = BespokeQuote.objects.create(
            workflow=source_quote.workflow,
            version=highest_version + 1,
            status=BespokeQuote.Status.DRAFT,
            title=source_quote.title,
            notes=source_quote.notes,
            delivery_cost=source_quote.delivery_cost,
            vat_enabled=source_quote.vat_enabled,
            vat_rate=source_quote.vat_rate,
            vat_on_delivery=source_quote.vat_on_delivery,
            created_by=user,
        )

        for source_line in source_quote.lines.all():

            new_quote.lines.create(
                description=source_line.description,
                quantity=source_line.quantity,
                unit_price=source_line.unit_price,
                sort_order=source_line.sort_order,
            )

        new_quote.recalculate_totals()
        new_quote.refresh_from_db()

    return new_quote


# =========================================================
# WHATSAPP HELPERS
# =========================================================

def normalise_whatsapp_number(
    phone_number,
):
    """
    Convert a telephone number into wa.me format.
    """

    if not phone_number:
        return ""

    cleaned = ""

    for character in str(
        phone_number
    ):

        if character.isdigit():

            cleaned += character

        elif (
            character == "+"
            and not cleaned
        ):

            cleaned += character

    if cleaned.startswith("00"):

        cleaned = (
            "+"
            + cleaned[2:]
        )

    if cleaned.startswith("+"):

        cleaned = cleaned[1:]

    elif cleaned.startswith("0"):

        cleaned = (
            "44"
            + cleaned[1:]
        )

    if len(cleaned) < 8:
        return ""

    return cleaned


def build_whatsapp_url(
    phone_number,
    message,
):
    """
    Build a WhatsApp click-to-chat URL.
    """

    number = normalise_whatsapp_number(
        phone_number
    )

    if not number:
        return ""

    encoded_message = quote(
        message,
        safe="",
    )

    return (
        f"https://wa.me/{number}"
        f"?text={encoded_message}"
    )


def default_whatsapp_message(order):
    """
    Default WhatsApp message.
    """

    first_name = customer_first_name(
        order
    )

    return (
        f"Hi {first_name}, "
        f"it's K9 regarding your bespoke order "
        f"{order.reference_number}. "
    )


# =========================================================
# ACTIVITY FEED
# =========================================================

def build_activity_feed(order):
    """
    Merge notes and communications into one activity feed.
    """

    items = []

    notes = (
        order.notes
        .select_related(
            "author"
        )
        .all()[:50]
    )

    communications = (
        order.communications
        .select_related(
            "logged_by",
            "design_version",
        )
        .all()[:50]
    )

    for note in notes:

        items.append(
            {
                "kind": "note",
                "timestamp": note.created_at,
                "note": note,
            }
        )

    for communication in communications:

        items.append(
            {
                "kind": "communication",
                "timestamp": (
                    communication.occurred_at
                ),
                "communication": (
                    communication
                ),
            }
        )

    items.sort(
        key=lambda item: item[
            "timestamp"
        ],
        reverse=True,
    )

    return items[:50]


# =========================================================
# WORKFLOW CHANGE LOGGING
# =========================================================

def log_workflow_field_changes(
    order,
    user,
    old_values,
    workflow,
):
    """
    Log important workflow changes.
    """

    changes = []

    if (
        old_values["priority"]
        != workflow.priority
    ):

        old_label = dict(
            BespokeOrderWorkflow
            .Priority
            .choices
        ).get(
            old_values["priority"],
            old_values["priority"],
        )

        changes.append(
            (
                "Priority changed from "
                f"'{old_label}' to "
                f"'{workflow.get_priority_display()}'."
            )
        )

    if (
        old_values["staff_summary"]
        != workflow.staff_summary
    ):

        changes.append(
            (
                "Working summary updated.\n\n"
                "Previous:\n"
                f"{old_values['staff_summary'] or 'Not set'}"
                "\n\n"
                "New:\n"
                f"{workflow.staff_summary or 'Not set'}"
            )
        )

    if (
        old_values["next_action"]
        != workflow.next_action
    ):

        changes.append(
            (
                "Next action updated.\n\n"
                "Previous:\n"
                f"{old_values['next_action'] or 'Not set'}"
                "\n\n"
                "New:\n"
                f"{workflow.next_action or 'Not set'}"
            )
        )

    if (
        old_values["next_action_due"]
        != workflow.next_action_due
    ):

        changes.append(
            (
                "Next action due date changed "
                f"from "
                f"'{format_datetime(old_values['next_action_due'])}' "
                f"to "
                f"'{format_datetime(workflow.next_action_due)}'."
            )
        )

    if (
        old_values["customer_waiting"]
        != workflow.customer_waiting
    ):

        if workflow.customer_waiting:

            changes.append(
                (
                    "Job marked as waiting "
                    "for the customer."
                )
            )

        else:

            changes.append(
                (
                    "Waiting for customer "
                    "status cleared."
                )
            )

    for change in changes:

        log_job_activity(
            order=order,
            user=user,
            message=change,
        )




# =========================================================
# STEP 4 - QUOTE PDF
# =========================================================

@staff_member_required
def bespoke_quote_pdf(
    request,
    quote_id,
):
    """
    Generate the saved quotation as a PDF.

    Superusers may view any bespoke quote.
    Ordinary staff may only view quotes belonging to jobs
    assigned to them.

    ?download=1 changes the response from inline viewing to
    a downloadable PDF.
    """

    quote_query = (
        BespokeQuote.objects
        .select_related(
            "workflow",
            "workflow__order",
            "workflow__assigned_to",
            "created_by",
        )
        .prefetch_related(
            "lines"
        )
    )

    if not request.user.is_superuser:

        quote_query = quote_query.filter(
            workflow__assigned_to=request.user
        )

    selected_quote = get_object_or_404(
        quote_query,
        pk=quote_id,
    )

    order = selected_quote.workflow.order

    selected_quote.recalculate_totals()
    selected_quote.refresh_from_db()

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import (
            ParagraphStyle,
            getSampleStyleSheet,
        )
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Image,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

    except ImportError:

        return HttpResponse(
            (
                "PDF support requires ReportLab. "
                "Install it with: pip install reportlab"
            ),
            status=500,
            content_type="text/plain",
        )

    filename = (
        f"K9-{order.reference_number}-"
        f"Quote-V{selected_quote.version}.pdf"
    )

    download_requested = (
        request.GET.get("download")
        == "1"
    )

    disposition = (
        "attachment"
        if download_requested
        else "inline"
    )

    response = HttpResponse(
        content_type="application/pdf"
    )

    response[
        "Content-Disposition"
    ] = (
        f'{disposition}; filename="{filename}"'
    )

    document = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=(
            f"K9 Quote V{selected_quote.version}"
        ),
        author="K9",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "K9QuoteTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#212529"),
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "K9QuoteSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#6c757d"),
        spaceAfter=14,
    )

    heading_style = ParagraphStyle(
        "K9QuoteHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#212529"),
        spaceBefore=8,
        spaceAfter=6,
    )

    normal_style = ParagraphStyle(
        "K9QuoteNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#343a40"),
    )

    right_style = ParagraphStyle(
        "K9QuoteRight",
        parent=normal_style,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#111111"),
    )

    table_header_style = ParagraphStyle(
        "K9QuoteTableHeader",
        parent=normal_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    table_header_right_style = ParagraphStyle(
        "K9QuoteTableHeaderRight",
        parent=table_header_style,
        alignment=TA_RIGHT,
    )

    reference_label_style = ParagraphStyle(
        "K9ReferenceLabel",
        parent=normal_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
    )

    reference_value_style = ParagraphStyle(
        "K9ReferenceValue",
        parent=normal_style,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#111111"),
        alignment=TA_RIGHT,
    )

    story = []

    # =====================================================
    # K9 BRANDED PDF HEADER
    #
    # Find the logo through Django's static-file system so
    # this works locally and after deployment/collectstatic.
    # The project file is expected at:
    # static/media/logo-I.png
    # =====================================================

    logo_path = finders.find(
        "media/logo-I.png"
    )

    if logo_path:

        logo = Image(
            logo_path
        )

        max_logo_width = 48 * mm
        max_logo_height = 30 * mm

        scale = min(
            max_logo_width / logo.drawWidth,
            max_logo_height / logo.drawHeight,
            1,
        )

        logo.drawWidth *= scale
        logo.drawHeight *= scale

        brand_element = logo

    else:

        # Safe fallback if the logo file cannot be found.
        brand_element = Paragraph(
            "K9",
            title_style,
        )

    header_right = Paragraph(
        (
            "<b>QUOTATION</b><br/>"
            f"Quote V{selected_quote.version}<br/>"
            f"Order {escape(order.reference_number)}"
        ),
        right_style,
    )

    header_table = Table(
        [
            [
                brand_element,
                header_right,
            ]
        ],
        colWidths=[
            92 * mm,
            71 * mm,
        ],
    )

    header_table.setStyle(
        TableStyle(
            [
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "ALIGN",
                    (1, 0),
                    (1, 0),
                    "RIGHT",
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, -1),
                    1,
                    colors.HexColor("#212529"),
                ),
            ]
        )
    )

    story.append(
        header_table
    )

    story.append(
        Spacer(
            1,
            4 * mm,
        )
    )

    story.append(
        Paragraph(
            "Handmade, personalised &amp; bespoke gifts",
            subtitle_style,
        )
    )

    reference_data = [
        [
            Paragraph(
                "<b>Quote</b>",
                reference_label_style,
            ),
            Paragraph(
                f"Quote V{selected_quote.version}",
                reference_value_style,
            ),
        ],
        [
            Paragraph(
                "<b>Order reference</b>",
                reference_label_style,
            ),
            Paragraph(
                escape(order.reference_number),
                reference_value_style,
            ),
        ],
        [
            Paragraph(
                "<b>Customer</b>",
                reference_label_style,
            ),
            Paragraph(
                escape(order.customer_name or ""),
                reference_value_style,
            ),
        ],
        [
            Paragraph(
                "<b>Email</b>",
                reference_label_style,
            ),
            Paragraph(
                escape(order.customer_email or ""),
                reference_value_style,
            ),
        ],
        [
            Paragraph(
                "<b>Document</b>",
                reference_label_style,
            ),
            Paragraph(
                "Quotation",
                reference_value_style,
            ),
        ],
        [
            Paragraph(
                "<b>Created</b>",
                reference_label_style,
            ),
            Paragraph(
                timezone.localtime(
                    selected_quote.created_at
                ).strftime(
                    "%d %b %Y %H:%M"
                ),
                reference_value_style,
            ),
        ],
    ]

    reference_table = Table(
        reference_data,
        colWidths=[
            55 * mm,
            100 * mm,
        ],
    )

    reference_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.HexColor("#212529"),
                ),
                (
                    "BACKGROUND",
                    (1, 0),
                    (1, -1),
                    colors.white,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.9,
                    colors.HexColor("#adb5bd"),
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.45,
                    colors.HexColor("#ced4da"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    7,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
            ]
        )
    )

    story.append(
        reference_table
    )

    story.append(
        Spacer(
            1,
            8 * mm,
        )
    )

    story.append(
        Paragraph(
            escape(selected_quote.title),
            heading_style,
        )
    )

    line_data = [
        [
            Paragraph(
                "Description",
                table_header_style,
            ),
            Paragraph(
                "Qty",
                table_header_right_style,
            ),
            Paragraph(
                "Unit",
                table_header_right_style,
            ),
            Paragraph(
                "Total",
                table_header_right_style,
            ),
        ]
    ]

    for line in selected_quote.lines.all():

        line_data.append(
            [
                Paragraph(
                    escape(line.description),
                    normal_style,
                ),
                Paragraph(
                    f"{line.quantity:g}",
                    right_style,
                ),
                Paragraph(
                    f"£{line.unit_price:.2f}",
                    right_style,
                ),
                Paragraph(
                    f"£{line.line_total:.2f}",
                    right_style,
                ),
            ]
        )

    line_table = Table(
        line_data,
        colWidths=[
            92 * mm,
            18 * mm,
            25 * mm,
            28 * mm,
        ],
        repeatRows=1,
    )

    line_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#212529"),
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, 0),
                    colors.white,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.HexColor("#ced4da"),
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.HexColor("#dee2e6"),
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    story.append(
        line_table
    )

    story.append(
        Spacer(
            1,
            6 * mm,
        )
    )

    totals_data = [
        [
            "Subtotal",
            f"£{selected_quote.subtotal:.2f}",
        ],
        [
            "Delivery",
            f"£{selected_quote.delivery_cost:.2f}",
        ],
    ]

    if selected_quote.vat_enabled:

        vat_label = (
            f"VAT @ {selected_quote.vat_rate:g}%"
        )

        totals_data.append(
            [
                vat_label,
                f"£{selected_quote.vat_amount:.2f}",
            ]
        )

    else:

        totals_data.append(
            [
                "VAT",
                "Not applied",
            ]
        )

    totals_data.append(
        [
            "TOTAL",
            f"£{selected_quote.total:.2f}",
        ]
    )

    totals_table = Table(
        totals_data,
        colWidths=[
            55 * mm,
            35 * mm,
        ],
        hAlign="RIGHT",
    )

    totals_table.setStyle(
        TableStyle(
            [
                (
                    "ALIGN",
                    (1, 0),
                    (1, -1),
                    "RIGHT",
                ),
                (
                    "FONTNAME",
                    (0, -1),
                    (-1, -1),
                    "Helvetica-Bold",
                ),
                (
                    "FONTSIZE",
                    (0, -1),
                    (-1, -1),
                    11,
                ),
                (
                    "LINEABOVE",
                    (0, -1),
                    (-1, -1),
                    0.75,
                    colors.HexColor("#212529"),
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
            ]
        )
    )

    story.append(
        totals_table
    )

    if selected_quote.vat_enabled:

        vat_delivery_text = (
            "VAT includes delivery."
            if selected_quote.vat_on_delivery
            else "VAT excludes delivery."
        )

        story.append(
            Spacer(
                1,
                3 * mm,
            )
        )

        story.append(
            Paragraph(
                vat_delivery_text,
                subtitle_style,
            )
        )

    if selected_quote.notes:

        story.append(
            Spacer(
                1,
                5 * mm,
            )
        )

        story.append(
            Paragraph(
                "Quote Notes",
                heading_style,
            )
        )

        safe_notes = (
            escape(
                selected_quote.notes
            )
            .replace(
                "\n",
                "<br/>"
            )
        )

        story.append(
            Paragraph(
                safe_notes,
                normal_style,
            )
        )

    story.append(
        Spacer(
            1,
            8 * mm,
        )
    )

    story.append(
        Paragraph(
            (
                "This quotation relates to K9 bespoke order "
                f"{order.reference_number}. Final approval and "
                "payment are handled separately."
            ),
            subtitle_style,
        )
    )

    document.build(
        story
    )

    return response


# =========================================================
# STAFF JOB DASHBOARD
# =========================================================

@staff_member_required
def staff_jobs_dashboard(request):
    """
    Ordinary staff only see jobs assigned directly to them.
    """

    if request.user.is_superuser:

        return redirect(
            "bespoke_jobs_dashboard"
        )

    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    stage_filter = request.GET.get(
        "stage",
        "",
    ).strip()

    priority_filter = request.GET.get(
        "priority",
        "",
    ).strip()

    show_closed = (
        request.GET.get(
            "show_closed"
        )
        == "1"
    )

    jobs = (
        BespokeOrderWorkflow.objects
        .select_related(
            "order",
            "order__bespoke_request",
            "assigned_to",
            "last_worked_by",
        )
        .filter(
            assigned_to=request.user
        )
    )

    if search_query:

        jobs = jobs.filter(

            Q(
                order__reference_number__icontains=(
                    search_query
                )
            )

            |

            Q(
                order__customer_name__icontains=(
                    search_query
                )
            )

            |

            Q(
                order__customer_email__icontains=(
                    search_query
                )
            )

            |

            Q(
                order__bespoke_request__reference__icontains=(
                    search_query
                )
            )

            |

            Q(
                next_action__icontains=(
                    search_query
                )
            )
        )

    valid_stages = {
        value
        for value, label
        in (
            BespokeOrderWorkflow
            .Stage
            .choices
        )
    }

    if (
        stage_filter
        and stage_filter
        in valid_stages
    ):

        jobs = jobs.filter(
            stage=stage_filter
        )

    valid_priorities = {
        value
        for value, label
        in (
            BespokeOrderWorkflow
            .Priority
            .choices
        )
    }

    if (
        priority_filter
        and priority_filter
        in valid_priorities
    ):

        jobs = jobs.filter(
            priority=priority_filter
        )

    if not show_closed:

        jobs = jobs.exclude(
            stage__in=CLOSED_STAGES
        )

    jobs = jobs.order_by(
        "-customer_waiting",
        "-last_worked_at",
        "-updated_at",
    )

    my_jobs = (
        BespokeOrderWorkflow.objects
        .filter(
            assigned_to=request.user
        )
    )

    job_counts = {

        "active": (
            my_jobs
            .exclude(
                stage__in=CLOSED_STAGES
            )
            .count()
        ),

        "waiting": (
            my_jobs
            .filter(
                customer_waiting=True
            )
            .exclude(
                stage__in=CLOSED_STAGES
            )
            .count()
        ),

        "urgent": (
            my_jobs
            .filter(
                priority=(
                    BespokeOrderWorkflow
                    .Priority
                    .URGENT
                )
            )
            .exclude(
                stage__in=CLOSED_STAGES
            )
            .count()
        ),

        "completed": (
            my_jobs
            .filter(
                stage=(
                    BespokeOrderWorkflow
                    .Stage
                    .COMPLETED
                )
            )
            .count()
        ),

        "cancelled": (
            my_jobs
            .filter(
                stage=(
                    BespokeOrderWorkflow
                    .Stage
                    .CANCELLED
                )
            )
            .count()
        ),
    }

    context = {

        "jobs": jobs,

        "search_query": (
            search_query
        ),

        "stage_filter": (
            stage_filter
        ),

        "priority_filter": (
            priority_filter
        ),

        "show_closed": (
            show_closed
        ),

        "job_counts": (
            job_counts
        ),

        "stage_choices": (
            BespokeOrderWorkflow
            .Stage
            .choices
        ),

        "priority_choices": (
            BespokeOrderWorkflow
            .Priority
            .choices
        ),
    }

    return render(
        request,
        "orders/staff_jobs_dashboard.html",
        context,
    )


# =========================================================
# BESPOKE JOB WIZARD
# =========================================================

@staff_member_required
def bespoke_job_wizard(
    request,
    reference_number,
    step,
):
    """
    Persistent bespoke staff workflow.

    Ordinary staff may only open jobs assigned to them.
    Superusers may open any bespoke job.
    """

    # =====================================================
    # VALIDATE STEP
    # =====================================================

    if step not in WIZARD_STEPS:

        if request.user.is_superuser:

            return redirect(
                "bespoke_jobs_dashboard"
            )

        return redirect(
            "staff_jobs_dashboard"
        )

    # =====================================================
    # SECURE JOB QUERY
    # =====================================================

    workflow_query = (
        BespokeOrderWorkflow.objects
        .select_related(
            "order",
            "order__bespoke_request",
            "assigned_to",
            "last_worked_by",
        )
    )

    if not request.user.is_superuser:

        workflow_query = (
            workflow_query.filter(
                assigned_to=request.user
            )
        )

    workflow = get_object_or_404(
        workflow_query,
        order__reference_number=(
            reference_number
        ),
    )

    order = workflow.order

    is_closed = (
        workflow.stage
        in CLOSED_STAGES
    )

    # =====================================================
    # DESIGN MASTER RECORD
    # =====================================================

    design = (
        BespokeDesign.objects
        .filter(
            workflow=workflow
        )
        .first()
    )

    if (
        step >= 3
        and not design
    ):

        design = (
            BespokeDesign.objects.create(
                workflow=workflow
            )
        )

    accepted_design_version = None

    if design:

        accepted_design_version = (
            design.accepted_version
        )

    # =====================================================
    # QUOTE STATE
    # =====================================================

    active_quote = (
        workflow.quotes
        .filter(
            status__in=[
                BespokeQuote.Status.SENT,
                BespokeQuote.Status.ACCEPTED,
            ]
        )
        .order_by("-version")
        .first()
    )

    accepted_quote = (
        workflow.quotes
        .filter(
            status=BespokeQuote.Status.ACCEPTED
        )
        .order_by("-version")
        .first()
    )

    # =====================================================
    # HARD DESIGN GATE
    #
    # No job can progress beyond Step 3 unless one design
    # revision has actually been accepted.
    # =====================================================

    if (
        step > 3
        and not is_closed
        and not accepted_design_version
    ):

        if workflow.current_step > 3:

            workflow.current_step = (
                BespokeOrderWorkflow
                .Step
                .DESIGN
            )

            workflow.stage = (
                BespokeOrderWorkflow
                .Stage
                .DESIGN
            )

            workflow.save(
                update_fields=[
                    "current_step",
                    "stage",
                    "updated_at",
                ]
            )

        messages.warning(
            request,
            (
                "A design must be accepted by the "
                "customer before this job can progress "
                "beyond Design & Specification."
            ),
        )

        return redirect(
            "bespoke_job_wizard",
            reference_number=(
                order.reference_number
            ),
            step=3,
        )

    # =====================================================
    # HARD QUOTE ACCEPTANCE GATE
    #
    # Sending a quote does not unlock Step 5.
    # The customer must accept the quote first. The public
    # acceptance view advances the workflow automatically.
    # =====================================================

    if (
        step > 4
        and not is_closed
        and not accepted_quote
    ):

        if workflow.current_step > 4:

            workflow.current_step = (
                BespokeOrderWorkflow
                .Step
                .QUOTE
            )

            workflow.stage = (
                BespokeOrderWorkflow
                .Stage
                .QUOTE
            )

            workflow.save(
                update_fields=[
                    "current_step",
                    "stage",
                    "updated_at",
                ]
            )

        messages.warning(
            request,
            (
                "The customer must accept the quotation "
                "before this job can progress to Approval "
                "& Payment."
            ),
        )

        return redirect(
            "bespoke_job_wizard",
            reference_number=(
                order.reference_number
            ),
            step=4,
        )

    # =====================================================
    # PAYMENT STATE / HARD PRODUCTION GATE
    #
    # Quote acceptance unlocks Step 5.
    # Confirmed payment unlocks Step 6.
    # =====================================================

    approval_payment = (
        BespokeApprovalPayment.objects
        .select_related(
            "quote"
        )
        .filter(
            workflow=workflow
        )
        .first()
    )

    if (
        step > 5
        and not is_closed
        and (
            not approval_payment
            or not approval_payment.can_start_production
        )
    ):

        if workflow.current_step > 5:

            workflow.current_step = (
                BespokeOrderWorkflow
                .Step
                .APPROVAL
            )

            workflow.stage = (
                BespokeOrderWorkflow
                .Stage
                .PAYMENT
            )

            workflow.save(
                update_fields=[
                    "current_step",
                    "stage",
                    "updated_at",
                ]
            )

        messages.warning(
            request,
            (
                "Confirmed payment is required before "
                "this job can progress to Production."
            ),
        )

        return redirect(
            "bespoke_job_wizard",
            reference_number=(
                order.reference_number
            ),
            step=5,
        )


    # =====================================================
    # STOP GENERAL FORWARD SKIPPING
    # =====================================================

    if (
        step > workflow.current_step
        and workflow.stage
        not in CLOSED_STAGES
    ):

        return redirect(
            "bespoke_job_wizard",
            reference_number=(
                order.reference_number
            ),
            step=workflow.current_step,
        )

    # =====================================================
    # GENERIC FORMS
    # =====================================================

    workflow_form = (
        BespokeJobWorkflowForm(
            instance=workflow
        )
    )

    email_form = CustomerEmailForm(
        initial={
            "subject": (
                "Update on your K9 bespoke order "
                f"{order.reference_number}"
            ),

            "message": (
                default_customer_email_message(
                    order
                )
            ),
        }
    )

    whatsapp_form = (
        WhatsAppMessageForm(
            initial={
                "message": (
                    default_whatsapp_message(
                        order
                    )
                ),
            }
        )
    )

    communication_log_form = (
        CommunicationLogForm()
    )

    whatsapp_url = ""

    whatsapp_prepared_message = ""

    # =====================================================
    # STEP 3 FORMS
    # =====================================================

    master_design_form = None

    design_version_form = None

    design_version_email_form = None

    selected_design_version = None

    # Legacy forms remain available temporarily until
    # the template is replaced in the next step.

    design_form = None

    design_email_form = None

    if step == 3:

        master_design_form = (
            BespokeDesignMasterForm(
                instance=design
            )
        )

        # -----------------------------------------------------
        # PREPARE NEXT DESIGN VERSION
        #
        # Carry the previous design description forward.
        # If the customer requested changes, automatically
        # include those in the next revision form.
        # -----------------------------------------------------

        next_version_initial = (
            build_next_design_version_initial(
                design
            )
        )

        design_version_form = (
            BespokeDesignVersionForm(
                initial=next_version_initial
            )
        )

        design_version_email_form = (
            DesignVersionEmailForm()
        )

        design_form = (
            BespokeDesignForm(
                instance=design
            )
        )

        design_email_form = (
            DesignCustomerEmailForm(
                initial={
                    "subject": (
                        "Design update for your "
                        "K9 bespoke order "
                        f"{order.reference_number}"
                    ),
                }
            )
        )

    # =====================================================
    # STEP 4 FORMS
    # =====================================================

    quote_form = None
    quote_line_formset = None
    quote_editor = None

    if step == 4:

        quote_editor = (
            workflow.quotes
            .filter(
                status=BespokeQuote.Status.DRAFT
            )
            .order_by("-version")
            .first()
        )

        if quote_editor:

            quote_form = (
                BespokeQuoteForm(
                    instance=quote_editor
                )
            )

            quote_line_formset = (
                BespokeQuoteLineFormSet(
                    instance=quote_editor,
                    prefix="quote_lines",
                )
            )

        else:

            quote_form = (
                BespokeQuoteForm()
            )

            quote_line_formset = (
                BespokeQuoteLineFormSet(
                    prefix="quote_lines",
                )
            )

    # =====================================================
    # HANDLE POST
    # =====================================================

    if request.method == "POST":

        action = request.POST.get(
            "action",
            "save",
        )

        # -------------------------------------------------
        # CLOSED JOBS
        # -------------------------------------------------

        if is_closed:

            messages.warning(
                request,
                (
                    "This job is closed and "
                    "can no longer be edited."
                ),
            )

            return redirect(
                "bespoke_job_wizard",
                reference_number=(
                    order.reference_number
                ),
                step=step,
            )

        # =================================================
        # STEP 2 - SEND EMAIL
        # =================================================

        if (
            step == 2
            and action == "send_email"
        ):

            email_form = CustomerEmailForm(
                request.POST,
                request.FILES,
            )

            if email_form.is_valid():

                subject = (
                    email_form
                    .cleaned_data[
                        "subject"
                    ]
                    .strip()
                )

                email_message = (
                    email_form
                    .cleaned_data[
                        "message"
                    ]
                    .strip()
                )

                attachment = (
                    email_form
                    .cleaned_data
                    .get(
                        "attachment"
                    )
                )

                attachment_names = []

                if attachment:

                    attachment_names.append(
                        attachment.name
                    )

                if (
                    order.reference_number.lower()
                    not in subject.lower()
                ):

                    subject = (
                        f"{order.reference_number} | "
                        f"{subject}"
                    )

                from_email = (
                    settings.DEFAULT_FROM_EMAIL
                )

                now = timezone.now()

                (
                    plain_content,
                    html_content,
                ) = build_k9_email_content(
                    order,
                    email_message,
                    "Customer Contact",
                )

                try:

                    message = (
                        EmailMultiAlternatives(
                            subject=subject,
                            body=plain_content,
                            from_email=from_email,
                            to=[
                                order.customer_email
                            ],
                        )
                    )

                    message.attach_alternative(
                        html_content,
                        "text/html",
                    )

                    attach_uploaded_file(
                        message,
                        attachment,
                    )

                    message.send(
                        fail_silently=False
                    )

                except Exception:

                    OrderCommunication.objects.create(

                        order=order,

                        channel=(
                            OrderCommunication
                            .Channel
                            .EMAIL
                        ),

                        context=(
                            OrderCommunication
                            .Context
                            .CONTACT
                        ),

                        direction=(
                            OrderCommunication
                            .Direction
                            .OUTGOING
                        ),

                        status=(
                            OrderCommunication
                            .Status
                            .FAILED
                        ),

                        subject=subject,

                        from_address=(
                            from_email
                        ),

                        to_address=(
                            order.customer_email
                        ),

                        summary=(
                            "Email failed to send."
                        ),

                        content=(
                            email_message
                        ),

                        has_attachment=bool(
                            attachment_names
                        ),

                        attachment_names=(
                            attachment_names
                        ),

                        attachment_notes=(
                            (
                                "Attachment was selected "
                                "for this failed email attempt."
                            )
                            if attachment_names
                            else ""
                        ),

                        logged_by=(
                            request.user
                        ),

                        occurred_at=now,
                    )

                    log_job_activity(
                        order=order,
                        user=request.user,
                        message=(
                            "Attempted to email the customer "
                            "from Customer Contact, but the "
                            "email failed to send."
                        ),
                    )

                    messages.error(
                        request,
                        (
                            "The email could not be sent. "
                            "The failed attempt has been "
                            "recorded."
                        ),
                    )

                else:

                    OrderCommunication.objects.create(

                        order=order,

                        channel=(
                            OrderCommunication
                            .Channel
                            .EMAIL
                        ),

                        context=(
                            OrderCommunication
                            .Context
                            .CONTACT
                        ),

                        direction=(
                            OrderCommunication
                            .Direction
                            .OUTGOING
                        ),

                        status=(
                            OrderCommunication
                            .Status
                            .SENT
                        ),

                        subject=subject,

                        from_address=(
                            from_email
                        ),

                        to_address=(
                            order.customer_email
                        ),

                        summary=subject,

                        content=(
                            email_message
                        ),

                        has_attachment=bool(
                            attachment_names
                        ),

                        attachment_names=(
                            attachment_names
                        ),

                        attachment_notes=(
                            (
                                "Attachment sent with "
                                "customer email."
                            )
                            if attachment_names
                            else ""
                        ),

                        logged_by=(
                            request.user
                        ),

                        occurred_at=now,
                    )

                    touch_workflow(
                        workflow,
                        request.user,
                    )

                    ensure_order_processing(
                        order,
                        request.user,
                    )

                    log_job_activity(
                        order=order,
                        user=request.user,
                        message=(
                            "Customer email sent from "
                            "Customer Contact.\n"
                            f"To: {order.customer_email}\n"
                            f"Subject: {subject}"
                        ),
                    )

                    messages.success(
                        request,
                        (
                            "Email sent successfully and "
                            "added to the job communications."
                        ),
                    )

                    return redirect(
                        "bespoke_job_wizard",
                        reference_number=(
                            order.reference_number
                        ),
                        step=2,
                    )

        # =================================================
        # STEP 2 - PREPARE WHATSAPP
        # =================================================

        elif (
            step == 2
            and action
            == "prepare_whatsapp"
        ):

            whatsapp_form = (
                WhatsAppMessageForm(
                    request.POST
                )
            )

            if whatsapp_form.is_valid():

                whatsapp_prepared_message = (
                    whatsapp_form
                    .cleaned_data[
                        "message"
                    ]
                    .strip()
                )

                whatsapp_url = (
                    build_whatsapp_url(
                        order.phone_number,
                        whatsapp_prepared_message,
                    )
                )

                if not whatsapp_url:

                    whatsapp_form.add_error(
                        None,
                        (
                            "This customer does not have "
                            "a valid telephone number "
                            "available for WhatsApp."
                        ),
                    )

        # =================================================
        # STEP 2 - CONFIRM WHATSAPP SENT
        # =================================================

        elif (
            step == 2
            and action
            == "log_whatsapp_sent"
        ):

            whatsapp_message = (
                request.POST.get(
                    "whatsapp_message",
                    "",
                ).strip()
            )

            if not whatsapp_message:

                messages.warning(
                    request,
                    (
                        "There is no WhatsApp "
                        "message to record."
                    ),
                )

            else:

                now = timezone.now()

                OrderCommunication.objects.create(

                    order=order,

                    channel=(
                        OrderCommunication
                        .Channel
                        .WHATSAPP
                    ),

                    context=(
                        OrderCommunication
                        .Context
                        .CONTACT
                    ),

                    direction=(
                        OrderCommunication
                        .Direction
                        .OUTGOING
                    ),

                    status=(
                        OrderCommunication
                        .Status
                        .SENT
                    ),

                    from_address="K9",

                    to_address=(
                        order.phone_number
                        or ""
                    ),

                    summary=(
                        "WhatsApp message sent "
                        "to customer."
                    ),

                    content=(
                        whatsapp_message
                    ),

                    logged_by=(
                        request.user
                    ),

                    occurred_at=now,
                )

                touch_workflow(
                    workflow,
                    request.user,
                )

                ensure_order_processing(
                    order,
                    request.user,
                )

                log_job_activity(
                    order=order,
                    user=request.user,
                    message=(
                        "Outgoing WhatsApp message "
                        "recorded from Customer Contact."
                    ),
                )

                messages.success(
                    request,
                    (
                        "WhatsApp message recorded "
                        "in the job communications."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=2,
                )

        # =================================================
        # STEP 2 - MANUAL CONTACT
        # =================================================

        elif (
            step == 2
            and action
            == "log_communication"
        ):

            communication_log_form = (
                CommunicationLogForm(
                    request.POST
                )
            )

            if communication_log_form.is_valid():

                channel = (
                    communication_log_form
                    .cleaned_data[
                        "channel"
                    ]
                )

                direction = (
                    communication_log_form
                    .cleaned_data[
                        "direction"
                    ]
                )

                summary = (
                    communication_log_form
                    .cleaned_data[
                        "summary"
                    ]
                    .strip()
                )

                content = (
                    communication_log_form
                    .cleaned_data[
                        "content"
                    ]
                    .strip()
                )

                occurred_at = (
                    communication_log_form
                    .cleaned_data[
                        "occurred_at"
                    ]
                    or timezone.now()
                )

                if (
                    direction
                    == (
                        OrderCommunication
                        .Direction
                        .INCOMING
                    )
                ):

                    status = (
                        OrderCommunication
                        .Status
                        .RECEIVED
                    )

                    from_address = (
                        order.phone_number
                        or order.customer_email
                    )

                    to_address = "K9"

                else:

                    status = (
                        OrderCommunication
                        .Status
                        .LOGGED
                    )

                    from_address = "K9"

                    to_address = (
                        order.phone_number
                        or order.customer_email
                    )

                communication = (
                    OrderCommunication.objects.create(

                        order=order,

                        channel=channel,

                        context=(
                            OrderCommunication
                            .Context
                            .CONTACT
                        ),

                        direction=direction,

                        status=status,

                        from_address=(
                            from_address
                        ),

                        to_address=(
                            to_address
                        ),

                        summary=summary,

                        content=content,

                        logged_by=(
                            request.user
                        ),

                        occurred_at=(
                            occurred_at
                        ),
                    )
                )

                touch_workflow(
                    workflow,
                    request.user,
                )

                ensure_order_processing(
                    order,
                    request.user,
                )

                log_job_activity(
                    order=order,
                    user=request.user,
                    message=(
                        "Customer communication logged.\n"
                        f"Method: "
                        f"{communication.get_channel_display()}\n"
                        f"Direction: "
                        f"{communication.get_direction_display()}\n"
                        f"Summary: {summary}"
                    ),
                )

                messages.success(
                    request,
                    (
                        "Communication added "
                        "to the job history."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=2,
                )

        # =================================================
        # STEP 3 - SAVE MASTER DESIGN BRIEF
        # =================================================

        elif (
            step == 3
            and action
            == "save_design_master"
        ):

            master_design_form = (
                BespokeDesignMasterForm(
                    request.POST,
                    instance=design,
                )
            )

            if master_design_form.is_valid():

                old_specification = (
                    design.specification
                )

                old_internal_notes = (
                    design.internal_notes
                )

                design = (
                    master_design_form.save(
                        commit=False
                    )
                )

                design.last_updated_by = (
                    request.user
                )

                design.save()

                touch_workflow(
                    workflow,
                    request.user,
                )

                ensure_order_processing(
                    order,
                    request.user,
                )

                if (
                    old_specification
                    != design.specification
                ):

                    log_job_activity(
                        order=order,
                        user=request.user,
                        message=(
                            "Master design specification "
                            "updated."
                        ),
                    )

                if (
                    old_internal_notes
                    != design.internal_notes
                ):

                    log_job_activity(
                        order=order,
                        user=request.user,
                        message=(
                            "Master internal design notes "
                            "updated."
                        ),
                    )

                messages.success(
                    request,
                    (
                        "Master design brief saved."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=3,
                )

        # =================================================
        # STEP 3 - CREATE DESIGN VERSION
        # =================================================

        elif (
            step == 3
            and action
            == "create_design_version"
        ):

            design_version_form = (
                BespokeDesignVersionForm(
                    request.POST
                )
            )

            if design_version_form.is_valid():

                with transaction.atomic():

                    locked_design = (
                        BespokeDesign.objects
                        .select_for_update()
                        .get(
                            pk=design.pk
                        )
                    )

                    highest_version = (
                        locked_design
                        .versions
                        .aggregate(
                            maximum=Max(
                                "version"
                            )
                        )
                        .get(
                            "maximum"
                        )
                        or 0
                    )

                    new_version = (
                        design_version_form
                        .save(
                            commit=False
                        )
                    )

                    new_version.design = (
                        locked_design
                    )

                    new_version.version = (
                        highest_version
                        + 1
                    )

                    new_version.status = (
                        BespokeDesignVersion
                        .Status
                        .DRAFT
                    )

                    new_version.created_by = (
                        request.user
                    )

                    new_version.save()

                touch_workflow(
                    workflow,
                    request.user,
                )

                ensure_order_processing(
                    order,
                    request.user,
                )

                log_job_activity(
                    order=order,
                    user=request.user,
                    message=(
                        f"{new_version.version_label} "
                        "created as a draft."
                    ),
                )

                messages.success(
                    request,
                    (
                        f"{new_version.version_label} "
                        "created successfully."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=3,
                )

        # =================================================
        # STEP 3 - SAVE EXISTING DRAFT VERSION
        # =================================================

        elif (
            step == 3
            and action
            == "save_design_version"
        ):

            version_id = request.POST.get(
                "design_version_id"
            )

            selected_design_version = (
                get_object_or_404(
                    BespokeDesignVersion,
                    pk=version_id,
                    design=design,
                )
            )

            if (
                selected_design_version.status
                != (
                    BespokeDesignVersion
                    .Status
                    .DRAFT
                )
            ):

                messages.warning(
                    request,
                    (
                        "Only draft design versions "
                        "can be edited."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=3,
                )

            design_version_form = (
                BespokeDesignVersionForm(
                    request.POST,
                    instance=(
                        selected_design_version
                    ),
                )
            )

            if design_version_form.is_valid():

                design_version_form.save()

                touch_workflow(
                    workflow,
                    request.user,
                )

                log_job_activity(
                    order=order,
                    user=request.user,
                    message=(
                        f"{selected_design_version.version_label} "
                        "draft updated."
                    ),
                )

                messages.success(
                    request,
                    (
                        f"{selected_design_version.version_label} "
                        "saved."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=3,
                )

        # =================================================
        # STEP 3 - SEND DESIGN VERSION EMAIL
        # =================================================

        elif (
            step == 3
            and action
            == "send_design_version_email"
        ):

            version_id = request.POST.get(
                "design_version_id"
            )

            selected_design_version = (
                get_object_or_404(
                    BespokeDesignVersion,
                    pk=version_id,
                    design=design,
                )
            )

            allowed_statuses = {
                BespokeDesignVersion
                .Status
                .DRAFT,

                BespokeDesignVersion
                .Status
                .SENT,
            }

            if (
                selected_design_version.status
                not in allowed_statuses
            ):

                messages.warning(
                    request,
                    (
                        "This design version can no "
                        "longer be sent for review."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=3,
                )

            design_version_email_form = (
                DesignVersionEmailForm(
                    request.POST,
                    request.FILES,
                )
            )

            if (
                design_version_email_form
                .is_valid()
            ):

                subject = (
                    design_version_email_form
                    .cleaned_data[
                        "subject"
                    ]
                    .strip()
                )

                email_message = (
                    design_version_email_form
                    .cleaned_data[
                        "message"
                    ]
                    .strip()
                )

                attachment = (
                    design_version_email_form
                    .cleaned_data
                    .get(
                        "attachment"
                    )
                )

                if (
                    order.reference_number.lower()
                    not in subject.lower()
                ):

                    subject = (
                        f"{order.reference_number} | "
                        f"{subject}"
                    )

                attachment_names = []

                file_metadata = (
                    calculate_file_metadata(
                        attachment
                    )
                )

                if attachment:

                    attachment_names.append(
                        attachment.name
                    )

                review_url = (
                    build_customer_design_review_url(
                        request,
                        selected_design_version,
                    )
                )

                from_email = (
                    settings.DEFAULT_FROM_EMAIL
                )

                now = timezone.now()

                (
                    plain_content,
                    html_content,
                ) = build_k9_email_content(

                    order=order,

                    staff_message=(
                        email_message
                    ),

                    section_title=(
                        selected_design_version
                        .version_label
                    ),

                    action_url=(
                        review_url
                    ),

                    action_label=(
                        "Review This Design"
                    ),
                )

                try:

                    message = (
                        EmailMultiAlternatives(
                            subject=subject,
                            body=plain_content,
                            from_email=from_email,
                            to=[
                                order.customer_email
                            ],
                        )
                    )

                    message.attach_alternative(
                        html_content,
                        "text/html",
                    )

                    attach_uploaded_file(
                        message,
                        attachment,
                    )

                    message.send(
                        fail_silently=False
                    )

                except Exception:

                    OrderCommunication.objects.create(

                        order=order,

                        design_version=(
                            selected_design_version
                        ),

                        channel=(
                            OrderCommunication
                            .Channel
                            .EMAIL
                        ),

                        context=(
                            OrderCommunication
                            .Context
                            .DESIGN
                        ),

                        direction=(
                            OrderCommunication
                            .Direction
                            .OUTGOING
                        ),

                        status=(
                            OrderCommunication
                            .Status
                            .FAILED
                        ),

                        subject=subject,

                        from_address=(
                            from_email
                        ),

                        to_address=(
                            order.customer_email
                        ),

                        summary=(
                            f"{selected_design_version.version_label} "
                            "email failed to send."
                        ),

                        content=(
                            email_message
                        ),

                        has_attachment=bool(
                            attachment_names
                        ),

                        attachment_names=(
                            attachment_names
                        ),

                        attachment_notes=(
                            (
                                "Design attachment was selected "
                                "for this failed email attempt."
                            )
                            if attachment_names
                            else ""
                        ),

                        logged_by=(
                            request.user
                        ),

                        occurred_at=now,
                    )

                    log_job_activity(
                        order=order,
                        user=request.user,
                        message=(
                            f"Attempted to send "
                            f"{selected_design_version.version_label} "
                            "to the customer, but the email failed."
                        ),
                    )

                    messages.error(
                        request,
                        (
                            "The design email could not be "
                            "sent. The failed attempt has "
                            "been recorded."
                        ),
                    )

                else:

                    with transaction.atomic():

                        supersede_other_active_designs(
                            selected_design_version
                        )

                        selected_design_version.status = (
                            BespokeDesignVersion
                            .Status
                            .SENT
                        )

                        selected_design_version.sent_at = (
                            now
                        )

                        selected_design_version.sent_by = (
                            request.user
                        )

                        if attachment:

                            selected_design_version.file_name = (
                                file_metadata[
                                    "file_name"
                                ]
                            )

                            selected_design_version.file_content_type = (
                                file_metadata[
                                    "file_content_type"
                                ]
                            )

                            selected_design_version.file_size = (
                                file_metadata[
                                    "file_size"
                                ]
                            )

                            selected_design_version.file_sha256 = (
                                file_metadata[
                                    "file_sha256"
                                ]
                            )

                        selected_design_version.save()

                        OrderCommunication.objects.create(

                            order=order,

                            design_version=(
                                selected_design_version
                            ),

                            channel=(
                                OrderCommunication
                                .Channel
                                .EMAIL
                            ),

                            context=(
                                OrderCommunication
                                .Context
                                .DESIGN
                            ),

                            direction=(
                                OrderCommunication
                                .Direction
                                .OUTGOING
                            ),

                            status=(
                                OrderCommunication
                                .Status
                                .SENT
                            ),

                            subject=subject,

                            from_address=(
                                from_email
                            ),

                            to_address=(
                                order.customer_email
                            ),

                            summary=(
                                f"{selected_design_version.version_label} "
                                "sent to customer for review."
                            ),

                            content=(
                                email_message
                            ),

                            has_attachment=bool(
                                attachment_names
                            ),

                            attachment_names=(
                                attachment_names
                            ),

                            attachment_notes=(
                                (
                                    "Design attachment sent "
                                    "with customer review email."
                                )
                                if attachment_names
                                else ""
                            ),

                            logged_by=(
                                request.user
                            ),

                            occurred_at=now,
                        )

                        workflow.stage = (
                            BespokeOrderWorkflow
                            .Stage
                            .DESIGN
                        )

                        workflow.customer_waiting = (
                            True
                        )

                        workflow.customer_waiting_since = (
                            now
                        )

                        workflow.last_worked_by = (
                            request.user
                        )

                        workflow.last_worked_at = (
                            now
                        )

                        if workflow.started_at is None:

                            workflow.started_at = (
                                now
                            )

                        workflow.save()

                    ensure_order_processing(
                        order,
                        request.user,
                    )

                    attachment_text = ""

                    if attachment_names:

                        attachment_text = (
                            "\nAttachment: "
                            + ", ".join(
                                attachment_names
                            )
                        )

                    fingerprint_text = ""

                    if (
                        selected_design_version
                        .file_sha256
                    ):

                        fingerprint_text = (
                            "\nFile fingerprint: "
                            f"{selected_design_version.file_sha256}"
                        )

                    log_job_activity(
                        order=order,
                        user=request.user,
                        message=(
                            f"{selected_design_version.version_label} "
                            "sent to the customer for review.\n"
                            f"To: {order.customer_email}"
                            f"{attachment_text}"
                            f"{fingerprint_text}"
                        ),
                    )

                    messages.success(
                        request,
                        (
                            f"{selected_design_version.version_label} "
                            "sent to the customer for review."
                        ),
                    )

                    return redirect(
                        "bespoke_job_wizard",
                        reference_number=(
                            order.reference_number
                        ),
                        step=3,
                    )

        # =================================================
        # STEP 4 - CREATE QUOTE
        # =================================================

        elif (
            step == 4
            and action == "create_quote"
        ):

            highest_version = (
                workflow.quotes
                .aggregate(maximum=Max("version"))
                .get("maximum")
                or 0
            )

            new_quote = BespokeQuote(
                workflow=workflow,
                version=highest_version + 1,
                status=BespokeQuote.Status.DRAFT,
                created_by=request.user,
            )

            quote_form = BespokeQuoteForm(
                request.POST,
                instance=new_quote,
            )

            quote_line_formset = (
                BespokeQuoteLineFormSet(
                    request.POST,
                    instance=new_quote,
                    prefix="quote_lines",
                )
            )

            if (
                quote_form.is_valid()
                and quote_line_formset.is_valid()
            ):

                with transaction.atomic():

                    new_quote = quote_form.save(
                        commit=False
                    )

                    new_quote.workflow = workflow
                    new_quote.version = (
                        highest_version + 1
                    )
                    new_quote.status = (
                        BespokeQuote.Status.DRAFT
                    )
                    new_quote.created_by = (
                        request.user
                    )
                    new_quote.save()

                    quote_line_formset.instance = (
                        new_quote
                    )
                    quote_line_formset.save()

                    new_quote.recalculate_totals()
                    new_quote.refresh_from_db()

                touch_workflow(
                    workflow,
                    request.user,
                )

                ensure_order_processing(
                    order,
                    request.user,
                )

                log_job_activity(
                    order=order,
                    user=request.user,
                    message=(
                        f"Quote V{new_quote.version} created "
                        f"as a draft. Total: £{new_quote.total:.2f}."
                    ),
                )

                messages.success(
                    request,
                    (
                        f"Quote V{new_quote.version} "
                        "created successfully."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=4,
                )

        # =================================================
        # STEP 4 - SAVE DRAFT QUOTE
        # =================================================

        elif (
            step == 4
            and action == "save_quote"
        ):

            quote_id = request.POST.get(
                "quote_id"
            )

            selected_quote = get_object_or_404(
                BespokeQuote,
                pk=quote_id,
                workflow=workflow,
            )

            if (
                selected_quote.status
                != BespokeQuote.Status.DRAFT
            ):

                messages.warning(
                    request,
                    "Only draft quotations can be edited.",
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=4,
                )

            quote_form = BespokeQuoteForm(
                request.POST,
                instance=selected_quote,
            )

            quote_line_formset = (
                BespokeQuoteLineFormSet(
                    request.POST,
                    instance=selected_quote,
                    prefix="quote_lines",
                )
            )

            if (
                quote_form.is_valid()
                and quote_line_formset.is_valid()
            ):

                with transaction.atomic():

                    selected_quote = (
                        quote_form.save()
                    )

                    quote_line_formset.save()

                    selected_quote.recalculate_totals()
                    selected_quote.refresh_from_db()

                touch_workflow(
                    workflow,
                    request.user,
                )

                log_job_activity(
                    order=order,
                    user=request.user,
                    message=(
                        f"Quote V{selected_quote.version} "
                        f"draft updated. Total: "
                        f"£{selected_quote.total:.2f}."
                    ),
                )

                messages.success(
                    request,
                    (
                        f"Quote V{selected_quote.version} "
                        "saved."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=4,
                )

        # =================================================
        # STEP 4 - CREATE REVISION
        # =================================================

        elif (
            step == 4
            and action == "create_quote_revision"
        ):

            quote_id = request.POST.get(
                "quote_id"
            )

            source_quote = get_object_or_404(
                BespokeQuote.objects.prefetch_related(
                    "lines"
                ),
                pk=quote_id,
                workflow=workflow,
            )

            existing_draft = (
                workflow.quotes
                .filter(
                    status=BespokeQuote.Status.DRAFT
                )
                .exclude(pk=source_quote.pk)
                .first()
            )

            if existing_draft:

                messages.warning(
                    request,
                    (
                        f"Quote V{existing_draft.version} is already "
                        "an editable draft. Finish or send that "
                        "revision before creating another."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=4,
                )

            new_quote = clone_quote_revision(
                source_quote,
                request.user,
            )

            touch_workflow(
                workflow,
                request.user,
            )

            log_job_activity(
                order=order,
                user=request.user,
                message=(
                    f"Quote V{new_quote.version} created from "
                    f"Quote V{source_quote.version} for revision."
                ),
            )

            messages.success(
                request,
                (
                    f"Quote V{new_quote.version} created. "
                    "You can now adjust the pricing."
                ),
            )

            return redirect(
                "bespoke_job_wizard",
                reference_number=(
                    order.reference_number
                ),
                step=4,
            )

        # =================================================
        # STEP 4 - SEND QUOTE EMAIL
        # =================================================

        elif (
            step == 4
            and action == "send_quote_email"
        ):

            quote_id = request.POST.get(
                "quote_id"
            )

            selected_quote = get_object_or_404(
                BespokeQuote.objects.prefetch_related(
                    "lines"
                ),
                pk=quote_id,
                workflow=workflow,
            )

            if selected_quote.status not in {
                BespokeQuote.Status.DRAFT,
                BespokeQuote.Status.SENT,
            }:

                messages.warning(
                    request,
                    (
                        "This quotation can no longer be "
                        "sent to the customer."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=4,
                )

            selected_quote.recalculate_totals()
            selected_quote.refresh_from_db()

            if not selected_quote.lines.exists():

                messages.error(
                    request,
                    (
                        "Add at least one line item before "
                        "sending this quotation."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=4,
                )

            subject = (
                request.POST.get(
                    "subject",
                    "",
                ).strip()
                or (
                    f"Quote V{selected_quote.version} | "
                    f"K9 bespoke order {order.reference_number}"
                )
            )

            staff_message = (
                request.POST.get(
                    "message",
                    "",
                ).strip()
                or (
                    f"Hi {customer_first_name(order)},\n\n"
                    "We've prepared your bespoke quotation."
                )
            )

            if (
                order.reference_number.lower()
                not in subject.lower()
            ):

                subject = (
                    f"{order.reference_number} | {subject}"
                )

            email_message = format_quote_email_message(
                order,
                selected_quote,
                staff_message,
            )

            approval_payment, _ = (
                BespokeApprovalPayment.objects
                .get_or_create(
                    workflow=workflow
                )
            )

            review_url = (
                build_customer_quote_review_url(
                    request,
                    approval_payment,
                )
            )

            from_email = settings.DEFAULT_FROM_EMAIL
            now = timezone.now()

            (
                plain_content,
                html_content,
            ) = build_k9_email_content(
                order=order,
                staff_message=email_message,
                section_title=(
                    f"Quote V{selected_quote.version}"
                ),
                action_url=review_url,
                action_label="Approve Quote & Pay",
            )

            pdf_filename = (
                f"K9-{order.reference_number}-"
                f"Quote-V{selected_quote.version}.pdf"
            )

            try:

                pdf_response = bespoke_quote_pdf(
                    request,
                    selected_quote.pk,
                )

                if (
                    pdf_response.status_code != 200
                    or pdf_response.get(
                        "Content-Type",
                        ""
                    ) != "application/pdf"
                ):
                    raise RuntimeError(
                        "Quote PDF generation failed."
                    )

                message = EmailMultiAlternatives(
                    subject=subject,
                    body=plain_content,
                    from_email=from_email,
                    to=[order.customer_email],
                )

                message.attach_alternative(
                    html_content,
                    "text/html",
                )

                message.attach(
                    pdf_filename,
                    pdf_response.content,
                    "application/pdf",
                )

                message.send(
                    fail_silently=False
                )

            except Exception:

                OrderCommunication.objects.create(
                    order=order,
                    channel=(
                        OrderCommunication.Channel.EMAIL
                    ),
                    context=(
                        OrderCommunication.Context.QUOTE
                    ),
                    direction=(
                        OrderCommunication.Direction.OUTGOING
                    ),
                    status=(
                        OrderCommunication.Status.FAILED
                    ),
                    subject=subject,
                    from_address=from_email,
                    to_address=order.customer_email,
                    summary=(
                        f"Quote V{selected_quote.version} "
                        "email failed to send."
                    ),
                    content=email_message,
                    has_attachment=True,
                    attachment_names=[
                        pdf_filename
                    ],
                    attachment_notes=(
                        "The generated quote PDF was prepared "
                        "for this email attempt."
                    ),
                    thread_reference=(
                        f"quote:{selected_quote.pk}"
                    ),
                    logged_by=request.user,
                    occurred_at=now,
                )

                log_job_activity(
                    order=order,
                    user=request.user,
                    message=(
                        f"Attempted to send Quote V"
                        f"{selected_quote.version}, but the "
                        "email failed."
                    ),
                )

                messages.error(
                    request,
                    (
                        "The quote email could not be sent. "
                        "The failed attempt has been recorded."
                    ),
                )

            else:

                with transaction.atomic():

                    supersede_other_active_quotes(
                        selected_quote
                    )

                    selected_quote.status = (
                        BespokeQuote.Status.SENT
                    )
                    selected_quote.sent_at = now
                    selected_quote.save(
                        update_fields=[
                            "status",
                            "sent_at",
                            "updated_at",
                        ]
                    )

                    approval_payment.mark_approval_requested(
                        selected_quote
                    )

                    # A new/revised quote starts a fresh approval
                    # cycle. Clear any stale approval/payment data
                    # left from an earlier version.
                    approval_payment.approved_name = ""
                    approval_payment.approved_email = ""
                    approval_payment.approval_notes = ""
                    approval_payment.payment_provider = ""
                    approval_payment.payment_reference = ""
                    approval_payment.checkout_reference = ""
                    approval_payment.payment_metadata = {}

                    approval_payment.save(
                        update_fields=[
                            "approved_name",
                            "approved_email",
                            "approval_notes",
                            "payment_provider",
                            "payment_reference",
                            "checkout_reference",
                            "payment_metadata",
                            "updated_at",
                        ]
                    )

                    OrderCommunication.objects.create(
                        order=order,
                        channel=(
                            OrderCommunication.Channel.EMAIL
                        ),
                        context=(
                            OrderCommunication.Context.QUOTE
                        ),
                        direction=(
                            OrderCommunication.Direction.OUTGOING
                        ),
                        status=(
                            OrderCommunication.Status.SENT
                        ),
                        subject=subject,
                        from_address=from_email,
                        to_address=order.customer_email,
                        summary=(
                            f"Quote V{selected_quote.version} "
                            f"sent to customer. Total: "
                            f"£{selected_quote.total:.2f}."
                        ),
                        content=email_message,
                        has_attachment=True,
                        attachment_names=[
                            pdf_filename
                        ],
                        attachment_notes=(
                            "Generated Quote PDF attached to "
                            "the customer email."
                        ),
                        thread_reference=(
                            f"quote:{selected_quote.pk}"
                        ),
                        logged_by=request.user,
                        occurred_at=now,
                    )

                    workflow.current_step = (
                        BespokeOrderWorkflow.Step.QUOTE
                    )
                    workflow.stage = (
                        BespokeOrderWorkflow.Stage.QUOTE
                    )
                    workflow.customer_waiting = True
                    workflow.customer_waiting_since = now
                    workflow.last_worked_by = request.user
                    workflow.last_worked_at = now

                    if workflow.started_at is None:
                        workflow.started_at = now

                    workflow.save()

                ensure_order_processing(
                    order,
                    request.user,
                )

                log_job_activity(
                    order=order,
                    user=request.user,
                    message=(
                        f"Quote V{selected_quote.version} sent "
                        f"to {order.customer_email}. Total: "
                        f"£{selected_quote.total:.2f}."
                    ),
                )

                messages.success(
                    request,
                    (
                        f"Quote V{selected_quote.version} "
                        "sent successfully."
                    ),
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=4,
                )

        # =================================================
        # STEP 8 - COMPLETE JOB
        # =================================================

        elif (
            action == "complete_job"
            and step == 8
        ):

            with transaction.atomic():

                workflow.current_step = 8

                workflow.last_worked_by = (
                    request.user
                )

                workflow.last_worked_at = (
                    timezone.now()
                )

                workflow.save()

                order.status = "sent"

                order.save()

                sync_bespoke_workflow_with_order(
                    order,
                    request.user,
                )

                log_job_activity(
                    order=order,
                    user=request.user,
                    message=(
                        "Bespoke job closed through "
                        "the staff workflow wizard."
                    ),
                )

            messages.success(
                request,
                (
                    f"{order.reference_number} "
                    "has been completed."
                ),
            )

            if request.user.is_superuser:

                return redirect(
                    "bespoke_jobs_dashboard"
                )

            return redirect(
                "staff_jobs_dashboard"
            )

        # =================================================
        # NORMAL WORKFLOW SAVE
        # =================================================

        elif action in {
            "save",
            "save_exit",
            "save_continue",
        }:

            # ---------------------------------------------
            # DESIGN GATE
            # ---------------------------------------------

            if (
                step == 3
                and action
                == "save_continue"
            ):

                accepted_design_version = (
                    design.accepted_version
                    if design
                    else None
                )

                if not accepted_design_version:

                    messages.warning(
                        request,
                        (
                            "The customer must accept a "
                            "design version before this "
                            "job can continue to Pricing "
                            "& Quote."
                        ),
                    )

                    return redirect(
                        "bespoke_job_wizard",
                        reference_number=(
                            order.reference_number
                        ),
                        step=3,
                    )

            # ---------------------------------------------
            # QUOTE ACCEPTANCE GATE
            # ---------------------------------------------

            if (
                step == 4
                and action == "save_continue"
            ):

                accepted_quote = (
                    workflow.quotes
                    .filter(
                        status=BespokeQuote.Status.ACCEPTED
                    )
                    .order_by("-version")
                    .first()
                )

                if not accepted_quote:

                    messages.warning(
                        request,
                        (
                            "The customer must accept the quotation "
                            "before the workflow can continue to "
                            "Approval & Payment."
                        ),
                    )

                    return redirect(
                        "bespoke_job_wizard",
                        reference_number=(
                            order.reference_number
                        ),
                        step=4,
                    )

            # ---------------------------------------------
            # PAYMENT GATE
            # ---------------------------------------------

            if (
                step == 5
                and action == "save_continue"
            ):

                current_payment = (
                    BespokeApprovalPayment.objects
                    .filter(
                        workflow=workflow
                    )
                    .first()
                )

                if (
                    not current_payment
                    or not current_payment.can_start_production
                ):

                    messages.warning(
                        request,
                        (
                            "Confirmed payment is required "
                            "before production can begin."
                        ),
                    )

                    return redirect(
                        "bespoke_job_wizard",
                        reference_number=(
                            order.reference_number
                        ),
                        step=5,
                    )

            old_values = {

                "priority": (
                    workflow.priority
                ),

                "staff_summary": (
                    workflow.staff_summary
                ),

                "next_action": (
                    workflow.next_action
                ),

                "next_action_due": (
                    workflow.next_action_due
                ),

                "customer_waiting": (
                    workflow.customer_waiting
                ),

                "current_step": (
                    workflow.current_step
                ),

                "stage": (
                    workflow.stage
                ),
            }

            workflow_form = (
                BespokeJobWorkflowForm(
                    request.POST,
                    instance=workflow,
                )
            )

            if workflow_form.is_valid():

                with transaction.atomic():

                    workflow = (
                        workflow_form.save(
                            commit=False
                        )
                    )

                    now = timezone.now()

                    # -------------------------------------
                    # CUSTOMER WAITING
                    # -------------------------------------

                    if (
                        not old_values[
                            "customer_waiting"
                        ]
                        and workflow
                        .customer_waiting
                    ):

                        workflow.customer_waiting_since = (
                            now
                        )

                    elif (
                        old_values[
                            "customer_waiting"
                        ]
                        and not workflow
                        .customer_waiting
                    ):

                        workflow.customer_waiting_since = (
                            None
                        )

                    # -------------------------------------
                    # STAFF ACTIVITY
                    # -------------------------------------

                    if workflow.started_at is None:

                        workflow.started_at = now

                        log_job_activity(
                            order=order,
                            user=request.user,
                            message=(
                                "Bespoke job started "
                                "in the workflow wizard."
                            ),
                        )

                    workflow.last_worked_by = (
                        request.user
                    )

                    workflow.last_worked_at = (
                        now
                    )

                    # -------------------------------------
                    # ORDER STATUS
                    # -------------------------------------

                    if order.status == "pending":

                        order.status = (
                            "processing"
                        )

                        order.save()

                        log_job_activity(
                            order=order,
                            user=request.user,
                            message=(
                                "Order status changed "
                                "from 'Pending' to "
                                "'Processing' when staff "
                                "started work."
                            ),
                        )

                    # -------------------------------------
                    # PROGRESS
                    # -------------------------------------

                    progress_step = max(
                        old_values[
                            "current_step"
                        ],
                        step,
                    )

                    if (
                        action
                        == "save_continue"
                        and step < 8
                    ):

                        progress_step = max(
                            progress_step,
                            step + 1,
                        )

                    workflow.current_step = (
                        progress_step
                    )

                    # -------------------------------------
                    # STAGE
                    # -------------------------------------

                    if (
                        progress_step
                        > old_values[
                            "current_step"
                        ]
                        or old_values[
                            "stage"
                        ]
                        == (
                            BespokeOrderWorkflow
                            .Stage
                            .NEW
                        )
                    ):

                        workflow.stage = (
                            STEP_STAGE_MAP[
                                progress_step
                            ]
                        )

                    workflow.save()

                    log_workflow_field_changes(
                        order=order,
                        user=request.user,
                        old_values=(
                            old_values
                        ),
                        workflow=workflow,
                    )

                    # -------------------------------------
                    # STAGE LOG
                    # -------------------------------------

                    if (
                        old_values["stage"]
                        != workflow.stage
                    ):

                        old_stage_name = dict(
                            BespokeOrderWorkflow
                            .Stage
                            .choices
                        ).get(
                            old_values[
                                "stage"
                            ],
                            old_values[
                                "stage"
                            ],
                        )

                        log_job_activity(
                            order=order,
                            user=request.user,
                            message=(
                                "Workflow stage changed "
                                f"from '{old_stage_name}' "
                                "to "
                                f"'{workflow.get_stage_display()}'."
                            ),
                        )

                    # -------------------------------------
                    # STEP LOG
                    # -------------------------------------

                    if (
                        old_values[
                            "current_step"
                        ]
                        != workflow.current_step
                    ):

                        next_step_data = (
                            WIZARD_STEPS[
                                workflow.current_step
                            ]
                        )

                        log_job_activity(
                            order=order,
                            user=request.user,
                            message=(
                                "Workflow moved to "
                                f"Step "
                                f"{workflow.current_step}: "
                                f"{next_step_data['title']}."
                            ),
                        )

                # =========================================
                # SAVE & EXIT
                # =========================================

                if action == "save_exit":

                    messages.success(
                        request,
                        (
                            "Job saved. You can resume "
                            "from this point later."
                        ),
                    )

                    if request.user.is_superuser:

                        return redirect(
                            "bespoke_jobs_dashboard"
                        )

                    return redirect(
                        "staff_jobs_dashboard"
                    )

                # =========================================
                # SAVE & CONTINUE
                # =========================================

                if (
                    action
                    == "save_continue"
                    and step < 8
                ):

                    messages.success(
                        request,
                        "Progress saved.",
                    )

                    return redirect(
                        "bespoke_job_wizard",
                        reference_number=(
                            order.reference_number
                        ),
                        step=step + 1,
                    )

                # =========================================
                # NORMAL SAVE
                # =========================================

                messages.success(
                    request,
                    "Job progress saved.",
                )

                return redirect(
                    "bespoke_job_wizard",
                    reference_number=(
                        order.reference_number
                    ),
                    step=step,
                )

    # =====================================================
    # CONTACT COMMUNICATIONS
    # =====================================================

    contact_communications = (
        order.communications
        .filter(
            context=(
                OrderCommunication
                .Context
                .CONTACT
            )
        )
        .select_related(
            "logged_by"
        )
        .order_by(
            "-occurred_at",
            "-created_at",
        )
    )

    # =====================================================
    # DESIGN DATA
    # =====================================================

    design_versions = []

    design_communications = []

    latest_design_version = None

    accepted_design_version = None

    if design:

        design_versions = (
            design.versions
            .select_related(
                "created_by",
                "sent_by",
            )
            .prefetch_related(
                "communications"
            )
            .order_by(
                "-version"
            )
        )

        latest_design_version = (
            design.latest_version
        )

        accepted_design_version = (
            design.accepted_version
        )

        design_communications = (
            order.communications
            .filter(
                context=(
                    OrderCommunication
                    .Context
                    .DESIGN
                )
            )
            .select_related(
                "logged_by",
                "design_version",
            )
            .order_by(
                "-occurred_at",
                "-created_at",
            )
        )

    # =====================================================
    # DEFAULT DESIGN EMAIL FORM
    # =====================================================

    if (
        step == 3
        and latest_design_version
        and not (
            request.method == "POST"
            and request.POST.get(
                "action"
            )
            == "send_design_version_email"
        )
    ):

        design_version_email_form = (
            DesignVersionEmailForm(
                initial={
                    "subject": (
                        f"{latest_design_version.version_label} "
                        f"| K9 bespoke order "
                        f"{order.reference_number}"
                    ),

                    "message": (
                        default_design_version_email_message(
                            order,
                            latest_design_version,
                        )
                    ),
                }
            )
        )

    # =====================================================
    # QUOTE DATA
    # =====================================================

    quotes = []
    latest_quote = None
    active_quote = None
    accepted_quote = None
    quote_communications = []

    if step >= 4:

        quotes = (
            workflow.quotes
            .select_related("created_by")
            .prefetch_related("lines")
            .order_by("-version")
        )

        latest_quote = (
            workflow.quotes
            .order_by("-version")
            .first()
        )

        active_quote = (
            workflow.quotes
            .filter(
                status__in=[
                    BespokeQuote.Status.SENT,
                    BespokeQuote.Status.ACCEPTED,
                ]
            )
            .order_by("-version")
            .first()
        )

        accepted_quote = (
            workflow.quotes
            .filter(
                status=BespokeQuote.Status.ACCEPTED
            )
            .order_by("-version")
            .first()
        )

        quote_communications = (
            order.communications
            .filter(
                context=(
                    OrderCommunication.Context.QUOTE
                )
            )
            .select_related("logged_by")
            .order_by(
                "-occurred_at",
                "-created_at",
            )
        )

    # =====================================================
    # WIZARD NAVIGATION
    # =====================================================

    wizard_navigation = []

    for (
        number,
        data,
    ) in WIZARD_STEPS.items():

        unlocked = (
            number
            <= workflow.current_step
            or is_closed
        )

        # Even if legacy data says the user reached later
        # steps, do not expose them without accepted design.

        if (
            number > 3
            and not is_closed
            and not accepted_design_version
        ):

            unlocked = False

        if (
            number > 4
            and not is_closed
            and not accepted_quote
        ):

            unlocked = False

        if (
            number > 5
            and not is_closed
            and (
                not approval_payment
                or not approval_payment.can_start_production
            )
        ):

            unlocked = False

        wizard_navigation.append(
            {
                "number": number,

                "title": (
                    data[
                        "short_title"
                    ]
                ),

                "full_title": (
                    data[
                        "title"
                    ]
                ),

                "active": (
                    number == step
                ),

                "complete": (
                    number
                    < workflow.current_step
                ),

                "unlocked": (
                    unlocked
                ),
            }
        )

    # =====================================================
    # PROGRESS
    # =====================================================

    progress_percent = int(
        (
            workflow.current_step
            / len(WIZARD_STEPS)
        )
        * 100
    )

    # =====================================================
    # ACTIVITY FEED
    # =====================================================

    activity_feed = (
        build_activity_feed(
            order
        )
    )

    # =====================================================
    # CONTEXT
    # =====================================================

    context = {

        "workflow": workflow,

        "order": order,

        "form": workflow_form,

        "step": step,

        "step_data": (
            WIZARD_STEPS[
                step
            ]
        ),

        "wizard_steps": (
            wizard_navigation
        ),

        "progress_percent": (
            progress_percent
        ),

        "activity_feed": (
            activity_feed
        ),

        "is_closed": (
            is_closed
        ),

        # ---------------------------------------------
        # STEP 2
        # ---------------------------------------------

        "email_form": (
            email_form
        ),

        "whatsapp_form": (
            whatsapp_form
        ),

        "communication_log_form": (
            communication_log_form
        ),

        "contact_communications": (
            contact_communications
        ),

        "whatsapp_url": (
            whatsapp_url
        ),

        "whatsapp_prepared_message": (
            whatsapp_prepared_message
        ),

        "whatsapp_number_available": bool(
            normalise_whatsapp_number(
                order.phone_number
            )
        ),

        # ---------------------------------------------
        # STEP 3 - NEW VERSIONED DESIGN SYSTEM
        # ---------------------------------------------

        "design": (
            design
        ),

        "master_design_form": (
            master_design_form
        ),

        "design_version_form": (
            design_version_form
        ),

        "design_version_email_form": (
            design_version_email_form
        ),

        "design_versions": (
            design_versions
        ),

        "latest_design_version": (
            latest_design_version
        ),

        "accepted_design_version": (
            accepted_design_version
        ),

        "design_communications": (
            design_communications
        ),

        # ---------------------------------------------
        # STEP 4 - QUOTE SYSTEM
        # ---------------------------------------------

        "quote_form": (
            quote_form
        ),

        "quote_line_formset": (
            quote_line_formset
        ),

        "quote_editor": (
            quote_editor
        ),

        "quotes": (
            quotes
        ),

        "latest_quote": (
            latest_quote
        ),

        "active_quote": (
            active_quote
        ),

        "accepted_quote": (
            accepted_quote
        ),

        "approval_payment": (
            approval_payment
        ),

        "quote_communications": (
            quote_communications
        ),

        # Legacy template compatibility.
        "design_form": (
            design_form
        ),

        "design_email_form": (
            design_email_form
        ),
    }

    return render(
        request,
        "orders/bespoke_job_wizard.html",
        context,
    )
