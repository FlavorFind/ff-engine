"""
E22 — The Judge (tier classification).

Decides, for each candidate dish, whether it belongs in the
exact, can_make, or almost tier — or should be dropped entirely.

Architecture section 6.2 — Tier definitions:

  Exact    — Every non-staple required ingredient is covered by the user's
              ingredients, AND the dish uses every ingredient the user typed.
              (missing is empty AND unused is empty)

  Can make — Every non-staple required ingredient is covered, but the user
              typed some ingredient the dish does not use.
              (missing is empty AND unused is not empty)

  Almost   — Missing at most K required non-staple ingredients (K=1 default).
              Explore mode only.

Architecture section 6.5 — Decision flow:
  1. Remove staples from the dish's required list  → real requirements
  2. Which real requirements has the user not covered?  → missing list
  3. Which of the user's ingredients does the dish not use at all?  → unused list
  4. missing empty AND unused empty  → Exact
  5. missing empty AND unused not empty  → Can make
  6. explore mode AND missing count <= almost_limit  → Almost
  7. Anything else  → Dropped

Exit check (E22):
  "Property tests: adding an ingredient never removes a can-make dish."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from apps.search.finder import CandidateDish
from apps.search.staples import get_staple_ids

logger = logging.getLogger(__name__)

# Default maximum missing ingredients for the 'almost' tier
DEFAULT_ALMOST_LIMIT = 1


class Tier(str, Enum):
    EXACT = "exact"
    CAN_MAKE = "can_make"
    ALMOST = "almost"


@dataclass
class JudgedDish:
    """
    A candidate that has been assigned a tier.
    Carries the classification data needed by the Ranker and Explainer.
    """

    candidate: CandidateDish
    tier: Tier
    # IDs the user provided that the dish actually requires (non-staple)
    matched_ids: list[str] = field(default_factory=list)
    # Non-staple required IDs the user did NOT provide
    missing_ids: list[str] = field(default_factory=list)
    # IDs the user provided that the dish does not use at all
    unused_ids: list[str] = field(default_factory=list)
    # Staple IDs that were assumed present (from the pool, not from user input)
    staples_assumed: list[str] = field(default_factory=list)


def judge_candidates(
    candidates: list[CandidateDish],
    matched_ids: list[str],
    pool: list[str],
    *,
    explore: bool = False,
    almost_limit: int = DEFAULT_ALMOST_LIMIT,
) -> list[JudgedDish]:
    """
    Classify each candidate into a tier.

    Parameters
    ----------
    candidates:
        Output of find_candidates().
    matched_ids:
        IDs the user actually typed and resolved (NOT including staples).
    pool:
        Full pool including staples — used for coverage check.
    explore:
        If True, include the 'almost' tier (dishes missing ≤ almost_limit
        non-staple required ingredients).
    almost_limit:
        Maximum missing ingredients for the 'almost' tier.

    Returns
    -------
    List of JudgedDish for dishes that passed tier classification.
    Dropped dishes are excluded.
    """
    staples = get_staple_ids()
    pool_set = set(pool)
    user_set = set(matched_ids)

    judged: list[JudgedDish] = []

    for candidate in candidates:
        result = _classify(
            candidate=candidate,
            user_set=user_set,
            pool_set=pool_set,
            staples=staples,
            explore=explore,
            almost_limit=almost_limit,
        )
        if result is not None:
            judged.append(result)

    logger.debug(
        "judge_candidates: %d candidates → %d judged (explore=%s)",
        len(candidates),
        len(judged),
        explore,
    )
    return judged


def _classify(
    candidate: CandidateDish,
    user_set: set[str],
    pool_set: set[str],
    staples: frozenset[str],
    explore: bool,
    almost_limit: int,
) -> JudgedDish | None:
    """Classify a single candidate. Returns None if the dish should be dropped."""

    # Step 1: real requirements = required_ids with staples removed
    # (candidate.required_ids was already stored without staples by rebuild_search_arrays,
    # but we double-check here in case a staple flag changed after rebuild)
    real_required = [iid for iid in candidate.required_ids if iid not in staples]

    # Step 2: missing = real requirements the pool does NOT cover
    missing = [iid for iid in real_required if iid not in pool_set]

    # Step 3: unused = user's matched ingredients the dish doesn't use at all
    dish_all_set = set(candidate.all_ids)
    unused = [iid for iid in user_set if iid not in dish_all_set]

    # Step 4/5/6/7: tier decision
    if not missing and not unused:
        tier = Tier.EXACT
    elif not missing and unused:
        tier = Tier.CAN_MAKE
    elif explore and len(missing) <= almost_limit:
        tier = Tier.ALMOST
    else:
        return None  # Dropped

    # matched = real requirements that ARE covered by the pool
    matched = [iid for iid in real_required if iid in pool_set]

    # staples assumed = staple IDs in the pool that the dish actually uses
    staples_assumed = [iid for iid in candidate.all_ids if iid in staples and iid in pool_set]

    return JudgedDish(
        candidate=candidate,
        tier=tier,
        matched_ids=matched,
        missing_ids=missing,
        unused_ids=unused,
        staples_assumed=staples_assumed,
    )
