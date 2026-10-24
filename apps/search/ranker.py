"""
E23 — The Ranker (weighted scoring).

Computes a score for each judged dish and sorts results within each tier.

Architecture section 6.4 — Scoring (starting weights):

  Signal           Weight    Meaning
  ─────────────────────────────────────────────────────────────────────
  coverage         0.40      Share of dish's non-staple required ingredients
                             the user has
  primary_hit      0.20      Share of dish's primary ingredients in user input
  usage_ratio      0.15      Share of user's ingredients the dish actually uses
  popularity       0.10      How commonly the dish is cooked or viewed
  quality_bonus    0.10      verified > reviewed > seeded/community
  region_pref      0.05      Optional boost for a chosen region/cuisine
  missing_penalty  -0.15     Per missing ingredient (almost tier only)

Weights live in configuration, not code.  Every change is checked against
the golden set in CI, so tuning one query cannot silently break ten others.

Tie-breaking: equal scores → alphabetical by slug (deterministic).

Exit check (E23):
  "Deterministic; ties broken by name."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from apps.search.judge import JudgedDish, Tier

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Default weights (can be overridden in settings or passed at call time)
# ──────────────────────────────────────────────────────────────────────────────

DEFAULT_WEIGHTS: dict[str, float] = {
    "coverage": 0.40,
    "primary_hit": 0.20,
    "usage_ratio": 0.15,
    "popularity": 0.10,
    "quality_bonus": 0.10,
    "region_pref": 0.05,
    "missing_penalty": -0.15,
}

# Quality level → bonus score (0.0–1.0)
_QUALITY_SCORE: dict[str, float] = {
    "verified": 1.0,
    "reviewed": 0.6,
    "community": 0.3,
    "seeded": 0.1,
}


@dataclass
class RankedDish:
    """A judged dish with its computed score and score breakdown."""

    judged: JudgedDish
    score: float
    score_breakdown: dict[str, float] = field(default_factory=dict)

    # Convenience pass-throughs
    @property
    def tier(self) -> Tier:
        return self.judged.tier

    @property
    def slug(self) -> str:
        return self.judged.candidate.slug


def rank(
    judged: list[JudgedDish],
    matched_ids: list[str],
    *,
    weights: dict[str, float] | None = None,
    preferred_region_id: str | None = None,
) -> list[RankedDish]:
    """
    Score and sort all judged dishes.

    Results are grouped by tier (exact first, then can_make, then almost)
    and sorted by descending score within each tier.  Ties are broken
    alphabetically by slug.

    Parameters
    ----------
    judged:
        Output of judge_candidates().
    matched_ids:
        IDs the user actually typed (used for usage_ratio calculation).
    weights:
        Override the default weights.  Any missing key falls back to default.
    preferred_region_id:
        Optional region UUID string to boost region_pref signal.

    Returns
    -------
    Flat list of RankedDish ordered by tier then score then slug.
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    user_count = max(len(matched_ids), 1)  # avoid division by zero
    user_set = set(matched_ids)

    ranked: list[RankedDish] = []
    for jd in judged:
        scored = _score_dish(jd, w, user_count, user_set, preferred_region_id)
        ranked.append(scored)

    # Sort: tier order first, then descending score, then slug for determinism
    tier_order = {Tier.EXACT: 0, Tier.CAN_MAKE: 1, Tier.ALMOST: 2}
    ranked.sort(key=lambda r: (tier_order[r.tier], -r.score, r.slug))

    logger.debug("rank: %d dishes scored (weights=%s)", len(ranked), list(w.keys()))
    return ranked


def _score_dish(
    jd: JudgedDish,
    w: dict[str, float],
    user_count: int,
    user_set: set[str],
    preferred_region_id: str | None,
) -> RankedDish:
    """Compute the weighted score for a single JudgedDish."""
    c = jd.candidate

    # 1. Coverage: what fraction of non-staple required ingredients does the
    #    user cover?
    real_required_count = len(jd.matched_ids) + len(jd.missing_ids)
    if real_required_count > 0:
        coverage = len(jd.matched_ids) / real_required_count
    else:
        # Dish has no non-staple requirements (e.g. only staples) → perfect
        coverage = 1.0

    # 2. Primary hit: fraction of primary ingredients in user's input
    primary_count = len(c.primary_ids)
    if primary_count > 0:
        hits = sum(1 for pid in c.primary_ids if pid in user_set)
        primary_hit = hits / primary_count
    else:
        primary_hit = 0.0

    # 3. Usage ratio: fraction of user's ingredients the dish uses
    dish_all_set = set(c.all_ids)
    used = sum(1 for uid in user_set if uid in dish_all_set)
    usage_ratio = used / user_count

    # 4. Popularity (already 0–1 from model, cap just in case)
    popularity = min(max(c.popularity, 0.0), 1.0)

    # 5. Quality bonus
    quality_bonus = _QUALITY_SCORE.get(c.quality_level, 0.1)

    # 6. Region preference
    region_pref = 0.0
    if preferred_region_id:
        # Deferred import to avoid circular dependency; region check is optional
        try:
            from apps.regions.models import DishRegion

            if DishRegion.objects.filter(dish_id=c.dish_id, region_id=preferred_region_id).exists():
                region_pref = 1.0
        except Exception:
            pass

    # 7. Missing penalty (almost tier only)
    missing_penalty = len(jd.missing_ids) * abs(w.get("missing_penalty", 0.15))

    # Weighted sum
    score = (
        w["coverage"] * coverage
        + w["primary_hit"] * primary_hit
        + w["usage_ratio"] * usage_ratio
        + w["popularity"] * popularity
        + w["quality_bonus"] * quality_bonus
        + w["region_pref"] * region_pref
        - missing_penalty
    )

    breakdown = {
        "coverage": round(w["coverage"] * coverage, 4),
        "primary_hit": round(w["primary_hit"] * primary_hit, 4),
        "usage_ratio": round(w["usage_ratio"] * usage_ratio, 4),
        "popularity": round(w["popularity"] * popularity, 4),
        "quality_bonus": round(w["quality_bonus"] * quality_bonus, 4),
        "region_pref": round(w["region_pref"] * region_pref, 4),
        "missing_penalty": round(-missing_penalty, 4),
        "total": round(score, 4),
    }

    return RankedDish(judged=jd, score=round(score, 6), score_breakdown=breakdown)
