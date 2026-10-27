"""
E58 — compute_popularity management command.

Sets initial popularity values (0.0–1.0) for all dishes using three signals:

  1. Ingredient coverage ratio (0.0–1.0)
     Dishes with more ingredients score higher as a rough proxy for
     complexity and interest. Normalised by the maximum ingredient count
     across all dishes.

  2. Quality bonus (0.0–1.0)
     verified=1.0 > reviewed=0.6 > community=0.3 > seeded=0.1
     Reflects human confidence in the entry.

  3. Golden set hint (0.0 or 1.0)
     Dishes referenced in data/golden/golden_set_v0.json are boosted.
     These are dishes people demonstrably search for. Currently 0 for
     all dishes because the golden set tests resolver inputs, not dish
     names. Documented here for the next iteration.

Formula:
    raw = ingredient_ratio * 0.4 + quality_score * 0.4 + golden_hit * 0.2
    popularity = clamp(round(raw, 4), 0.0, 1.0)

Usage:
    python manage.py compute_popularity
    python manage.py compute_popularity --dry-run   # print values, save nothing
    python manage.py compute_popularity --min-quality reviewed  # skip seeded/community
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

_QUALITY_SCORE: dict[str, float] = {
    "verified": 1.0,
    "reviewed": 0.6,
    "community": 0.3,
    "seeded": 0.1,
}


class Command(BaseCommand):
    help = "E58 — Compute initial popularity scores for all dishes."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Print computed values without saving.",
        )
        parser.add_argument(
            "--min-quality",
            default=None,
            choices=["seeded", "community", "reviewed", "verified"],
            help="Only update dishes at or above this quality level.",
        )

    def handle(self, *args, **options) -> None:
        dry_run: bool = options["dry_run"]
        min_quality: str | None = options["min_quality"]
        verbosity: int = options["verbosity"]

        from apps.dishes.models import Dish

        qs = Dish.objects.prefetch_related("dish_ingredients")
        if min_quality:
            quality_order = ["seeded", "community", "reviewed", "verified"]
            min_idx = quality_order.index(min_quality)
            allowed = quality_order[min_idx:]
            qs = qs.filter(quality_level__in=allowed)

        dishes = list(qs)
        if not dishes:
            self.stdout.write("No dishes found.")
            return

        # Max ingredient count for normalisation
        counts = {d.pk: d.dish_ingredients.count() for d in dishes}
        max_count = max(counts.values()) if counts else 1
        if max_count == 0:
            max_count = 1

        # Load golden set dish slugs (best-effort; empty if file missing)
        golden_slugs = _load_golden_slugs()

        updates: list[Dish] = []
        rows: list[tuple[str, float]] = []

        for dish in dishes:
            ingredient_count = counts[dish.pk]
            ingredient_ratio = ingredient_count / max_count
            quality_score = _QUALITY_SCORE.get(dish.quality_level, 0.1)
            golden_hit = 1.0 if dish.slug in golden_slugs else 0.0

            raw = ingredient_ratio * 0.4 + quality_score * 0.4 + golden_hit * 0.2
            popularity = round(max(0.0, min(1.0, raw)), 4)

            if dry_run or verbosity >= 2:
                rows.append((dish.slug, popularity))

            if not dry_run:
                dish.popularity = popularity
                updates.append(dish)

        if dry_run:
            self.stdout.write(self.style.MIGRATE_HEADING("[DRY RUN] compute_popularity\n"))
            for slug, pop in sorted(rows, key=lambda x: -x[1])[:20]:
                self.stdout.write(f"  {slug:<50} {pop:.4f}")
            if len(rows) > 20:
                self.stdout.write(f"  … ({len(rows) - 20} more)")
            self.stdout.write(f"\nWould update {len(rows)} dishes. Remove --dry-run to save.\n")
            return

        # Bulk update
        Dish.objects.bulk_update(updates, ["popularity"], batch_size=200)

        pops = [d.popularity for d in updates]
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ compute_popularity: updated {len(updates)} dishes.\n"
                f"  min={min(pops):.4f}  max={max(pops):.4f}  "
                f"avg={sum(pops)/len(pops):.4f}\n"
                f"  golden set dishes: {len(golden_slugs)}\n"
            )
        )


def _load_golden_slugs() -> set[str]:
    """
    Extract any dish slugs mentioned in the golden set JSON.

    The golden set v0 tests resolver inputs, not dish outputs, so this
    currently returns an empty set. Kept as the extension point for
    when golden cases include expected dish slugs.
    """
    import json
    from pathlib import Path

    golden_path = Path(__file__).resolve().parents[5] / "data" / "golden" / "golden_set_v0.json"
    if not golden_path.exists():
        return set()

    try:
        cases = json.loads(golden_path.read_text())
        slugs: set[str] = set()
        for case in cases:
            expected = case.get("expected", {})
            # Future: extract dish slugs from expected results
            # e.g. expected.get("dish_slugs", [])
            for slug in expected.get("dish_slugs", []):
                slugs.add(slug)
        return slugs
    except Exception:
        return set()
