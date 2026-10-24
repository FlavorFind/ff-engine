from django.apps import AppConfig


class SearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.search"
    verbose_name = "Search"

    def ready(self):
        # Connect DishIngredient signals so search arrays auto-rebuild.
        import apps.search.signals  # noqa: F401
