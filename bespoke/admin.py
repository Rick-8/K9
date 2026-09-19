from django.contrib import admin, messages
from django.utils.html import format_html

from .models import (
    BespokeAttachment,
    BespokeNotificationPreference,
    BespokeRequest,
)


# =========================================================
# BESPOKE ATTACHMENTS INLINE
# =========================================================

class BespokeAttachmentInline(admin.TabularInline):
    """
    Future attachment support.

    Customer uploads are not enabled yet, but this prepares
    the admin for inspiration images/files later.
    """

    model = BespokeAttachment
    extra = 0

    fields = (
        "file",
        "original_name",
        "caption",
        "sort_order",
        "uploaded_at",
    )

    readonly_fields = (
        "uploaded_at",
    )

    ordering = (
        "sort_order",
        "uploaded_at",
    )


# =========================================================
# BESPOKE REQUEST ADMIN
# =========================================================

@admin.register(BespokeRequest)
class BespokeRequestAdmin(admin.ModelAdmin):

    # -----------------------------------------------------
    # LIST PAGE
    # -----------------------------------------------------

    list_display = (
        "reference",
        "request_title_display",
        "customer_display",
        "status_badge",
        "item_type",
        "budget_display_admin",
        "needed_by",
        "submitted_at",
        "created_at",
    )

    list_filter = (
        "status",
        "preferred_contact",
        "fulfilment",
        "budget_flexible",
        "deadline_flexible",
        "details_confirmed",
        "terms_accepted",
        "contact_consent",
        "created_at",
        "submitted_at",
    )

    search_fields = (
        "reference",
        "request_title",
        "item_type",
        "description",
        "name",
        "email",
        "phone",
        "recipient_name",
        "recipient_relationship",
        "occasion",
        "theme",
        "colours",
        "materials",
        "personalisation_text",
        "delivery_postcode",
    )

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"

    list_per_page = 25

    save_on_top = True

    inlines = [
        BespokeAttachmentInline,
    ]

    # -----------------------------------------------------
    # READ ONLY FIELDS
    # -----------------------------------------------------

    readonly_fields = (
        "reference",
        "created_at",
        "updated_at",
        "submitted_at",
        "budget_summary",
        "customer_account_display",
    )

    # -----------------------------------------------------
    # ADMIN FORM LAYOUT
    # -----------------------------------------------------

    fieldsets = (

        (
            "Request Overview",
            {
                "fields": (
                    "reference",
                    "status",
                    "current_step",
                    "user",
                    "customer_account_display",
                    "created_at",
                    "updated_at",
                    "submitted_at",
                ),
            },
        ),

        (
            "1. The Customer's Idea",
            {
                "fields": (
                    "request_title",
                    "item_type",
                    "description",
                    "inspiration_source",
                ),
            },
        ),

        (
            "2. Recipient & Occasion",
            {
                "fields": (
                    "recipient_name",
                    "recipient_relationship",
                    "recipient_age",
                    "occasion",
                    "occasion_date",
                    "recipient_interests",
                    "story_or_meaning",
                ),
            },
        ),

        (
            "3. Design & Personalisation",
            {
                "fields": (
                    "style",
                    "theme",
                    "colours",
                    "materials",
                    "size_or_dimensions",
                    "personalisation_text",
                    "must_include",
                    "avoid",
                    "finish_notes",
                ),
            },
        ),

        (
            "Future Attachments",
            {
                "classes": (
                    "collapse",
                ),
                "fields": (
                    "attachment_notes",
                ),
                "description": (
                    "Customer image/file uploads are not enabled yet. "
                    "This section is reserved for future attachment support."
                ),
            },
        ),

        (
            "4. Budget & Practical Details",
            {
                "fields": (
                    "quantity",
                    "budget",
                    "budget_min",
                    "budget_max",
                    "budget_summary",
                    "budget_flexible",
                    "needed_by",
                    "deadline_flexible",
                    "fulfilment",
                    "delivery_postcode",
                    "practical_notes",
                ),
            },
        ),

        (
            "5. Customer Contact Details",
            {
                "fields": (
                    "name",
                    "email",
                    "phone",
                    "preferred_contact",
                    "best_contact_time",
                ),
            },
        ),

        (
            "6. Customer Confirmations",
            {
                "fields": (
                    "details_confirmed",
                    "terms_accepted",
                    "contact_consent",
                ),
            },
        ),
    )

    # -----------------------------------------------------
    # BULK ACTIONS
    # -----------------------------------------------------

    actions = (
        "mark_under_review",
        "mark_more_information_needed",
        "mark_quoted",
        "mark_accepted",
        "mark_in_progress",
        "mark_ready",
        "mark_completed",
        "mark_cancelled",
    )

    # =====================================================
    # DISPLAY HELPERS
    # =====================================================

    @admin.display(
        description="Request",
        ordering="request_title",
    )
    def request_title_display(self, obj):
        return (
            obj.request_title
            or obj.item_type
            or "Untitled Request"
        )

    @admin.display(
        description="Customer",
        ordering="name",
    )
    def customer_display(self, obj):
        return obj.customer_name

    @admin.display(
        description="Budget",
    )
    def budget_display_admin(self, obj):
        return obj.budget_display

    @admin.display(
        description="Budget Summary",
    )
    def budget_summary(self, obj):
        return obj.budget_display

    @admin.display(
        description="Customer Account",
    )
    def customer_account_display(self, obj):

        if obj.user:
            return format_html(
                "<strong>{}</strong><br>"
                "<span style='color:#666;'>{}</span>",
                obj.user.get_username(),
                "Linked K9 account",
            )

        return format_html(
            "<span style='color:#888;'>{}</span>",
            "Guest request - no account linked",
        )

    # =====================================================
    # STATUS BADGE
    # =====================================================

    @admin.display(
        description="Status",
        ordering="status",
    )
    def status_badge(self, obj):

        colours = {
            BespokeRequest.Status.DRAFT: "#6c757d",
            BespokeRequest.Status.SUBMITTED: "#0d6efd",
            BespokeRequest.Status.REVIEWING: "#6610f2",
            BespokeRequest.Status.MORE_INFO: "#fd7e14",
            BespokeRequest.Status.QUOTED: "#0dcaf0",
            BespokeRequest.Status.ACCEPTED: "#198754",
            BespokeRequest.Status.IN_PROGRESS: "#ffc107",
            BespokeRequest.Status.READY: "#20c997",
            BespokeRequest.Status.COMPLETED: "#198754",
            BespokeRequest.Status.DECLINED: "#dc3545",
            BespokeRequest.Status.CANCELLED: "#6c757d",
        }

        colour = colours.get(
            obj.status,
            "#6c757d",
        )

        return format_html(
            (
                '<span style="'
                'background:{};'
                'color:white;'
                'padding:4px 9px;'
                'border-radius:12px;'
                'font-size:11px;'
                'font-weight:600;'
                'white-space:nowrap;'
                '">{}</span>'
            ),
            colour,
            obj.get_status_display(),
        )

    # =====================================================
    # BULK STATUS ACTIONS
    # =====================================================

    @admin.action(
        description="Mark selected requests as Under Review"
    )
    def mark_under_review(self, request, queryset):

        updated = queryset.update(
            status=BespokeRequest.Status.REVIEWING
        )

        self.message_user(
            request,
            f"{updated} request(s) marked as Under Review.",
        )

    @admin.action(
        description="Mark selected requests as More Information Needed"
    )
    def mark_more_information_needed(
        self,
        request,
        queryset,
    ):

        updated = queryset.update(
            status=BespokeRequest.Status.MORE_INFO
        )

        self.message_user(
            request,
            (
                f"{updated} request(s) marked as "
                "More Information Needed."
            ),
        )

    @admin.action(
        description="Mark selected requests as Quote Sent"
    )
    def mark_quoted(self, request, queryset):

        updated = queryset.update(
            status=BespokeRequest.Status.QUOTED
        )

        self.message_user(
            request,
            f"{updated} request(s) marked as Quote Sent.",
        )

    @admin.action(
        description="Mark selected requests as Quote Accepted"
    )
    def mark_accepted(self, request, queryset):

        updated = queryset.update(
            status=BespokeRequest.Status.ACCEPTED
        )

        self.message_user(
            request,
            f"{updated} request(s) marked as Quote Accepted.",
        )

    @admin.action(
        description="Mark selected requests as In Progress"
    )
    def mark_in_progress(self, request, queryset):

        updated = queryset.update(
            status=BespokeRequest.Status.IN_PROGRESS
        )

        self.message_user(
            request,
            f"{updated} request(s) marked as In Progress.",
        )

    @admin.action(
        description="Mark selected requests as Ready"
    )
    def mark_ready(self, request, queryset):

        updated = queryset.update(
            status=BespokeRequest.Status.READY
        )

        self.message_user(
            request,
            f"{updated} request(s) marked as Ready.",
        )

    @admin.action(
        description="Mark selected requests as Completed"
    )
    def mark_completed(self, request, queryset):

        updated = queryset.update(
            status=BespokeRequest.Status.COMPLETED
        )

        self.message_user(
            request,
            f"{updated} request(s) marked as Completed.",
        )

    @admin.action(
        description="Mark selected requests as Cancelled"
    )
    def mark_cancelled(self, request, queryset):

        updated = queryset.update(
            status=BespokeRequest.Status.CANCELLED
        )

        self.message_user(
            request,
            f"{updated} request(s) marked as Cancelled.",
        )


