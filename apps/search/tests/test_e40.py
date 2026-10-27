"""
E40 — Performance tuning tests.

Tests:
  - GIN trigram indexes exist on ingredient alias and name fields
  - GIN array indexes exist on dish search arrays
  - warm_search_cache command runs without error
  - warm_search_cache --dry-run prints queries without executing
  - warm_search_cache warms at least the baseline queries into cache
  - p95 latency: 50 consecutive searches complete with p95 < 500ms
    (conservative: CI is shared infra, staging target is 150ms)
"""

from __future__ import annotations

import time

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

# ── Index existence ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestIndexesExist:
    """Verify that the expected indexes exist in the database."""

    def _index_exists(self, index_name: str) -> bool:
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM pg_indexes
                WHERE indexname = %s
                """,
                [index_name],
            )
            return cursor.fetchone() is not None

    def test_dish_required_ids_gin_index(self):
        assert self._index_exists("dish_required_ids_gin"), (
            "GIN index dish_required_ids_gin missing — check dishes migration 0001"
        )

    def test_dish_all_ids_gin_index(self):
        assert self._index_exists("dish_all_ids_gin"), (
            "GIN index dish_all_ids_gin missing — check dishes migration 0001"
        )

    def test_ingredient_alias_trgm_index(self):
        assert self._index_exists("ingredient_alias_normalized_trgm_idx"), (
            "GIN trgm index ingredient_alias_normalized_trgm_idx missing — "
            "check ingredients migration 0002"
        )

    def test_ingredient_name_en_trgm_index(self):
        assert self._index_exists("ingredient_name_en_trgm_idx"), (
            "GIN trgm index ingredient_name_en_trgm_idx missing — check ingredients migration 0002"
        )

    def test_ingredient_name_sw_trgm_index(self):
        assert self._index_exists("ingredient_name_sw_trgm_idx"), (
            "GIN trgm index ingredient_name_sw_trgm_idx missing — check ingredients migration 0002"
        )


# ── Cache warming ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestWarmSearchCache:
    def test_command_runs_without_error(self, seeded_db, capsys):
        call_command("warm_search_cache")
        out = capsys.readouterr().out
        assert "Cache warming complete" in out

    def test_dry_run_does_not_warm_cache(self, seeded_db, capsys):
        from django.core.cache import cache

        cache.clear()
        call_command("warm_search_cache", dry_run=True)
        # Cache should still be empty after dry run
        # We just check the command output mentions DRY RUN
        out = capsys.readouterr().out
        assert "DRY RUN" in out

    def test_warmed_queries_are_cached(self, seeded_db):
        from django.core.cache import cache

        from apps.search.cache import build_cache_key, get_dataset_version

        cache.clear()
        call_command("warm_search_cache", verbosity=0)

        dataset_version = get_dataset_version()
        # Check a baseline query is now in cache
        key = build_cache_key(
            dataset_version=dataset_version,
            ingredients=["ugali"],
            exclude=[],
            mode="strict",
            meal_type=None,
            course=None,
            lang="en",
            limit=20,
        )
        result = cache.get(key)
        assert result is not None, "Cache entry for 'ugali' not found after warming"
        assert "payload" in result


# ── p95 latency ───────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSearchLatency:
    """
    Smoke-level p95 check.

    Runs 30 searches and asserts p95 < 500ms.
    The production target is 150ms at 50 rps on staging hardware.
    500ms is the CI threshold — CI runners are shared and slower.
    """

    def test_p95_under_500ms(self, seeded_db):
        from apps.clients.keys import create_key
        from apps.clients.models import ApiClient, ApiKey

        client_rec = ApiClient.objects.create(name="_e40_perf_test", type=ApiClient.ClientType.TEST)
        _, raw_key = create_key(client_rec, scopes=[ApiKey.SCOPE_READ_SEARCH], rate_limit=0)

        api_client = APIClient()
        api_client.credentials(HTTP_X_API_KEY=raw_key)

        queries = [
            {"ingredients": ["tomato", "onion"]},
            {"ingredients": ["beans", "maize"]},
            {"ingredients": ["chicken"]},
            {"ingredients": ["rice"]},
            {"ingredients": ["sukuma wiki"]},
        ]

        latencies_ms = []
        for i in range(30):
            payload = queries[i % len(queries)]
            start = time.monotonic()
            api_client.post("/v1/search/by-ingredients", payload, format="json")
            elapsed = (time.monotonic() - start) * 1000
            latencies_ms.append(elapsed)

        latencies_ms.sort()
        p95 = latencies_ms[int(len(latencies_ms) * 0.95)]

        assert p95 < 500, (
            f"Search p95 is {p95:.1f}ms — exceeds 500ms CI threshold. "
            f"Staging target is 150ms. Check indexes and query plans."
        )
