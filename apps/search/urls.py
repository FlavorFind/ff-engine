"""Search app URL routing."""

from django.urls import path

from apps.search import views

urlpatterns = [
    path("by-ingredients", views.search_by_ingredients, name="search-by-ingredients"),
]
