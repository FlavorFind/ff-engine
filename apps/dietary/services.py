"""
E31 — Dietary derivation rules.

Automatically derives dietary tags for a dish from its ingredient flags.

Blueprint section 8 (The Safety Filter):
  - Vegetarian: no ingredient flagged as meat, poultry, fish or seafood.
  - Vegan: vegetarian + no dairy, eggs or honey.
  - Contains pork: any ingredient flagged as pork or pork-derived.
  - Halal-friendly (guidance only): no pork and no alcohol-based ingredients.
  - Gluten-free: no ingredient flagged as wheat, barley or rye.
  - Nut-free: no ingredient linked to nut allergen.
  - Dairy-free: no ingredient linked to dairy allergen.
  - Egg-free: no ingredient linked to egg allergen.

Two-lock principle:
  Lock 1 (automatic) — this module. Tags derived from ingredient flags.
  Lock 2 (human)     — DishDietaryTag with source=manual. Reviewer override with reason.

E32: Every manual override is logged to ChangeLog via the admin save hook.
"""

from __future__ import annotations

import logging

from django.db import transaction

logger = logging.getLogger(__name__)

# Ingredient kind values that disqualify vegetarian/vegan
_MEAT_KINDS = {"primary"}  # We use allergen slugs, not kind, for precision

# Allergen slugs that block dietary tags
_MEAT_ALLERGEN_SLUGS = {"meat", "poultry", "fish", "seafood"}
_PORK_ALLERGEN_SLUGS = {"pork"}
_ALCOHOL_ALLERGEN_SLUGS = {"alcohol"}
_GLUTEN_ALLERGEN_SLUGS = {"gluten", "wheat", "barley", "rye"}
_NUT_ALLERGEN_SLUGS = {"nuts", "tree-nuts", "peanuts"}
_DAIRY_ALLERGEN_SLUGS = {"dairy", "milk"}
_EGG_ALLERGEN_SLUGS = {"eggs", "egg"}
_HONEY_ALLERGEN_SLUGS = {"honey"}

# Ingredient name keywords for meat detection (fallback when allergens not set)
_MEAT_NAME_KEYWORDS = {
    "beef",
    "goat",
    "chicken",
    "lamb",
    "mutton",
    "pork",
    "meat",
    "fish",
    "tilapia",
    "omena",
    "dagaa",
    "prawn",
    "shrimp",
    "crab",
    "lobster",
    "octopus",
    "squid",
    "tuna",
    "salmon",
    "sardine",
    "turkey",
    "duck",
    "rabbit",
    "offal",
    "tripe",
    "liver",
    "kidney",
    "blood",
    "bacon",
    "ham",
    "sausage",
    "nyama",
}
_DAIRY_NAME_KEYWORDS = {"milk", "cheese", "butter", "cream", "yoghurt", "yogurt", "mursik", "ghee"}
_EGG_NAME_KEYWORDS = {"egg", "eggs"}
_HONEY_NAME_KEYWORDS = {"honey"}
_PORK_NAME_KEYWORDS = {"pork", "bacon", "ham", "lard"}
_GLUTEN_NAME_KEYWORDS = {"wheat", "barley", "rye", "bread flour", "plain flour", "wheat flour"}
_NUT_NAME_KEYWORDS = {
    "peanut",
    "groundnut",
    "almond",
    "cashew",
    "walnut",
    "pecan",
    "macadamia",
    "hazelnut",
    "pistachio",
}


