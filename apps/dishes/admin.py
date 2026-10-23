"""Dishes admin — E6 (Admin v0 for data entry).

Enhancements over E5:
  - Bulk status actions (draft, reviewed, verified, archived)
  - Search by dish alias (not just name_en/name_sw/slug)
  - Autocomplete fields for source
  - Region inline (DishRegion) so a curator adds regions from the Dish page
  - save_model hook calls rebuild_search_arrays on every Dish save
  - DishIngredient/DishAlias/DishStep registered as standalone admins
"""

from django.contrib import admin

from apps.dishes.models import Dish, DishAlias, DishIngredient, DishStep
from apps.regions.models import DishRegion

# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------


class DishIngredientInline(admin.TabularInline):
    model = DishIngredient
    extra = 2
    fields = ["ingredient", "role", "quantity", "unit", "preparation_note", "position"]
    ordering = ["position", "role"]
    autocomplete_fields = ["ingredient", "unit"]


class DishAliasInline(admin.TabularInline):
    model = DishAlias
    extra = 1
    fields = ["alias", "language"]


class DishStepInline(admin.TabularInline):
    model = DishStep
    extra = 1
    fields = ["position", "text_en", "text_sw"]
    ordering = ["position"]


class DishRegionInline(admin.TabularInline):
    model = DishRegion
    extra = 1
    fields = ["region"]
    autocomplete_fields = ["region"]


# ---------------------------------------------------------------------------
# Bulk actions
# ---------------------------------------------------------------------------


def _bulk_set_status(modeladmin, request, queryset, new_status):
    updated = queryset.update(status=new_status)
    modeladmin.message_user(
        request,
        f"{updated} dish(es) marked as {new_status}.",
    )


@admin.action(description="Mark selected as Draft")
def mark_draft(modeladmin, request, queryset):
    _bulk_set_status(modeladmin, request, queryset, "draft")


@admin.action(description="Mark selected as Reviewed")
def mark_reviewed(modeladmin, request, queryset):
    _bulk_set_status(modeladmin, request, queryset, "reviewed")


@admin.action(description="Mark selected as Verified")
def mark_verified(modeladmin, request, queryset):
    _bulk_set_status(modeladmin, request, queryset, "verified")


@admin.action(description="Mark selected as Archived")
def mark_archived(modeladmin, request, queryset):
    _bulk_set_status(modeladmin, request, queryset, "archived")


# ---------------------------------------------------------------------------
# DishAdmin
# ---------------------------------------------------------------------------


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = [
        "name_en",
        "name_sw",
        "meal_type",
        "course",
        "quality_level",
        "status",
        "popularity",
    ]
    list_filter = ["status", "quality_level", "meal_type", "course", "spice_level", "difficulty"]
    search_fields = ["name_en", "name_sw", "slug"]
    prepopulated_fields = {"slug": ("name_en",)}
    autocomplete_fields = ["source"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "required_ids",
        "optional_ids",
        "primary_ids",
        "all_ids",
    ]
    inlines = [
        DishIngredientInline,
        DishAliasInline,
        DishStepInline,
        DishRegionInline,
    ]
    actions = [mark_draft, mark_reviewed, mark_verified, mark_archived]
    ordering = ["name_en"]
    fieldsets = [
        (None, {"fields": ["slug", "name_en", "name_sw", "description"]}),
        (
            "Classification",
            {
                "fields": [
                    "meal_type",
                    "course",
                    "spice_level",
                    "difficulty",
                    "prep_min",
                    "cook_min",
                    "servings",
                ]
            },
        ),
        (
            "Curation",
            {"fields": ["quality_level", "status", "popularity", "source"]},
        ),
        (
            "Search arrays (auto-managed)",
            {
                "fields": ["required_ids", "optional_ids", "primary_ids", "all_ids"],
                "classes": ["collapse"],
            },
        ),
        ("Timestamps", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]

    def save_related(self, request, form, formsets, change):
        """
        Save inline formsets, then rebuild search arrays.

        save_related runs AFTER inlines are saved, so DishIngredient rows
        are already in the database when rebuild_search_arrays() runs.
        """
        super().save_related(request, form, formsets, change)
        form.instance.rebuild_search_arrays()

    def get_search_results(self, request, queryset, search_term):
        """Search by dish name, slug, or any alias string."""
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        if search_term:
            alias_matches = self.model.objects.filter(aliases__alias__icontains=search_term)
            queryset = queryset.union(alias_matches)
            may_have_duplicates = True
        return queryset, may_have_duplicates


# ---------------------------------------------------------------------------
# Standalone admins for related models
# ---------------------------------------------------------------------------


@admin.register(DishIngredient)
class DishIngredientAdmin(admin.ModelAdmin):
    list_display = ["dish", "ingredient", "role", "quantity", "unit", "position"]
    list_filter = ["role", "dish", "ingredient"]
    search_fields = ["dish__name_en", "ingredient__name_en", "preparation_note"]
    autocomplete_fields = ["dish", "ingredient", "unit"]
    ordering = ["dish__name_en", "position", "role"]


@admin.register(DishAlias)
class DishAliasAdmin(admin.ModelAdmin):
    list_display = ["alias", "language", "dish"]
    list_filter = ["language"]
    search_fields = ["alias", "dish__name_en"]
    autocomplete_fields = ["dish"]
    ordering = ["alias"]


@admin.register(DishStep)
class DishStepAdmin(admin.ModelAdmin):
    list_display = ["dish", "position", "text_en"]
    list_filter = ["dish"]
    search_fields = ["text_en", "text_sw", "dish__name_en"]
    autocomplete_fields = ["dish"]
    ordering = ["dish__name_en", "position"]
