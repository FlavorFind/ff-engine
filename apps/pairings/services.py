"""
E29 — Pairing service.

Business logic for pairing retrieval.
Thin service layer — views stay thin, logic lives here.
"""
from __future__ import annotations

from apps.pairings.models import Pairing


def get_pairings_for_dish(
    dish_id: str,
    *,
    pairing_type: str | None = None,
    min_strength: int = 1,
    limit: int = 20,
) -> list[Pairing]:
    """
    Return pairings for a dish, ordered by strength descending.

    Parameters
    ----------
    dish_id:
        UUID string of the dish.
    pairing_type:
        Optional filter: 'side', 'drink', 'dessert', 'starter'.
    min_strength:
        Minimum strength to include (1–5). Default 1 = include all.
    limit:
        Maximum results.
    """
    qs = (
        Pairing.objects.filter(dish_id=dish_id, strength__gte=min_strength)
        .select_related("paired_dish")
        .order_by("-strength", "pairing_type")
    )
    if pairing_type:
        qs = qs.filter(pairing_type=pairing_type)
    return list(qs[:limit])
