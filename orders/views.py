from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .activity import log_job_activity
from .forms import BespokeJobAssignmentForm
from .models import (
    BespokeOrderWorkflow,
    Order,
    OrderNote,
)


# =========================================================
# GENERAL HELPERS
# =========================================================

def get_user_display_name(user):
    """
    Return the most useful display name for a user.
    """

    if not user:
        return "Unknown user"

    full_name = user.get_full_name().strip()

    if full_name:
        return full_name

    return user.username


def get_stage_label(stage_value):
    """
    Return the human-readable workflow stage.
    """

    return dict(
        BespokeOrderWorkflow.Stage.choices
    ).get(
        stage_value,
        stage_value,
    )


def get_order_status_label(status_value):
    """
    Return the human-readable Order status.
    """

    return dict(
        Order.STATUS_CHOICES
    ).get(
        status_value,
        status_value,
    )


def display_value(value):
    """
    Make values clearer inside the activity feed.
    """

    if value is None or value == "":
        return "Not set"

    return str(value)


# =========================================================
# PERMISSION HELPERS
# =========================================================

def require_superuser(request):
    """
    Commercial order management is restricted
    to superusers.

    Staff members use the bespoke jobs workspace instead.
    """

    if not request.user.is_superuser:
        raise PermissionDenied


# =========================================================
# BESPOKE WORKFLOW SYNC
# =========================================================

def sync_bespoke_workflow_with_order(
    order,
    user=None,
):
    """
    Keep the bespoke workflow aligned with the main
    commercial Order when an order is closed or reopened.

    Important:
    normal production stages such as Design, Quote and
    Production are NOT overwritten during normal work.

    Any meaningful automatic workflow change is written
    into the job activity feed.
    """

    if order.order_type != "bespoke":
        return None

    workflow, created = (
        BespokeOrderWorkflow.objects.get_or_create(
            order=order
        )
    )

    now = timezone.now()

    old_stage = workflow.stage
    old_customer_waiting = workflow.customer_waiting
    old_customer_waiting_since = (
        workflow.customer_waiting_since
    )
    old_completed_at = workflow.completed_at

    changed = False

    # =====================================================
    # CANCELLED ORDER
    # =====================================================

    if order.status == "cancelled":

        if (
            workflow.stage
            != BespokeOrderWorkflow.Stage.CANCELLED
        ):
            workflow.stage = (
                BespokeOrderWorkflow.Stage.CANCELLED
            )
            changed = True

        if workflow.customer_waiting:
            workflow.customer_waiting = False
            changed = True

        if workflow.customer_waiting_since is not None:
            workflow.customer_waiting_since = None
            changed = True

        # Cancelled is closed, but not completed.
        if workflow.completed_at is not None:
            workflow.completed_at = None
            changed = True

    # =====================================================
    # SENT / COMPLETED ORDER
    # =====================================================

    elif order.status == "sent":

        if (
            workflow.stage
            != BespokeOrderWorkflow.Stage.COMPLETED
        ):
            workflow.stage = (
                BespokeOrderWorkflow.Stage.COMPLETED
            )
            changed = True

        if workflow.completed_at is None:
            workflow.completed_at = now
            changed = True

        if workflow.customer_waiting:
            workflow.customer_waiting = False
            changed = True

        if workflow.customer_waiting_since is not None:
            workflow.customer_waiting_since = None
            changed = True

    # =====================================================
    # REOPEN PREVIOUSLY CLOSED ORDER
    # =====================================================

    elif (
        order.status in {
            "pending",
            "processing",
        }
        and workflow.stage
        in {
            BespokeOrderWorkflow.Stage.CANCELLED,
            BespokeOrderWorkflow.Stage.COMPLETED,
        }
    ):

        if order.status == "processing":
            workflow.stage = (
                BespokeOrderWorkflow.Stage.REVIEW
            )
        else:
            workflow.stage = (
                BespokeOrderWorkflow.Stage.NEW
            )

        workflow.completed_at = None
        changed = True

    # =====================================================
    # STAFF ACTIVITY METADATA
    # =====================================================

    if changed and user is not None:

        workflow.last_worked_by = user
        workflow.last_worked_at = now

        if workflow.started_at is None:
            workflow.started_at = now

    # =====================================================
    # SAVE WORKFLOW
    # =====================================================

    if changed:
        workflow.save()

    # =====================================================
    # ACTIVITY LOGGING
    # =====================================================

    if user is not None:

        # -------------------------------------------------
        # Workflow created
        # -------------------------------------------------

        if created:

            log_job_activity(
                order=order,
                user=user,
                message=(
                    "Bespoke workflow record created."
                ),
            )

        # -------------------------------------------------
        # Stage changed
        # -------------------------------------------------

        if old_stage != workflow.stage:

            log_job_activity(
                order=order,
                user=user,
                message=(
                    "Bespoke workflow stage changed from "
                    f"'{get_stage_label(old_stage)}' to "
                    f"'{get_stage_label(workflow.stage)}'."
                ),
            )

        # -------------------------------------------------
        # Customer waiting automatically cleared
        # -------------------------------------------------

        if (
            old_customer_waiting
            and not workflow.customer_waiting
        ):

            log_job_activity(
                order=order,
                user=user,
                message=(
                    "Customer waiting status cleared "
                    "automatically."
                ),
            )

        # -------------------------------------------------
        # Customer waiting timestamp cleared
        # -------------------------------------------------

        if (
            old_customer_waiting_since is not None
            and workflow.customer_waiting_since is None
            and not old_customer_waiting
        ):

            log_job_activity(
                order=order,
                user=user,
                message=(
                    "Customer waiting timestamp cleared."
                ),
            )

        # -------------------------------------------------
        # Completion timestamp created
        # -------------------------------------------------

        if (
            old_completed_at is None
            and workflow.completed_at is not None
        ):

            log_job_activity(
                order=order,
                user=user,
                message=(
                    "Bespoke job completion timestamp "
                    "recorded."
                ),
            )

        # -------------------------------------------------
        # Completion timestamp removed / reopened
        # -------------------------------------------------

        if (
            old_completed_at is not None
            and workflow.completed_at is None
            and order.status
            in {
                "pending",
                "processing",
            }
        ):

            log_job_activity(
                order=order,
                user=user,
                message=(
                    "Bespoke job reopened. Previous "
                    "completion status cleared."
                ),
            )

    return workflow


