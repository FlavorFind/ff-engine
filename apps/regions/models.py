"""
Region models.

Architecture section 5 (Data Model):
  region       id, slug, name, type [county, coast, cuisine], parent_id
  dish_region  dish_id, region_id  (many-to-many through)

Blueprint section 4 (The Knowledge Library):
  Region — a county, the coast or a cuisine group.
  Examples: Coastal, Luo, Kikuyu.
"""

from django.db import models
from django.utils.text import slugify

from apps.core.models import TimeStampedModel


class Region(TimeStampedModel):
    """
    A geographic or culinary region.

    Architecture: region(id, slug, name, type [county, coast, cuisine], parent_id)
    """

    class Type(models.TextChoices):
        COUNTY = "county", "County"
        COAST = "coast", "Coast"
        CUISINE = "cuisine", "Cuisine group"

    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=Type.choices)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    description = models.TextField(blank=True)

    class Meta:
        db_table = "region"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.name} ({self.get_type_display()})"


class DishRegion(models.Model):
    """
    Links a dish to a region.

    Architecture: dish_region(dish_id, region_id)
    Explicit through table so extra metadata can be added later (e.g. is_primary_region).
    The Dish FK uses a string reference to avoid circular imports.
    """

    dish = models.ForeignKey(
        "dishes.Dish",
        on_delete=models.CASCADE,
        related_name="dish_regions",
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        related_name="dish_regions",
    )

    class Meta:
        db_table = "dish_region"
        unique_together = [("dish", "region")]

    def __str__(self) -> str:
        return f"{self.dish} — {self.region}"
