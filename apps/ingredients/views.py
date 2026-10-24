"""
Ingredients views.

POST /v1/ingredients/resolve
  Turn free text into ingredient IDs with confidence and ambiguity info.
  Architecture section 7: "Turn free text into ingredient IDs with
  confidence and ambiguity."
"""

from __future__ import annotations

import logging

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
