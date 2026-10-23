"""API URL routing."""
from django.urls import path

from apps.api import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("meta/version/", views.version, name="version"),
]
