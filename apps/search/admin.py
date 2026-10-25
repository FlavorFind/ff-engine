"""E43 — Admin for ZeroResultQuery."""

from django.contrib import admin

from apps.search.models import ZeroResultQuery


@admin.register(ZeroResultQuery)
class ZeroResultQueryAdmin(admin.ModelAdmin):
    list_display = ["raw_input", "count", "last_seen", "normalised_input"]
    list_filter = ["last_seen"]
    search_fields = ["raw_input", "normalised_input"]
    ordering = ["-count", "-last_seen"]
    readonly_fields = ["normalised_input", "count", "last_seen"]
