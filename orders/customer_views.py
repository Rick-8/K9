from django.contrib import messages
from django.db import transaction
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone

from .activity import log_job_activity
from .forms import CustomerDesignResponseForm
from .models import (
    BespokeDesignVersion,
    BespokeOrderWorkflow,
    OrderCommunication,
)


# =========================================================
# CUSTOMER DESIGN REVIEW
# =========================================================

def design_review(
    request,
    token,
):
    """
    Public customer-facing design review page.

    Access is controlled by the unique UUID token stored
    against one exact BespokeDesignVersion.

    No login is required because the secure token identifies
    the design review request.
    """

    design_version = get_object_or_404(
        BespokeDesignVersion.objects
        .select_related(
            "design",
            "design__workflow",
            "design__workflow__order",
            "sent_by",
        ),
        response_token=token,
    )

    design = design_version.design
    workflow = design.workflow
    order = workflow.order

    # =====================================================
    # DETERMINE WHETHER CUSTOMER CAN RESPOND
    # =====================================================

    can_respond = (
        design_version.status
        == BespokeDesignVersion.Status.SENT
    )

    # =====================================================
    # DEFAULT FORM
    # =====================================================

    response_form = (
        CustomerDesignResponseForm(
            initial={
                "response_name": (
                    order.customer_name
                    or ""
                ),
                "response_email": (
                    order.customer_email
                    or ""
                ),
            }
        )
    )

    # =====================================================
    # HANDLE RESPONSE
    # =====================================================

    if request.method == "POST":

        # -------------------------------------------------
        # ALREADY RESPONDED / NO LONGER ACTIVE
        # -------------------------------------------------

        if not can_respond:

            messages.info(
                request,
                (
                    "This design version has already "
                    "received a response or is no longer "
                    "available for review."
                ),
            )

            return redirect(
                "customer_design_review",
                token=(
                    design_version
                    .response_token
                ),
            )

        decision = (
            request.POST.get(
                "decision",
                ""
            )
            .strip()
            .lower()
        )

        if decision not in {
            "accept",
            "reject",
        }:

            messages.error(
                request,
                (
                    "Please choose either Accept Design "
                    "or Request Changes."
                ),
            )

            return redirect(
                "customer_design_review",
                token=(
                    design_version
                    .response_token
                ),
            )

        response_form = (
            CustomerDesignResponseForm(
                request.POST,
                decision=decision,
            )
        )

        if response_form.is_valid():

            response_name = (
                response_form
                .cleaned_data[
                    "response_name"
                ]
                .strip()
            )

            response_email = (
                response_form
                .cleaned_data[
                    "response_email"
                ]
                .strip()
            )

            response_notes = (
                response_form
                .cleaned_data[
                    "response_notes"
                ]
                .strip()
            )

            now = timezone.now()

            with transaction.atomic():

                # =========================================
                # ACCEPTED
                # =========================================

                if decision == "accept":

                    design_version.mark_accepted(
                        name=response_name,
                        email=response_email,
                        notes=response_notes,
                    )

                    communication_summary = (
                        f"{design_version.version_label} "
                        "accepted by customer."
                    )

                    if response_notes:

                        communication_content = (
                            "Customer accepted the design.\n\n"
                            "Customer comments:\n"
                            f"{response_notes}"
                        )

                    else:

                        communication_content = (
                            "Customer accepted the design."
                        )

                    activity_message = (
                        f"{design_version.version_label} "
                        "accepted by the customer.\n"
                        f"Name: {response_name}\n"
                        f"Email: {response_email}"
                    )

                    if response_notes:

                        activity_message += (
                            "\nComments: "
                            f"{response_notes}"
                        )

                # =========================================
                # REJECTED / CHANGES REQUESTED
                # =========================================

                else:

                    design_version.mark_rejected(
                        name=response_name,
                        email=response_email,
                        notes=response_notes,
                    )

                    communication_summary = (
                        f"{design_version.version_label} "
                        "rejected / changes requested."
                    )

                    communication_content = (
                        "Customer requested changes to "
                        "the design.\n\n"
                        "Requested changes:\n"
                        f"{response_notes}"
                    )

                    activity_message = (
                        f"{design_version.version_label} "
                        "rejected / changes requested "
                        "by the customer.\n"
                        f"Name: {response_name}\n"
                        f"Email: {response_email}\n"
                        "Requested changes: "
                        f"{response_notes}"
                    )

                # =========================================
                # COMMUNICATION RECORD
                # =========================================

                OrderCommunication.objects.create(

                    order=order,

                    design_version=(
                        design_version
                    ),

                    channel=(
                        OrderCommunication
                        .Channel
                        .OTHER
                    ),

                    context=(
                        OrderCommunication
                        .Context
                        .DESIGN
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

                    from_address=(
                        response_email
                    ),

                    to_address="K9",

                    summary=(
                        communication_summary
                    ),

                    content=(
                        communication_content
                    ),

                    logged_by=None,

                    occurred_at=now,
                )

                # =========================================
                # WORKFLOW
                # =========================================

                workflow.stage = (
                    BespokeOrderWorkflow
                    .Stage
                    .DESIGN
                )

                workflow.customer_waiting = (
                    False
                )

                workflow.customer_waiting_since = (
                    None
                )

                workflow.last_worked_at = (
                    now
                )

                workflow.save(
                    update_fields=[
                        "stage",
                        "customer_waiting",
                        "customer_waiting_since",
                        "last_worked_at",
                        "updated_at",
                    ]
                )

                # =========================================
                # ACTIVITY LOG
                # =========================================

                log_job_activity(
                    order=order,
                    user=None,
                    message=(
                        activity_message
                    ),
                )

            # Refresh so the template receives the
            # newly updated status immediately.

            design_version.refresh_from_db()

            if decision == "accept":

                messages.success(
                    request,
                    (
                        "Thank you. Your design has "
                        "been accepted successfully."
                    ),
                )

            else:

                messages.success(
                    request,
                    (
                        "Thank you. Your requested "
                        "changes have been sent to K9."
                    ),
                )

            return redirect(
                "customer_design_review",
                token=(
                    design_version
                    .response_token
                ),
            )

    # =====================================================
    # REFRESH RESPONSE STATE
    # =====================================================

    can_respond = (
        design_version.status
        == BespokeDesignVersion.Status.SENT
    )

    # =====================================================
    # FILE DETAILS
    # =====================================================

    file_size_display = ""

    if design_version.file_size:

        size = (
            design_version.file_size
        )

        if size >= (
            1024
            * 1024
        ):

            file_size_display = (
                f"{size / (1024 * 1024):.2f} MB"
            )

        elif size >= 1024:

            file_size_display = (
                f"{size / 1024:.1f} KB"
            )

        else:

            file_size_display = (
                f"{size} bytes"
            )

    # =====================================================
    # CONTEXT
    # =====================================================

    context = {

        "design_version": (
            design_version
        ),

        "design": (
            design
        ),

        "workflow": (
            workflow
        ),

        "order": (
            order
        ),

        "response_form": (
            response_form
        ),

        "can_respond": (
            can_respond
        ),

        "file_size_display": (
            file_size_display
        ),

        "is_accepted": (
            design_version.status
            == (
                BespokeDesignVersion
                .Status
                .ACCEPTED
            )
        ),

        "is_rejected": (
            design_version.status
            == (
                BespokeDesignVersion
                .Status
                .REJECTED
            )
        ),

        "is_superseded": (
            design_version.status
            == (
                BespokeDesignVersion
                .Status
                .SUPERSEDED
            )
        ),
    }

    return render(
        request,
        "orders/customer_design_review.html",
        context,
    )
