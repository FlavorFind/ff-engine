"""
E28 — Substitution model.

A suggested replacement for an ingredient, with a quality grade.

Architecture section 5 (Data Model):
  substitution(id, ingredient_id, substitute_id, ratio, quality [great, ok, emergency],
               context_dish_id [nullable], note)

Blueprint section 7 (The Advisor):
  - Great: almost no difference in the dish (spinach for sukuma wiki).
  - OK: noticeably different but works well (cabbage for sukuma wiki).
  - Emergency: only if no other choice; a warning is shown.
  - context_dish_id: a substitution can be general (valid everywhere) or tied to
    a specific dish (spinach works for sukuma wiki in a stew but not every recipe).
"""

from django.db import models

from apps.core.models import TimeStampedModel


class Substitution(TimeStampedModel):
    """
    ingredient_id → substitute_id with quality grade.
    """

    class Quality(models.TextChoices):
        GREAT = "great", "Great — almost no difference"
        OK = "ok", "OK — noticeably different but works"
        EMERGENCY = "emergency", "Emergency — only if no other choice"

    ingredient = models.ForeignKey(
        "ingredients.Ingredient",
        on_delete=models.CASCADE,
        related_name="substitutions_as_original",
        help_text="The ingredient being replaced.",
    )
    substitute = models.ForeignKey(
        "ingredients.Ingredient",
        on_delete=models.CASCADE,
        related_name="substitutions_as_substitute",
        help_text="The replacement ingredient.",
    )
    ratio = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        default=1.0,
        help_text="How much substitute to use per 1 unit of the original (e.g. 0.75 means 75%).",
    )
    quality = models.CharField(
        max_length=20,
        choices=Quality.choices,
        default=Quality.OK,
        db_index=True,
    )
    context_dish = models.ForeignKey(
        "dishes.Dish",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="substitutions",
        help_text="If set, this substitution only applies in the context of this dish.",
    )
    note = models.TextField(blank=True)

    class Meta:
        db_table = "substitution"
        ordering = ["quality", "ingredient__name_en"]
        indexes = [
            models.Index(fields=["ingredient", "quality"]),
            models.Index(fields=["context_dish"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["ingredient", "substitute", "context_dish"],
                name="unique_substitution_per_context",
                # nulls_distinct=False treats two rows with NULL context_dish as duplicates.
                # This is the correct behaviour: a general substitution (no context) should
                # exist at most once per (ingredient, substitute) pair.
                # Requires PostgreSQL 15+ (released Oct 2022). Docker image uses postgres:16.
                #
                # Two-index fallback for PG < 15 (not needed here, documented for reference):
                #   1. UniqueConstraint(fields=[ingredient, substitute],
                #                       condition=Q(context_dish__isnull=True),
                #                       name="unique_sub_no_context")
                #   2. UniqueConstraint(fields=[ingredient, substitute, context_dish],
                #                       condition=Q(context_dish__isnull=False),
                #                       name="unique_sub_with_context")
                nulls_distinct=False,
            ),
        ]

    def __str__(self) -> str:
        ctx = f" (in {self.context_dish.name_en})" if self.context_dish else ""
        return f"{self.ingredient.name_en} → {self.substitute.name_en} [{self.quality}]{ctx}"
