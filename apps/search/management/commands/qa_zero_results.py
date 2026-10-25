"""
E43 — QA zero-results command.

Usage:
  python manage.py qa_zero_results
  python manage.py qa_zero_results --limit 50
  python manage.py qa_zero_results --min-count 5

Lists the most frequent zero-result search queries, ordered by count
descending.  Intended for the QA team to identify missing ingredients
and dish names so they can be added to the dictionary.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "List the most frequent zero-result search queries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Maximum number of queries to display (default: 20).",
        )
        parser.add_argument(
            "--min-count",
            type=int,
            default=1,
            help="Only show queries seen at least this many times (default: 1).",
        )

    def handle(self, *args, **options):
        from apps.search.models import ZeroResultQuery

        limit: int = options["limit"]
        min_count: int = options["min_count"]

        qs = ZeroResultQuery.objects.filter(count__gte=min_count).order_by("-count", "-last_seen")[
            :limit
        ]

        total = ZeroResultQuery.objects.filter(count__gte=min_count).count()

        if not qs:
            self.stdout.write(
                self.style.WARNING("No zero-result queries found matching the criteria.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(f"\nZero-result queries (showing {min(limit, total)} of {total}):\n")
        )

        # Header
        self.stdout.write(f"{'Count':>6}  {'Last seen':19}  Query")
        self.stdout.write("-" * 70)

        for zrq in qs:
            last_seen_str = zrq.last_seen.strftime("%Y-%m-%d %H:%M")
            self.stdout.write(f"{zrq.count:>6}  {last_seen_str:19}  {zrq.raw_input}")

        self.stdout.write("")
