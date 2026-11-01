from django.contrib import admin

from .models import Order, OrderNote


# =========================================================
# ORDER NOTES INLINE
# =========================================================

class OrderNoteInline(admin.TabularInline):
    """
    Display the communication / notes history directly
    inside each order.
    """

    model = OrderNote

    extra = 0

    fields = (
        "content",
        "author",
        "created_at",
    )

    readonly_fields = (
        "created_at",
    )

    ordering = (
        "-created_at",
    )

    show_change_link = True


# =========================================================
# ORDER ADMIN
# =========================================================

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Main administration screen for K9 customer orders.
    """

    # -----------------------------------------------------
    # ORDER LIST
    # -----------------------------------------------------

    list_display = (
        "reference_number",
        "customer_name",
        "customer_email",
        "order_type",
        "status",
        "created_at",
        "completed_at",
    )

    list_display_links = (
        "reference_number",
        "customer_name",
    )

    # -----------------------------------------------------
    # FILTERING
    # -----------------------------------------------------

    list_filter = (
        "status",
        "order_type",
        "created_at",
        "completed_at",
    )

    # -----------------------------------------------------
    # SEARCH
    # -----------------------------------------------------

    search_fields = (
        "reference_number",
        "customer_name",
        "customer_email",
        "customer_phone",
    )

    # -----------------------------------------------------
    # READ ONLY
    # -----------------------------------------------------

    readonly_fields = (
        "reference_number",
        "created_at",
        "updated_at",
        "completed_at",
    )

    # -----------------------------------------------------
    # ORDERING
    # -----------------------------------------------------

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"

    # -----------------------------------------------------
    # PAGE LAYOUT
    # -----------------------------------------------------

    fieldsets = (

        (
            "Order",
            {
                "fields": (
                    "reference_number",
                    "order_type",
                    "status",
                )
            },
        ),

        (
            "Customer",
            {
                "fields": (
                    "customer_name",
                    "customer_email",
                    "customer_phone",
                    "shipping_address",
                )
            },
        ),

        (
            "Bespoke Order",
            {
                "fields": (
                    "bespoke_request",
                ),
                "classes": (
                    "collapse",
                ),
            },
        ),

        (
            "Order Dates",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "completed_at",
                )
            },
        ),

    )

    # -----------------------------------------------------
    # INLINE ORDER COMMUNICATION / NOTES
    # -----------------------------------------------------

    inlines = [
        OrderNoteInline,
    ]

    # -----------------------------------------------------
    # ADMIN PERFORMANCE / USABILITY
    # -----------------------------------------------------

    list_per_page = 50

    save_on_top = True


# =========================================================
# ORDER NOTE ADMIN
# =========================================================

@admin.register(OrderNote)
class OrderNoteAdmin(admin.ModelAdmin):
    """
    Separate admin view for searching and reviewing
    order notes / communication history.
    """

    list_display = (
        "order",
        "author",
        "short_content",
        "created_at",
    )

    list_filter = (
        "created_at",
    )

    search_fields = (
        "order__reference_number",
        "order__customer_name",
        "order__customer_email",
        "content",
    )

    readonly_fields = (
        "created_at",
    )

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"

    list_per_page = 50

    @admin.display(
        description="Note",
    )
    def short_content(self, obj):
        """
        Keep long notes tidy on the admin list screen.
        """

        if len(obj.content) > 80:
            return f"{obj.content[:80]}..."

        return obj.content
