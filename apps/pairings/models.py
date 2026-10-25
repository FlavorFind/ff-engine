"""
E28 — Pairing model.

A recommendation of what goes with a dish (side, drink, dessert, starter).

Architecture section 5 (Data Model):
  pairing(id, dish_id, paired_dish_id [nullable], paired_label,
          type [side, drink, dessert, starter], strength 1-5, note)

Blueprint section 7 (The Advisor):
  - Strength 1 (possible) to 5 (classic, almost always served together).
  - Directional: ugali → sukuma wiki (5), not the other way around.
  - paired_dish_id is nullable: a pairing can point to a dish in the library
    OR just a label (e.g. "chai") when it is not a full recipe.
  - Hotels filter pairings to what is on their menu, which is why strength matters.
"""

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class Pairing(TimeStampedModel):
    """
    Directional recommendation: dish → paired_dish (or paired_label).

    Blueprint pairing types: side, drink, dessert, starter.
    """

    class PairingType(models.TextChoices):
        SIDE = "side", "Side dish"
        DRINK = "drink", "Drink"
        DESSERT = "dessert", "Dessert"
        STARTER = "starter", "Starter"

    dish = models.ForeignKey(
        "dishes.Dish",
        on_delete=models.CASCADE,
        related_name="pairings",
        help_text="The dish that is being paired from.",
    )
    paired_dish = models.ForeignKey(
        "dishes.Dish",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paired_by",
        help_text="The dish being paired to (optional — use paired_label instead for non-dishes).",
    )
    paired_label = models.CharField(
        max_length=150,
        blank=True,
        help_text="Free-text label when the pairing is not a full dish (e.g. 'chai', 'soda').",
    )
    pairing_type = models.CharField(
        max_length=20,
        choices=PairingType.choices,
        default=PairingType.SIDE,
        db_index=True,
    )
    strength = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="1=possible/rarely served, 5=classic/almost always served together.",
    )
    note = models.TextField(blank=True)

    class Meta:
        db_table = "pairing"
        ordering = ["-strength", "pairing_type"]
        indexes = [
            models.Index(fields=["dish", "pairing_type"]),
            models.Index(fields=["strength"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(paired_dish__isnull=False) | ~models.Q(paired_label=""),
                name="pairing_has_dish_or_label",
            ),
        ]

    def __str__(self) -> str:
        target = self.paired_dish.name_en if self.paired_dish else self.paired_label
        return f"{self.dish.name_en} → {target} [{self.pairing_type}] ({self.strength}/5)"
