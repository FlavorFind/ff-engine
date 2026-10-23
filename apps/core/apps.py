from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"

    def ready(self):
        """Customise the admin site header, title and index title."""
        from django.contrib import admin

        admin.site.site_header = "Flavor Find — Engine Admin"
        admin.site.site_title = "Flavor Find Engine"
        admin.site.index_title = "Curation"
