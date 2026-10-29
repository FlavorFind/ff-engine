"""
E24 — The Explainer.

Attaches human-readable reasons to every result so the caller knows
exactly what matched, what is missing, what was unused, and why the
dish scored the way it did.

Architecture section 6.1, step 7:
  "Return what matched, what is missing, what was unused, the assumed
   staples and the score breakdown."

Architecture response fields (per dish):
  slug, name, score, matched, missing, unused, assumed_staples,
  quality, score_breakdown

Exit check (E24):
  "Each result carries all reasons."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from apps.search.ranker import RankedDish

logger = logging.getLogger(__name__)


@dataclass
class IngredientRef:
    """A lightweight ingredient reference attached to explained results."""

    id: str
    slug: str
    name_en: str
    name_sw: str = ""


@dataclass
class ExplainedResult:
    """
    A fully explained search result.

    This is the final shape handed to the serializer / API response.
    """

    dish_id: str
    slug: str
    name_en: str
    name_sw: str
    tier: str  # "exact" | "can_make" | "almost"
    score: float
    score_breakdown: dict[str, float]
    matched: list[IngredientRef]  # non-staple required ings user has
    missing: list[IngredientRef]  # non-staple required ings user lacks
    unused: list[IngredientRef]  # user's ings the dish doesn't use
    assumed_staples: list[IngredientRef]  # staples assumed in the kitchen
    quality_level: str
    status: str


def explain(
    ranked: list[RankedDish],
    *,
    lang: str = "en",
) -> list[ExplainedResult]:
    """
    Attach ingredient details to each ranked dish.

    Performs a single batched DB lookup for all unique ingredient IDs
    referenced across all results, then assembles the explanations.

    Parameters
    ----------
    ranked:
        Output of ranker.rank().
    lang:
        Preferred language for names ("en" or "sw").
        Falls back to English when the Swahili name is empty.

    Returns
    -------
    List of ExplainedResult in the same order as *ranked*.
    """
    if not ranked:
        return []

    # Collect every ingredient ID we need to look up (one batch query)
    all_ids: set[str] = set()
    for rd in ranked:
        jd = rd.judged
        all_ids.update(jd.matched_ids)
        all_ids.update(jd.missing_ids)
        all_ids.update(jd.unused_ids)
        all_ids.update(jd.staples_assumed)

    # Batch fetch ingredient info
    ing_map = _fetch_ingredients(all_ids)

    results: list[ExplainedResult] = []
    for rd in ranked:
        jd = rd.judged
        c = jd.candidate

        results.append(
            ExplainedResult(
                dish_id=c.dish_id,
                slug=c.slug,
                name_en=c.name_en,
                name_sw=c.name_sw,
                tier=rd.tier.value,
                score=rd.score,
                score_breakdown=rd.score_breakdown,
                matched=_refs(jd.matched_ids, ing_map),
                missing=_refs(jd.missing_ids, ing_map),
                unused=_refs(jd.unused_ids, ing_map),
                assumed_staples=_refs(jd.staples_assumed, ing_map),
                quality_level=c.quality_level,
                status=c.status,
            )
        )

    logger.debug("explain: %d results explained", len(results))
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _fetch_ingredients(ids: set[str]) -> dict[str, IngredientRef]:
    """Fetch all ingredient rows for the given IDs in one query."""
    if not ids:
        return {}

    from apps.ingredients.models import Ingredient

    rows = Ingredient.objects.filter(id__in=ids).values("id", "slug", "name_en", "name_sw")

    return {
        str(row["id"]): IngredientRef(
            id=str(row["id"]),
            slug=row["slug"],
            name_en=row["name_en"],
            name_sw=row["name_sw"] or "",
        )
        for row in rows
    }


def _refs(ids: list[str], ing_map: dict[str, IngredientRef]) -> list[IngredientRef]:
    """Convert a list of IDs to IngredientRef objects, preserving order."""
    result = []
    for iid in ids:
        ref = ing_map.get(iid)
        if ref is not None:
            result.append(ref)
        else:
            # Graceful degradation — ID in search arrays but not in ingredients table
            logger.warning("explain: ingredient %s not found in DB", iid)
            result.append(IngredientRef(id=iid, slug="", name_en="", name_sw=""))
    return result
