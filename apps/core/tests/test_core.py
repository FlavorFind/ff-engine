"""
Tests for core app components:
  - SecurityHeadersMiddleware  (apps.core.security)
  - RequestIDMiddleware        (apps.core.middleware)
  - custom_exception_handler   (apps.core.exceptions)
  - TimeStampedModel           (apps.core.models)
"""

from __future__ import annotations

import uuid

import pytest
from django.test import RequestFactory
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory

from apps.core.exceptions import custom_exception_handler
from apps.core.middleware import RequestIDMiddleware
from apps.core.security import SecurityHeadersMiddleware

# ── helpers ───────────────────────────────────────────────────────────────────


def _simple_response(status_code: int = 200, body: bytes = b"ok") -> Response:
    """Build a minimal HttpResponse-like object for middleware tests."""
    from django.http import HttpResponse

    return HttpResponse(body, status=status_code)


def _make_get_response(status_code: int = 200):
    """Return a callable that always returns a fixed HttpResponse."""

    def get_response(request):
        return _simple_response(status_code)

    return get_response


# ── SecurityHeadersMiddleware ─────────────────────────────────────────────────


class TestSecurityHeadersMiddleware:
    def _call(self, path: str = "/v1/health/", status_code: int = 200):
        factory = RequestFactory()
        request = factory.get(path)
        middleware = SecurityHeadersMiddleware(_make_get_response(status_code))
        return middleware(request)

    def test_sets_x_content_type_options(self):
        resp = self._call()
        assert resp["X-Content-Type-Options"] == "nosniff"

    def test_sets_x_frame_options(self):
        resp = self._call()
        assert resp["X-Frame-Options"] == "DENY"

    def test_sets_referrer_policy(self):
        resp = self._call()
        assert resp["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_sets_permissions_policy(self):
        resp = self._call()
        assert "camera=()" in resp["Permissions-Policy"]
        assert "microphone=()" in resp["Permissions-Policy"]

    def test_api_path_gets_cache_control_no_store(self):
        resp = self._call(path="/v1/dishes/")
        assert resp["Cache-Control"] == "no-store"

    def test_non_api_path_does_not_get_cache_control(self):
        resp = self._call(path="/admin/")
        assert "Cache-Control" not in resp

    def test_does_not_override_existing_cache_control(self):
        """Views that set their own Cache-Control are left alone."""

        def get_response(request):
            r = _simple_response()
            r["Cache-Control"] = "max-age=60"
            return r

        factory = RequestFactory()
        request = factory.get("/v1/search/by-ingredients")
        middleware = SecurityHeadersMiddleware(get_response)
        resp = middleware(request)
        assert resp["Cache-Control"] == "max-age=60"

    def test_headers_present_on_4xx_responses(self):
        resp = self._call(status_code=404)
        assert resp["X-Content-Type-Options"] == "nosniff"
        assert resp["X-Frame-Options"] == "DENY"


# ── RequestIDMiddleware ────────────────────────────────────────────────────────


class TestRequestIDMiddleware:
    def _call(self, path: str = "/v1/health/", incoming_id: str | None = None):
        factory = RequestFactory()
        headers = {}
        if incoming_id:
            headers["HTTP_X_REQUEST_ID"] = incoming_id
        request = factory.get(path, **headers)
        middleware = RequestIDMiddleware(_make_get_response())
        resp = middleware(request)
        return request, resp

    def test_response_has_x_request_id_header(self):
        _, resp = self._call()
        assert "X-Request-ID" in resp

    def test_generated_request_id_is_valid_uuid(self):
        _, resp = self._call()
        # Should not raise
        uuid.UUID(resp["X-Request-ID"])

    def test_passes_through_client_supplied_request_id(self):
        client_id = str(uuid.uuid4())
        _, resp = self._call(incoming_id=client_id)
        assert resp["X-Request-ID"] == client_id

    def test_attaches_request_id_to_request_object(self):
        request, _ = self._call()
        assert hasattr(request, "request_id")
        uuid.UUID(request.request_id)

    def test_different_requests_get_different_ids(self):
        _, r1 = self._call()
        _, r2 = self._call()
        assert r1["X-Request-ID"] != r2["X-Request-ID"]


# ── custom_exception_handler ──────────────────────────────────────────────────


class TestCustomExceptionHandler:
    def _context(self, request=None):
        if request is None:
            factory = APIRequestFactory()
            request = factory.get("/v1/test/")
            # Simulate RequestIDMiddleware attachment
            request.request_id = "test-req-id-123"
        return {"request": request, "view": None}

    def test_validation_error_returns_400_with_envelope(self):
        exc = ValidationError({"name": ["This field is required."]})
        context = self._context()
        response = custom_exception_handler(exc, context)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.data
        assert response.data["error"]["code"] == "bad_request"

    def test_not_found_returns_404_with_envelope(self):
        exc = NotFound("Dish not found.")
        context = self._context()
        response = custom_exception_handler(exc, context)
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["error"]["code"] == "not_found"

    def test_error_envelope_has_message_and_request_id(self):
        exc = ValidationError("bad input")
        context = self._context()
        response = custom_exception_handler(exc, context)
        error = response.data["error"]
        assert "message" in error
        assert error["message"]
        assert error["request_id"] == "test-req-id-123"

    def test_unhandled_exception_returns_500(self):
        """Exceptions not handled by DRF get a 500 with internal_error code."""
        exc = RuntimeError("something exploded")
        context = self._context()
        response = custom_exception_handler(exc, context)
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.data["error"]["code"] == "internal_error"

    def test_error_code_mapping(self):
        from rest_framework.exceptions import (
            AuthenticationFailed,
            MethodNotAllowed,
            PermissionDenied,
            Throttled,
        )

        cases = [
            (AuthenticationFailed(), 401, "unauthorized"),
            (PermissionDenied(), 403, "forbidden"),
            (NotFound(), 404, "not_found"),
            (MethodNotAllowed("DELETE"), 405, "method_not_allowed"),
            (Throttled(), 429, "rate_limit_exceeded"),
        ]
        for exc, expected_status, expected_code in cases:
            resp = custom_exception_handler(exc, self._context())
            assert resp.status_code == expected_status, f"{exc}: expected {expected_status}"
            assert resp.data["error"]["code"] == expected_code, f"{exc}: expected {expected_code}"


# ── TimeStampedModel ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestTimeStampedModel:
    """
    TimeStampedModel is abstract — test via a concrete model that inherits it.
    IngredientCategory is a minimal subclass (slug + name_en only).
    """

    def test_created_at_set_on_save(self):
        from apps.ingredients.models import IngredientCategory

        cat = IngredientCategory.objects.create(name_en="Test category TS1", slug="test-cat-ts1")
        assert cat.created_at is not None

    def test_updated_at_set_on_save(self):
        from apps.ingredients.models import IngredientCategory

        cat = IngredientCategory.objects.create(name_en="Test category TS2", slug="test-cat-ts2")
        assert cat.updated_at is not None

    def test_updated_at_changes_on_update(self):
        from apps.ingredients.models import IngredientCategory

        cat = IngredientCategory.objects.create(name_en="Test category TS3", slug="test-cat-ts3")
        original_updated_at = cat.updated_at
        cat.name_en = "Updated category TS3"
        cat.save()
        cat.refresh_from_db()
        assert cat.updated_at >= original_updated_at

    def test_pk_is_uuid(self):
        from apps.ingredients.models import IngredientCategory

        cat = IngredientCategory.objects.create(name_en="Test category TS4", slug="test-cat-ts4")
        assert isinstance(cat.id, uuid.UUID)

    def test_created_at_does_not_change_on_update(self):
        from apps.ingredients.models import IngredientCategory

        cat = IngredientCategory.objects.create(name_en="Test category TS5", slug="test-cat-ts5")
        original_created_at = cat.created_at
        cat.name_en = "Updated category TS5"
        cat.save()
        cat.refresh_from_db()
        assert cat.created_at == original_created_at
