"""
E16 — The Resolver.

Maps a normalised text token to an ingredient ID (or a list of options
when the word is ambiguous).

Resolution pipeline (Architecture section 6.1, step 2):
  1. Exact match  — look up normalised_alias in IngredientAlias.
  2. Name match   — look up normalised text against ingredient name_en / name_sw.
  3. Fuzzy match  — pg_trgm similarity on alias and name tables (threshold 0.45).
  4. Ambiguity    — if step 1/2 maps the same text to multiple ingredients,
                    return all options and let the caller decide.  Never guess.

Return value is a ResolveResult dataclass:

    ResolveResult(
        raw="nyanya",
        normalised="nyanya",
        status="matched",          # matched | ambiguous | unmatched
        ingredient_id="<uuid>",    # set when status == "matched"
        confidence=1.0,            # 1.0 for exact, 0.45–0.99 for fuzzy
        options=[],                # set when status == "ambiguous"
        method="exact_alias",      # exact_alias | exact_name | fuzzy
    )

Exit check (E16):
  "Correct on 100 test words, including Swahili and misspellings."
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from apps.curation.normaliser import normalise

logger = logging.getLogger(__name__)

# Minimum similarity score to accept a fuzzy match
FUZZY_THRESHOLD = 0.45

# Status constants
STATUS_MATCHED = "matched"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_UNMATCHED = "unmatched"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ResolveOption:
    """One candidate when a word is ambiguous."""

    ingredient_id: str
    name: str
    confidence: float


@dataclass
class ResolveResult:
    """Result for a single input token."""

    raw: str
    normalised: str
    status: str  # matched | ambiguous | unmatched
    ingredient_id: str | None = None
    confidence: float = 0.0
    method: str = ""  # exact_alias | exact_name | fuzzy
    options: list[ResolveOption] = field(default_factory=list)

    @property
    def is_matched(self) -> bool:
        return self.status == STATUS_MATCHED

    @property
    def is_ambiguous(self) -> bool:
        return self.status == STATUS_AMBIGUOUS

    @property
    def is_unmatched(self) -> bool:
        return self.status == STATUS_UNMATCHED


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve(raw: str) -> ResolveResult:
    """
    Resolve a single raw ingredient text to an ingredient ID.

    Steps: normalise → exact alias → exact name → fuzzy.
    """
    norm = normalise(raw)

    if not norm:
        return ResolveResult(raw=raw, normalised=norm, status=STATUS_UNMATCHED)

    # 1. Exact alias match
    result = _exact_alias(raw, norm)
    if result is not None:
        return result

    # 2. Exact name match (name_en / name_sw)
    result = _exact_name(raw, norm)
    if result is not None:
        return result

    # 3. Fuzzy match
    result = _fuzzy(raw, norm)
    if result is not None:
        return result

    return ResolveResult(raw=raw, normalised=norm, status=STATUS_UNMATCHED)


def resolve_many(raw_tokens: list[str]) -> list[ResolveResult]:
    """Resolve a list of raw ingredient texts."""
    return [resolve(t) for t in raw_tokens]


# ---------------------------------------------------------------------------
# Step 1: exact alias lookup
# ---------------------------------------------------------------------------


def _exact_alias(raw: str, norm: str) -> ResolveResult | None:
    """
    Look up *norm* in IngredientAlias.normalized_alias.

    If multiple aliases point to different ingredients, return ambiguous.
    If all aliases point to the same ingredient, return matched.
    """
    from apps.ingredients.models import IngredientAlias

    matches = list(
        IngredientAlias.objects.filter(normalized_alias=norm)
        .select_related("ingredient")
        .values("ingredient__id", "ingredient__name_en")
    )

    if not matches:
        return None

    unique_ids = {str(m["ingredient__id"]) for m in matches}

    if len(unique_ids) == 1:
        ing_id = next(iter(unique_ids))
        return ResolveResult(
            raw=raw,
            normalised=norm,
            status=STATUS_MATCHED,
            ingredient_id=ing_id,
            confidence=1.0,
            method="exact_alias",
        )

    # Same normalised alias maps to multiple ingredients → ambiguous
    seen: dict[str, str] = {}
    for m in matches:
        seen[str(m["ingredient__id"])] = m["ingredient__name_en"]

    return ResolveResult(
        raw=raw,
        normalised=norm,
        status=STATUS_AMBIGUOUS,
        options=[
            ResolveOption(ingredient_id=iid, name=name, confidence=1.0)
            for iid, name in seen.items()
        ],
        method="exact_alias",
    )


# ---------------------------------------------------------------------------
# Step 2: exact name match
# ---------------------------------------------------------------------------


def _exact_name(raw: str, norm: str) -> ResolveResult | None:
    """
    Match *norm* against normalised ingredient name_en and name_sw.
    """
    from apps.curation.normaliser import normalise as _norm
    from apps.ingredients.models import Ingredient

    # Collect candidates whose normalised name matches
    candidates = []
    for ing in Ingredient.objects.all().values("id", "name_en", "name_sw"):
        if _norm(ing["name_en"]) == norm or (ing["name_sw"] and _norm(ing["name_sw"]) == norm):
            candidates.append(ing)

    if not candidates:
        return None

    if len(candidates) == 1:
        return ResolveResult(
            raw=raw,
            normalised=norm,
            status=STATUS_MATCHED,
            ingredient_id=str(candidates[0]["id"]),
            confidence=1.0,
            method="exact_name",
        )

    # Multiple ingredients with the same normalised name → ambiguous
    return ResolveResult(
        raw=raw,
        normalised=norm,
        status=STATUS_AMBIGUOUS,
        options=[
            ResolveOption(
                ingredient_id=str(c["id"]),
                name=c["name_en"],
                confidence=1.0,
            )
            for c in candidates
        ],
        method="exact_name",
    )


# ---------------------------------------------------------------------------
# Step 3: fuzzy match via pg_trgm (Python fallback for tests)
# ---------------------------------------------------------------------------


def _fuzzy(raw: str, norm: str) -> ResolveResult | None:
    """
    Use PostgreSQL trigram similarity to find close matches.
    Falls back to Python difflib when pg_trgm is not available.
    """
    from django.db import transaction as _tx

    try:
        with _tx.atomic():
            return _pg_fuzzy(raw, norm)
    except Exception:
        return _python_fuzzy(raw, norm)


def _pg_fuzzy(raw: str, norm: str) -> ResolveResult | None:
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT set_limit(%s)", [FUZZY_THRESHOLD])
        cursor.execute(
            """
            SELECT id, name_en,
                   GREATEST(
                       similarity(lower(name_en), %s),
                       similarity(lower(COALESCE(name_sw, '')), %s)
                   ) AS sim
            FROM ingredient
            WHERE (
                lower(name_en) %% %s
                OR lower(COALESCE(name_sw, '')) %% %s
            )
            ORDER BY sim DESC
            LIMIT 5
            """,
            [norm, norm, norm, norm],
        )
        rows = cursor.fetchall()

    if not rows:
        return None

    best_sim = float(rows[0][2])

    # Also check aliases for fuzzy
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT ia.ingredient_id, i.name_en,
                   similarity(lower(ia.alias), %s) AS sim
            FROM ingredient_alias ia
            JOIN ingredient i ON i.id = ia.ingredient_id
            WHERE lower(ia.alias) %% %s
            ORDER BY sim DESC
            LIMIT 5
            """,
            [norm, norm],
        )
        alias_rows = cursor.fetchall()

    # Merge and pick the highest-confidence unique ingredient
    all_rows = [(str(r[0]), r[1], float(r[2])) for r in rows]
    all_rows += [(str(r[0]), r[1], float(r[2])) for r in alias_rows]
    all_rows.sort(key=lambda x: x[2], reverse=True)

    if not all_rows:
        return None

    # Deduplicate by ingredient ID, keep best score
    seen: dict[str, tuple[str, float]] = {}
    for iid, name, sim in all_rows:
        if iid not in seen or sim > seen[iid][1]:
            seen[iid] = (name, sim)

    top = sorted(seen.items(), key=lambda x: x[1][1], reverse=True)
    best_id, (best_name, best_sim) = top[0]

    if best_sim < FUZZY_THRESHOLD:
        return None

    # If top two are very close in score, return ambiguous
    if len(top) > 1:
        second_id, (second_name, second_sim) = top[1]
        if best_sim - second_sim < 0.05:
            return ResolveResult(
                raw=raw,
                normalised=norm,
                status=STATUS_AMBIGUOUS,
                method="fuzzy",
                options=[
                    ResolveOption(ingredient_id=best_id, name=best_name, confidence=best_sim),
                    ResolveOption(ingredient_id=second_id, name=second_name, confidence=second_sim),
                ],
            )

    return ResolveResult(
        raw=raw,
        normalised=norm,
        status=STATUS_MATCHED,
        ingredient_id=best_id,
        confidence=best_sim,
        method="fuzzy",
    )


