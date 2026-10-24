"""
Search pipeline entry point — input stage.

Takes raw ingredient text from a caller, runs it through the full
input pipeline (normalise → resolve → expand with staples) and returns
a ResolvedQuery ready for the retrieval step (E21+).

Architecture section 6.1 steps 1–3:
  1. Normalise  (E15)
  2. Resolve    (E16)
  3. Expand     (E20 — add staples, honour exclusions)

Usage::

    from apps.search.pipeline import resolve_ingredients

    query = resolve_ingredients(["tomato", "onion", "nyanya"])
    # query.matched_ids   → [uuid, uuid]   (unique IDs of resolved ingredients)
    # query.ambiguous     → [ResolveResult, ...]  (words needing clarification)
    # query.unmatched     → ["xyz"]               (words that resolved to nothing)
    # query.staples_added → [uuid, ...]           (staple IDs added to the pool)
    # query.pool          → [uuid, ...]           (all IDs incl staples, for GIN query)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from apps.search.resolver import ResolveResult, resolve_many
from apps.search.staples import expand_with_staples

logger = logging.getLogger(__name__)


@dataclass
class ResolvedQuery:
    """
    The result of the input stage of the search pipeline.

    matched_ids     — UUIDs of ingredients that resolved cleanly (as strings)
    ambiguous       — ResolveResults where the word could mean multiple things
    unmatched       — raw tokens that could not be resolved at all
    staples_added   — staple UUIDs that were added to the pool
    pool            — full set of ingredient IDs for the GIN query (matched + staples)
    results         — all individual ResolveResults, for full inspection
    """

    matched_ids: list[str] = field(default_factory=list)
    ambiguous: list[ResolveResult] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)
    staples_added: list[str] = field(default_factory=list)
    pool: list[str] = field(default_factory=list)
    results: list[ResolveResult] = field(default_factory=list)

    @property
    def has_ambiguity(self) -> bool:
        return len(self.ambiguous) > 0

    @property
    def is_empty(self) -> bool:
        """True if no ingredients resolved at all (not even via staples)."""
        return not self.matched_ids and not self.staples_added


def resolve_ingredients(
    raw_inputs: list[str],
    excluded_ids: list[str] | None = None,
) -> ResolvedQuery:
    """
    Run the full input pipeline on *raw_inputs*.

    Parameters
    ----------
    raw_inputs:
        List of raw ingredient strings from the caller, e.g.
        ["2 tomatoes", "Nyanya", "onion", "salt"].
    excluded_ids:
        Optional list of ingredient UUIDs the user explicitly said they
        don't have.  Staples in this list are NOT added to the pool.

    Returns
    -------
    ResolvedQuery with matched IDs, ambiguous words, unmatched words,
    and the full pool for GIN retrieval.
    """
    if not raw_inputs:
        return ResolvedQuery()

    # Deduplicate inputs (case-insensitive)
    seen_raw: set[str] = set()
    unique_inputs: list[str] = []
    for raw in raw_inputs:
        key = raw.strip().lower()
        if key and key not in seen_raw:
            seen_raw.add(key)
            unique_inputs.append(raw.strip())

    results = resolve_many(unique_inputs)

    matched_ids: list[str] = []
    ambiguous: list[ResolveResult] = []
    unmatched: list[str] = []

    for r in results:
        if r.is_matched:
            if r.ingredient_id not in matched_ids:
                matched_ids.append(r.ingredient_id)
        elif r.is_ambiguous:
            ambiguous.append(r)
        else:
            unmatched.append(r.raw)

    # Expand with staples
    pool = expand_with_staples(matched_ids, excluded_ids=excluded_ids)

    # Calculate which staples were actually added
    matched_set = set(matched_ids)
    staples_added = [sid for sid in pool if sid not in matched_set]

    logger.debug(
        "resolve_ingredients: %d matched, %d ambiguous, %d unmatched, %d staples added",
        len(matched_ids),
        len(ambiguous),
        len(unmatched),
        len(staples_added),
    )

    return ResolvedQuery(
        matched_ids=matched_ids,
        ambiguous=ambiguous,
        unmatched=unmatched,
        staples_added=staples_added,
        pool=pool,
        results=results,
    )
