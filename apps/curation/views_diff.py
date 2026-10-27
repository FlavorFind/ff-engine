"""
E54 — Dataset diff endpoint.

GET /v1/internal/diff?since=VERSION
GET /v1/datasets/diff?since=VERSION

Returns a summary of what changed between VERSION and the current dataset.
Consumer apps and hotel platforms use this to sync after a dataset release.

Response shape:
    {
      "since_version":   "2026.10.0",
      "current_version": "2026.11.0",
      "generated_at":    "2026-11-01T12:00:00Z",
      "dishes": {
        "added":   [{"slug": "...", "name_en": "...", "changed_at": "..."}],
        "changed": [...],
        "removed": []   // soft deletes not yet implemented
      },
      "ingredients": {
        "added":   [...],
        "removed": []
      }
    }

Architecture reference: Architecture doc section 7 — clients can pin to a
dataset version while they test a new one, and need to know what changed.
"""

from __future__ import annotations

import logging
from datetime import datetime

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from apps.clients.models import ApiKey
from apps.clients.permissions import HasScope
from apps.core.models import StatusChoices
from apps.curation.models import DatasetRelease

logger = logging.getLogger(__name__)

_LIVE_STATUSES = [StatusChoices.REVIEWED, StatusChoices.VERIFIED]


@extend_schema(
    summary="What changed since dataset version X",
    description=(
        "Returns dishes and ingredients added, changed or removed between "
        "the given dataset version and the current one. "
        "Use this to sync consumer apps or hotel platforms after a release."
    ),
    parameters=[
        OpenApiParameter(
            name="since",
            description="Dataset version to compare from, e.g. 2026.10.0",
            required=True,
            type=str,
        )
    ],
    responses={
        200: OpenApiResponse(description="Diff summary"),
        400: OpenApiResponse(description="Missing 'since' parameter"),
        404: OpenApiResponse(description="Unknown dataset version"),
    },
    tags=["Datasets"],
)
@api_view(["GET"])
@permission_classes([HasScope(ApiKey.SCOPE_READ_CATALOG)])
def dataset_diff(request: Request) -> Response:
    """
    GET /v1/datasets/diff?since=VERSION

    Returns what changed in the dataset since the given version.
    """
    since_version = request.query_params.get("since", "").strip()
    if not since_version:
        return Response(
            {"error": "Query parameter 'since' is required.", "code": "missing_parameter"},
            status=http_status.HTTP_400_BAD_REQUEST,
        )

    # Resolve the requested version to a timestamp
    try:
        since_release = DatasetRelease.objects.get(version=since_version)
    except DatasetRelease.DoesNotExist:
        return Response(
            {
                "error": f"Dataset version {since_version!r} not found.",
                "code": "version_not_found",
            },
            status=http_status.HTTP_404_NOT_FOUND,
        )

    since_dt = since_release.created_at

    # Current version
    current_release = DatasetRelease.objects.order_by("-created_at").first()
    current_version = current_release.version if current_release else "0.0.0"

    # ── Dishes ──────────────────────────────────────────────────────────────
    from apps.dishes.models import Dish

    dishes_added = list(
        Dish.objects.filter(
            created_at__gt=since_dt,
            status__in=_LIVE_STATUSES,
        ).values("slug", "name_en", "updated_at")
    )

    dishes_changed = list(
        Dish.objects.filter(
            updated_at__gt=since_dt,
            created_at__lte=since_dt,
            status__in=_LIVE_STATUSES,
        ).values("slug", "name_en", "updated_at")
    )

    # Soft deletes are not yet implemented — always empty
    dishes_removed: list = []

    # ── Ingredients ──────────────────────────────────────────────────────────
    from apps.ingredients.models import Ingredient

    ingredients_added = list(
        Ingredient.objects.filter(
            created_at__gt=since_dt,
            status__in=_LIVE_STATUSES,
        ).values("slug", "name_en", "updated_at")
    )

    ingredients_removed: list = []

    def _fmt(items: list[dict]) -> list[dict]:
        """Rename updated_at → changed_at for the response."""
        return [
            {"slug": r["slug"], "name_en": r["name_en"], "changed_at": r["updated_at"]}
            for r in items
        ]

    payload = {
        "since_version": since_version,
        "current_version": current_version,
        "generated_at": datetime.now(tz=datetime.UTC),
        "dishes": {
            "added": _fmt(dishes_added),
            "changed": _fmt(dishes_changed),
            "removed": dishes_removed,
        },
        "ingredients": {
            "added": _fmt(ingredients_added),
            "removed": ingredients_removed,
        },
    }

    logger.info(
        "dataset_diff: since=%s → dishes +%d ~%d, ingredients +%d",
        since_version,
        len(dishes_added),
        len(dishes_changed),
        len(ingredients_added),
    )

    return Response(payload, status=http_status.HTTP_200_OK)
