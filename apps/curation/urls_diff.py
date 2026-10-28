"""Curation URL routing — dataset diff endpoint (E54)."""

from django.urls import path

from apps.curation import views_diff

urlpatterns = [
    # E54 — Dataset diff (requires read:catalog scope)
    path("diff/", views_diff.dataset_diff, name="dataset-diff"),
]
