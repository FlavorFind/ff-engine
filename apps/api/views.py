"""Health and version endpoints."""

from django.conf import settings
from django.db import connection
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response


@extend_schema(
    summary="Health check",
    description=(
        "Returns 200 if the service and database are reachable. "
        "Returns 503 if the database cannot be reached."
    ),
    responses={
        200: OpenApiResponse(description="Service is healthy"),
        503: OpenApiResponse(description="Database is unreachable"),
    },
    tags=["Meta"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    """
    Health check endpoint.
    Returns 200 if the service and database are reachable.
    """
    try:
        connection.ensure_connection()
        db_status = "ok"
    except Exception:
        db_status = "error"

    status_code = 200 if db_status == "ok" else 503
    return Response(
        {
            "status": "ok" if db_status == "ok" else "degraded",
            "database": db_status,
        },
        status=status_code,
    )


@extend_schema(
    summary="Engine version",
    description="Returns the engine version, dataset version and API version string.",
    responses={
        200: OpenApiResponse(description="Version information"),
    },
    tags=["Meta"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def version(request: Request) -> Response:
    """
    Version endpoint.
    Returns the engine version and current dataset version.
    """
    from apps.search.cache import get_dataset_version

    return Response(
        {
            "engine_version": getattr(settings, "ENGINE_VERSION", "dev"),
            "dataset_version": get_dataset_version(),
            "api_version": "v1",
        }
    )