# =========================================================
# STAFF BESPOKE JOBS DASHBOARD
# =========================================================

@staff_member_required
def bespoke_jobs_dashboard(request):
    """
    Bespoke production workspace.

    SUPERUSERS
    ----------
    - See every bespoke job.
    - See unassigned jobs.
    - Assign/reassign jobs.
    - Filter across all staff work.

    STAFF
    -----
    - Only see jobs assigned to themselves.
    - Cannot reveal jobs belonging to somebody else
      through URL/query manipulation.
    """

    # =====================================================
    # SUPERUSER JOB ASSIGNMENT
    # =====================================================

    if (
        request.method == "POST"
        and "assign_job" in request.POST
    ):

        if not request.user.is_superuser:
            raise PermissionDenied

        job_id = request.POST.get(
            "job_id"
        )

        job = get_object_or_404(
            BespokeOrderWorkflow.objects.select_related(
                "order",
                "assigned_to",
            ),
            pk=job_id,
        )

        previous_assignee = job.assigned_to

        assignment_form = BespokeJobAssignmentForm(
            request.POST,
            instance=job,
        )

        if assignment_form.is_valid():

            with transaction.atomic():

                updated_job = assignment_form.save()

                new_assignee = (
                    updated_job.assigned_to
                )

                previous_name = (
                    get_user_display_name(
                        previous_assignee
                    )
                    if previous_assignee
                    else "Unassigned"
                )

                new_name = (
                    get_user_display_name(
                        new_assignee
                    )
                    if new_assignee
                    else "Unassigned"
                )

                # -----------------------------------------
                # Only log genuine changes
                # -----------------------------------------

                if previous_assignee != new_assignee:

                    log_job_activity(
                        order=job.order,
                        user=request.user,
                        message=(
                            "Bespoke job assignment "
                            "changed from "
                            f"'{previous_name}' to "
                            f"'{new_name}'."
                        ),
                    )

                    messages.success(
                        request,
                        (
                            f"{job.order.reference_number} "
                            f"assigned to {new_name}."
                        ),
                    )

                else:

                    messages.info(
                        request,
                        (
                            "The job assignment "
                            "was unchanged."
                        ),
                    )

        else:

            messages.error(
                request,
                (
                    "The job could not be assigned. "
                    "Please try again."
                ),
            )

        return redirect(
            "bespoke_jobs_dashboard"
        )

    # =====================================================
    # FILTER VALUES
    # =====================================================

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

    assigned_filter = request.GET.get(
        "assigned",
        "",
    ).strip()

    show_closed = (
        request.GET.get("show_closed")
        == "1"
    )

    # =====================================================
    # BASE QUERY
    # =====================================================

    jobs = (
        BespokeOrderWorkflow.objects
        .select_related(
            "order",
            "order__bespoke_request",
            "assigned_to",
            "created_by",
            "last_worked_by",
        )
    )

    # =====================================================
    # SECURITY BOUNDARY
    # =====================================================

    if not request.user.is_superuser:

        jobs = jobs.filter(
            assigned_to=request.user
        )

        assigned_filter = "mine"

    # =====================================================
    # SEARCH
    # =====================================================

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
                order__phone_number__icontains=(
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
                order__bespoke_request__request_title__icontains=(
                    search_query
                )
            )
            |
            Q(
                order__bespoke_request__item_type__icontains=(
                    search_query
                )
            )
            |
            Q(
                staff_summary__icontains=(
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

    # =====================================================
    # STAGE FILTER
    # =====================================================

    valid_stages = {
        value
        for value, label
        in BespokeOrderWorkflow.Stage.choices
    }

    if (
        stage_filter
        and stage_filter in valid_stages
    ):

        jobs = jobs.filter(
            stage=stage_filter
        )

    # =====================================================
    # PRIORITY FILTER
    # =====================================================

    valid_priorities = {
        value
        for value, label
        in BespokeOrderWorkflow.Priority.choices
    }

    if (
        priority_filter
        and priority_filter in valid_priorities
    ):

        jobs = jobs.filter(
            priority=priority_filter
        )

    # =====================================================
    # ASSIGNMENT FILTER
    # SUPERUSER ONLY
    # =====================================================

    if request.user.is_superuser:

        if assigned_filter == "mine":

            jobs = jobs.filter(
                assigned_to=request.user
            )

        elif assigned_filter == "unassigned":

            jobs = jobs.filter(
                assigned_to__isnull=True
            )

    # =====================================================
    # CLOSED JOBS
    # =====================================================

    closed_stages = [
        BespokeOrderWorkflow.Stage.COMPLETED,
        BespokeOrderWorkflow.Stage.CANCELLED,
    ]

    if not show_closed:

        jobs = jobs.exclude(
            stage__in=closed_stages
        )

    # =====================================================
    # ORDERING
    # =====================================================

    jobs = jobs.order_by(
        "-priority",
        "-last_worked_at",
        "-updated_at",
    )

    # =====================================================
    # COUNT QUERYSET
    # =====================================================

    if request.user.is_superuser:

        all_jobs = (
            BespokeOrderWorkflow.objects
            .all()
        )

    else:

        all_jobs = (
            BespokeOrderWorkflow.objects
            .filter(
                assigned_to=request.user
            )
        )

    # =====================================================
    # DASHBOARD COUNTS
    # =====================================================

    counts = {

        "active": (
            all_jobs
            .exclude(
                stage__in=closed_stages
            )
            .count()
        ),

        "mine": (
            all_jobs
            .filter(
                assigned_to=request.user
            )
            .exclude(
                stage__in=closed_stages
            )
            .count()
        ),

        "unassigned": (
            all_jobs
            .filter(
                assigned_to__isnull=True
            )
            .exclude(
                stage__in=closed_stages
            )
            .count()
        ),

        "waiting": (
            all_jobs
            .filter(
                customer_waiting=True
            )
            .exclude(
                stage__in=closed_stages
            )
            .count()
        ),

        "urgent": (
            all_jobs
            .filter(
                priority=(
                    BespokeOrderWorkflow.Priority.URGENT
                )
            )
            .exclude(
                stage__in=closed_stages
            )
            .count()
        ),

        "completed": (
            all_jobs
            .filter(
                stage=(
                    BespokeOrderWorkflow.Stage.COMPLETED
                )
            )
            .count()
        ),

        "cancelled": (
            all_jobs
            .filter(
                stage=(
                    BespokeOrderWorkflow.Stage.CANCELLED
                )
            )
            .count()
        ),
    }

    # =====================================================
    # PREPARE JOB CARDS
    # =====================================================

    jobs = list(jobs)

    if request.user.is_superuser:

        for job in jobs:

            job.assignment_form = (
                BespokeJobAssignmentForm(
                    instance=job
                )
            )

    # =====================================================
    # TEMPLATE CONTEXT
    # =====================================================

    context = {
        "jobs": jobs,
        "search_query": search_query,
        "stage_filter": stage_filter,
        "priority_filter": priority_filter,
        "assigned_filter": assigned_filter,
        "show_closed": show_closed,
        "job_counts": counts,
        "stage_choices": (
            BespokeOrderWorkflow.Stage.choices
        ),
        "priority_choices": (
            BespokeOrderWorkflow.Priority.choices
        ),
        "is_superuser_view": (
            request.user.is_superuser
        ),
    }

    return render(
        request,
        "orders/bespoke_jobs_dashboard.html",
        context,
    )


# =========================================================
# MASTER ORDER DASHBOARD
# SUPERUSER ONLY
# =========================================================

@staff_member_required
def order_dashboard(request):
    """
    Commercial order-management dashboard.

    Superusers only.
    """

    require_superuser(request)

    search_query = request.GET.get(
        "q",
        "",
    ).strip()

    status_filter = request.GET.get(
        "status",
        "",
    ).strip()

    show_closed = (
        request.GET.get("show_closed")
        == "1"
    )

    orders = Order.objects.all()

    # =====================================================
    # SEARCH
    # =====================================================

    if search_query:

        orders = orders.filter(
            Q(
                reference_number__icontains=(
                    search_query
                )
            )
            |
            Q(
                customer_name__icontains=(
                    search_query
                )
            )
            |
            Q(
                customer_email__icontains=(
                    search_query
                )
            )
            |
            Q(
                phone_number__icontains=(
                    search_query
                )
            )
            |
            Q(
                tracking_number__icontains=(
                    search_query
                )
            )
        )

        if status_filter in {
            "pending",
            "processing",
            "sent",
            "cancelled",
        }:

            orders = orders.filter(
                status=status_filter
            )

    # =====================================================
    # NORMAL DASHBOARD BROWSING
    # =====================================================

    else:

        if show_closed:

            if status_filter in {
                "pending",
                "processing",
                "sent",
                "cancelled",
            }:

                orders = orders.filter(
                    status=status_filter
                )

        else:

            if status_filter in {
                "pending",
                "processing",
            }:

                orders = orders.filter(
                    status=status_filter
                )

            else:

                orders = orders.filter(
                    status__in=[
                        "pending",
                        "processing",
                    ]
                )

    orders = orders.order_by(
        "-created_at"
    )

    # =====================================================
    # COUNTS
    # =====================================================

    counts = Order.objects.aggregate(

        pending=Count(
            "id",
            filter=Q(
                status="pending"
            ),
        ),

        processing=Count(
            "id",
            filter=Q(
                status="processing"
            ),
        ),

        sent=Count(
            "id",
            filter=Q(
                status="sent"
            ),
        ),

        cancelled=Count(
            "id",
            filter=Q(
                status="cancelled"
            ),
        ),
    )

    context = {
        "orders": orders,
        "search_query": search_query,
        "status_filter": status_filter,
        "show_closed": show_closed,
        "status_counts": counts,
    }

    return render(
        request,
        "orders/dashboard.html",
        context,
    )


# =========================================================
# ORDER DETAIL
# SUPERUSER ONLY
# =========================================================

@staff_member_required
def order_detail(
    request,
    reference_number,
):
    """
    Commercial order detail and management screen.

    Superusers only.

    All meaningful changes are recorded in the
    central job activity feed.
    """

    require_superuser(request)

    order = get_object_or_404(
        Order,
        reference_number=reference_number,
    )

    # =====================================================
    # POST ACTIONS
    # =====================================================

    if request.method == "POST":

        # =================================================
        # QUICK MARK COMPLETE
        # =================================================

        if "mark_complete" in request.POST:

            old_status = order.status

            with transaction.atomic():

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
                        "Order status changed from "
                        f"'{get_order_status_label(old_status)}' "
                        "to "
                        f"'{get_order_status_label(order.status)}' "
                        "using Quick Mark Complete."
                    ),
                )

            messages.success(
                request,
                (
                    "Order timestamped and "
                    "marked as Sent."
                ),
            )

            return redirect(
                "order_detail",
                reference_number=(
                    order.reference_number
                ),
            )

        # =================================================
        # UPDATE ORDER
        # =================================================

        elif "update_order" in request.POST:

            # -------------------------------------------------
            # CURRENT VALUES BEFORE UPDATE
            # -------------------------------------------------

            old_values = {
                "status": order.status,
                "customer_name": (
                    order.customer_name or ""
                ),
                "customer_email": (
                    order.customer_email or ""
                ),
                "phone_number": (
                    order.phone_number or ""
                ),
                "shipping_address": (
                    order.shipping_address or ""
                ),
                "tracking_number": (
                    order.tracking_number or ""
                ),
                "order_total": order.order_total,
            }

            new_status = request.POST.get(
                "status",
                "",
            ).strip()

            cancel_reason = (
                request.POST
                .get(
                    "cancel_reason",
                    "",
                )
                .strip()
            )

            valid_statuses = {
                choice[0]
                for choice
                in Order.STATUS_CHOICES
            }

            # -------------------------------------------------
            # VALIDATE STATUS
            # -------------------------------------------------

            if new_status not in valid_statuses:

                messages.error(
                    request,
                    "Invalid order status selected.",
                )

                return redirect(
                    "order_detail",
                    reference_number=(
                        order.reference_number
                    ),
                )

            is_new_cancellation = (
                new_status == "cancelled"
                and old_values["status"]
                != "cancelled"
            )

            # -------------------------------------------------
            # CANCELLATION REASON REQUIRED
            # -------------------------------------------------

            if (
                is_new_cancellation
                and not cancel_reason
            ):

                messages.error(
                    request,
                    (
                        "Please provide a reason "
                        "for cancelling the order."
                    ),
                )

                return redirect(
                    "order_detail",
                    reference_number=(
                        order.reference_number
                    ),
                )

            # -------------------------------------------------
            # NEW FORM VALUES
            # -------------------------------------------------

            new_customer_name = (
                request.POST
                .get(
                    "customer_name",
                    "",
                )
                .strip()
            )

            new_customer_email = (
                request.POST
                .get(
                    "customer_email",
                    "",
                )
                .strip()
            )

            new_phone_number = (
                request.POST
                .get(
                    "phone_number",
                    "",
                )
                .strip()
            )

            new_shipping_address = (
                request.POST
                .get(
                    "shipping_address",
                    "",
                )
                .strip()
            )

            new_tracking_number = (
                request.POST
                .get(
                    "tracking_number",
                    "",
                )
                .strip()
            )

            total_val = (
                request.POST
                .get(
                    "order_total",
                    "",
                )
                .strip()
            )

            # -------------------------------------------------
            # VALIDATE ORDER TOTAL
            # -------------------------------------------------

            new_order_total = order.order_total

            if total_val:

                try:

                    new_order_total = Decimal(
                        total_val
                    )

                except InvalidOperation:

                    messages.error(
                        request,
                        (
                            "Please enter a valid "
                            "order total."
                        ),
                    )

                    return redirect(
                        "order_detail",
                        reference_number=(
                            order.reference_number
                        ),
                    )

                if new_order_total < 0:

                    messages.error(
                        request,
                        (
                            "Order total cannot "
                            "be negative."
                        ),
                    )

                    return redirect(
                        "order_detail",
                        reference_number=(
                            order.reference_number
                        ),
                    )

            # =================================================
            # SAVE EVERYTHING TOGETHER
            # =================================================

            with transaction.atomic():

                # ---------------------------------------------
                # UPDATE ORDER
                # ---------------------------------------------

                order.status = new_status
                order.customer_name = (
                    new_customer_name
                )
                order.customer_email = (
                    new_customer_email
                )
                order.phone_number = (
                    new_phone_number
                )
                order.shipping_address = (
                    new_shipping_address
                )
                order.tracking_number = (
                    new_tracking_number
                )

                if total_val:
                    order.order_total = new_order_total

                order.save()

                # ---------------------------------------------
                # ORDER STATUS CHANGE
                # ---------------------------------------------

                if (
                    old_values["status"]
                    != order.status
                ):

                    log_job_activity(
                        order=order,
                        user=request.user,
                        message=(
                            "Order status changed from "
                            f"'{
                                get_order_status_label(
                                    old_values['status']
                                )
                            }' to "
                            f"'{
                                get_order_status_label(
                                    order.status
                                )
                            }'."
                        ),
                    )

                # ---------------------------------------------
                # CANCELLATION REASON
                # ---------------------------------------------

                if is_new_cancellation:

                    log_job_activity(
                        order=order,
                        user=request.user,
                        message=(
                            "Order cancelled. "
                            f"Reason: {cancel_reason}"
                        ),
                    )

                # ---------------------------------------------
                # RECORD DETAIL CHANGES
                # ---------------------------------------------

                detail_changes = []

                if (
                    old_values["customer_name"]
                    != order.customer_name
                ):

                    detail_changes.append(
                        (
                            "Customer name: "
                            f"'{display_value(
                                old_values['customer_name']
                            )}' → "
                            f"'{display_value(
                                order.customer_name
                            )}'"
                        )
                    )

                if (
                    old_values["customer_email"]
                    != order.customer_email
                ):

                    detail_changes.append(
                        (
                            "Customer email: "
                            f"'{display_value(
                                old_values['customer_email']
                            )}' → "
                            f"'{display_value(
                                order.customer_email
                            )}'"
                        )
                    )

                if (
                    old_values["phone_number"]
                    != order.phone_number
                ):

                    detail_changes.append(
                        (
                            "Phone number: "
                            f"'{display_value(
                                old_values['phone_number']
                            )}' → "
                            f"'{display_value(
                                order.phone_number
                            )}'"
                        )
                    )

                if (
                    old_values["shipping_address"]
                    != order.shipping_address
                ):

                    detail_changes.append(
                        (
                            "Shipping address changed from "
                            f"'{display_value(
                                old_values['shipping_address']
                            )}' to "
                            f"'{display_value(
                                order.shipping_address
                            )}'."
                        )
                    )

                if (
                    old_values["tracking_number"]
                    != order.tracking_number
                ):

                    detail_changes.append(
                        (
                            "Tracking number: "
                            f"'{display_value(
                                old_values['tracking_number']
                            )}' → "
                            f"'{display_value(
                                order.tracking_number
                            )}'"
                        )
                    )

                if (
                    old_values["order_total"]
                    != order.order_total
                ):

                    old_total = (
                        f"£{old_values['order_total']:.2f}"
                        if old_values["order_total"]
                        is not None
                        else "Not set"
                    )

                    new_total = (
                        f"£{order.order_total:.2f}"
                        if order.order_total
                        is not None
                        else "Not set"
                    )

                    detail_changes.append(
                        (
                            "Order total: "
                            f"{old_total} → {new_total}"
                        )
                    )

                # ---------------------------------------------
                # ONE FEED EVENT FOR DETAIL EDITS
                # ---------------------------------------------

                if detail_changes:

                    log_job_activity(
                        order=order,
                        user=request.user,
                        message=(
                            "Order details updated:\n"
                            + "\n".join(
                                f"• {change}"
                                for change
                                in detail_changes
                            )
                        ),
                    )

                # ---------------------------------------------
                # SYNC BESPOKE WORKFLOW
                # ---------------------------------------------

                sync_bespoke_workflow_with_order(
                    order,
                    request.user,
                )

            # =================================================
            # USER MESSAGE
            # =================================================

            if is_new_cancellation:

                messages.success(
                    request,
                    (
                        "Cancellation reason logged, "
                        "order cancelled and bespoke "
                        "job closed."
                    ),
                )

            elif (
                old_values["status"]
                != order.status
            ):

                messages.success(
                    request,
                    (
                        "Order updated and status "
                        "change logged."
                    ),
                )

            else:

                messages.success(
                    request,
                    (
                        "Order details updated "
                        "successfully."
                    ),
                )

            return redirect(
                "order_detail",
                reference_number=(
                    order.reference_number
                ),
            )

        # =================================================
        # ADD STAFF NOTE
        # =================================================

        elif "add_note" in request.POST:

            content = (
                request.POST
                .get(
                    "note_content",
                    "",
                )
                .strip()
            )

            note_type = (
                request.POST.get(
                    "note_type",
                    "internal",
                )
            )

            valid_note_types = {
                choice[0]
                for choice
                in OrderNote.NOTE_TYPE_CHOICES
            }

            if note_type not in valid_note_types:
                note_type = "internal"

            if content:

                log_job_activity(
                    order=order,
                    user=request.user,
                    message=content,
                    note_type=note_type,
                )

                messages.success(
                    request,
                    "Note added successfully.",
                )

            else:

                messages.warning(
                    request,
                    (
                        "Please enter a note "
                        "before saving."
                    ),
                )

            return redirect(
                "order_detail",
                reference_number=(
                    order.reference_number
                ),
            )

    # =====================================================
    # DISPLAY ORDER
    # =====================================================

    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
        },
    )
