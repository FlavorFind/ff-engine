"""
E20 — Staples handling.

Staples are ingredients assumed to be present in every kitchen
(water, salt, cooking oil, etc.).  They must never block a match —
a user who types only "maize flour" should still find ugali even though
ugali also needs water and salt.

Rules (Architecture section 6.1, step 3 / Blueprint section 4):
  • Staple IDs are always added to the user's resolved ingredient pool.
  • A user can explicitly exclude a staple ("I don't have oil") by passing
    its ID in excluded_ids — the pipeline will then honour that exclusion.
  • Staple status is determined by Ingredient.is_staple == True.

Exit check (E20):
  "Water, salt and oil never block a match."
"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_staple_ids() -> frozenset[str]:
    """
    Return a frozenset of UUID strings for all staple ingredients.

    Result is cached for the process lifetime.  Call invalidate_staple_cache()
    after bulk-updating staple flags (e.g. in tests or after an import).
    """
    from apps.ingredients.models import Ingredient

    ids = frozenset(
        str(pk) for pk in Ingredient.objects.filter(is_staple=True).values_list("id", flat=True)
    )
    logger.debug("Staple cache loaded: %d staples", len(ids))
    return ids


def invalidate_staple_cache() -> None:
    """Clear the LRU cache so the next call re-queries the DB."""
    get_staple_ids.cache_clear()


def expand_with_staples(
    resolved_ids: list[str],
    excluded_ids: list[str] | None = None,
) -> list[str]:
    """
    Add staple IDs to *resolved_ids*, minus any the user explicitly excluded.

    Parameters
    ----------
    resolved_ids:
        UUIDs (as strings) of ingredients the user provided.
    excluded_ids:
        UUIDs the user explicitly said they don't have.
        Staples in this list are NOT added back.

    Returns
    -------
    A deduplicated list containing both the user's ingredients and all
    applicable staples.
    """
    excluded = set(excluded_ids or [])
    staples = get_staple_ids() - excluded

    combined = set(resolved_ids) | staples
    return list(combined)


def is_staple(ingredient_id: str) -> bool:
    """Return True if *ingredient_id* is in the staples set."""
    return str(ingredient_id) in get_staple_ids()


def non_staple_required_ids(dish) -> list[str]:
    """
    Return the required_ids of *dish* with staple IDs removed.

    This is the set that must be fully covered for an exact or can-make match.
    *dish* is a Dish model instance.
    """
    staples = get_staple_ids()
    return [str(uid) for uid in dish.required_ids if str(uid) not in staples]
