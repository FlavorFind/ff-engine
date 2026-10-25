"""Regions app URL routing — E35."""

from django.urls import path

from apps.regions.views import region_list

urlpatterns = [
    path("", region_list, name="region-list"),
]
