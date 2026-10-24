"""
E25 — Search views.

POST /v1/search/by-ingredients
  The main search endpoint.  Takes a list of ingredient strings and
  returns tiered, scored, explained dish matches.
"""

from __future__ import annotations

import logging

from django.conf import settings
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.search.engine import search
from apps.search.pipeline import resolve_ingredients
from apps.search.serializers import SearchRequestSerializer, SearchResultItemSerializer

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([AllowAny])
def search_by_ingredients(request: Request) -> Response:
    """
    POST /v1/search/by-ingredients

    Search for dishes by ingredient strings.

    Request body (JSON):
        {
          "ingredients": ["tomato", "onion"],   // required, up to 30
          "exclude": [],                         // optional slugs to exclude
          "mode": "strict",                      // "strict" | "explore"
          "meal_type": null,                     // optional filter
          "course": null,                        // optional filter
          "lang": "en",                          // "en" | "sw"
          "limit": 20                            // 1–50 per tier
        }

    Response (200):
        {
          "dataset_version": "0.0.0",
          "mode": "strict",
          "candidate_count": 12,
          "total_results": 3,
          "resolved": [...],
          "ambiguous": [...],
          "unmatched": [...],
          "results": {
            "exact":    [...],
            "can_make": [...],
            "almost":   []
          }
        }
    """
    req_ser = SearchRequestSerializer(data=request.data)
    if not req_ser.is_valid():
        return Response(
            {"errors": req_ser.errors},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    data = req_ser.validated_data
    ingredients: list[str] = data["ingredients"]
    exclude: list[str] = data.get("exclude") or []
    mode: str = data.get("mode", "strict")
    meal_type: str | None = data.get("meal_type")
    course: str | None = data.get("course")
    lang: str = data.get("lang", "en")
    limit: int = data.get("limit", 20)

    # ── Step 1-3: Normalise, resolve, expand ──────────────────────────────────
    # Resolve excluded slugs to IDs
    excluded_ids = _slugs_to_ids(exclude) if exclude else None

    query = resolve_ingredients(ingredients, excluded_ids=excluded_ids)

    # ── Steps 4-7: Find, judge, rank, explain ─────────────────────────────────
    result = search(
        query,
        explore=(mode == "explore"),
        meal_type=meal_type,
        course=course,
        lang=lang,
        limit=limit,
    )

    # ── Serialize response ────────────────────────────────────────────────────
    def serialise_tier(items):
        return SearchResultItemSerializer(items, many=True).data

    resolved_info = [
        {
            "token": r.raw,
            "status": r.status,
            "ingredient_id": r.ingredient_id,
            "method": r.method,
            "confidence": r.confidence,
        }
        for r in query.results
    ]

    payload = {
        "dataset_version": getattr(settings, "DATASET_VERSION", "0.0.0"),
        "mode": mode,
        "candidate_count": result.candidate_count,
        "total_results": result.total_results,
        "resolved": resolved_info,
        "ambiguous": [r.raw for r in query.ambiguous],
        "unmatched": list(query.unmatched),
        "results": {
            "exact": serialise_tier(result.exact),
            "can_make": serialise_tier(result.can_make),
            "almost": serialise_tier(result.almost),
        },
    }

    return Response(payload, status=http_status.HTTP_200_OK)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _slugs_to_ids(slugs: list[str]) -> list[str]:
    """
    Convert a list of ingredient slugs or UUID strings to UUID strings.
    Invalid / not-found slugs are silently ignored.
    """
    from apps.ingredients.models import Ingredient

    ids: list[str] = []
    for slug in slugs:
        # Accept both slug and raw UUID
        qs = Ingredient.objects.filter(slug=slug).values_list("id", flat=True)
        for pk in qs:
            ids.append(str(pk))
    return ids
