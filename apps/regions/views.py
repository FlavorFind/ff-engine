"""
E35 — Regions API views.

GET /v1/regions/
  Returns all regions, optionally filtered by type.
  Used by clients to populate region filter dropdowns.
"""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.regions.models import Region


@api_view(["GET"])
@permission_classes([AllowAny])
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
    return Response({"count": len(data), "results": data})
