"""E39 — Admin for NutritionFact."""

from django.contrib import admin

from apps.nutrition.models import NutritionFact


@admin.register(NutritionFact)
class NutritionFactAdmin(admin.ModelAdmin):
    list_display = [
        "ingredient",
        "kcal",
        "protein_g",
        "carbs_g",
        "fat_g",
        "fibre_g",
        "sodium_mg",
        "confidence",
        "source",
    ]
    list_filter = ["confidence"]
    search_fields = ["ingredient__name_en", "ingredient__name_sw", "source"]
    ordering = ["ingredient__name_en"]
    readonly_fields = ["created_at", "updated_at"]
