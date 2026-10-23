"""Health and version endpoints."""
from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response


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


@api_view(["GET"])
@permission_classes([AllowAny])
def version(request: Request) -> Response:
    """
    Version endpoint.
    Returns the engine version and current dataset version.
    """
    return Response(
        {
            "engine_version": getattr(settings, "ENGINE_VERSION", "dev"),
            "dataset_version": getattr(settings, "DATASET_VERSION", "0.0.0"),
            "api_version": "v1",
        }
    )
