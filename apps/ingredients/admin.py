"""
Ingredients admin — E4.

Registers all ingredient models with useful list displays and filters.
Full inline rows and bulk status actions come in E6 (Admin v0).
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


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ["name_en", "name_sw", "category", "kind", "is_staple", "status"]
    list_filter = ["status", "kind", "is_staple", "category"]
    search_fields = ["name_en", "name_sw", "slug"]
    prepopulated_fields = {"slug": ("name_en",)}
    readonly_fields = ["created_at", "updated_at"]
    inlines = [IngredientAliasInline, IngredientAllergenInline]
    ordering = ["name_en"]


@admin.register(IngredientAlias)
class IngredientAliasAdmin(admin.ModelAdmin):
    list_display = ["alias", "language", "is_misspelling", "ingredient"]
    list_filter = ["language", "is_misspelling"]
    search_fields = ["alias", "normalized_alias", "ingredient__name_en"]
    ordering = ["alias"]
