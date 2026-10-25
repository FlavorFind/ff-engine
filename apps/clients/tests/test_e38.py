"""
E38 — Usage metering and daily rollup tests.

Tests:
  - MeteringMiddleware writes a RequestLog row after each request
  - Unauthenticated requests are NOT logged
  - rollup_daily_usage aggregates RequestLog into UsageRecord correctly
  - Rollup: calls count, error count, p95_ms
  - Duplicate rollup updates existing UsageRecord (not creates new)
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.clients.keys import create_key
from apps.clients.models import ApiClient, ApiKey, RequestLog, UsageRecord


@pytest.fixture
def client_record(db):
    return ApiClient.objects.create(name="_test_e38_client", type=ApiClient.ClientType.TEST)


@pytest.fixture
def auth_client(client_record):
    _, raw_key = create_key(client_record, scopes=[ApiKey.SCOPE_READ_SEARCH], rate_limit=0)
    c = APIClient()
    c.credentials(HTTP_X_API_KEY=raw_key)
    return c


@pytest.mark.django_db
class TestMeteringMiddleware:
    def test_authenticated_request_creates_log(self, auth_client, client_record) -> None:
        auth_client.post("/v1/search/by-ingredients", {"ingredients": []}, format="json")
        assert RequestLog.objects.filter(client=client_record).count() == 1

    def test_log_records_endpoint(self, auth_client, client_record) -> None:
        auth_client.post("/v1/search/by-ingredients", {"ingredients": []}, format="json")
        log = RequestLog.objects.get(client=client_record)
        assert log.endpoint == "/v1/search/by-ingredients"

    def test_log_records_status_code(self, auth_client, client_record) -> None:
        auth_client.post("/v1/search/by-ingredients", {"ingredients": []}, format="json")
        log = RequestLog.objects.get(client=client_record)
        assert log.status_code == 200

    def test_log_records_response_ms(self, auth_client, client_record) -> None:
        auth_client.post("/v1/search/by-ingredients", {"ingredients": []}, format="json")
        log = RequestLog.objects.get(client=client_record)
        assert log.response_ms >= 0

    def test_multiple_requests_create_multiple_logs(self, auth_client, client_record) -> None:
        for _ in range(3):
            auth_client.post("/v1/search/by-ingredients", {"ingredients": []}, format="json")
        assert RequestLog.objects.filter(client=client_record).count() == 3

    def test_unauthenticated_request_not_logged(self, db) -> None:
        anon = APIClient()
        anon.post("/v1/search/by-ingredients", {"ingredients": []}, format="json")
        assert RequestLog.objects.count() == 0


@pytest.mark.django_db
class TestRollupTask:
    def test_rollup_creates_usage_record(self, client_record) -> None:
        from apps.clients.tasks import rollup_daily_usage

        today = date.today()
        RequestLog.objects.create(
            client=client_record,
            endpoint="/v1/search/by-ingredients",
            status_code=200,
            response_ms=50,
            # logged_at defaults to now → date = today
        )
        # Manually set logged_at to today for rollup
        RequestLog.objects.filter(client=client_record).update(logged_at=f"{today}T12:00:00Z")

        result = rollup_daily_usage(target_date_iso=str(today))

        assert result["records_created"] == 1
        assert UsageRecord.objects.filter(client=client_record, date=today).exists()

    def test_rollup_counts_calls_correctly(self, client_record) -> None:
        from apps.clients.tasks import rollup_daily_usage

        today = date.today()
        for status in [200, 200, 400, 200]:
            RequestLog.objects.create(
                client=client_record,
                endpoint="/v1/search/by-ingredients",
                status_code=status,
                response_ms=30,
            )
        RequestLog.objects.filter(client=client_record).update(logged_at=f"{today}T12:00:00Z")

        rollup_daily_usage(target_date_iso=str(today))

        record = UsageRecord.objects.get(client=client_record, date=today)
        assert record.calls == 4
        assert record.errors == 1

    def test_rollup_computes_p95(self, client_record) -> None:
        from apps.clients.tasks import rollup_daily_usage

        today = date.today()
        # 20 requests with known response times
        for ms in range(10, 210, 10):  # 10, 20, ..., 200
            RequestLog.objects.create(
                client=client_record,
                endpoint="/v1/search/by-ingredients",
                status_code=200,
                response_ms=ms,
            )
        RequestLog.objects.filter(client=client_record).update(logged_at=f"{today}T12:00:00Z")

        rollup_daily_usage(target_date_iso=str(today))

        record = UsageRecord.objects.get(client=client_record, date=today)
        assert record.p95_ms is not None
        assert record.p95_ms >= 180  # 95th percentile of [10..200]

    def test_duplicate_rollup_updates_not_creates(self, client_record) -> None:
        from apps.clients.tasks import rollup_daily_usage

        today = date.today()
        RequestLog.objects.create(
            client=client_record,
            endpoint="/v1/search/by-ingredients",
            status_code=200,
            response_ms=50,
        )
        RequestLog.objects.filter(client=client_record).update(logged_at=f"{today}T12:00:00Z")

        rollup_daily_usage(target_date_iso=str(today))
        rollup_daily_usage(target_date_iso=str(today))

        assert UsageRecord.objects.filter(client=client_record, date=today).count() == 1

    def test_rollup_skips_other_dates(self, client_record) -> None:
        from apps.clients.tasks import rollup_daily_usage

        yesterday = date.today() - timedelta(days=1)
        today = date.today()

        RequestLog.objects.create(
            client=client_record,
            endpoint="/v1/search/by-ingredients",
            status_code=200,
            response_ms=50,
        )
        RequestLog.objects.filter(client=client_record).update(logged_at=f"{today}T12:00:00Z")

        result = rollup_daily_usage(target_date_iso=str(yesterday))
        assert result["logs_processed"] == 0
        assert not UsageRecord.objects.filter(client=client_record, date=yesterday).exists()
