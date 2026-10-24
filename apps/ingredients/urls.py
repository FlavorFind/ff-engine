"""Ingredients app URL routing."""

from django.urls import path

from apps.ingredients import views

urlpatterns = [
    path("resolve", views.resolve, name="ingredients-resolve"),
]
