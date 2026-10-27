"""
E56 — Category word expansion.

Expands category words (e.g. 'greens', 'meat') to the ingredient IDs
that belong to that category, before the GIN shortlist query.

Blueprint section 5 (The Dictionary):
  "greens, meat — Category words. The engine expands them to member
   ingredients (sukuma wiki, spinach, cabbage; beef, goat, chicken)."

Architecture section 6.1, step 3:
  "Expand: Category inputs such as 'greens' expand to member ingredients;
   staples are added to the pool unless excluded."

Pipeline position: called in resolve_ingredients() BEFORE resolve_many(),
so category-expanded IDs bypass the resolver and go straight to the pool.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from apps.curation.normaliser import normalise

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hard-coded alias map: common words → expected category slugs
#
# Category slugs come from IngredientCategory.slug (auto-derived from name_en
# in seed_all via slugify). This map covers the most common natural-language
# category words users type.
# ---------------------------------------------------------------------------

_CATEGORY_ALIASES: dict[str, list[str]] = {
    # Vegetables / greens
    "greens": ["vegetables", "vegetables-and-greens", "vegetables-greens"],
    "vegetables": ["vegetables", "vegetables-and-greens", "vegetables-greens"],
    "veggies": ["vegetables", "vegetables-and-greens", "vegetables-greens"],
    "mboga": ["vegetables", "vegetables-and-greens"],  # Swahili for vegetables
    "majani": ["vegetables", "vegetables-and-greens"],  # Swahili: leafy greens
    # Meat
    "meat": ["meat", "meat-offal-and-poultry", "meat-offal-poultry"],
    "nyama": ["meat", "meat-offal-and-poultry", "meat-offal-poultry"],  # Swahili: meat
    # Poultry
    "poultry": ["poultry", "meat-offal-and-poultry", "meat-offal-poultry"],
    "chicken": None,  # 'chicken' is an ingredient, not a category — skip
    # Fish / seafood
    "fish": ["fish-and-seafood", "fish-seafood", "fish"],
    "seafood": ["fish-and-seafood", "fish-seafood"],
    "samaki": ["fish-and-seafood", "fish-seafood"],  # Swahili: fish
    # Grains / starches
    "grains": ["grains", "grains-flours-and-starches", "grains-flours-starches"],
    "starches": ["grains", "grains-flours-and-starches", "grains-flours-starches"],
    "flour": ["grains", "grains-flours-and-starches", "grains-flours-starches"],
    # Legumes / pulses
    "legumes": ["legumes", "legumes-and-pulses"],
    "pulses": ["legumes", "legumes-and-pulses"],
    "beans": None,  # 'beans' is an ingredient — skip
    # Dairy
    "dairy": ["dairy", "dairy-and-eggs", "dairy-eggs"],
    "maziwa": ["dairy", "dairy-and-eggs"],  # Swahili: milk/dairy
    # Spices / seasonings
    "spices": ["spices", "spices-herbs-and-seasonings", "spices-and-seasonings"],
    "seasonings": ["spices", "spices-herbs-and-seasonings"],
    "herbs": ["spices", "spices-herbs-and-seasonings"],
    # Oils / fats
    "oils": ["fats-oils", "fats-and-oils", "oils-fats-and-sauces"],
    "oil": None,  # 'oil' is an ingredient — skip
    # Fruits
    "fruits": ["fruit", "fruits"],
    "matunda": ["fruit", "fruits"],  # Swahili: fruits
    # Nuts and seeds
    "nuts": ["nuts-and-seeds", "nuts-seeds"],
    "seeds": ["nuts-and-seeds", "nuts-seeds"],
}


def expand_category_terms(
    raw_tokens: list[str],
) -> tuple[list[str], list[str]]:
    """
    Check each raw token against the category word list.

    Parameters
    ----------
    raw_tokens:
        List of raw ingredient strings from the caller.

    Returns
    -------
    (expanded_ids, remaining_tokens)
        expanded_ids    — UUID strings of all ingredients in matched categories
        remaining_tokens — tokens that did NOT match any category (pass to resolver)
    """
    expanded_ids: list[str] = []
    remaining: list[str] = []

    for token in raw_tokens:
        norm = normalise(token)
        candidate_slugs = _CATEGORY_ALIASES.get(norm)

        if candidate_slugs is None:
            # Token is in the alias map with value=None (it's an ingredient, not category)
            remaining.append(token)
            continue

        if norm not in _CATEGORY_ALIASES:
            # Token not in the alias map at all
            remaining.append(token)
            continue

        ids = _resolve_category_to_ids(candidate_slugs)
        if ids:
            expanded_ids.extend(ids)
            logger.debug("category_expander: %r → %d ingredient IDs via category", token, len(ids))
        else:
            # No matching category found in DB — treat as normal ingredient token
            remaining.append(token)

    # Deduplicate expanded IDs while preserving order
    seen: set[str] = set()
    unique_ids: list[str] = []
    for iid in expanded_ids:
        if iid not in seen:
            seen.add(iid)
            unique_ids.append(iid)

    return unique_ids, remaining


def _resolve_category_to_ids(candidate_slugs: list[str]) -> list[str]:
    """
    Try each slug in candidate_slugs until one matches a category in the DB.
    Returns the ingredient IDs for all ingredients in that category
    (including children via parent FK).
    """
    for slug in candidate_slugs:
        ids = _get_category_ingredient_ids(slug)
        if ids:
            return ids
    return []


def get_category_ingredient_ids(category_slug: str) -> list[str]:
    """
    Public interface: return all ingredient UUID strings for the given category,
    including any child sub-categories.
    """
    return _get_category_ingredient_ids(category_slug)


@lru_cache(maxsize=64)
def _get_category_ingredient_ids(category_slug: str) -> list[str]:
    """
    Return ingredient UUIDs for a category slug (and its children).
    Result is cached per slug for the process lifetime.

    Cache is invalidated in tests via invalidate_category_cache().
    """
    from apps.ingredients.models import Ingredient, IngredientCategory

    try:
        cat = IngredientCategory.objects.filter(slug=category_slug).first()
        if cat is None:
            return []

        # Collect this category and all children (one level deep for v1)
        cat_ids = [cat.pk]
        child_ids = list(IngredientCategory.objects.filter(parent=cat).values_list("id", flat=True))
        cat_ids.extend(child_ids)

        ids = list(Ingredient.objects.filter(category_id__in=cat_ids).values_list("id", flat=True))
        return [str(iid) for iid in ids]
    except Exception as exc:
        logger.warning("category_expander: failed to fetch category %r: %s", category_slug, exc)
        return []


def invalidate_category_cache() -> None:
    """Clear the LRU cache. Call after bulk-importing new categories or in tests."""
    _get_category_ingredient_ids.cache_clear()
