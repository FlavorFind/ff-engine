"""
E13 — Duplicate detector.

Detects potential duplicate ingredients and dishes by comparing names using
trigram similarity (PostgreSQL pg_trgm) and normalised string distance.

Falls back to a pure-Python Jaro-Winkler approximation when PostgreSQL
trigram functions are not available (e.g. SQLite in tests).

Usage::

    from apps.curation.duplicate_detector import find_duplicate_ingredients, find_duplicate_dishes

    dupes = find_duplicate_ingredients("Tomato Paste")
    # → [DuplicateMatch(name="Tomato paste", similarity=0.93, pk="...")]

    dupes = find_duplicate_dishes("Nyama Choma")
    # → [DuplicateMatch(name="Nyama choma", similarity=1.0, pk="...")]

Blueprint spec:
  "Duplicate detector: warns when a new dish or ingredient looks like
   an existing one."
  "Catches deliberately planted duplicates."
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class DuplicateMatch:
    """A potential duplicate found by the detector."""

    name: str
    similarity: float  # 0.0 – 1.0
    pk: str
    kind: str  # "ingredient" | "dish"

    def __str__(self) -> str:
        pct = int(self.similarity * 100)
        return f"{self.name!r} ({pct}% similar)"


# Minimum similarity to be flagged as a potential duplicate
DEFAULT_THRESHOLD = 0.75


def find_duplicate_ingredients(
    name: str,
    threshold: float = DEFAULT_THRESHOLD,
    exclude_pk: str | None = None,
) -> list[DuplicateMatch]:
    """
    Return ingredients whose name_en is similar to *name*.

    Checks both name_en and name_sw.
    """
    from apps.curation.normaliser import normalise
    from apps.ingredients.models import Ingredient

    norm = normalise(name)
    matches: list[DuplicateMatch] = []

    # Try PostgreSQL trigram similarity first (requires pg_trgm extension).
    # Wrap in a savepoint so a ProgrammingError doesn't abort the outer transaction.
    from django.db import transaction as _tx

    try:
        with _tx.atomic():
            matches = _pg_ingredient_similarity(norm, threshold, exclude_pk)
    except Exception:
        # Fallback: Python SequenceMatcher over all names
        matches = _python_ingredient_similarity(Ingredient, norm, threshold, exclude_pk)

    return sorted(matches, key=lambda m: m.similarity, reverse=True)


def find_duplicate_dishes(
    name: str,
    threshold: float = DEFAULT_THRESHOLD,
    exclude_pk: str | None = None,
) -> list[DuplicateMatch]:
    """
    Return dishes whose name_en or name_sw is similar to *name*.
    """
    from apps.curation.normaliser import normalise
    from apps.dishes.models import Dish

    norm = normalise(name)
    matches: list[DuplicateMatch] = []

    from django.db import transaction as _tx

    try:
        with _tx.atomic():
            matches = _pg_dish_similarity(norm, threshold, exclude_pk)
    except Exception:
        matches = _python_dish_similarity(Dish, norm, threshold, exclude_pk)

    return sorted(matches, key=lambda m: m.similarity, reverse=True)


# ---------------------------------------------------------------------------
# PostgreSQL trigram backend
# ---------------------------------------------------------------------------


def _pg_ingredient_similarity(
    norm: str, threshold: float, exclude_pk: str | None
) -> list[DuplicateMatch]:
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT set_limit(%s)", [threshold])
        query = """
            SELECT id, name_en,
                   GREATEST(
                       similarity(lower(name_en), lower(%s)),
                       similarity(lower(COALESCE(name_sw, '')), lower(%s))
                   ) AS sim
            FROM ingredient
            WHERE (
                lower(name_en) %% lower(%s)
                OR lower(COALESCE(name_sw, '')) %% lower(%s)
            )
            ORDER BY sim DESC
            LIMIT 10
        """
        params = [norm, norm, norm, norm]
        if exclude_pk:
            query = query.replace("WHERE (", "WHERE id != %s AND (")
            params = [exclude_pk] + params
        cursor.execute(query, params)
        rows = cursor.fetchall()

    return [
        DuplicateMatch(name=row[1], similarity=float(row[2]), pk=str(row[0]), kind="ingredient")
        for row in rows
    ]


def _pg_dish_similarity(
    norm: str, threshold: float, exclude_pk: str | None
) -> list[DuplicateMatch]:
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT set_limit(%s)", [threshold])
        query = """
            SELECT id, name_en,
                   GREATEST(
                       similarity(lower(name_en), lower(%s)),
                       similarity(lower(COALESCE(name_sw, '')), lower(%s))
                   ) AS sim
            FROM dish
            WHERE (
                lower(name_en) %% lower(%s)
                OR lower(COALESCE(name_sw, '')) %% lower(%s)
            )
            ORDER BY sim DESC
            LIMIT 10
        """
        params = [norm, norm, norm, norm]
        if exclude_pk:
            query = query.replace("WHERE (", "WHERE id != %s AND (")
            params = [exclude_pk] + params
        cursor.execute(query, params)
        rows = cursor.fetchall()

    return [
        DuplicateMatch(name=row[1], similarity=float(row[2]), pk=str(row[0]), kind="dish")
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Pure-Python fallback (used in tests with SQLite / no pg_trgm)
# ---------------------------------------------------------------------------


def _similarity(a: str, b: str) -> float:
    """SequenceMatcher-based similarity in [0, 1]."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _python_ingredient_similarity(
    model, norm: str, threshold: float, exclude_pk: str | None
) -> list[DuplicateMatch]:
    qs = model.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    matches = []
    for obj in qs:
        sim_en = _similarity(norm, obj.name_en or "")
        sim_sw = _similarity(norm, obj.name_sw or "")
        sim = max(sim_en, sim_sw)
        if sim >= threshold:
            matches.append(
                DuplicateMatch(name=obj.name_en, similarity=sim, pk=str(obj.pk), kind="ingredient")
            )
    return matches


def _python_dish_similarity(
    model, norm: str, threshold: float, exclude_pk: str | None
) -> list[DuplicateMatch]:
    qs = model.objects.all()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    matches = []
    for obj in qs:
        sim_en = _similarity(norm, obj.name_en or "")
        sim_sw = _similarity(norm, obj.name_sw or "")
        sim = max(sim_en, sim_sw)
        if sim >= threshold:
            matches.append(
                DuplicateMatch(name=obj.name_en, similarity=sim, pk=str(obj.pk), kind="dish")
            )
    return matches
