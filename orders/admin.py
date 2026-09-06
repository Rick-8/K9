from django.contrib import admin
from .models import Order, OrderNote


class OrderNoteInline(admin.TabularInline):
    model = OrderNote
    extra = 1 # Shows one blank row for a new note by default
    readonly_fields = ('created_at',)
    fields = ('content', 'author', 'created_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('reference_number', 'customer_name', 'order_type', 'status', 'created_at', 'completed_at')
    list_filter = ('status', 'order_type')
    search_fields = ('reference_number', 'customer_name', 'customer_email')
    readonly_fields = ('reference_number', 'created_at', 'updated_at', 'completed_at')

    # Embeds the notes system directly inside the order
    inlines = [OrderNoteInline]
