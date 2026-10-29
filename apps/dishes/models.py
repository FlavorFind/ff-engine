"""
Dish models — the recipe layer.

Architecture section 5 (Data Model) tables implemented here:
  dish            id, slug, name_en, name_sw, description, meal_type[], course,
                  spice_level, difficulty, prep_min, cook_min, servings,
                  popularity, quality_level, status, source_id,
                  required_ids int[], optional_ids int[], primary_ids int[], all_ids int[]
  dish_alias      dish_id, alias, language
  dish_ingredient id, dish_id, ingredient_id, role (primary/required/optional/garnish),
                  quantity, unit_id, preparation_note, position
  dish_step       dish_id, position, text_en, text_sw

Blueprint section 4 (The Knowledge Library):
  The four ingredient roles:
    primary  — what the dish is built around (heavily rewarded when present)
    required — the dish cannot exist without it (must be covered)
    optional — a common variation (counts as 'used', never blocks a match)
    garnish  — finishing touch (lowest weight, never blocks a match)

  Denormalised search arrays (required_ids, optional_ids, primary_ids, all_ids)
  are PostgreSQL integer arrays with GIN indexes — rebuilt on every dish change.
  (Arrays store ingredient PKs as integers for fast GIN-indexed shortlist queries.)
"""

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.text import slugify

from apps.core.models import StatusChoices, TimeStampedModel
from apps.curation.models import Source
from apps.ingredients.models import Ingredient, Unit


