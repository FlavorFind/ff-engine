"""
E37 — Rate limits and quotas.

Tests:
  - Requests within the limit succeed (200)
  - Exceeding the per-minute limit returns 429
  - 429 response includes Retry-After header
  - A key with rate_limit=0 is never throttled
  - Throttle keys are per-key (two different keys don't share a bucket)
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.clients.keys import create_key
from apps.clients.models import ApiClient, ApiKey


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """Flush cache before and after each test to reset throttle counters."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client_record(db):
    return ApiClient.objects.create(name="_test_e37_client", type=ApiClient.ClientType.TEST)


def _make_client(client_record, rpm: int) -> tuple[APIClient, object]:
    """Create an APIClient with a key limited to *rpm* requests per minute."""
    api_key, raw_key = create_key(client_record, scopes=[ApiKey.SCOPE_READ_SEARCH], rate_limit=rpm)
    c = APIClient()
    c.credentials(HTTP_X_API_KEY=raw_key)
    return c, api_key


@pytest.mark.django_db
class TestRateLimiting:
    def test_requests_within_limit_succeed(self, client_record) -> None:
        """3 requests with a 5 rpm limit should all succeed."""
        client, _ = _make_client(client_record, rpm=5)
        for _ in range(3):
            resp = client.post(
                "/v1/search/by-ingredients",
                {"ingredients": ["tomato"]},
                format="json",
            )
            assert resp.status_code == 200

    def test_exceeding_limit_returns_429(self, client_record) -> None:
        """rpm=2 → third request should be throttled."""
        client, _ = _make_client(client_record, rpm=2)
        resp1 = client.post("/v1/search/by-ingredients", {"ingredients": ["tomato"]}, format="json")
        resp2 = client.post("/v1/search/by-ingredients", {"ingredients": ["tomato"]}, format="json")
        resp3 = client.post("/v1/search/by-ingredients", {"ingredients": ["tomato"]}, format="json")

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp3.status_code == 429

    def test_429_has_retry_after_header(self, client_record) -> None:
        """Throttled response must include Retry-After header."""
        client, _ = _make_client(client_record, rpm=1)
        client.post("/v1/search/by-ingredients", {"ingredients": ["tomato"]}, format="json")
        resp = client.post("/v1/search/by-ingredients", {"ingredients": ["tomato"]}, format="json")

        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_unlimited_key_never_throttled(self, client_record) -> None:
        """rate_limit=0 means unlimited — should never return 429."""
        client, _ = _make_client(client_record, rpm=0)
        for _ in range(10):
            resp = client.post(
                "/v1/search/by-ingredients",
                {"ingredients": ["tomato"]},
                format="json",
            )
            assert resp.status_code == 200

    def test_throttle_is_per_key(self, client_record) -> None:
        """Two different keys have independent throttle buckets."""
        client_a, _ = _make_client(client_record, rpm=1)
        client_b, _ = _make_client(client_record, rpm=1)

        # Exhaust client_a's limit
        client_a.post("/v1/search/by-ingredients", {"ingredients": ["tomato"]}, format="json")
        resp_a = client_a.post(
            "/v1/search/by-ingredients", {"ingredients": ["tomato"]}, format="json"
        )
        assert resp_a.status_code == 429

        # client_b's bucket is independent — should still be 200
        resp_b = client_b.post(
            "/v1/search/by-ingredients", {"ingredients": ["tomato"]}, format="json"
        )
        assert resp_b.status_code == 200
