"""E28 — Substitutions admin."""

from django.contrib import admin

from apps.substitutions.models import Substitution


@admin.register(Substitution)
class SubstitutionAdmin(admin.ModelAdmin):
    list_display = ["ingredient", "substitute", "quality", "ratio", "context_dish"]
    list_filter = ["quality"]
    search_fields = ["ingredient__name_en", "substitute__name_en", "context_dish__name_en"]
    autocomplete_fields = ["ingredient", "substitute", "context_dish"]
    ordering = ["ingredient__name_en", "quality"]
