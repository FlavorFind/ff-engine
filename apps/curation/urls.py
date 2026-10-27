"""Curation URL routing — internal endpoints."""

from django.urls import path

from apps.curation import views, views_diff

urlpatterns = [
    # E52 — Community submissions
    path("submissions/", views.create_submission, name="create-submission"),
    # E54 — Dataset diff
    path("diff/", views_diff.dataset_diff, name="dataset-diff"),
]
