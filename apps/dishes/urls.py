"""Dishes app URL routing — advisor endpoints (E29, E30) + catalogue (E35)."""

from django.urls import path

from apps.dishes.views_advisor import dish_missing, dish_pairings, dish_substitutions
from apps.dishes.views_catalogue import dish_catalogue, dish_detail

urlpatterns = [
    path("", dish_catalogue, name="dish-catalogue"),
    path("<slug:slug>/", dish_detail, name="dish-detail"),
    path("<slug:slug>/pairings/", dish_pairings, name="dish-pairings"),
    path("<slug:slug>/substitutions/", dish_substitutions, name="dish-substitutions"),
    path("<slug:slug>/missing/", dish_missing, name="dish-missing"),
]
