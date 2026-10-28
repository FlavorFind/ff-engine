"""API URL routing."""

from django.urls import include, path

from apps.api import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("meta/version/", views.version, name="version"),
    path("ingredients/", include("apps.ingredients.urls")),
    path("search/", include("apps.search.urls")),
    path("dishes/", include("apps.dishes.urls")),
    path("dishes/", include("apps.nutrition.urls")),
    path("regions/", include("apps.regions.urls")),
    # E52: community submissions intake (internal:curation scope)
    path("internal/", include("apps.curation.urls_submissions")),
    # E54: dataset diff endpoint (read:catalog scope)
    path("datasets/", include("apps.curation.urls_diff")),
]
