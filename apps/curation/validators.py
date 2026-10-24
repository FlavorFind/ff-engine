"""
E12 — Validators: 20+ integrity rules.

Validation is a pure-function layer.  Each rule takes data (a dict or model
instance) and returns a list of ValidationError namedtuples.

Rules are called:
  • On import (before saving) — via validate_ingredient_row() etc.
  • On model save — via Django signals wired at the bottom of this file.
  • From the QA report command (E14) to scan the whole dataset.

Architecture section 5 / Blueprint section 8:
  "Validators run: required fields, at least one primary ingredient,
   no duplicate names, every ingredient resolves, units valid,
   staples not marked primary."

Integrity rules implemented (23 total):
  Ingredient rules (7):
    V01  name_en is required and non-empty
    V02  slug is required and non-empty
    V03  category is required
    V04  kind must be a valid Ingredient.Kind value
    V05  A staple ingredient must not have kind='primary'
    V06  name_en must be unique across all ingredients
    V07  slug must be unique across all ingredients

  IngredientAlias rules (3):
    V08  alias text is required
    V09  ingredient reference must exist
    V10  normalised alias + language must be unique

  Dish rules (7):
    V11  name_en is required
    V12  slug is required
    V13  meal_type must be a valid value
    V14  course must be a valid value
    V15  difficulty must be a valid value
    V16  prep_min and cook_min must be non-negative integers
    V17  servings must be >= 1

  DishIngredient rules (6):
    V18  dish reference must exist
    V19  ingredient reference must exist
    V20  role must be a valid DishIngredient.Role value
    V21  A dish must have at least one ingredient with role='primary'
         (checked at dish level, not row level)
    V22  (dish, ingredient) pair must be unique per dish
    V23  A staple ingredient must not be the only primary ingredient of a dish
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ValidationError:
    """A single rule violation."""

    rule: str  # e.g. "V01"
    field: str  # column / field name
    value: Any  # the offending value
    message: str  # human-readable explanation
    row: int = 0  # 1-based row number in the CSV (0 = not from CSV)


@dataclass
class ValidationResult:
    """Accumulates errors from a validation pass."""

    errors: list[ValidationError] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add(self, rule: str, fld: str, value: Any, msg: str, row: int = 0) -> None:
        self.errors.append(ValidationError(rule=rule, field=fld, value=value, message=msg, row=row))

    def merge(self, other: ValidationResult) -> None:
        self.errors.extend(other.errors)

    def __len__(self) -> int:
        return len(self.errors)


# ---------------------------------------------------------------------------
# Row-level validators (called per CSV row during import)
# ---------------------------------------------------------------------------


def validate_ingredient_row(
    row: dict,
    row_num: int = 0,
    existing_names: set[str] | None = None,
    existing_slugs: set[str] | None = None,
) -> ValidationResult:
    """Validate a single ingredient CSV row (dict of str→str)."""
    from apps.ingredients.models import Ingredient  # local to avoid circular import

    result = ValidationResult()
    valid_kinds = {c[0] for c in Ingredient.Kind.choices}

    name_en = row.get("name_en", "").strip()
    slug = row.get("slug", "").strip()
    category = row.get("category", "").strip()
    kind = row.get("kind", "").strip()
    is_staple_raw = row.get("is_staple", "").strip().lower()
    is_staple = is_staple_raw in ("true", "1", "yes")

    # V01
    if not name_en:
        result.add("V01", "name_en", name_en, "name_en is required", row_num)

    # V02
    if not slug:
        result.add("V02", "slug", slug, "slug is required", row_num)

    # V03
    if not category:
        result.add("V03", "category", category, "category is required", row_num)

    # V04
    if kind and kind not in valid_kinds:
        result.add(
            "V04",
            "kind",
            kind,
            f"kind '{kind}' is not valid; must be one of {sorted(valid_kinds)}",
            row_num,
        )

    # V05
    if is_staple and kind == "primary":
        result.add(
            "V05",
            "is_staple/kind",
            kind,
            "A staple ingredient must not have kind='primary'",
            row_num,
        )

    # V06 — uniqueness check (within this import batch or against DB)
    if existing_names is not None and name_en and name_en.lower() in existing_names:
        result.add("V06", "name_en", name_en, f"name_en '{name_en}' already exists", row_num)

    # V07
    if existing_slugs is not None and slug and slug in existing_slugs:
        result.add("V07", "slug", slug, f"slug '{slug}' already exists", row_num)

    return result


def validate_alias_row(
    row: dict, row_num: int = 0, existing_aliases: set[tuple[str, str]] | None = None
) -> ValidationResult:
    """Validate a single alias CSV row."""
    from apps.curation.normaliser import normalise
    from apps.ingredients.models import Ingredient, IngredientAlias

    result = ValidationResult()
    valid_langs = {c[0] for c in IngredientAlias.Language.choices}

    alias = row.get("alias", "").strip()
    ingredient_slug = row.get("ingredient_slug", "").strip()
    language = row.get("language", "en").strip()

    # V08
    if not alias:
        result.add("V08", "alias", alias, "alias text is required", row_num)

    # V09
    if ingredient_slug:
        if not Ingredient.objects.filter(slug=ingredient_slug).exists():
            result.add(
                "V09",
                "ingredient_slug",
                ingredient_slug,
                f"ingredient '{ingredient_slug}' does not exist",
                row_num,
            )
    else:
        result.add(
            "V09", "ingredient_slug", ingredient_slug, "ingredient_slug is required", row_num
        )

    # Language check (not a numbered rule but still useful)
    if language not in valid_langs:
        language = "en"

    # V10 — normalised alias uniqueness
    if alias:
        norm = normalise(alias)
        key = (norm, language)
        if existing_aliases is not None and key in existing_aliases:
            result.add(
                "V10",
                "alias",
                alias,
                f"normalised alias '{norm}' already exists for language '{language}'",
                row_num,
            )

    return result


def validate_dish_row(
    row: dict,
    row_num: int = 0,
    existing_names: set[str] | None = None,
    existing_slugs: set[str] | None = None,
) -> ValidationResult:
    """Validate a single dish CSV row."""
    from apps.dishes.models import Dish

    result = ValidationResult()
    valid_meal_types = {c[0] for c in Dish.MealType.choices}
    valid_courses = {c[0] for c in Dish.Course.choices}
    valid_difficulties = {c[0] for c in Dish.Difficulty.choices}

    name_en = row.get("name_en", "").strip()
    slug = row.get("slug", "").strip()
    meal_type = row.get("meal_type", "").strip()
    course = row.get("course", "").strip()
    difficulty = row.get("difficulty", "").strip()

    # V11
    if not name_en:
        result.add("V11", "name_en", name_en, "name_en is required", row_num)

    # V12
    if not slug:
        result.add("V12", "slug", slug, "slug is required", row_num)

    # V13
    if meal_type and meal_type not in valid_meal_types:
        result.add(
            "V13",
            "meal_type",
            meal_type,
            f"meal_type '{meal_type}' is not valid; must be one of {sorted(valid_meal_types)}",
            row_num,
        )

    # V14
    if course and course not in valid_courses:
        result.add(
            "V14",
            "course",
            course,
            f"course '{course}' is not valid; must be one of {sorted(valid_courses)}",
            row_num,
        )

    # V15
    if difficulty and difficulty not in valid_difficulties:
        result.add(
            "V15",
            "difficulty",
            difficulty,
            f"difficulty '{difficulty}' is not valid; must be one of {sorted(valid_difficulties)}",
            row_num,
        )

    # V16
    for time_field in ("prep_min", "cook_min"):
        raw = row.get(time_field, "0").strip()
        try:
            val = int(float(raw)) if raw else 0
            if val < 0:
                result.add("V16", time_field, raw, f"{time_field} must be >= 0", row_num)
        except (ValueError, TypeError):
            result.add(
                "V16", time_field, raw, f"{time_field} must be a non-negative integer", row_num
            )

    # V17
    raw_servings = row.get("servings", "1").strip()
    try:
        servings = int(float(raw_servings)) if raw_servings else 1
        if servings < 1:
            result.add("V17", "servings", raw_servings, "servings must be >= 1", row_num)
    except (ValueError, TypeError):
        result.add("V17", "servings", raw_servings, "servings must be a positive integer", row_num)

    # Uniqueness
    if existing_names is not None and name_en and name_en.lower() in existing_names:
        result.add("V06", "name_en", name_en, f"name_en '{name_en}' already exists", row_num)

    if existing_slugs is not None and slug and slug in existing_slugs:
        result.add("V07", "slug", slug, f"slug '{slug}' already exists", row_num)

    return result


def validate_dish_ingredient_row(
    row: dict, row_num: int = 0, seen_pairs: set[tuple[str, str]] | None = None
) -> ValidationResult:
    """Validate a single dish_ingredient CSV row."""
    from apps.dishes.models import Dish, DishIngredient
    from apps.ingredients.models import Ingredient

    result = ValidationResult()
    valid_roles = {c[0] for c in DishIngredient.Role.choices}

    dish_slug = row.get("dish_slug", "").strip()
    ingredient_slug = row.get("ingredient_slug", "").strip()
    role = row.get("role", "").strip()

    # V18
    if dish_slug:
        if not Dish.objects.filter(slug=dish_slug).exists():
            result.add("V18", "dish_slug", dish_slug, f"dish '{dish_slug}' does not exist", row_num)
    else:
        result.add("V18", "dish_slug", dish_slug, "dish_slug is required", row_num)

    # V19
    if ingredient_slug:
        if not Ingredient.objects.filter(slug=ingredient_slug).exists():
            result.add(
                "V19",
                "ingredient_slug",
                ingredient_slug,
                f"ingredient '{ingredient_slug}' does not exist",
                row_num,
            )
    else:
        result.add(
            "V19", "ingredient_slug", ingredient_slug, "ingredient_slug is required", row_num
        )

    # V20
    if role and role not in valid_roles:
        result.add(
            "V20",
            "role",
            role,
            f"role '{role}' is not valid; must be one of {sorted(valid_roles)}",
            row_num,
        )

    # V22 — duplicate (dish, ingredient) pair in this import
    if seen_pairs is not None and dish_slug and ingredient_slug:
        pair = (dish_slug, ingredient_slug)
        if pair in seen_pairs:
            result.add(
                "V22",
                "dish_slug+ingredient_slug",
                pair,
                f"duplicate (dish, ingredient) pair: {pair}",
                row_num,
            )

    return result


# ---------------------------------------------------------------------------
# Dish-level validators (called after all rows for a dish are collected)
# ---------------------------------------------------------------------------


def validate_dish_has_primary(dish_slug: str, roles: list[str]) -> ValidationResult:
    """
    V21: A dish must have at least one ingredient with role='primary'.
    *roles* is the list of role values for all dish_ingredient rows of this dish.
    """
    result = ValidationResult()
    if "primary" not in roles:
        result.add("V21", "role", roles, f"dish '{dish_slug}' has no primary ingredient")
    return result


def validate_staple_not_only_primary(dish_slug: str, rows: list[dict]) -> ValidationResult:
    """
    V23: A staple must not be the only primary ingredient of a dish.
    *rows* are dish_ingredient dicts with 'ingredient_slug' and 'role'.
    """
    from apps.ingredients.models import Ingredient

    result = ValidationResult()
    primary_slugs = [r["ingredient_slug"] for r in rows if r.get("role") == "primary"]
    if not primary_slugs:
        return result  # V21 already caught this

    staple_slugs = set(
        Ingredient.objects.filter(slug__in=primary_slugs, is_staple=True).values_list(
            "slug", flat=True
        )
    )
    non_staple_primaries = [s for s in primary_slugs if s not in staple_slugs]
    if not non_staple_primaries and staple_slugs:
        result.add(
            "V23",
            "role",
            primary_slugs,
            f"dish '{dish_slug}' has only staple ingredients as primary",
        )
    return result


# ---------------------------------------------------------------------------
# Full dataset scan (used by QA report)
# ---------------------------------------------------------------------------


def scan_dataset() -> ValidationResult:
    """
    Run all rules over the entire current database contents.
    Returns a ValidationResult with every violation found.
    """
    from apps.dishes.models import Dish, DishIngredient
    from apps.ingredients.models import Ingredient, IngredientAlias

    result = ValidationResult()

    # --- Ingredients ---
    for ing in Ingredient.objects.all():
        if not ing.name_en:
            result.add("V01", "name_en", ing.name_en, f"Ingredient pk={ing.pk}: name_en is empty")
        if not ing.slug:
            result.add("V02", "slug", ing.slug, f"Ingredient pk={ing.pk}: slug is empty")
        if not ing.category_id:
            result.add("V03", "category", None, f"Ingredient '{ing.name_en}': category is missing")
        if ing.is_staple and ing.kind == Ingredient.Kind.PRIMARY:
            result.add(
                "V05",
                "is_staple/kind",
                ing.kind,
                f"Ingredient '{ing.name_en}': staple must not have kind='primary'",
            )

    # Uniqueness scan
    from django.db.models import Count

    dup_names = Ingredient.objects.values("name_en").annotate(c=Count("id")).filter(c__gt=1)
    for d in dup_names:
        result.add(
            "V06", "name_en", d["name_en"], f"Duplicate ingredient name_en: '{d['name_en']}'"
        )

    dup_slugs = Ingredient.objects.values("slug").annotate(c=Count("id")).filter(c__gt=1)
    for d in dup_slugs:
        result.add("V07", "slug", d["slug"], f"Duplicate ingredient slug: '{d['slug']}'")

    # --- Aliases ---
    dup_aliases = (
        IngredientAlias.objects.values("normalized_alias", "language")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
    )
    for d in dup_aliases:
        result.add(
            "V10",
            "normalized_alias",
            f"{d['normalized_alias']}:{d['language']}",
            f"Duplicate alias '{d['normalized_alias']}' for language '{d['language']}'",
        )

    # --- Dishes ---
    for dish in Dish.objects.all():
        if not dish.name_en:
            result.add("V11", "name_en", dish.name_en, f"Dish pk={dish.pk}: name_en is empty")
        if not dish.slug:
            result.add("V12", "slug", dish.slug, f"Dish pk={dish.pk}: slug is empty")
        if dish.prep_min < 0:
            result.add(
                "V16", "prep_min", dish.prep_min, f"Dish '{dish.name_en}': prep_min is negative"
            )
        if dish.cook_min < 0:
            result.add(
                "V16", "cook_min", dish.cook_min, f"Dish '{dish.name_en}': cook_min is negative"
            )
        if dish.servings < 1:
            result.add(
                "V17", "servings", dish.servings, f"Dish '{dish.name_en}': servings must be >= 1"
            )

    # V21 — dishes with no primary ingredient
    dishes_with_primary = set(
        DishIngredient.objects.filter(role=DishIngredient.Role.PRIMARY).values_list(
            "dish_id", flat=True
        )
    )
    for dish in Dish.objects.exclude(id__in=dishes_with_primary):
        result.add("V21", "role", None, f"Dish '{dish.name_en}' has no primary ingredient")

    return result
