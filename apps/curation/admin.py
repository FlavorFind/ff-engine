"""Curation admin — Source, ChangeLog, DatasetRelease."""

from django.contrib import admin

from apps.curation.models import ChangeLog, DatasetRelease, Source


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "permission_status", "contributor", "created_at"]
    list_filter = ["kind", "permission_status"]
    search_fields = ["title", "contributor", "citation"]
    ordering = ["title"]


@admin.register(ChangeLog)
class ChangeLogAdmin(admin.ModelAdmin):
    list_display = ["object_type", "object_id", "action", "actor", "created_at"]
    list_filter = ["action", "object_type"]
    search_fields = ["object_type", "object_id", "actor__username"]
    readonly_fields = ["object_type", "object_id", "action", "diff", "actor", "created_at"]
    ordering = ["-created_at"]

    def has_add_permission(self, request):
        return False  # audit log is append-only

    def has_change_permission(self, request, obj=None):
        return False  # audit log is immutable

    def has_delete_permission(self, request, obj=None):
        return False  # audit log is immutable


@admin.register(DatasetRelease)
class DatasetReleaseAdmin(admin.ModelAdmin):
    list_display = ["version", "released_by", "created_at"]
    search_fields = ["version", "notes"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]
