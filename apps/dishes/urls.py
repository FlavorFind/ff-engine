"""Dishes app URL routing — advisor endpoints (E29, E30) + catalogue (E35)."""

from django.urls import path

from apps.dishes.views_advisor import dish_missing, dish_pairings, dish_substitutions
from apps.dishes.views_catalogue import dish_catalogue

urlpatterns = [
    path("", dish_catalogue, name="dish-catalogue"),
    path("<uuid:dish_id>/pairings/", dish_pairings, name="dish-pairings"),
    path("<uuid:dish_id>/substitutions/", dish_substitutions, name="dish-substitutions"),
    path("<uuid:dish_id>/missing/", dish_missing, name="dish-missing"),
]
