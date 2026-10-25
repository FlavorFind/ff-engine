"""
E31 — Dietary tag and dish dietary tag models.

Blueprint section 8 (The Safety Filter):
  - Tags are derived automatically from ingredient flags (Lock 1).
  - A reviewer can override a tag with a recorded reason (Lock 2).
  - The engine always reports how a tag was set (derived or manual).

Architecture section 5:
  dietary_tag(id, slug, name)
  dish_dietary_tag(dish_id, tag_id, source [derived, manual])

E32 — Manual overrides: DishDietaryTag carries reason and is logged to ChangeLog.
"""

from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class DietaryTag(TimeStampedModel):
    """
    A dietary or allergen label applied to dishes.

    Examples: vegetarian, vegan, gluten-free, contains-pork, nut-free, dairy-free, egg-free.
    Derived automatically from ingredient allergen/kind flags, or set manually with a reason.
    """

    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_allergen_tag = models.BooleanField(
        default=False,
        help_text="True for allergen-based tags (e.g. contains-nuts). These always beat everything.",
    )

    class Meta:
        db_table = "dietary_tag"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class DishDietaryTag(TimeStampedModel):
    """
    Link a DietaryTag to a Dish, recording whether it was derived or manually set.

    E31 — derived: set automatically by derive_dietary_tags().
    E32 — manual: set by a reviewer with a reason; logged to ChangeLog.

    Blueprint two-lock principle:
      Lock 1 (automatic): derived from ingredient flags, cannot be forgotten.
      Lock 2 (human): reviewer overrides with reason; every override audited.
    """

    class Source(models.TextChoices):
        DERIVED = "derived", "Derived from ingredients"
        MANUAL = "manual", "Manual override"

    dish = models.ForeignKey(
        "dishes.Dish",
        on_delete=models.CASCADE,
        related_name="dietary_tags",
    )
    tag = models.ForeignKey(
        DietaryTag,
        on_delete=models.CASCADE,
        related_name="dish_links",
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.DERIVED,
        db_index=True,
    )
    reason = models.TextField(
        blank=True,
        help_text="Required when source=manual. Explains why the tag was overridden.",
    )
    set_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dietary_overrides",
        help_text="The reviewer who set this manual override.",
    )

    class Meta:
        db_table = "dish_dietary_tag"
        unique_together = [("dish", "tag")]
        indexes = [
            models.Index(fields=["dish", "source"]),
            models.Index(fields=["tag"]),
        ]

    def __str__(self) -> str:
        return f"{self.dish.name_en} — {self.tag.name} [{self.source}]"
