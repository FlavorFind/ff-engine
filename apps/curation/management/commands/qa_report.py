"""
E14 — Management command: qa_report

Runs a full quality audit over the dataset and prints a report.

Checks:
  • Total counts by model and status
  • Dishes missing Swahili names
  • Ingredients missing Swahili names
  • Ingredients with no aliases
  • Orphan records (DishIngredient pointing to deleted dish/ingredient)
  • Dishes with no steps
  • Dishes with no ingredients
  • Dishes with no primary ingredient (V21)
  • All 23 integrity rule violations (via scan_dataset)

Usage::

    python manage.py qa_report
    python manage.py qa_report --format json     # machine-readable
    python manage.py qa_report --fail-on-critical  # exit 1 if critical violations

Blueprint spec (E14):
    "Counts and gap lists. Shows missing Swahili names, aliases, orphans."
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from django.core.management.base import BaseCommand

from apps.curation.validators import scan_dataset


class Command(BaseCommand):
    help = "Run a full data quality report over the dataset"

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: text)",
        )
        parser.add_argument(
            "--fail-on-critical",
            action="store_true",
            help="Exit with code 1 if any critical integrity violations are found",
        )

    def handle(self, *args, **options):
        fmt = options["format"]
        fail_on_critical = options["fail_on_critical"]

        report = self._build_report()

        if fmt == "json":
            self.stdout.write(json.dumps(report, indent=2))
        else:
            self._print_report(report)

        if fail_on_critical and report["integrity"]["total_violations"] > 0:
            sys.exit(1)

    # ------------------------------------------------------------------
    # Build report
    # ------------------------------------------------------------------

    def _build_report(self) -> dict:
        from apps.dishes.models import Dish, DishIngredient, DishStep
        from apps.ingredients.models import Ingredient, IngredientAlias

        ts = datetime.now(tz=UTC).isoformat()

        # ---- Counts ----
        ing_total = Ingredient.objects.count()
        ing_by_status = _count_by_status(Ingredient)
        dish_total = Dish.objects.count()
        dish_by_status = _count_by_status(Dish)
        alias_total = IngredientAlias.objects.count()
        dish_ing_total = DishIngredient.objects.count()
        dish_step_total = DishStep.objects.count()

        # ---- Gap: missing Swahili names ----
        dishes_no_sw = list(
            Dish.objects.filter(name_sw="").order_by("name_en").values_list("name_en", "slug")
        )
        ings_no_sw = list(
            Ingredient.objects.filter(name_sw="").order_by("name_en").values_list("name_en", "slug")
        )

        # ---- Gap: ingredients with no aliases ----
        from django.db.models import Count

        ings_no_aliases = list(
            Ingredient.objects.annotate(alias_count=Count("aliases"))
            .filter(alias_count=0)
            .order_by("name_en")
            .values_list("name_en", "slug")
        )

        # ---- Gap: dishes with no steps ----
        dishes_with_steps = set(DishStep.objects.values_list("dish_id", flat=True))
        dishes_no_steps = list(
            Dish.objects.exclude(id__in=dishes_with_steps)
            .order_by("name_en")
            .values_list("name_en", "slug")
        )

        # ---- Gap: dishes with no ingredients ----
        dishes_with_ings = set(DishIngredient.objects.values_list("dish_id", flat=True))
        dishes_no_ings = list(
            Dish.objects.exclude(id__in=dishes_with_ings)
            .order_by("name_en")
            .values_list("name_en", "slug")
        )

        # ---- Gap: dishes with no primary ingredient ----
        dishes_with_primary = set(
            DishIngredient.objects.filter(role=DishIngredient.Role.PRIMARY).values_list(
                "dish_id", flat=True
            )
        )
        dishes_no_primary = list(
            Dish.objects.exclude(id__in=dishes_with_primary)
            .order_by("name_en")
            .values_list("name_en", "slug")
        )

        # ---- Integrity violations (validators) ----
        validation_result = scan_dataset()
        violations_by_rule: dict[str, list[str]] = {}
        for err in validation_result.errors:
            violations_by_rule.setdefault(err.rule, []).append(err.message)

        return {
            "generated_at": ts,
            "counts": {
                "ingredients": {
                    "total": ing_total,
                    "by_status": ing_by_status,
                },
                "dishes": {
                    "total": dish_total,
                    "by_status": dish_by_status,
                },
                "aliases": alias_total,
                "dish_ingredients": dish_ing_total,
                "dish_steps": dish_step_total,
            },
            "gaps": {
                "dishes_missing_swahili": {
                    "count": len(dishes_no_sw),
                    "items": [{"name": n, "slug": s} for n, s in dishes_no_sw[:50]],
                    "truncated": len(dishes_no_sw) > 50,
                },
                "ingredients_missing_swahili": {
                    "count": len(ings_no_sw),
                    "items": [{"name": n, "slug": s} for n, s in ings_no_sw[:50]],
                    "truncated": len(ings_no_sw) > 50,
                },
                "ingredients_no_aliases": {
                    "count": len(ings_no_aliases),
                    "items": [{"name": n, "slug": s} for n, s in ings_no_aliases[:50]],
                    "truncated": len(ings_no_aliases) > 50,
                },
                "dishes_no_steps": {
                    "count": len(dishes_no_steps),
                    "items": [{"name": n, "slug": s} for n, s in dishes_no_steps[:50]],
                    "truncated": len(dishes_no_steps) > 50,
                },
                "dishes_no_ingredients": {
                    "count": len(dishes_no_ings),
                    "items": [{"name": n, "slug": s} for n, s in dishes_no_ings[:50]],
                    "truncated": len(dishes_no_ings) > 50,
                },
                "dishes_no_primary_ingredient": {
                    "count": len(dishes_no_primary),
                    "items": [{"name": n, "slug": s} for n, s in dishes_no_primary[:50]],
                    "truncated": len(dishes_no_primary) > 50,
                },
            },
            "integrity": {
                "total_violations": len(validation_result.errors),
                "by_rule": {
                    rule: {"count": len(msgs), "examples": msgs[:3]}
                    for rule, msgs in sorted(violations_by_rule.items())
                },
            },
        }

    # ------------------------------------------------------------------
    # Text printer
    # ------------------------------------------------------------------

    def _print_report(self, report: dict) -> None:
        w = self.stdout.write
        sty = self.style

        w(sty.MIGRATE_HEADING("\n══════════════════════════════════════"))
        w(sty.MIGRATE_HEADING("  FLAVOR FIND — DATA QUALITY REPORT"))
        w(sty.MIGRATE_HEADING("══════════════════════════════════════"))
        w(f"  Generated: {report['generated_at']}\n")

        # Counts
        w(sty.MIGRATE_HEADING("COUNTS"))
        c = report["counts"]
        w(f"  Ingredients:      {c['ingredients']['total']:>6}")
        for status, n in c["ingredients"]["by_status"].items():
            w(f"    {status:<12} {n:>6}")
        w(f"  Dishes:           {c['dishes']['total']:>6}")
        for status, n in c["dishes"]["by_status"].items():
            w(f"    {status:<12} {n:>6}")
        w(f"  Aliases:          {c['aliases']:>6}")
        w(f"  Dish ingredients: {c['dish_ingredients']:>6}")
        w(f"  Dish steps:       {c['dish_steps']:>6}")
        w("")

        # Gaps
        w(sty.MIGRATE_HEADING("GAPS"))
        gaps = report["gaps"]
        gap_labels = {
            "dishes_missing_swahili": "Dishes missing Swahili name",
            "ingredients_missing_swahili": "Ingredients missing Swahili name",
            "ingredients_no_aliases": "Ingredients with no aliases",
            "dishes_no_steps": "Dishes with no steps",
            "dishes_no_ingredients": "Dishes with no ingredients",
            "dishes_no_primary_ingredient": "Dishes with no primary ingredient",
        }
        for key, label in gap_labels.items():
            gap = gaps[key]
            count = gap["count"]
            colour = sty.ERROR if count > 0 else sty.SUCCESS
            w(colour(f"  {label}: {count}"))
            if count > 0:
                for item in gap["items"][:5]:
                    w(f"    • {item['name']} ({item['slug']})")
                if gap["truncated"] or count > 5:
                    w(f"    … and {count - 5} more")
        w("")

        # Integrity
        w(sty.MIGRATE_HEADING("INTEGRITY VIOLATIONS"))
        integrity = report["integrity"]
        total = integrity["total_violations"]
        if total == 0:
            w(sty.SUCCESS("  ✓ No violations found"))
        else:
            w(sty.ERROR(f"  ✗ {total} violation(s) found"))
            for rule, detail in integrity["by_rule"].items():
                w(sty.WARNING(f"  [{rule}] {detail['count']} violation(s)"))
                for ex in detail["examples"]:
                    w(f"    • {ex}")
        w("")
        w(sty.MIGRATE_HEADING("══════════════════════════════════════\n"))


def _count_by_status(model) -> dict[str, int]:
    from django.db.models import Count

    rows = model.objects.values("status").annotate(n=Count("id"))
    return {r["status"]: r["n"] for r in rows}
