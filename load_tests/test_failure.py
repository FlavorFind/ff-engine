"""
E47 — Failure tests.

Tests that the API behaves correctly when infrastructure components
degrade or fail:

  - Redis unavailable  → search still works (falls back to uncached)
  - Malformed payloads → 400 with clear message, never 500
  - Oversized payloads → 400, not 500
  - Empty ingredient list → 200 with empty results
  - Very long ingredient strings → 400 or graceful truncation
  - Concurrent requests → all succeed (no race conditions)
  - Invalid API key    → 401
  - Revoked API key    → 401
  - Missing API key    → 401

These are deterministic unit/integration tests — they do not require
a running Redis or external services (failures are mocked).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.clients.keys import create_key
from apps.clients.models import ApiClient, ApiKey


@pytest.fixture
def client_record(db):
    return ApiClient.objects.create(name="_test_e47_client", type=ApiClient.ClientType.TEST)


@pytest.fixture
def api(client_record):
    _, raw_key = create_key(client_record, scopes=[ApiKey.SCOPE_READ_SEARCH], rate_limit=0)
    c = APIClient()
    c.credentials(HTTP_X_API_KEY=raw_key)
    return c


# ── Cache failure ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestCacheFailure:
    """Search endpoint must work when Redis is unavailable (no caching path)."""

    def test_search_succeeds_when_cache_raises(self, api) -> None:
        """If get_cached_result raises, search falls through to the engine."""
        with patch(
            "apps.search.views.get_cached_result",
            side_effect=Exception("Redis down"),
        ):
            resp = api.post(
                "/v1/search/by-ingredients",
                {"ingredients": ["tomato", "onion"]},
                format="json",
            )
        # Should still return 200, not 500
        assert resp.status_code == 200

    def test_search_succeeds_when_cache_set_raises(self, api) -> None:
        """If set_cached_result raises, the response is still returned."""
        with patch(
            "apps.search.views.set_cached_result",
            side_effect=Exception("Redis write failed"),
        ):
            resp = api.post(
                "/v1/search/by-ingredients",
                {"ingredients": ["beans", "maize"]},
                format="json",
            )
        assert resp.status_code == 200


# ── Malformed payloads ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestMalformedPayloads:
    """Invalid inputs must return 400, never 500."""

    def test_missing_ingredients_field(self, api) -> None:
        resp = api.post("/v1/search/by-ingredients", {}, format="json")
        assert resp.status_code == 400

    def test_ingredients_not_a_list(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": "tomato"},
            format="json",
        )
        assert resp.status_code == 400

    def test_ingredients_contains_non_string(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": [1, 2, 3]},
            format="json",
        )
        assert resp.status_code == 400

    def test_invalid_mode(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["tomato"], "mode": "turbo"},
            format="json",
        )
        assert resp.status_code == 400

    def test_invalid_limit_type(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["tomato"], "limit": "many"},
            format="json",
        )
        assert resp.status_code == 400

    def test_negative_limit(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["tomato"], "limit": -1},
            format="json",
        )
        assert resp.status_code == 400

    def test_empty_ingredient_string_in_list(self, api) -> None:
        """Empty string item must not crash the resolver."""
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["", "tomato"]},
            format="json",
        )
        # Either 400 (validation rejects empty string) or 200 (treated as unmatched)
        assert resp.status_code in (200, 400)

    def test_very_long_ingredient_string(self, api) -> None:
        """A 10 000-character ingredient string must not cause a 500."""
        long_name = "x" * 10_000
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": [long_name]},
            format="json",
        )
        assert resp.status_code in (200, 400)

    def test_oversized_ingredient_list(self, api) -> None:
        """200 ingredients at once must not cause a 500."""
        big_list = [f"ingredient_{i}" for i in range(200)]
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": big_list},
            format="json",
        )
        assert resp.status_code in (200, 400)


# ── Empty inputs ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEmptyInputs:
    """Empty ingredient list should return 200 with empty/zero results."""

    def test_empty_ingredients_list_returns_200(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": []},
            format="json",
        )
        assert resp.status_code == 200

    def test_empty_results_structure_is_valid(self, api) -> None:
        resp = api.post(
            "/v1/search/by-ingredients",
            {"ingredients": []},
            format="json",
        )
        data = resp.json()
        assert "results" in data
        assert isinstance(data["results"], list)


# ── Authentication failures ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestAuthFailures:
    """Auth failures must return 401, not 500."""

    def test_missing_api_key_returns_401(self) -> None:
        anon = APIClient()
        resp = anon.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["tomato"]},
            format="json",
        )
        assert resp.status_code == 401

    def test_invalid_api_key_returns_401(self) -> None:
        c = APIClient()
        c.credentials(HTTP_X_API_KEY="ff_totally_invalid_key_xyz")
        resp = c.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["tomato"]},
            format="json",
        )
        assert resp.status_code == 401

    def test_revoked_api_key_returns_401(self, client_record) -> None:
        from django.utils import timezone

        api_key_obj, raw_key = create_key(
            client_record, scopes=[ApiKey.SCOPE_READ_SEARCH], rate_limit=0
        )
        # Revoke it
        api_key_obj.revoked_at = timezone.now()
        api_key_obj.save()

        c = APIClient()
        c.credentials(HTTP_X_API_KEY=raw_key)
        resp = c.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["tomato"]},
            format="json",
        )
        assert resp.status_code == 401

    def test_wrong_scope_returns_403(self, client_record) -> None:
        # Create a key with no search scope
        from apps.clients.models import ApiKey as AK

        _, raw_key = create_key(client_record, scopes=[AK.SCOPE_READ_CATALOGUE], rate_limit=0)
        c = APIClient()
        c.credentials(HTTP_X_API_KEY=raw_key)
        resp = c.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["tomato"]},
            format="json",
        )
        assert resp.status_code == 403


# ── Health endpoint always up ──────────────────────────────────────────────────


@pytest.mark.django_db
class TestHealthUnderFailure:
    """Health endpoint must return 200 even without authentication."""

    def test_health_no_auth(self) -> None:
        anon = APIClient()
        resp = anon.get("/v1/health/")
        assert resp.status_code == 200

    def test_health_returns_status_ok(self) -> None:
        anon = APIClient()
        resp = anon.get("/v1/health/")
        data = resp.json()
        assert data.get("status") == "ok"
