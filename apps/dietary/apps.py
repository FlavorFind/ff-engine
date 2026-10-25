from django.apps import AppConfig


class DietaryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dietary"

    def ready(self):
        import apps.dietary.signals  # noqa: F401
