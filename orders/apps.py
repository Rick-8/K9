from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orders"

    def ready(self):
        """
        Load order signals when Django starts.

        This ensures every bespoke order automatically
        receives its staff workflow/job record.
        """
        from . import signals  # noqa: F401
