"""
E25 — Search engine entry point.

Wires the Finder (E21), Judge (E22), Ranker (E23) and Explainer (E24)
into a single callable that takes a ResolvedQuery and returns
structured, explained, tiered search results.

Usage::

    from apps.search.pipeline import resolve_ingredients
    from apps.search.engine import search

    query = resolve_ingredients(["maize flour"])
    result = search(query)
    # result.exact    → list of ExplainedResult
    # result.can_make → list of ExplainedResult
    # result.almost   → list of ExplainedResult (explore mode only)

Architecture section 6.1, steps 4–7.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from apps.search.explainer import ExplainedResult, explain
from apps.search.finder import find_candidates
from apps.search.judge import judge_candidates
from apps.search.pipeline import ResolvedQuery
from apps.search.ranker import rank

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """
    The complete output of a search call.

    Tiers are populated according to mode:
      - strict (default): exact + can_make
      - explore:          exact + can_make + almost
    """

    exact: list[ExplainedResult] = field(default_factory=list)
    can_make: list[ExplainedResult] = field(default_factory=list)
    almost: list[ExplainedResult] = field(default_factory=list)

    # Input metadata (echoed back to the caller)
    resolved_inputs: list[str] = field(default_factory=list)  # matched slugs/tokens
    ambiguous_inputs: list[str] = field(default_factory=list)  # tokens needing choice
    unmatched_inputs: list[str] = field(default_factory=list)  # tokens not resolved

    # How many dishes were retrieved before filtering
    candidate_count: int = 0

    @property
    def total_results(self) -> int:
        return len(self.exact) + len(self.can_make) + len(self.almost)

    @property
    def has_results(self) -> bool:
        return self.total_results > 0


def search(
    query: ResolvedQuery,
    *,
    explore: bool = False,
    almost_limit: int = 1,
    meal_type: str | None = None,
    course: str | None = None,
    diet: list[str] | None = None,
    status_filter: list[str] | None = None,
    weights: dict[str, float] | None = None,
    preferred_region_id: str | None = None,
    lang: str = "en",
    limit: int = 50,
) -> SearchResult:
    """
    Run the full matching pipeline on a resolved query.

    Parameters
    ----------
    query:
        Output of resolve_ingredients() — contains the ingredient pool.
    explore:
        If True, include the 'almost' tier (dishes missing ≤ almost_limit
        non-staple required ingredients).
    almost_limit:
        Max missing ingredients for the 'almost' tier (default 1).
    meal_type:
        Hard filter by meal type (e.g. 'breakfast', 'lunch').
    course:
        Hard filter by course (e.g. 'main', 'side', 'dessert').
    status_filter:
        Override which dish statuses are included.
        Defaults to reviewed + verified.
    weights:
        Override the default scoring weights.
    preferred_region_id:
        UUID string of a region to boost in scoring.
    lang:
        Language preference for ingredient names in explanations ('en' or 'sw').
    limit:
        Max results per tier (applied after ranking).

    Returns
    -------
    SearchResult with tiered, scored, explained results.
    """
    if query.is_empty:
        logger.debug("search: empty query, returning empty SearchResult")
        return SearchResult(
            unmatched_inputs=list(query.unmatched),
            ambiguous_inputs=[r.raw for r in query.ambiguous],
        )

    # ── Step 4: Retrieve candidates (GIN) ─────────────────────────────────────
    candidates = find_candidates(
        query.pool,
        status_filter=status_filter,
        meal_type=meal_type,
        course=course,
        diet=diet,
        limit=200,  # over-fetch; judge will trim
    )

    if not candidates:
        logger.debug("search: no candidates found for pool of %d", len(query.pool))
        return SearchResult(
            resolved_inputs=query.matched_ids,
            unmatched_inputs=list(query.unmatched),
            ambiguous_inputs=[r.raw for r in query.ambiguous],
            candidate_count=0,
        )

    # ── Step 5: Classify into tiers ───────────────────────────────────────────
    judged = judge_candidates(
        candidates,
        matched_ids=query.matched_ids,
        pool=query.pool,
        explore=explore,
        almost_limit=almost_limit,
    )

    # ── Step 6: Score and rank ────────────────────────────────────────────────
    ranked = rank(
        judged,
        matched_ids=query.matched_ids,
        weights=weights,
        preferred_region_id=preferred_region_id,
    )

    # ── Step 7: Explain ───────────────────────────────────────────────────────
    explained = explain(ranked, lang=lang)

    # ── Split by tier and apply per-tier limit ────────────────────────────────
    exact = [r for r in explained if r.tier == "exact"][:limit]
    can_make = [r for r in explained if r.tier == "can_make"][:limit]
    almost = [r for r in explained if r.tier == "almost"][:limit]

    logger.info(
        "search: %d candidates → exact=%d can_make=%d almost=%d (explore=%s)",
        len(candidates),
        len(exact),
        len(can_make),
        len(almost),
        explore,
    )

    return SearchResult(
        exact=exact,
        can_make=can_make,
        almost=almost,
        resolved_inputs=query.matched_ids,
        ambiguous_inputs=[r.raw for r in query.ambiguous],
        unmatched_inputs=list(query.unmatched),
        candidate_count=len(candidates),
    )
