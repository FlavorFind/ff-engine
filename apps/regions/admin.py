"""Regions admin — E5."""

from django.contrib import admin

from apps.regions.models import DishRegion, Region


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ["name", "type", "parent", "created_at"]
    list_filter = ["type"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["name"]


@admin.register(DishRegion)
class DishRegionAdmin(admin.ModelAdmin):
    list_display = ["dish", "region"]
    list_filter = ["region"]
    search_fields = ["dish__name_en", "region__name"]
