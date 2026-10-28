"""Ingredients app URL routing."""

from django.urls import path

from apps.ingredients import views

urlpatterns = [
    path("", views.ingredient_list, name="ingredient-list"),
    path("resolve", views.resolve, name="ingredients-resolve"),
    path("<slug:slug>/", views.ingredient_detail, name="ingredient-detail"),
]
