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
from rest_framework.request import Request
from rest_framework.response import Response

from apps.clients.models import ApiKey
from apps.clients.permissions import HasScope
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
@permission_classes([HasScope(ApiKey.SCOPE_READ_CATALOG)])
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
        # Support both offset= (direct) and cursor= (opaque token that encodes the offset)
        cursor_raw = request.query_params.get("cursor", "")
        if cursor_raw:
            offset = max(int(cursor_raw), 0)
        else:
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

    next_offset = offset + limit
    next_cursor = str(next_offset) if next_offset < total else None

    return Response(
        {
            "count": total,
            "limit": limit,
            "offset": offset,
            "next_cursor": next_cursor,
            "results": results,
        }
    )


@extend_schema(
    summary="Dish detail",
    description=(
        "Full detail for a single dish by slug. "
        "Returns ingredients with roles and quantities, cooking steps, "
        "region links, and derived dietary tags."
    ),
    responses={
        200: OpenApiResponse(description="Dish detail"),
        404: OpenApiResponse(description="Dish not found"),
    },
)
@api_view(["GET"])
@permission_classes([HasScope(ApiKey.SCOPE_READ_CATALOG)])
def dish_detail(request: Request, slug: str) -> Response:
    """
    GET /v1/dishes/{slug}/

    Returns full detail for a single dish.
    Only reviewed and verified dishes are accessible.
    """
    try:
        dish = (
            Dish.objects.filter(status__in=[StatusChoices.REVIEWED, StatusChoices.VERIFIED])
            .prefetch_related(
                "dish_ingredients__ingredient",
                "dish_ingredients__unit",
                "steps",
                "dish_regions__region",
                "dietary_tags__tag",
            )
            .get(slug=slug)
        )
    except Dish.DoesNotExist:
        from rest_framework.exceptions import NotFound

        raise NotFound("Dish not found.") from None

    ingredients = [
        {
            "slug": di.ingredient.slug,
            "name_en": di.ingredient.name_en,
            "name_sw": di.ingredient.name_sw,
            "role": di.role,
            "quantity": str(di.quantity) if di.quantity is not None else None,
            "unit": di.unit.code if di.unit else None,
            "preparation_note": di.preparation_note,
        }
        for di in dish.dish_ingredients.all()
    ]
    steps = [
        {"position": s.position, "text_en": s.text_en, "text_sw": s.text_sw}
        for s in dish.steps.order_by("position")
    ]
    regions = [dr.region.slug for dr in dish.dish_regions.all()]
    dietary_tags = [
        {"slug": dt.tag.slug, "name": dt.tag.name, "source": dt.source}
        for dt in dish.dietary_tags.all()
    ]

    return Response(
        {
            "slug": dish.slug,
            "name_en": dish.name_en,
            "name_sw": dish.name_sw,
            "description": dish.description,
            "meal_type": dish.meal_type,
            "course": dish.course,
            "spice_level": dish.spice_level,
            "difficulty": dish.difficulty,
            "prep_min": dish.prep_min,
            "cook_min": dish.cook_min,
            "servings": dish.servings,
            "popularity": dish.popularity,
            "quality_level": dish.quality_level,
            "status": dish.status,
            "ingredients": ingredients,
            "steps": steps,
            "regions": regions,
            "dietary_tags": dietary_tags,
        }
    )
