from django.contrib import admin

from .models import SiteBanner


@admin.register(SiteBanner)
class SiteBannerAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "enabled",
        "display_mode",
        "short_text",
        "updated_at",
    )

    list_filter = (
        "enabled",
        "display_mode",
    )

    readonly_fields = (
        "updated_at",
    )

    def short_text(self, obj):
        if len(obj.text) > 60:
            return f"{obj.text[:60]}..."
        return obj.text

    short_text.short_description = "Banner Text"
