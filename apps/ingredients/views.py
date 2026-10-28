"""
Ingredients views.

POST /v1/ingredients/resolve
  Turn free text into ingredient IDs with confidence and ambiguity info.
  Architecture section 7: "Turn free text into ingredient IDs with
  confidence and ambiguity."
"""

from __future__ import annotations

import logging

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.search.resolver import STATUS_AMBIGUOUS, STATUS_MATCHED, STATUS_UNMATCHED, resolve_many

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Request / Response serializers
# ──────────────────────────────────────────────────────────────────────────────


class ResolveRequestSerializer(serializers.Serializer):
    ingredients = serializers.ListField(
        child=serializers.CharField(max_length=200, allow_blank=False),
        min_length=1,
        max_length=30,
        help_text="List of raw ingredient strings to resolve.",
    )


class ResolveOptionSerializer(serializers.Serializer):
    ingredient_id = serializers.CharField()
    name = serializers.CharField()
    confidence = serializers.FloatField()


class ResolveResultSerializer(serializers.Serializer):
    token = serializers.CharField()
    normalised = serializers.CharField()
    status = serializers.CharField()  # matched | ambiguous | unmatched
    ingredient_id = serializers.CharField(allow_null=True, default=None)
    method = serializers.CharField(allow_blank=True, default="")
    confidence = serializers.FloatField(default=0.0)
    options = ResolveOptionSerializer(many=True, default=list)


# ──────────────────────────────────────────────────────────────────────────────
# View
# ──────────────────────────────────────────────────────────────────────────────


