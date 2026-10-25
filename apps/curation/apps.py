from django.apps import AppConfig


class CurationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.curation"

    def ready(self):
        # Import signals to register the post_save receiver that clears
        # the search cache when a new DatasetRelease is published.
        from apps.curation import signals  # noqa: F401
