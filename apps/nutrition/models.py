"""
E39 — Nutrition data model.

NutritionFact stores macro and micro nutrient values per 100 g of a
single ingredient.  The endpoint sums these per-serving when a dish
slug is requested.

Architecture references:
  Blueprint section 8 — nutrition facts, dietary filters
  Table: nutrition_fact(id, ingredient_id, kcal, protein_g, carbs_g,
         fat_g, fibre_g, sodium_mg, source, confidence, created_at,
         updated_at)
"""

from __future__ import annotations

from django.db import models

from apps.ingredients.models import Ingredient


class NutritionFact(models.Model):
    """
    Nutritional values per 100 g of a single ingredient.

    confidence:
      high   — lab-verified or official USDA / KENFRI data
      medium — packaged food label, reputable source
      low    — estimated / interpolated
    """

    class Confidence(models.TextChoices):
        HIGH = "high", "High (lab / official)"
        MEDIUM = "medium", "Medium (label / trusted source)"
        LOW = "low", "Low (estimate)"

    ingredient = models.OneToOneField(
        Ingredient,
        on_delete=models.CASCADE,
        related_name="nutrition",
    )

    # macros — per 100 g
    kcal = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text="Kilocalories per 100 g.",
    )
    protein_g = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text="Protein in grams per 100 g.",
    )
    carbs_g = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text="Total carbohydrates in grams per 100 g.",
    )
    fat_g = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        help_text="Total fat in grams per 100 g.",
    )

    # micros — per 100 g
    fibre_g = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
        help_text="Dietary fibre in grams per 100 g.",
    )
    sodium_mg = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Sodium in milligrams per 100 g.",
    )

    # provenance
    source = models.CharField(
        max_length=200,
        help_text="Data source (e.g. USDA FoodData Central, KENFRI 2019).",
    )
    confidence = models.CharField(
        max_length=10,
        choices=Confidence.choices,
        default=Confidence.MEDIUM,
        db_index=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "nutrition_fact"
        ordering = ["ingredient__name_en"]

    def __str__(self) -> str:
        return f"{self.ingredient.name_en} — {self.kcal} kcal/100 g"
