"""
E38 — Celery tasks for usage metering.

rollup_daily_usage:
  Aggregates RequestLog rows from yesterday into UsageRecord rows.
  Scheduled daily at 01:00 Africa/Nairobi via Celery beat.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="clients.rollup_daily_usage")
def rollup_daily_usage(target_date_iso: str | None = None) -> dict:
    """
    Roll up RequestLog rows for *target_date* into UsageRecord rows.

    Args:
        target_date_iso: ISO date string (YYYY-MM-DD). Defaults to yesterday.

    Returns:
        Dict with keys: date, records_created, records_updated, logs_processed.
    """
    from apps.clients.models import RequestLog, UsageRecord

    if target_date_iso:
        target_date = date.fromisoformat(target_date_iso)
    else:
        target_date = date.today() - timedelta(days=1)

    logs = list(RequestLog.objects.filter(logged_at__date=target_date).select_related("client"))

    # Group by (client_id, endpoint)
    groups: dict[tuple, list] = {}
    for log in logs:
        key = (log.client_id, log.endpoint)
        groups.setdefault(key, []).append(log)

    created = updated = 0

    for (client_id, endpoint), entries in groups.items():
        calls = len(entries)
        errors = sum(1 for e in entries if e.status_code >= 400)
        times = sorted(e.response_ms for e in entries)
        p95_ms = times[int(len(times) * 0.95)] if times else None

        _, was_created = UsageRecord.objects.update_or_create(
            client_id=client_id,
            endpoint=endpoint,
            date=target_date,
            defaults={"calls": calls, "errors": errors, "p95_ms": p95_ms},
        )
        if was_created:
            created += 1
        else:
            updated += 1

    logger.info(
        "rollup_daily_usage: date=%s created=%d updated=%d logs=%d",
        target_date,
        created,
        updated,
        len(logs),
    )
    return {
        "date": str(target_date),
        "records_created": created,
        "records_updated": updated,
        "logs_processed": len(logs),
    }
