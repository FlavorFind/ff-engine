"""E28 — Pairings admin."""

from django.contrib import admin

from apps.pairings.models import Pairing


@admin.register(Pairing)
class PairingAdmin(admin.ModelAdmin):
    list_display = ["dish", "paired_dish", "paired_label", "pairing_type", "strength"]
    list_filter = ["pairing_type", "strength"]
    search_fields = ["dish__name_en", "paired_dish__name_en", "paired_label"]
    autocomplete_fields = ["dish", "paired_dish"]
    ordering = ["dish__name_en", "-strength"]
    fieldsets = [
        (None, {"fields": ["dish", "pairing_type", "strength"]}),
        ("Target", {"fields": ["paired_dish", "paired_label"]}),
        ("Notes", {"fields": ["note"]}),
    ]
