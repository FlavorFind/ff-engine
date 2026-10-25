"""Nutrition app URL routing — E39."""

from django.urls import path

from apps.nutrition.views import dish_nutrition

urlpatterns = [
    path("<slug:slug>/nutrition/", dish_nutrition, name="dish-nutrition"),
]
