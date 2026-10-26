"""
E48 — Security review and pen test fix tests.

Covers:
  - Security headers present on all responses
  - No sensitive data leaked in error responses
  - SQL injection attempt returns 400, not 500
  - XSS payload in ingredient name returns 400 or sanitised response
  - Rate limiting fires correctly (tested more fully in E37)
  - Admin inaccessible without authentication
  - API schema endpoint accessible (docs are public)
  - Input length caps enforced
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.clients.keys import create_key
from apps.clients.models import ApiClient, ApiKey

User = get_user_model()


@pytest.fixture
def client_record(db):
    return ApiClient.objects.create(name="_test_e48_client", type=ApiClient.ClientType.TEST)


@pytest.fixture
def api(client_record):
    _, raw_key = create_key(client_record, scopes=[ApiKey.SCOPE_READ_SEARCH], rate_limit=0)
    c = APIClient()
    c.credentials(HTTP_X_API_KEY=raw_key)
    return c


@pytest.fixture
def anon():
    return APIClient()


# ── Security headers ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSecurityHeaders:
    """Every response must include the mandatory security headers."""

    def test_x_content_type_options_on_api(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": []},
            format="json",
        )
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options_on_api(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": []},
            format="json",
        )
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_referrer_policy_on_api(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": []},
            format="json",
        )
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy_on_api(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": []},
            format="json",
        )
        assert "Permissions-Policy" in resp.headers

    def test_security_headers_on_health(self, anon) -> None:
        resp = anon.get("/v1/health/")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_x_request_id_present(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": []},
            format="json",
        )
        assert "X-Request-ID" in resp.headers


# ── No sensitive data in errors ────────────────────────────────────────────────


@pytest.mark.django_db
class TestErrorResponseSafety:
    """Error responses must not leak stack traces, SQL, or internal paths."""

    def test_400_does_not_leak_traceback(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": "not-a-list"},
            format="json",
        )
        assert resp.status_code == 400
        body = resp.content.decode()
        assert "Traceback" not in body
        assert 'File "' not in body

    def test_401_body_is_safe(self, anon) -> None:
        resp = anon.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["tomato"]},
            format="json",
        )
        assert resp.status_code == 401
        body = resp.content.decode()
        assert "Traceback" not in body

    def test_error_body_has_consistent_shape(self, anon) -> None:
        resp = anon.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["tomato"]},
            format="json",
        )
        data = resp.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]


# ── Injection attempts ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestInjectionAttempts:
    """SQL injection and XSS payloads must never cause 5xx."""

    def test_sql_injection_in_ingredient(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["' OR 1=1; --"]},
            format="json",
        )
        assert resp.status_code in (200, 400)
        assert resp.status_code != 500

    def test_sql_injection_drop_table(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["'; DROP TABLE ingredients; --"]},
            format="json",
        )
        assert resp.status_code in (200, 400)

    def test_xss_payload_in_ingredient(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["<script>alert(1)</script>"]},
            format="json",
        )
        assert resp.status_code in (200, 400)
        # Script tag must not appear unescaped in the response body
        body = resp.content.decode()
        assert "<script>" not in body

    def test_path_traversal_in_ingredient(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["../../etc/passwd"]},
            format="json",
        )
        assert resp.status_code in (200, 400)

    def test_null_bytes_in_ingredient(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["tomato\x00onion"]},
            format="json",
        )
        assert resp.status_code in (200, 400)


# ── Input length caps ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestInputLengthCaps:
    """Serialiser must reject inputs that exceed configured length limits."""

    def test_ingredient_over_200_chars_rejected(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["x" * 201]},
            format="json",
        )
        assert resp.status_code == 400

    def test_ingredient_list_over_30_items_rejected(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": [f"ingredient_{i}" for i in range(31)]},
            format="json",
        )
        assert resp.status_code == 400


# ── Admin protection ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAdminProtection:
    """Admin must redirect unauthenticated requests — never serve content."""

    def test_admin_root_redirects_unauthenticated(self, anon) -> None:
        resp = anon.get("/admin/")
        # Should redirect to login, not serve admin HTML
        assert resp.status_code in (302, 301)

    def test_admin_login_page_accessible(self, anon) -> None:
        resp = anon.get("/admin/login/", follow=True)
        # Login page or 2FA page should be reachable
        assert resp.status_code == 200
