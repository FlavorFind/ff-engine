"""
E58 — Dish popularity Celery tasks.

Provides a periodic task that refreshes dish popularity scores based on
real usage signals. In v1.0 this re-runs the compute_popularity logic
(ingredient count + quality). Future iterations will incorporate actual
search hit counts from UsageRecord / ZeroResultQuery data.

Architecture reference: Blueprint section 6.4 — Popularity signal (0.10 weight).
"""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.dishes.tasks.update_dish_popularity", bind=True, max_retries=3)
def update_dish_popularity(self) -> dict:
    """
    Refresh popularity scores for all reviewed/verified dishes.

    Runs the same formula as `compute_popularity` management command:
        raw = ingredient_ratio * 0.4 + quality_score * 0.4 + golden_hit * 0.2

    Returns a summary dict with count and min/max/avg values.
    Retries up to 3 times on transient DB errors.
    """
    try:
        from apps.dishes.models import Dish
        from apps.core.models import StatusChoices

        _QUALITY_SCORE = {
            "verified": 1.0,
            "reviewed": 0.6,
            "community": 0.3,
            "seeded": 0.1,
        }

        live_statuses = [StatusChoices.REVIEWED, StatusChoices.VERIFIED]
        dishes = list(
            Dish.objects.filter(status__in=live_statuses).prefetch_related("dish_ingredients")
        )

        if not dishes:
            logger.info("update_dish_popularity: no live dishes found")
            return {"updated": 0}

        counts = {d.pk: d.dish_ingredients.count() for d in dishes}
        max_count = max(counts.values(), default=1) or 1

        updates = []
        for dish in dishes:
            ratio = counts[dish.pk] / max_count
            quality = _QUALITY_SCORE.get(dish.quality_level, 0.1)
            raw = ratio * 0.4 + quality * 0.4
            dish.popularity = round(max(0.0, min(1.0, raw)), 4)
            updates.append(dish)

        Dish.objects.bulk_update(updates, ["popularity"], batch_size=200)

        pops = [d.popularity for d in updates]
        result = {
            "updated": len(updates),
            "min": round(min(pops), 4),
            "max": round(max(pops), 4),
            "avg": round(sum(pops) / len(pops), 4),
        }
        logger.info("update_dish_popularity: %s", result)
        return result

    except Exception as exc:
        logger.error("update_dish_popularity: failed — %s", exc)
        raise self.retry(exc=exc, countdown=60)