def _python_fuzzy(raw: str, norm: str) -> ResolveResult | None:
    """Pure-Python fallback using SequenceMatcher."""
    from difflib import SequenceMatcher

    from apps.curation.normaliser import normalise as _norm
    from apps.ingredients.models import Ingredient

    candidates = []
    for ing in Ingredient.objects.all().values("id", "name_en", "name_sw"):
        sim_en = SequenceMatcher(None, norm, _norm(ing["name_en"])).ratio()
        sim_sw = SequenceMatcher(None, norm, _norm(ing["name_sw"] or "")).ratio()
        sim = max(sim_en, sim_sw)
        if sim >= FUZZY_THRESHOLD:
            candidates.append((str(ing["id"]), ing["name_en"], sim))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[2], reverse=True)
    best_id, best_name, best_sim = candidates[0]

    if len(candidates) > 1:
        _, _, second_sim = candidates[1]
        if best_sim - second_sim < 0.05:
            return ResolveResult(
                raw=raw,
                normalised=norm,
                status=STATUS_AMBIGUOUS,
                method="fuzzy",
                options=[
                    ResolveOption(ingredient_id=iid, name=name, confidence=sim)
                    for iid, name, sim in candidates[:3]
                ],
            )

    return ResolveResult(
        raw=raw,
        normalised=norm,
        status=STATUS_MATCHED,
        ingredient_id=best_id,
        confidence=best_sim,
        method="fuzzy",
    )