class Dish(TimeStampedModel):
    """
    A prepared food with a name, description, steps, region, meal type and quality level.

    Architecture section 5:
      dish(id, slug, name_en, name_sw, description, meal_type[], course,
           spice_level, difficulty, prep_min, cook_min, servings, popularity,
           quality_level, status, source_id,
           required_ids int[], optional_ids int[], primary_ids int[], all_ids int[])

    The denormalised int[] arrays are used by the search engine (E19) for
    GIN-indexed candidate retrieval. They are rebuilt via a signal/method
    whenever DishIngredient rows change.
    """

    class MealType(models.TextChoices):
        BREAKFAST = "breakfast", "Breakfast"
        LUNCH = "lunch", "Lunch"
        DINNER = "dinner", "Dinner"
        SNACK = "snack", "Snack"
        DRINK = "drink", "Drink"
        DESSERT = "dessert", "Dessert"
        ANY = "any", "Any"

    class Course(models.TextChoices):
        STARTER = "starter", "Starter"
        MAIN = "main", "Main"
        SIDE = "side", "Side"
        DESSERT = "dessert", "Dessert"
        DRINK = "drink", "Drink"
        SNACK = "snack", "Snack"

    class SpiceLevel(models.TextChoices):
        NONE = "none", "None"
        MILD = "mild", "Mild"
        MEDIUM = "medium", "Medium"
        HOT = "hot", "Hot"
        VERY_HOT = "very_hot", "Very hot"

    class Difficulty(models.TextChoices):
        EASY = "easy", "Easy"
        MEDIUM = "medium", "Medium"
        HARD = "hard", "Hard"

    class QualityLevel(models.TextChoices):
        SEEDED = "seeded", "Seeded"
        COMMUNITY = "community", "Community"
        REVIEWED = "reviewed", "Reviewed"
        VERIFIED = "verified", "Verified"

    # Identity
    slug = models.SlugField(max_length=200, unique=True)
    name_en = models.CharField(max_length=200, unique=True)
    name_sw = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    # Classification
    meal_type = models.CharField(
        max_length=20,
        choices=MealType.choices,
        default=MealType.ANY,
        db_index=True,
    )
    course = models.CharField(
        max_length=20,
        choices=Course.choices,
        default=Course.MAIN,
    )
    spice_level = models.CharField(
        max_length=20,
        choices=SpiceLevel.choices,
        default=SpiceLevel.NONE,
    )
    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.EASY,
    )

    # Timing and servings
    prep_min = models.PositiveIntegerField(default=0, help_text="Preparation time in minutes.")
    cook_min = models.PositiveIntegerField(default=0, help_text="Cooking time in minutes.")
    servings = models.PositiveIntegerField(default=1)

    # Quality and curation
    popularity = models.FloatField(
        default=0.0,
        help_text="0.0 to 1.0 — used as a ranking signal.",
    )
    quality_level = models.CharField(
        max_length=20,
        choices=QualityLevel.choices,
        default=QualityLevel.SEEDED,
        db_index=True,
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
        related_name="dishes",
    )

    # Regions (many-to-many via DishRegion in apps.regions)
    regions = models.ManyToManyField(
        "regions.Region",
        through="regions.DishRegion",
        related_name="dishes",
        blank=True,
    )

    # -----------------------------------------------------------------------
    # Denormalised search arrays (Architecture section 5)
    # Rebuilt by rebuild_search_arrays() whenever DishIngredient rows change.
    # GIN indexes added in the migration for fast candidate retrieval (E19).
    # Note: UUIDField arrays because Ingredient.id is a UUID (TimeStampedModel).
    # -----------------------------------------------------------------------
    required_ids = ArrayField(
        models.UUIDField(),
        default=list,
        help_text="PKs of required non-staple ingredients.",
    )
    optional_ids = ArrayField(
        models.UUIDField(),
        default=list,
        help_text="PKs of optional ingredients.",
    )
    primary_ids = ArrayField(
        models.UUIDField(),
        default=list,
        help_text="PKs of primary ingredients.",
    )
    all_ids = ArrayField(
        models.UUIDField(),
        default=list,
        help_text="PKs of all ingredients (required + optional + garnish).",
    )

    class Meta:
        db_table = "dish"
        ordering = ["name_en"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["quality_level"]),
            models.Index(fields=["meal_type"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name_en)
        super().save(*args, **kwargs)

    def rebuild_search_arrays(self):
        """
        Rebuild the four denormalised int[] arrays from DishIngredient rows.

        Called explicitly after bulk-creating DishIngredient rows, and wired
        to a post_save signal in E19 (search arrays and indexes step).
        """
        qs = self.dish_ingredients.select_related("ingredient")
        self.required_ids = [
            di.ingredient_id
            for di in qs
            if di.role == DishIngredient.Role.REQUIRED and not di.ingredient.is_staple
        ]
        self.optional_ids = [
            di.ingredient_id for di in qs if di.role == DishIngredient.Role.OPTIONAL
        ]
        self.primary_ids = [di.ingredient_id for di in qs if di.role == DishIngredient.Role.PRIMARY]
        self.all_ids = sorted([di.ingredient_id for di in qs])
        self.save(update_fields=["required_ids", "optional_ids", "primary_ids", "all_ids"])

    def __str__(self) -> str:
        return self.name_en


class DishIngredient(TimeStampedModel):
    """
    Links an ingredient to a dish with a role, quantity and position.

    Architecture section 5:
      dish_ingredient(id, dish_id, ingredient_id, role [primary/required/optional/garnish],
                      quantity, unit_id, preparation_note, position)

    Blueprint section 4 — the four roles:
      primary  — what the dish is built around
      required — cannot exist without it
      optional — common variation, never blocks a match
      garnish  — finishing touch, never blocks a match

    Integrity rule (E5 pass criterion):
      unique_together on (dish, ingredient) — no duplicate ingredient on one dish.
    """

    class Role(models.TextChoices):
        PRIMARY = "primary", "Primary"
        REQUIRED = "required", "Required"
        OPTIONAL = "optional", "Optional"
        GARNISH = "garnish", "Garnish"

    dish = models.ForeignKey(
        Dish,
        on_delete=models.CASCADE,
        related_name="dish_ingredients",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="dish_ingredients",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.REQUIRED,
        db_index=True,
    )
    quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )
    unit = models.ForeignKey(
        Unit,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dish_ingredients",
    )
    preparation_note = models.CharField(max_length=200, blank=True)
    position = models.PositiveIntegerField(
        default=0,
        help_text="Display order within the dish's ingredient list.",
    )

    class Meta:
        db_table = "dish_ingredient"
        # E5 pass criterion: no duplicate ingredient on one dish
        unique_together = [("dish", "ingredient")]
        ordering = ["position", "role"]

    def __str__(self) -> str:
        return f"{self.dish} — {self.ingredient} ({self.role})"


class DishAlias(models.Model):
    """
    Alternative names for a dish.

    Architecture: dish_alias(dish_id, alias, language)
    """

    class Language(models.TextChoices):
        EN = "en", "English"
        SW = "sw", "Swahili"
        SHENG = "sheng", "Sheng"
        OTHER = "other", "Other"

    dish = models.ForeignKey(
        Dish,
        on_delete=models.CASCADE,
        related_name="aliases",
    )
    alias = models.CharField(max_length=200, db_index=True)
    language = models.CharField(
        max_length=10,
        choices=Language.choices,
        default=Language.EN,
    )

    class Meta:
        db_table = "dish_alias"
        unique_together = [("dish", "alias")]
        ordering = ["alias"]

    def __str__(self) -> str:
        return f"{self.alias} [{self.language}] → {self.dish}"


class DishStep(models.Model):
    """
    An ordered preparation step for a dish.

    Architecture: dish_step(dish_id, position, text_en, text_sw)

    Blueprint section 11 (data style guide):
      Steps are in original wording; do not copy cookbook text without permission.
    """

    dish = models.ForeignKey(
        Dish,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    position = models.PositiveIntegerField()
    text_en = models.TextField()
    text_sw = models.TextField(blank=True)

    class Meta:
        db_table = "dish_step"
        unique_together = [("dish", "position")]
        ordering = ["position"]

    def __str__(self) -> str:
        return f"{self.dish} — step {self.position}"