@extend_schema(
    summary="Resolve ingredient strings",
    description=(
        "Turn free-text ingredient strings into canonical ingredient IDs. "
        "Handles misspellings, Swahili names, Sheng, and partial matches. "
        "Returns matched, ambiguous, and unmatched results."
    ),
    request=ResolveRequestSerializer,
    responses={
        200: OpenApiResponse(
            description="Resolution results with matched/ambiguous/unmatched counts"
        ),
        400: OpenApiResponse(description="Invalid request body"),
    },
    tags=["Ingredients"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
def resolve(request: Request) -> Response:
    """
    POST /v1/ingredients/resolve

    Turn free text into ingredient IDs with confidence and ambiguity info.

    Request body (JSON):
        {
          "ingredients": ["nyanya", "2 tomatoes", "unga wa mahindi"]
        }

    Response (200):
        {
          "results": [
            {
              "token": "nyanya",
              "normalised": "nyanya",
              "status": "matched",
              "ingredient_id": "<uuid>",
              "method": "exact_alias",
              "confidence": 1.0,
              "options": []
            },
            ...
          ],
          "matched_count": 2,
          "ambiguous_count": 0,
          "unmatched_count": 1
        }
    """
    req_ser = ResolveRequestSerializer(data=request.data)
    if not req_ser.is_valid():
        return Response(
            {"errors": req_ser.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    raw_tokens: list[str] = req_ser.validated_data["ingredients"]

    results = resolve_many(raw_tokens)

    serialised = []
    for r in results:
        serialised.append(
            {
                "token": r.raw,
                "normalised": r.normalised,
                "status": r.status,
                "ingredient_id": r.ingredient_id,
                "method": r.method,
                "confidence": r.confidence,
                "options": [
                    {
                        "ingredient_id": opt.ingredient_id,
                        "name": opt.name,
                        "confidence": opt.confidence,
                    }
                    for opt in r.options
                ],
            }
        )

    return Response(
        {
            "results": serialised,
            "matched_count": sum(1 for r in results if r.status == STATUS_MATCHED),
            "ambiguous_count": sum(1 for r in results if r.status == STATUS_AMBIGUOUS),
            "unmatched_count": sum(1 for r in results if r.status == STATUS_UNMATCHED),
        },
        status=status.HTTP_200_OK,
    )


# ──────────────────────────────────────────────────────────────────────────────
# P1-2 / P1-3 — Ingredient list and detail endpoints
# ──────────────────────────────────────────────────────────────────────────────


@extend_schema(
    summary="List ingredients",
    description=(
        "Returns a paginated list of ingredients. "
        "Use ?q= for autocomplete (searches name_en, name_sw, and aliases). "
        "Use ?category= to filter by category slug."
    ),
    parameters=[
        OpenApiParameter(
            name="q",
            description="Autocomplete search on name_en, name_sw, and alias text.",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="category",
            description="Filter by ingredient category slug.",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="limit",
            description="Page size (default 50, max 200).",
            required=False,
            type=int,
        ),
        OpenApiParameter(
            name="offset",
            description="Pagination offset (default 0).",
            required=False,
            type=int,
        ),
    ],
    responses={200: OpenApiResponse(description="Paginated ingredient list")},
    tags=["Ingredients"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def ingredient_list(request: Request) -> Response:
    """
    GET /v1/ingredients/

    Paginated list of ingredients with optional autocomplete and category filter.
    """
    from django.db.models import Q

    from apps.core.models import StatusChoices
    from apps.ingredients.models import Ingredient

    qs = Ingredient.objects.filter(
        status__in=[StatusChoices.REVIEWED, StatusChoices.VERIFIED]
    ).select_related("category")

    q = request.query_params.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name_en__icontains=q) | Q(name_sw__icontains=q) | Q(aliases__alias__icontains=q)
        ).distinct()

    category = request.query_params.get("category", "").strip()
    if category:
        qs = qs.filter(category__slug=category)

    try:
        limit = min(int(request.query_params.get("limit", 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = max(int(request.query_params.get("offset", 0)), 0)
    except (ValueError, TypeError):
        offset = 0

    total = qs.count()
    ingredients = qs[offset : offset + limit]

    results = [
        {
            "slug": ing.slug,
            "name_en": ing.name_en,
            "name_sw": ing.name_sw,
            "kind": ing.kind,
            "is_staple": ing.is_staple,
            "category": ing.category.slug if ing.category else None,
            "status": ing.status,
        }
        for ing in ingredients
    ]

    return Response({"count": total, "limit": limit, "offset": offset, "results": results})


@extend_schema(
    summary="Ingredient detail",
    description=(
        "Full detail for a single ingredient by slug. "
        "Includes all aliases (with language and misspelling flag) and linked allergens."
    ),
    responses={
        200: OpenApiResponse(description="Ingredient detail"),
        404: OpenApiResponse(description="Ingredient not found"),
    },
    tags=["Ingredients"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def ingredient_detail(request: Request, slug: str) -> Response:
    """
    GET /v1/ingredients/{slug}/

    Full detail for a single ingredient including aliases and allergens.
    Only reviewed and verified ingredients are accessible.
    """
    from apps.core.models import StatusChoices
    from apps.ingredients.models import Ingredient

    try:
        ing = (
            Ingredient.objects.filter(status__in=[StatusChoices.REVIEWED, StatusChoices.VERIFIED])
            .select_related("category", "typical_unit")
            .prefetch_related("aliases", "allergens")
            .get(slug=slug)
        )
    except Ingredient.DoesNotExist:
        return Response(
            {"error": "Ingredient not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    aliases = [
        {
            "alias": a.alias,
            "language": a.language,
            "is_misspelling": a.is_misspelling,
        }
        for a in ing.aliases.all()
    ]
    allergens = [{"slug": a.slug, "name": a.name} for a in ing.allergens.all()]

    return Response(
        {
            "slug": ing.slug,
            "name_en": ing.name_en,
            "name_sw": ing.name_sw,
            "kind": ing.kind,
            "is_staple": ing.is_staple,
            "category": ing.category.slug if ing.category else None,
            "typical_unit": ing.typical_unit.code if ing.typical_unit else None,
            "status": ing.status,
            "notes": ing.notes,
            "aliases": aliases,
            "allergens": allergens,
        }
    )
