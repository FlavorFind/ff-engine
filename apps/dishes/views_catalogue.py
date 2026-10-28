"""
E35 — Dishes catalogue view.

GET /v1/dishes/
  Browse all dishes with optional filters.
  Used by clients to build catalogues, menus and filter UIs.

Filters (all optional, combinable):
  region      — region slug (DishRegion link)
  meal_type   — breakfast | lunch | dinner | snack | drink | dessert
  course      — starter | main | side | dessert | drink | snack
  diet        — dietary tag slug (e.g. vegetarian, gluten-free)
  q           — text search on name_en / name_sw
  limit       — page size (default 50, max 200)
  offset      — pagination offset (default 0)
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.core.models import StatusChoices
from apps.dishes.models import Dish


@extend_schema(
    summary="List dishes",
    description=(
        "Returns a paginated list of dishes. "
        "Supports filtering by region, meal type, course, dietary tags, "
        "and free-text search."
    ),
    parameters=[
        OpenApiParameter(
            name="region",
            description="Filter by region slug.",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="meal_type",
            description="Filter by meal type: breakfast | lunch | dinner | snack | drink | dessert",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="course",
            description="Filter by course: starter | main | side | dessert | drink | snack",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="diet",
            description="Filter by dietary tag slug (e.g. vegetarian, gluten-free).",
            required=False,
            type=str,
        ),
        OpenApiParameter(
            name="q",
            description="Free-text search on dish name (English or Swahili).",
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
    responses={
        200: OpenApiResponse(description="Paginated list of dishes"),
        400: OpenApiResponse(description="Invalid query parameter"),
    },
    tags=["Dishes"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def dish_catalogue(request: Request) -> Response:
    """
    GET /v1/dishes/

    Returns a paginated list of dishes with basic metadata.
    """
    qs = Dish.objects.filter(status__in=[StatusChoices.REVIEWED, StatusChoices.VERIFIED]).order_by(
        "name_en"
    )

    # ── filters ───────────────────────────────────────────────────────────────

    region_slug = request.query_params.get("region", "").strip()
    if region_slug:
        qs = qs.filter(dish_regions__region__slug=region_slug)

    meal_type = request.query_params.get("meal_type", "").strip()
    valid_meal_types = {c[0] for c in Dish.MealType.choices}
    if meal_type:
        if meal_type not in valid_meal_types:
            return Response(
                {"error": f"Invalid meal_type. Choose from: {sorted(valid_meal_types)}"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        qs = qs.filter(meal_type=meal_type)

    course = request.query_params.get("course", "").strip()
    valid_courses = {c[0] for c in Dish.Course.choices}
    if course:
        if course not in valid_courses:
            return Response(
                {"error": f"Invalid course. Choose from: {sorted(valid_courses)}"},
                status=http_status.HTTP_400_BAD_REQUEST,
            )
        qs = qs.filter(course=course)

    diet = request.query_params.get("diet", "").strip()
    if diet:
        qs = qs.filter(dietary_tags__tag__slug=diet)

    q = request.query_params.get("q", "").strip()
    if q:
        from django.db.models import Q

        qs = qs.filter(Q(name_en__icontains=q) | Q(name_sw__icontains=q))

    # ── pagination ────────────────────────────────────────────────────────────

    try:
        limit = min(int(request.query_params.get("limit", 50)), 200)
        offset = max(int(request.query_params.get("offset", 0)), 0)
    except (ValueError, TypeError):
        return Response(
            {"error": "limit and offset must be integers"},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    total = qs.distinct().count()
    dishes = qs.distinct()[offset : offset + limit]

    results = [
        {
            "id": str(d.id),
            "slug": d.slug,
            "name_en": d.name_en,
            "name_sw": d.name_sw,
            "description": d.description,
            "meal_type": d.meal_type,
            "course": d.course,
            "spice_level": d.spice_level,
            "difficulty": d.difficulty,
            "prep_min": d.prep_min,
            "cook_min": d.cook_min,
            "servings": d.servings,
            "status": d.status,
        }
        for d in dishes
    ]

    return Response(
        {
            "count": total,
            "limit": limit,
            "offset": offset,
            "results": results,
        }
    )
