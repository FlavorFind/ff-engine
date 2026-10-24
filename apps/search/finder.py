"""
E21 — The Finder (candidate retrieval).

Uses PostgreSQL GIN indexes on the dish search arrays to quickly
shortlist dishes whose ingredient sets overlap the user's ingredient pool.

Architecture section 6.1, step 4:
  "Fetch candidate dishes whose ingredient arrays overlap the user's
   ingredients, using a GIN index. Apply hard filters (dietary tags,
   allergen exclusions, status)."

The Finder is intentionally permissive — it over-selects and passes
the full shortlist to the Judge (E22) which applies the strict tier rules.

Exit check (E21):
  "Returns only overlapping dishes; benchmarked."
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from apps.core.models import StatusChoices

logger = logging.getLogger(__name__)

# Statuses considered "live" for search
_LIVE_STATUSES = [StatusChoices.REVIEWED, StatusChoices.VERIFIED]


@dataclass
class CandidateDish:
    """
    A dish that passed the GIN overlap filter.

    Carries everything the Judge, Ranker and Explainer need
    so we don't have to re-query the DB per dish.
    """

    dish_id: str
    slug: str
    name_en: str
    name_sw: str
    required_ids: list[str]  # non-staple required (pre-filtered by Finder)
    optional_ids: list[str]
    primary_ids: list[str]
    all_ids: list[str]
    popularity: float
    quality_level: str
    status: str


def find_candidates(
    pool: list[str],
    *,
    status_filter: list[str] | None = None,
    meal_type: str | None = None,
    course: str | None = None,
    limit: int = 200,
) -> list[CandidateDish]:
    """
    Return dishes whose all_ids array overlaps *pool* using the GIN index.

    Parameters
    ----------
    pool:
        Full ingredient ID pool (matched + staples) from the pipeline.
    status_filter:
        List of StatusChoices values to include.
        Defaults to [REVIEWED, VERIFIED].
    meal_type:
        Optional meal_type filter (e.g. 'breakfast').
    course:
        Optional course filter (e.g. 'main').
    limit:
        Maximum number of candidates to return (safety cap).
        The Judge drops non-matching dishes afterwards.

    Returns
    -------
    List of CandidateDish, unordered.
    """
    if not pool:
        logger.debug("find_candidates: empty pool, returning []")
        return []

    from django.contrib.postgres.expressions import ArraySubquery  # noqa: F401
    from django.contrib.postgres.fields import ArrayField as _AF  # noqa: F401

    from apps.dishes.models import Dish

    statuses = status_filter or _LIVE_STATUSES

    # Convert string UUIDs to actual UUID objects for the array overlap query
    try:
        pool_uuids = [uuid.UUID(iid) for iid in pool]
    except (ValueError, AttributeError) as exc:
        logger.error("find_candidates: invalid UUID in pool: %s", exc)
        return []

    qs = Dish.objects.filter(
        status__in=statuses,
        all_ids__overlap=pool_uuids,
    ).values(
        "id",
        "slug",
        "name_en",
        "name_sw",
        "required_ids",
        "optional_ids",
        "primary_ids",
        "all_ids",
        "popularity",
        "quality_level",
        "status",
    )

    if meal_type:
        qs = qs.filter(meal_type=meal_type)
    if course:
        qs = qs.filter(course=course)

    qs = qs[:limit]

    candidates = []
    for row in qs:
        candidates.append(
            CandidateDish(
                dish_id=str(row["id"]),
                slug=row["slug"],
                name_en=row["name_en"],
                name_sw=row["name_sw"],
                required_ids=[str(u) for u in (row["required_ids"] or [])],
                optional_ids=[str(u) for u in (row["optional_ids"] or [])],
                primary_ids=[str(u) for u in (row["primary_ids"] or [])],
                all_ids=[str(u) for u in (row["all_ids"] or [])],
                popularity=float(row["popularity"]),
                quality_level=row["quality_level"],
                status=row["status"],
            )
        )

    logger.debug(
        "find_candidates: pool=%d ids → %d candidates (statuses=%s)",
        len(pool),
        len(candidates),
        statuses,
    )
    return candidates