# =========================================================
# FUTURE ATTACHMENT ADMIN
# =========================================================

@admin.register(BespokeAttachment)
class BespokeAttachmentAdmin(admin.ModelAdmin):

    list_display = (
        "request",
        "original_name",
        "caption",
        "sort_order",
        "uploaded_at",
    )

    search_fields = (
        "request__reference",
        "request__name",
        "request__email",
        "original_name",
        "caption",
    )

    ordering = (
        "-uploaded_at",
    )

    readonly_fields = (
        "uploaded_at",
    )


# =========================================================
# STAFF BESPOKE EMAIL NOTIFICATIONS
# =========================================================

@admin.register(BespokeNotificationPreference)
class BespokeNotificationPreferenceAdmin(
    admin.ModelAdmin
):

    """
    Staff can view notification settings.

    Only superusers may:
    - create notification preferences
    - enable or disable email notifications
    - bulk enable or disable notifications
    - delete notification preferences
    """

    list_display = (
        "staff_member",
        "staff_email",
        "staff_status",
        "email_notifications",
        "updated_at",
    )

    # Gives superusers a checkbox directly in the list.
    list_editable = (
        "email_notifications",
    )

    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
    )

    list_filter = (
        "email_notifications",
        "user__is_active",
        "user__is_staff",
        "user__is_superuser",
    )

    ordering = (
        "user__username",
    )

    list_select_related = (
        "user",
    )

    fields = (
        "user",
        "email_notifications",
        "updated_at",
    )

    readonly_fields = (
        "updated_at",
    )

    actions = (
        "enable_notifications",
        "disable_notifications",
    )

    # =====================================================
    # QUERYSET
    # =====================================================

    def get_queryset(self, request):

        queryset = super().get_queryset(
            request
        )

        return queryset.filter(
            user__is_staff=True,
        ).select_related(
            "user"
        )

    # =====================================================
    # STAFF MEMBER
    # =====================================================

    @admin.display(
        description="Staff Member",
        ordering="user__username",
    )
    def staff_member(self, obj):

        full_name = (
            obj.user.get_full_name()
        )

        if full_name:
            return (
                f"{full_name} "
                f"({obj.user.username})"
            )

        return obj.user.username

    # =====================================================
    # EMAIL
    # =====================================================

    @admin.display(
        description="Email",
        ordering="user__email",
    )
    def staff_email(self, obj):

        if obj.user.email:
            return obj.user.email

        return "No email address"

    # =====================================================
    # ACCOUNT STATUS
    # =====================================================

    @admin.display(
        description="Account",
    )
    def staff_status(self, obj):

        if not obj.user.is_active:

            return format_html(
                (
                    '<span style="'
                    'color:#dc3545;'
                    'font-weight:600;'
                    '">{}</span>'
                ),
                "Inactive",
            )

        if obj.user.is_superuser:

            return format_html(
                (
                    '<span style="'
                    'color:#6610f2;'
                    'font-weight:600;'
                    '">{}</span>'
                ),
                "Superuser",
            )

        return format_html(
            (
                '<span style="'
                'color:#198754;'
                'font-weight:600;'
                '">{}</span>'
            ),
            "Staff",
        )

    # =====================================================
    # BULK EMAIL SWITCHES
    # =====================================================

    @admin.action(
        description="Turn bespoke email notifications ON"
    )
    def enable_notifications(
        self,
        request,
        queryset,
    ):

        if not request.user.is_superuser:

            self.message_user(
                request,
                (
                    "Only a superuser can change "
                    "bespoke notification settings."
                ),
                level=messages.ERROR,
            )

            return

        updated = queryset.update(
            email_notifications=True
        )

        self.message_user(
            request,
            (
                f"Bespoke email notifications enabled "
                f"for {updated} staff member(s)."
            ),
        )

    @admin.action(
        description="Turn bespoke email notifications OFF"
    )
    def disable_notifications(
        self,
        request,
        queryset,
    ):

        if not request.user.is_superuser:

            self.message_user(
                request,
                (
                    "Only a superuser can change "
                    "bespoke notification settings."
                ),
                level=messages.ERROR,
            )

            return

        updated = queryset.update(
            email_notifications=False
        )

        self.message_user(
            request,
            (
                f"Bespoke email notifications disabled "
                f"for {updated} staff member(s)."
            ),
        )

    # =====================================================
    # PERMISSIONS
    # =====================================================

    def has_view_permission(
        self,
        request,
        obj=None,
    ):
        """
        Any staff account may view the settings.
        """

        return request.user.is_staff

    def has_add_permission(
        self,
        request,
    ):
        """
        Only superusers may add preferences.
        """

        return request.user.is_superuser

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        """
        Only superusers may change notification settings.
        """

        return request.user.is_superuser

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        """
        Only superusers may delete preferences.
        """

        return request.user.is_superuser

    # =====================================================
    # USER DROPDOWN
    # =====================================================

    def formfield_for_foreignkey(
        self,
        db_field,
        request,
        **kwargs,
    ):

        if db_field.name == "user":

            kwargs["queryset"] = (
                db_field.remote_field.model.objects
                .filter(
                    is_staff=True,
                )
                .order_by(
                    "username",
                )
            )

        return super().formfield_for_foreignkey(
            db_field,
            request,
            **kwargs,
        )

    # =====================================================
    # REMOVE ACTIONS FROM NON-SUPERUSERS
    # =====================================================

    def get_actions(self, request):

        actions = super().get_actions(
            request
        )

        if not request.user.is_superuser:

            actions.pop(
                "enable_notifications",
                None,
            )

            actions.pop(
                "disable_notifications",
                None,
            )

        return actions
