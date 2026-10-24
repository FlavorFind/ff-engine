"""API URL routing."""

from django.urls import include, path

from apps.api import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("meta/version/", views.version, name="version"),
    path("search/", include("apps.search.urls")),
]
