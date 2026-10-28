"""Curation URL routing — internal submission endpoints (E52)."""

from django.urls import path

from apps.curation import views

urlpatterns = [
    # E52 — Community submissions (requires internal:curation scope)
    path("submissions/", views.create_submission, name="create-submission"),
]
