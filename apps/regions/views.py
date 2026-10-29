"""
E35 — Regions API views.

GET /v1/regions/
  Returns all regions, optionally filtered by type.
  Used by clients to populate region filter dropdowns.
"""

from __future__ import annotations

import hashlib
import json

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from apps.clients.models import ApiKey
from apps.clients.permissions import HasScope
from apps.regions.models import Region


@extend_schema(
    summary="List regions",
    description=(
        "Returns all geographic regions and cuisine areas. "
        "Optionally filter by type (county, coast, or cuisine)."
    ),
    parameters=[
        OpenApiParameter(
            name="type",
            description="Filter by region type: county | coast | cuisine",
            required=False,
            type=str,
        ),
    ],
    responses={
        200: OpenApiResponse(description="List of regions"),
        304: OpenApiResponse(description="Not modified"),
        400: OpenApiResponse(description="Invalid query parameter"),
    },
    tags=["Regions"],
)
@api_view(["GET"])
@permission_classes([HasScope(ApiKey.SCOPE_READ_CATALOG)])
def region_list(request: Request) -> Response:
    """
    GET /v1/regions/

    Query params:
      type  — filter by region type: county | coast | cuisine
    """
    qs = Region.objects.select_related("parent").order_by("type", "name")

    region_type = request.query_params.get("type", "").strip()
    if region_type:
        qs = qs.filter(type=region_type)

    data = [
        {
            "id": str(r.id),
            "slug": r.slug,
            "name": r.name,
            "type": r.type,
            "parent_slug": r.parent.slug if r.parent else None,
            "description": r.description,
        }
        for r in qs
    ]

    payload = {"count": len(data), "results": data}

    # Compute ETag from the response body so clients can use If-None-Match / 304.
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    etag = hashlib.sha256(body.encode()).hexdigest()[:32]

    if_none_match = request.META.get("HTTP_IF_NONE_MATCH", "")
    if if_none_match and if_none_match == etag:
        resp = Response(status=304)
        resp["ETag"] = etag
        resp["Cache-Control"] = "public, max-age=300"
        return resp

    resp = Response(payload)
    resp["ETag"] = etag
    resp["Cache-Control"] = "public, max-age=300"
    return resp
