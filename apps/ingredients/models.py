"""
Ingredient models — the taxonomy and naming layer.

Architecture section 5 (Data Model) tables implemented here:
  ingredient_category   id, slug, name_en, name_sw, parent_id
  ingredient            id, slug, name_en, name_sw, category_id, kind, is_staple,
                        typical_unit, status, source_id, notes
  ingredient_alias      id, ingredient_id, alias, normalized_alias, language,
                        is_misspelling
  allergen              id, slug, name
  ingredient_allergen   ingredient_id, allergen_id  (many-to-many through)
  unit                  id, code, kind, to_base_factor

Blueprint section 4 (The Knowledge Library):
  - Each ingredient has one preferred English name and one preferred Swahili name.
  - Aliases carry a language tag and a misspelling flag.
  - Staples (water, salt, cooking oil) are flagged so they never block a match.
  - Status: draft → reviewed → verified.
"""

from django.db import models
from django.utils.text import slugify

from apps.core.models import StatusChoices, TimeStampedModel
from apps.curation.models import Source


class IngredientCategory(TimeStampedModel):
    """
    Hierarchical ingredient taxonomy.

    Architecture: ingredient_category(id, slug, name_en, name_sw, parent_id)
    Examples: Vegetables and greens, Grains flours and starches, Meat offal and poultry.
    """

    slug = models.SlugField(max_length=100, unique=True)
    name_en = models.CharField(max_length=100)
    name_sw = models.CharField(max_length=100, blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )

    class Meta:
        db_table = "ingredient_category"
        verbose_name = "Ingredient category"
        verbose_name_plural = "Ingredient categories"
        ordering = ["name_en"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name_en)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name_en


class Unit(TimeStampedModel):
    """
    Measurement units used in ingredient quantities and dish steps.

    Architecture: unit(id, code, kind [mass, volume, count], to_base_factor)
    Style guide: metric units — grams, millilitres, counts.
    Local measures (e.g. 'a handful') are notes, not units.
    """

    class Kind(models.TextChoices):
        MASS = "mass", "Mass"
        VOLUME = "volume", "Volume"
        COUNT = "count", "Count"

    code = models.CharField(max_length=20, unique=True)  # e.g. g, ml, tsp, kg
    name = models.CharField(max_length=50)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    to_base_factor = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        help_text="Multiply by this to convert to the base unit (g for mass, ml for volume).",
    )

    class Meta:
        db_table = "unit"
        ordering = ["kind", "code"]

    def __str__(self) -> str:
        return f"{self.code} ({self.get_kind_display()})"


class Allergen(TimeStampedModel):
    """
    Allergen types linked to ingredients.

    Architecture: allergen(id, slug, name)
    Blueprint section 8: nut-free, dairy-free, egg-free, gluten-free, contains pork, etc.
    """

    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "allergen"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class Ingredient(TimeStampedModel):
    """
    A single item used in cooking.

    Architecture section 5:
      ingredient(id, slug, name_en, name_sw, category_id, kind, is_staple,
                 typical_unit, status, source_id, notes)

    Kind values match the architecture spec:
      primary, secondary, seasoning, staple, liquid, garnish

    Blueprint section 4:
      - Staples (water, salt, cooking oil) flagged with is_staple=True.
      - Every ingredient has one canonical English name and one Swahili name.
      - Everything else goes in the alias table.
    """

    class Kind(models.TextChoices):
        PRIMARY = "primary", "Primary"
        SECONDARY = "secondary", "Secondary"
        SEASONING = "seasoning", "Seasoning"
        STAPLE = "staple", "Staple"
        LIQUID = "liquid", "Liquid"
        GARNISH = "garnish", "Garnish"

    slug = models.SlugField(max_length=150, unique=True)
    name_en = models.CharField(max_length=150, unique=True)
    name_sw = models.CharField(max_length=150, blank=True)
    category = models.ForeignKey(
        IngredientCategory,
        on_delete=models.PROTECT,
        related_name="ingredients",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SECONDARY)
    is_staple = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Staples are assumed present in every kitchen and never block a match.",
    )
    typical_unit = models.ForeignKey(
        Unit,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ingredients",
    )
    allergens = models.ManyToManyField(
        Allergen,
        through="IngredientAllergen",
        related_name="ingredients",
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT,
        db_index=True,
    )
    source = models.ForeignKey(
        Source,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ingredients",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "ingredient"
        ordering = ["name_en"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["is_staple"]),
            models.Index(fields=["kind"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name_en)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name_en


class IngredientAllergen(models.Model):
    """
    Explicit through table for ingredient ↔ allergen many-to-many.

    Architecture: ingredient_allergen(ingredient_id, allergen_id)
    Explicit through table allows adding metadata (e.g. notes) later.
    """

    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name="allergen_links",
    )
    allergen = models.ForeignKey(
        Allergen,
        on_delete=models.CASCADE,
        related_name="ingredient_links",
    )
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "ingredient_allergen"
        unique_together = [("ingredient", "allergen")]

    def __str__(self) -> str:
        return f"{self.ingredient} → {self.allergen}"


class IngredientAlias(models.Model):
    """
    Alternative names for an ingredient.

    Architecture section 5:
      ingredient_alias(id, ingredient_id, alias, normalized_alias,
                       language [en, sw, sheng, other], is_misspelling)

    Blueprint section 5 (The Dictionary):
      - Each alias points to only one ingredient.
      - If a word could mean two things it is stored as 'ambiguous' and the engine asks.
      - New aliases come from real searches that failed (zero-result log).
    """

    class Language(models.TextChoices):
        EN = "en", "English"
        SW = "sw", "Swahili"
        SHENG = "sheng", "Sheng"
        OTHER = "other", "Other"

    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name="aliases",
    )
    alias = models.CharField(max_length=150, db_index=True)
    normalized_alias = models.CharField(
        max_length=150,
        db_index=True,
        help_text="Lowercased, stripped, no punctuation — used for fast lookup.",
    )
    language = models.CharField(max_length=10, choices=Language.choices, default=Language.EN)
    is_misspelling = models.BooleanField(
        default=False,
        help_text="True if this alias is a common spelling mistake.",
    )

    class Meta:
        db_table = "ingredient_alias"
        # One alias string maps to exactly one ingredient (enforces dictionary rule)
        unique_together = [("normalized_alias", "language")]
        ordering = ["alias"]

    def __str__(self) -> str:
        flag = " (misspelling)" if self.is_misspelling else ""
        return f"{self.alias} [{self.language}] → {self.ingredient}{flag}"
