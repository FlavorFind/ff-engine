"""
E52 — Community submissions intake view.

POST /v1/internal/submissions

Accepts dish, ingredient and pairing drafts from consumer apps and hotel
platforms. Submissions are stored with status=PENDING and require curator
review before any content reaches the shared library.

Access: internal:curation scope only.
Rate limit: controlled by the submitting key's rate_limit field (ApiKey).
"""

from __future__ import annotations

import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from apps.clients.models import ApiKey
from apps.clients.permissions import HasScope
from apps.curation.models import ChangeLog, CommunitySubmission
from apps.curation.serializers import SubmissionRequestSerializer, SubmissionResponseSerializer

logger = logging.getLogger(__name__)


@extend_schema(
    summary="Submit a community draft",
    description=(
        "Accept a dish, ingredient or pairing draft from a community member, "
        "hotel or partner app. Submissions are stored with status=pending and "
        "require curator review before reaching the live dataset. "
        "Requires the internal:curation API key scope."
    ),
    request=SubmissionRequestSerializer,
    responses={
        201: OpenApiResponse(description="Submission accepted with status=pending"),
        400: OpenApiResponse(description="Validation error — invalid type or empty payload"),
        403: OpenApiResponse(description="Missing or insufficient API key scope"),
    },
    tags=["Internal"],
)
@api_view(["POST"])
@permission_classes([HasScope(ApiKey.SCOPE_INTERNAL_CURATION)])
def create_submission(request: Request) -> Response:
    """
    POST /v1/internal/submissions

    Request body:
        {
          "submission_type": "dish",        // "dish" | "ingredient" | "pairing"
          "payload": { ... },               // non-empty object; schema is type-specific
          "submitter_note": "optional note" // optional
        }

    Response (201):
        {
          "id": 1,
          "submission_type": "dish",
          "status": "pending",
          "created_at": "2026-10-27T..."
        }
    """
    req_ser = SubmissionRequestSerializer(data=request.data)
    if not req_ser.is_valid():
        return Response({"errors": req_ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)

    data = req_ser.validated_data

    # Identify the API client from the authenticated request
    # request.auth is the ApiKey instance (set by APIKeyAuthentication)
    submitter_client = getattr(request.auth, "client", None)

    submission = CommunitySubmission.objects.create(
        submission_type=data["submission_type"],
        payload=data["payload"],
        submitter_note=data.get("submitter_note", ""),
        submitter_client=submitter_client,
        status=CommunitySubmission.SubmissionStatus.PENDING,
    )

    # Log to audit trail
    ChangeLog.objects.create(
        object_type="CommunitySubmission",
        object_id=str(submission.pk),
        action=ChangeLog.Action.CREATE,
        diff={
            "submission_type": submission.submission_type,
            "status": submission.status,
            "client": submitter_client.name if submitter_client else None,
        },
        actor=request.user if request.user.is_authenticated else None,
        reason="Community submission intake",
    )

    logger.info(
        "submission: %s created (type=%s, client=%s)",
        submission.pk,
        submission.submission_type,
        submitter_client.name if submitter_client else "unknown",
    )

    return Response(
        SubmissionResponseSerializer(submission).data,
        status=http_status.HTTP_201_CREATED,
    )
