"""
E29 — Pairing and substitution endpoints.
E30 — Missing-ingredients endpoint.

Endpoints:
  GET  /v1/dishes/{dish_id}/pairings        → sides, drinks, desserts with strength
  GET  /v1/dishes/{dish_id}/substitutions   → replacements for dish ingredients
  POST /v1/dishes/{dish_id}/missing         → given what I have, what do I still need?

Architecture section 7 (API Specification):
  GET /v1/dishes/{id}/pairings
  GET /v1/dishes/{id}/substitutions
  POST /v1/dishes/{id}/missing
"""

from __future__ import annotations

import logging

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.dishes.models import Dish, DishIngredient
from apps.pairings.serializers import PairingSerializer
from apps.pairings.services import get_pairings_for_dish
from apps.substitutions.serializers import SubstitutionSerializer
from apps.substitutions.services import get_substitutions_for_dish

logger = logging.getLogger(__name__)


# ── E29: Pairings ─────────────────────────────────────────────────────────────


@extend_schema(
    summary="Dish pairings",
    description=(
        "Returns a list of dishes that pair well with the given dish. "
        "Pairings include sides, drinks, starters and desserts, ordered by strength."
    ),
    parameters=[
        OpenApiParameter(
            name="dish_id",
            description="UUID of the dish.",
            required=True,
            type=str,
            location=OpenApiParameter.PATH,
        ),
        OpenApiParameter(
            name="type",
            description="Filter pairing type: side | drink | dessert | starter",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="min_strength",
            description="Minimum pairing strength (1–5, default 1).",
            required=False,
            type=int,
        ),
        OpenApiParameter(
            name="lang",
            description="Language for names: en | sw (default en).",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="limit",
            description="Maximum number of results (default 20, max 50).",
            required=False,
            type=int,
        ),
    ],
    responses={
        200: OpenApiResponse(description="List of pairings for the dish"),
        404: OpenApiResponse(description="Dish not found"),
    },
    tags=["Dishes"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def dish_pairings(request: Request, dish_id: str) -> Response:
    """
    GET /v1/dishes/{dish_id}/pairings

    Returns pairings for the dish, ordered by strength.

    Query params:
      type       — filter by pairing type: side|drink|dessert|starter
      min_strength — minimum strength (1–5, default 1)
      lang       — en|sw
      limit      — max results (default 20)
    """
    dish = get_object_or_404(Dish, pk=dish_id)

    pairing_type = request.query_params.get("type")
    lang = request.query_params.get("lang", "en")
    limit = min(int(request.query_params.get("limit", 20)), 50)
    try:
        min_strength = int(request.query_params.get("min_strength", 1))
        min_strength = max(1, min(5, min_strength))
    except (ValueError, TypeError):
        min_strength = 1

    pairings = get_pairings_for_dish(
        str(dish.id),
        pairing_type=pairing_type,
        min_strength=min_strength,
        limit=limit,
    )

    serializer = PairingSerializer(pairings, many=True, context={"lang": lang})

    return Response(
        {
            "dish_id": str(dish.id),
            "dish_slug": dish.slug,
            "count": len(pairings),
            "pairings": serializer.data,
        }
    )


# ── E29: Substitutions ────────────────────────────────────────────────────────


@extend_schema(
    summary="Dish ingredient substitutions",
    description=(
        "Returns ingredient substitutions for all ingredients in the dish. "
        "Useful for adapting a recipe to available or preferred ingredients."
    ),
    parameters=[
        OpenApiParameter(
            name="dish_id",
            description="UUID of the dish.",
            required=True,
            type=str,
            location=OpenApiParameter.PATH,
        ),
        OpenApiParameter(
            name="lang",
            description="Language for names: en | sw (default en).",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="limit",
            description="Maximum number of results (default 50, max 100).",
            required=False,
            type=int,
        ),
    ],
    responses={
        200: OpenApiResponse(description="List of substitutions for dish ingredients"),
        404: OpenApiResponse(description="Dish not found"),
    },
    tags=["Dishes"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def dish_substitutions(request: Request, dish_id: str) -> Response:
    """
    GET /v1/dishes/{dish_id}/substitutions

    Returns substitutions for all ingredients in the dish.

    Query params:
      lang  — en|sw
      limit — max results (default 50)
    """
    dish = get_object_or_404(Dish, pk=dish_id)

    lang = request.query_params.get("lang", "en")
    limit = min(int(request.query_params.get("limit", 50)), 100)

    substitutions = get_substitutions_for_dish(str(dish.id), limit=limit)

    serializer = SubstitutionSerializer(substitutions, many=True, context={"lang": lang})

    return Response(
        {
            "dish_id": str(dish.id),
            "dish_slug": dish.slug,
            "count": len(substitutions),
            "substitutions": serializer.data,
        }
    )


# ── E30: Missing ingredients ──────────────────────────────────────────────────


@extend_schema(
    summary="Missing ingredients for a dish",
    description=(
        "Given a list of ingredients the user has, returns the non-staple "
        "required ingredients that are still missing for this dish. "
        "Also returns possible substitutes for each missing ingredient."
    ),
    parameters=[
        OpenApiParameter(
            name="dish_id",
            description="UUID of the dish.",
            required=True,
            type=str,
            location=OpenApiParameter.PATH,
        ),
    ],
    responses={
        200: OpenApiResponse(description="Missing ingredients with substitute suggestions"),
        400: OpenApiResponse(description="Invalid request body"),
        404: OpenApiResponse(description="Dish not found"),
    },
    tags=["Dishes"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def dish_missing(request: Request, dish_id: str) -> Response:
    """
    POST /v1/dishes/{dish_id}/missing

    Given what the user has, what non-staple required ingredients are missing?

    Request body:
      {
        "ingredients": ["tomato", "onion"],  // what the user has (raw text)
        "exclude": []                         // optional exclusions
      }

    Response:
      {
        "dish_id": "...",
        "dish_slug": "githeri",
        "missing": [
          {
            "ingredient_id": "...",
            "ingredient_slug": "dried-maize",
            "ingredient_name": "Dried maize",
            "role": "primary",
            "substitutes": [...]
          }
        ],
        "has_missing": true,
        "can_make": false
      }
    """
    dish = get_object_or_404(Dish, pk=dish_id)

    raw_ingredients = request.data.get("ingredients", [])
    exclude = request.data.get("exclude", [])
    lang = request.data.get("lang", "en")

    if not isinstance(raw_ingredients, list):
        return Response(
            {"error": "'ingredients' must be a list"},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    # Resolve the user's ingredients to IDs
    from apps.search.pipeline import resolve_ingredients
    from apps.search.staples import get_staple_ids
    from apps.substitutions.services import get_substitutions_for_ingredient

    excluded_ids = _slugs_to_ids(exclude) if exclude else None
    query = resolve_ingredients(raw_ingredients, excluded_ids=excluded_ids)

    pool_set = set(query.pool)
    staple_ids = get_staple_ids()

    # Find non-staple required ingredients the user does NOT have
    required_links = DishIngredient.objects.filter(
        dish=dish,
        role__in=[DishIngredient.Role.PRIMARY, DishIngredient.Role.REQUIRED],
    ).select_related("ingredient")

    missing = []
    for link in required_links:
        iid = str(link.ingredient.id)
        if iid in staple_ids:
            continue  # staples assumed present
        if iid in pool_set:
            continue  # user has it

        # Get substitutes for this ingredient in this dish context
        subs = get_substitutions_for_ingredient(
            iid,
            context_dish_id=str(dish.id),
            limit=3,
        )
        sub_data = SubstitutionSerializer(subs, many=True, context={"lang": lang}).data

        if lang == "sw" and link.ingredient.name_sw:
            ing_name = link.ingredient.name_sw
        else:
            ing_name = link.ingredient.name_en

        missing.append(
            {
                "ingredient_id": iid,
                "ingredient_slug": link.ingredient.slug,
                "ingredient_name": ing_name,
                "role": link.role,
                "substitutes": sub_data,
            }
        )

    return Response(
        {
            "dish_id": str(dish.id),
            "dish_slug": dish.slug,
            "missing": missing,
            "has_missing": len(missing) > 0,
            "can_make": len(missing) == 0,
            "resolved_inputs": [r.raw for r in query.results],
            "unmatched_inputs": list(query.unmatched),
        }
    )


# ── helpers ───────────────────────────────────────────────────────────────────


def _slugs_to_ids(slugs: list[str]) -> list[str]:
    from apps.ingredients.models import Ingredient

    ids: list[str] = []
    for slug in slugs:
        for pk in Ingredient.objects.filter(slug=slug).values_list("id", flat=True):
            ids.append(str(pk))
    return ids
