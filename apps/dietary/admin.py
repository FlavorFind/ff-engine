"""E31/E32 — Dietary admin with manual override support."""

from django.contrib import admin

from apps.dietary.models import DietaryTag, DishDietaryTag


@admin.register(DietaryTag)
class DietaryTagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_allergen_tag"]
    list_filter = ["is_allergen_tag"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(DishDietaryTag)
class DishDietaryTagAdmin(admin.ModelAdmin):
    list_display = ["dish", "tag", "source", "set_by", "created_at"]
    list_filter = ["source", "tag"]
    search_fields = ["dish__name_en", "tag__name"]
    autocomplete_fields = ["dish", "tag", "set_by"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = [
        (None, {"fields": ["dish", "tag", "source"]}),
        ("Override details", {"fields": ["reason", "set_by"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    ]

    def save_model(self, request, obj, form, change):
        """Log manual overrides to ChangeLog (E32)."""
        if obj.source == DishDietaryTag.Source.MANUAL and not obj.set_by:
            obj.set_by = request.user
        super().save_model(request, obj, form, change)
        if obj.source == DishDietaryTag.Source.MANUAL:
            from apps.curation.models import ChangeLog

            ChangeLog.objects.create(
                object_type="DishDietaryTag",
                object_id=str(obj.pk),
                action="update",
                diff={
                    "tag": obj.tag.slug,
                    "reason": obj.reason,
                    "dish": obj.dish.slug,
                    "source": "manual",
                },
                actor=request.user,
                reason=obj.reason,
            )
