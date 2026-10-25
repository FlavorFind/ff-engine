from django.apps import AppConfig


class ClientsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.clients"
    verbose_name = "API Clients"

    def ready(self):
        # Register the OpenAPI authentication extension for drf-spectacular.
        import apps.clients.openapi  # noqa: F401
