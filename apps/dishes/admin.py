"""Dishes admin — E5."""

from django.contrib import admin

from apps.dishes.models import Dish, DishAlias, DishIngredient, DishStep


class DishIngredientInline(admin.TabularInline):
    model = DishIngredient
    extra = 1
    fields = ["ingredient", "role", "quantity", "unit", "preparation_note", "position"]
    ordering = ["position", "role"]


class DishAliasInline(admin.TabularInline):
    model = DishAlias
    extra = 1
    fields = ["alias", "language"]


class DishStepInline(admin.TabularInline):
    model = DishStep
    extra = 1
    fields = ["position", "text_en", "text_sw"]
    ordering = ["position"]


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
    readonly_fields = [
        "created_at",
        "updated_at",
        "required_ids",
        "optional_ids",
        "primary_ids",
        "all_ids",
    ]
    inlines = [DishIngredientInline, DishAliasInline, DishStepInline]
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
