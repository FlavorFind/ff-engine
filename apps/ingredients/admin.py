"""Ingredients admin — E6 (Admin v0 for data entry).

Enhancements over E4:
  - Bulk status actions (draft, reviewed, verified, archived)
  - Search by ingredient alias (not just name fields)
  - Autocomplete for category, typical_unit
  - IngredientAllergen registered as standalone admin
"""

from django.contrib import admin

from apps.ingredients.models import (
    Allergen,
    Ingredient,
    IngredientAlias,
    IngredientAllergen,
    IngredientCategory,
    Unit,
)

# ---------------------------------------------------------------------------
# Bulk actions
# ---------------------------------------------------------------------------


def _bulk_set_status(modeladmin, request, queryset, new_status):
    updated = queryset.update(status=new_status)
    modeladmin.message_user(
        request,
        f"{updated} ingredient(s) marked as {new_status}.",
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
# Admins
# ---------------------------------------------------------------------------


@admin.register(IngredientCategory)
class IngredientCategoryAdmin(admin.ModelAdmin):
    list_display = ["name_en", "name_sw", "parent", "created_at"]
    list_filter = ["parent"]
    search_fields = ["name_en", "name_sw", "slug"]
    prepopulated_fields = {"slug": ("name_en",)}
    ordering = ["name_en"]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "kind", "to_base_factor"]
    list_filter = ["kind"]
    search_fields = ["code", "name"]
    ordering = ["kind", "code"]


@admin.register(Allergen)
class AllergenAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


class IngredientAliasInline(admin.TabularInline):
    model = IngredientAlias
    extra = 1
    fields = ["alias", "normalized_alias", "language", "is_misspelling"]


class IngredientAllergenInline(admin.TabularInline):
    model = IngredientAllergen
    extra = 1
    fields = ["allergen", "notes"]
    autocomplete_fields = ["allergen"]


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ["name_en", "name_sw", "category", "kind", "is_staple", "status"]
    list_filter = ["status", "kind", "is_staple", "category"]
    search_fields = ["name_en", "name_sw", "slug"]
    prepopulated_fields = {"slug": ("name_en",)}
    autocomplete_fields = ["category", "typical_unit", "source"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [IngredientAliasInline, IngredientAllergenInline]
    actions = [mark_draft, mark_reviewed, mark_verified, mark_archived]
    ordering = ["name_en"]
    fieldsets = [
        (None, {"fields": ["slug", "name_en", "name_sw", "category", "kind", "is_staple"]}),
        ("Measurement", {"fields": ["typical_unit"], "classes": ["collapse"]}),
        ("Curation", {"fields": ["status", "source", "notes"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"], "classes": ["collapse"]}),
    ]

    def get_search_results(self, request, queryset, search_term):
        """Search by name, slug, or any alias string."""
        queryset, may_have_duplicates = super().get_search_results(request, queryset, search_term)
        if search_term:
            alias_matches = self.model.objects.filter(aliases__alias__icontains=search_term)
            queryset = queryset.union(alias_matches)
            may_have_duplicates = True
        return queryset, may_have_duplicates


@admin.register(IngredientAlias)
class IngredientAliasAdmin(admin.ModelAdmin):
    list_display = ["alias", "language", "is_misspelling", "ingredient"]
    list_filter = ["language", "is_misspelling"]
    search_fields = ["alias", "normalized_alias", "ingredient__name_en"]
    autocomplete_fields = ["ingredient"]
    ordering = ["alias"]


@admin.register(IngredientAllergen)
class IngredientAllergenAdmin(admin.ModelAdmin):
    list_display = ["ingredient", "allergen", "notes"]
    list_filter = ["allergen"]
    search_fields = ["ingredient__name_en", "allergen__name"]
    autocomplete_fields = ["ingredient", "allergen"]
    ordering = ["ingredient__name_en"]
