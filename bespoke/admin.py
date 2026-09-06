from django.contrib import admin
from .models import BespokeRequest


@admin.register(BespokeRequest)
class BespokeRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'item_type', 'email', 'created_at')
    search_fields = ('name', 'email', 'item_type')
