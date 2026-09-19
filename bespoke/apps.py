from django.apps import AppConfig


class BespokeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "bespoke"

    def ready(self):
        from . import signals  # noqa: F401