def derive_dietary_tags(dish) -> dict[str, bool]:
    """
    Derive dietary properties for a dish from its ingredients.

    Returns a dict of {tag_slug: True/False} — True means the tag applies.
    For allergen tags (contains-pork, contains-gluten etc.) True means the dish HAS it.
    For restriction tags (vegetarian, vegan, gluten-free etc.) True means it IS safe.
    """
    from apps.dishes.models import DishIngredient
    from apps.ingredients.models import IngredientAllergen

    ingredient_ids = list(
        DishIngredient.objects.filter(dish=dish).values_list("ingredient_id", flat=True)
    )

    if not ingredient_ids:
        return {}

    # Gather allergen slugs across all ingredients
    allergen_slugs: set[str] = set(
        IngredientAllergen.objects.filter(ingredient_id__in=ingredient_ids).values_list(
            "allergen__slug", flat=True
        )
    )

    # Gather ingredient name_en values (lowercased) for keyword fallback
    from apps.ingredients.models import Ingredient

    ingredient_names: set[str] = set(
        Ingredient.objects.filter(id__in=ingredient_ids).values_list("name_en", flat=True)
    )
    name_lower = {n.lower() for n in ingredient_names}

    def _has_allergen(slugs: set[str]) -> bool:
        return bool(allergen_slugs & slugs)

    def _has_keyword(keywords: set[str]) -> bool:
        return any(kw in name for name in name_lower for kw in keywords)

    # --- Derive each tag ---
    has_meat = _has_allergen(_MEAT_ALLERGEN_SLUGS) or _has_keyword(_MEAT_NAME_KEYWORDS)
    has_dairy = _has_allergen(_DAIRY_ALLERGEN_SLUGS) or _has_keyword(_DAIRY_NAME_KEYWORDS)
    has_egg = _has_allergen(_EGG_ALLERGEN_SLUGS) or _has_keyword(_EGG_NAME_KEYWORDS)
    has_honey = _has_allergen(_HONEY_ALLERGEN_SLUGS) or _has_keyword(_HONEY_NAME_KEYWORDS)
    has_pork = _has_allergen(_PORK_ALLERGEN_SLUGS) or _has_keyword(_PORK_NAME_KEYWORDS)
    has_alcohol = _has_allergen(_ALCOHOL_ALLERGEN_SLUGS)
    has_gluten = _has_allergen(_GLUTEN_ALLERGEN_SLUGS) or _has_keyword(_GLUTEN_NAME_KEYWORDS)
    has_nuts = _has_allergen(_NUT_ALLERGEN_SLUGS) or _has_keyword(_NUT_NAME_KEYWORDS)

    return {
        "vegetarian": not has_meat,
        "vegan": not has_meat and not has_dairy and not has_egg and not has_honey,
        "contains-pork": has_pork,
        "halal-friendly": not has_pork and not has_alcohol,
        "gluten-free": not has_gluten,
        "nut-free": not has_nuts,
        "dairy-free": not has_dairy,
        "egg-free": not has_egg,
    }


def apply_derived_tags(dish, *, actor=None) -> int:
    """
    Run derive_dietary_tags() and persist derived DishDietaryTag rows.

    - Creates tags that are newly True.
    - Removes derived tags that are now False (does NOT touch manual overrides).
    - Returns count of tags applied.

    E32: Does not touch any DishDietaryTag with source=manual.
    """
    from apps.dietary.models import DietaryTag, DishDietaryTag

    derived = derive_dietary_tags(dish)
    applied = 0

    with transaction.atomic():
        for tag_slug, is_applicable in derived.items():
            tag, _ = DietaryTag.objects.get_or_create(
                slug=tag_slug,
                defaults={"name": tag_slug.replace("-", " ").title()},
            )

            existing = DishDietaryTag.objects.filter(dish=dish, tag=tag).first()

            if is_applicable:
                if existing is None:
                    DishDietaryTag.objects.create(
                        dish=dish,
                        tag=tag,
                        source=DishDietaryTag.Source.DERIVED,
                    )
                    applied += 1
                # Don't overwrite a manual override
            else:
                # Remove derived tag if it no longer applies
                if existing and existing.source == DishDietaryTag.Source.DERIVED:
                    existing.delete()

    logger.debug("apply_derived_tags: dish=%s applied=%d tags", dish.slug, applied)
    return applied


def apply_derived_tags_for_all_dishes() -> dict[str, int]:
    """Run apply_derived_tags() on every dish. Used by management commands and migrations."""
    from apps.dishes.models import Dish

    total_dishes = 0
    total_tags = 0
    for dish in Dish.objects.all():
        tags = apply_derived_tags(dish)
        total_dishes += 1
        total_tags += tags

    return {"dishes_processed": total_dishes, "tags_applied": total_tags}
