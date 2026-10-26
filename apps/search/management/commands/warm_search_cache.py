"""
E40 — Cache warming command.

Usage:
  python manage.py warm_search_cache
  python manage.py warm_search_cache --limit 50
  python manage.py warm_search_cache --dry-run

Warms the Redis search cache by running the top N most-queried
ingredient combinations through the search engine and storing the
results. Called automatically after a dataset release to ensure the
first real requests hit a warm cache.

Query seeds come from:
  1. The top ZeroResultQuery entries by count (so we warm the most
     common misses — they may now resolve after a data update).
  2. A set of hardcoded common single-ingredient queries that always
     appear in traffic (ugali, chapati, beans, etc.).
"""

from __future__ import annotations

import logging

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

# Hardcoded common queries to always warm
_BASELINE_QUERIES = [
    ["ugali"],
    ["chapati"],
    ["beans"],
    ["rice"],
    ["chicken"],
    ["tomato", "onion"],
    ["maize flour", "water"],
    ["beans", "maize"],
    ["sukuma wiki"],
    ["pilau"],
    ["githeri"],
    ["kachumbari"],
    ["mandazi"],
    ["tilapia"],
    ["nyama choma"],
]


class Command(BaseCommand):
    help = "Warm the Redis search cache with common queries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Number of zero-result queries to also warm (default: 20).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print queries that would be warmed without executing them.",
        )

    def handle(self, *args, **options):
        from apps.search.cache import build_cache_key, get_dataset_version, set_cached_result
        from apps.search.engine import search
        from apps.search.models import ZeroResultQuery
        from apps.search.pipeline import resolve_ingredients

        dry_run: bool = options["dry_run"]
        limit: int = options["limit"]

        dataset_version = get_dataset_version()

        # Build the list of queries to warm
        queries_to_warm: list[list[str]] = list(_BASELINE_QUERIES)

        # Add top zero-result queries (they may now resolve after new data)
        top_zero = ZeroResultQuery.objects.order_by("-count")[:limit]
        for zrq in top_zero:
            tokens = zrq.raw_input.split()
            if tokens and tokens not in queries_to_warm:
                queries_to_warm.append(tokens)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN — would warm {len(queries_to_warm)} queries:\n")
            )
            for q in queries_to_warm:
                self.stdout.write(f"  {q}")
            return

        warmed = 0
        skipped = 0

        for ingredients in queries_to_warm:
            try:
                query = resolve_ingredients(ingredients)
                result = search(query)

                from apps.search.serializers import SearchResultItemSerializer

                def serialise(items):
                    return SearchResultItemSerializer(items, many=True).data

                resolved_info = [
                    {
                        "token": r.raw,
                        "status": r.status,
                        "ingredient_id": r.ingredient_id,
                        "method": r.method,
                        "confidence": r.confidence,
                    }
                    for r in query.results
                ]

                payload = {
                    "dataset_version": dataset_version,
                    "mode": "strict",
                    "candidate_count": result.candidate_count,
                    "total_results": result.total_results,
                    "resolved": resolved_info,
                    "ambiguous": [r.raw for r in query.ambiguous],
                    "unmatched": list(query.unmatched),
                    "results": {
                        "exact": serialise(result.exact),
                        "can_make": serialise(result.can_make),
                        "almost": serialise(result.almost),
                    },
                }

                from apps.search.cache import compute_etag

                etag = compute_etag(payload)
                cache_key = build_cache_key(
                    dataset_version=dataset_version,
                    ingredients=ingredients,
                    exclude=[],
                    mode="strict",
                    meal_type=None,
                    course=None,
                    lang="en",
                    limit=20,
                )
                set_cached_result(cache_key, payload, etag, dataset_version)
                warmed += 1

            except Exception:
                logger.exception("warm_search_cache: failed for query %s", ingredients)
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Cache warming complete: {warmed} warmed, {skipped} skipped "
                f"(dataset version: {dataset_version})"
            )
        )
