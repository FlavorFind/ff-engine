"""
E25/E26 — Search views.

POST /v1/search/by-ingredients
  The main search endpoint.  Takes a list of ingredient strings and
  returns tiered, scored, explained dish matches.

E26 adds dataset-version-aware caching with ETag / Cache-Control headers.
"""

from __future__ import annotations

import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status as http_status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from apps.search.cache import (
    build_cache_key,
    compute_etag,
    get_cached_result,
    get_dataset_version,
    set_cached_result,
)
from apps.search.engine import search
from apps.search.pipeline import resolve_ingredients
from apps.search.serializers import SearchRequestSerializer, SearchResultItemSerializer

logger = logging.getLogger(__name__)

CACHE_CONTROL = "private, max-age=300"


@extend_schema(
    summary="Search dishes by ingredients",
    description=(
        "The core search endpoint. Takes a list of free-text ingredient strings "
        "and returns tiered, scored, explained dish matches. "
        "Supports strict mode (exact match) and explore mode (loose match). "
        "Responses are cached by dataset version with ETag support."
    ),
    request=SearchRequestSerializer,
    responses={
        200: OpenApiResponse(
            description=(
                "Tiered search results: exact (can make now), can_make (with staples), "
                "almost (one or two ingredients short)."
            )
        ),
        304: OpenApiResponse(description="Not modified — client cache is current"),
        400: OpenApiResponse(description="Invalid request body"),
    },
    tags=["Search"],
)
@api_view(["POST"])
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

    Headers:
        X-Cache-Hit: true|false
        ETag: "<hash>"
        Cache-Control: private, max-age=300
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
    diet: list[str] = data.get("diet") or []

    # ── Dataset version (drives cache key) ────────────────────────────────────
    dataset_version = get_dataset_version()

    # ── Cache lookup ───────────────────────────────────────────────────────────
    cache_key = build_cache_key(
        dataset_version=dataset_version,
        ingredients=ingredients,
        exclude=exclude,
        mode=mode,
        meal_type=meal_type,
        course=course,
        lang=lang,
        limit=limit,
        diet=diet,
    )

    cached = None
    try:
        cached = get_cached_result(cache_key)
    except Exception:
        logger.warning("Cache read failed — falling through to engine", exc_info=True)

    if cached is not None:
        payload = cached["payload"]
        etag = cached["etag"]

        # If-None-Match → 304 Not Modified
        if_none_match = request.META.get("HTTP_IF_NONE_MATCH")
        if if_none_match is not None and if_none_match == etag:
            response = Response(status=http_status.HTTP_304_NOT_MODIFIED)
            response.headers["ETag"] = etag
            response.headers["Cache-Control"] = CACHE_CONTROL
            response.headers["X-Cache-Hit"] = "true"
            return response

        response = Response(payload, status=http_status.HTTP_200_OK)
        response.headers["X-Cache-Hit"] = "true"
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = CACHE_CONTROL
        return response

    # ── Cache miss: run the pipeline ──────────────────────────────────────────
    # Resolve excluded slugs to IDs
    excluded_ids = _slugs_to_ids(exclude) if exclude else None

    query = resolve_ingredients(ingredients, excluded_ids=excluded_ids)

    # ── Steps 4-7: Find, judge, rank, explain ─────────────────────────────────
    result = search(
        query,
        explore=(mode == "explore"),
        meal_type=meal_type,
        course=course,
        diet=diet or None,
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
        "dataset_version": dataset_version,
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

    etag = compute_etag(payload)
    try:
        set_cached_result(cache_key, payload, etag, dataset_version)
    except Exception:
        logger.warning("Cache write failed — response still returned", exc_info=True)

    # ── Log zero-result queries for observatory (E43) ──────────────────────
    if result.total_results == 0 and ingredients:
        try:
            from apps.search.models import log_zero_result

            log_zero_result(" ".join(ingredients))
        except Exception:
            logger.exception("observatory: failed to log zero-result query")

    # If-None-Match → 304 Not Modified
    if_none_match = request.META.get("HTTP_IF_NONE_MATCH")
    if if_none_match is not None and if_none_match == etag:
        response = Response(status=http_status.HTTP_304_NOT_MODIFIED)
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = CACHE_CONTROL
        response.headers["X-Cache-Hit"] = "false"
        return response

    response = Response(payload, status=http_status.HTTP_200_OK)
    response.headers["X-Cache-Hit"] = "false"
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = CACHE_CONTROL
    return response


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
