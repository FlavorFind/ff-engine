"""
Management command: run_golden_set
-----------------------------------
Runs the E18 golden set — a hand-authored fixture of 20 test cases that
exercise the search input pipeline (normalise → resolve → expand).

Each case specifies:
  - inputs:           list of raw ingredient strings to pass to resolve_ingredients()
  - excluded_slugs:   optional slugs to exclude (mapped to IDs before the call)
  - aliases_required: aliases to create for the duration of the test
  - dish_slug:        used for pool-completeness checks (G15)
  - expect:           assertions to verify

Exit codes:
  0  all cases passed
  1  one or more cases failed (or fixture not found)

Usage::

    python manage.py run_golden_set
    python manage.py run_golden_set --fixture data/golden/golden_set_v0.json
    python manage.py run_golden_set --fail-fast
    python manage.py run_golden_set --json          # machine-readable output
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

DEFAULT_FIXTURE = Path(settings.BASE_DIR) / "data" / "golden" / "golden_set_v0.json"


class Command(BaseCommand):
    help = "Run the E18 golden set against the search pipeline."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--fixture",
            default=str(DEFAULT_FIXTURE),
            help="Path to the golden set JSON fixture (default: data/golden/golden_set_v0.json)",
        )
        parser.add_argument(
            "--fail-fast",
            action="store_true",
            default=False,
            help="Stop on the first failing case.",
        )
        parser.add_argument(
            "--json",
            dest="json_output",
            action="store_true",
            default=False,
            help="Output machine-readable JSON instead of human text.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        fixture_path = Path(options["fixture"])
        if not fixture_path.exists():
            self.stderr.write(self.style.ERROR(f"Fixture not found: {fixture_path}"))
            sys.exit(1)

        with fixture_path.open() as fh:
            fixture = json.load(fh)

        cases = fixture.get("cases", [])
        results: list[dict[str, Any]] = []
        passed = 0
        failed = 0

        for case in cases:
            result = _run_case(case)
            results.append(result)
            if result["passed"]:
                passed += 1
            else:
                failed += 1
                if options["fail_fast"]:
                    break

        if options["json_output"]:
            self.stdout.write(
                json.dumps(
                    {
                        "fixture": str(fixture_path),
                        "total": len(results),
                        "passed": passed,
                        "failed": failed,
                        "cases": results,
                    },
                    indent=2,
                )
            )
        else:
            self._print_human(results, fixture_path)

        if failed > 0:
            sys.exit(1)

    # ------------------------------------------------------------------
    # Human-readable output
    # ------------------------------------------------------------------

    def _print_human(self, results: list[dict[str, Any]], fixture_path: Path) -> None:
        self.stdout.write(f"\nGolden set: {fixture_path.name}")
        self.stdout.write("-" * 60)
        for r in results:
            icon = "✓" if r["passed"] else "✗"
            self.stdout.write(f"  {icon} [{r['id']}] {r['description']}")
            if not r["passed"]:
                for failure in r["failures"]:
                    self.stdout.write(self.style.ERROR(f"      FAIL: {failure}"))
        self.stdout.write("-" * 60)
        total = len(results)
        passed = sum(1 for r in results if r["passed"])
        failed = total - passed
        summary = f"  {passed}/{total} passed"
        if failed:
            self.stdout.write(self.style.ERROR(summary + f"  ({failed} failed)"))
        else:
            self.stdout.write(self.style.SUCCESS(summary))
        self.stdout.write("")


# ---------------------------------------------------------------------------
# Case runner — runs outside a transaction so DB state is live
# ---------------------------------------------------------------------------


def _run_case(case: dict[str, Any]) -> dict[str, Any]:
    """Run a single golden-set case and return a result dict."""
    from django.db import transaction

    case_id = case["id"]
    description = case.get("description", "")
    inputs: list[str] = case.get("inputs", [])
    excluded_slugs: list[str] = case.get("excluded_slugs", [])
    aliases_required: list[dict[str, str]] = case.get("aliases_required", [])
    dish_slug: str | None = case.get("dish_slug")
    expect: dict[str, Any] = case.get("expect", {})

    failures: list[str] = []

    # Use a savepoint so alias creation is rolled back after the case
    with transaction.atomic():
        sid = transaction.savepoint()
        try:
            _create_aliases(aliases_required)
            excluded_ids = _slugs_to_ids(excluded_slugs)
            query = _call_pipeline(inputs, excluded_ids)
            failures = _check_expectations(expect, query, inputs, dish_slug)
        except Exception as exc:
            failures = [f"Exception: {exc}"]
        finally:
            transaction.savepoint_rollback(sid)

    return {
        "id": case_id,
        "description": description,
        "inputs": inputs,
        "passed": len(failures) == 0,
        "failures": failures,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_aliases(aliases_required: list[dict[str, str]]) -> None:
    from apps.ingredients.models import Ingredient, IngredientAlias

    for spec in aliases_required:
        try:
            ing = Ingredient.objects.get(slug=spec["ingredient_slug"])
        except Ingredient.DoesNotExist as exc:
            raise ValueError(
                f"Ingredient with slug '{spec['ingredient_slug']}' not found in DB. "
                "Run seed_all first."
            ) from exc
        IngredientAlias.objects.get_or_create(
            ingredient=ing,
            alias=spec["alias"],
            defaults={
                "normalized_alias": spec.get("normalized_alias", spec["alias"]),
                "language": spec.get("language", "en"),
            },
        )


def _slugs_to_ids(slugs: list[str]) -> list[str]:
    from apps.ingredients.models import Ingredient

    if not slugs:
        return []
    ids = []
    for slug in slugs:
        try:
            ing = Ingredient.objects.get(slug=slug)
            ids.append(str(ing.id))
        except Ingredient.DoesNotExist as exc:
            raise ValueError(f"excluded_slug '{slug}' not found. Run seed_all first.") from exc
    return ids


def _call_pipeline(inputs: list[str], excluded_ids: list[str]):
    from apps.search.pipeline import resolve_ingredients

    return resolve_ingredients(inputs, excluded_ids=excluded_ids if excluded_ids else None)


def _check_expectations(
    expect: dict[str, Any],
    query: Any,
    inputs: list[str],
    dish_slug: str | None,
) -> list[str]:
    from apps.ingredients.models import Ingredient
    from apps.search.staples import non_staple_required_ids

    failures: list[str] = []

    # Helper: slug → id
    def slug_to_id(slug: str) -> str | None:
        try:
            return str(Ingredient.objects.get(slug=slug).id)
        except Ingredient.DoesNotExist:
            return None

    # matched_slugs — every listed slug must be in query.matched_ids
    if "matched_slugs" in expect:
        for slug in expect["matched_slugs"]:
            iid = slug_to_id(slug)
            if iid is None:
                failures.append(f"matched_slugs: ingredient '{slug}' not in DB")
            elif iid not in query.matched_ids:
                failures.append(f"matched_slugs: '{slug}' not in matched_ids {query.matched_ids}")

    # matched_count — exact count of matched_ids
    if "matched_count" in expect:
        actual = len(query.matched_ids)
        expected_count = expect["matched_count"]
        if actual != expected_count:
            failures.append(f"matched_count: expected {expected_count}, got {actual}")

    # unmatched — every listed raw token must be in query.unmatched
    if "unmatched" in expect:
        for token in expect["unmatched"]:
            if token not in query.unmatched:
                failures.append(f"unmatched: '{token}' not in unmatched {query.unmatched}")

    # is_empty
    if "is_empty" in expect:
        if query.is_empty != expect["is_empty"]:
            failures.append(f"is_empty: expected {expect['is_empty']}, got {query.is_empty}")

    # has_ambiguity
    if "has_ambiguity" in expect:
        if query.has_ambiguity != expect["has_ambiguity"]:
            failures.append(
                f"has_ambiguity: expected {expect['has_ambiguity']}, got {query.has_ambiguity}"
            )

    # staples_added_min — at least N staples must have been added
    if "staples_added_min" in expect:
        actual = len(query.staples_added)
        if actual < expect["staples_added_min"]:
            failures.append(
                f"staples_added_min: expected ≥{expect['staples_added_min']}, got {actual}"
            )

    # pool_excludes_slugs — these slugs must NOT be in the pool
    if "pool_excludes_slugs" in expect:
        for slug in expect["pool_excludes_slugs"]:
            iid = slug_to_id(slug)
            if iid and iid in query.pool:
                failures.append(f"pool_excludes_slugs: '{slug}' should not be in pool but it is")

    # pool_covers_dish_non_staple_required — pool must cover all non-staple
    # required IDs for the specified dish
    if expect.get("pool_covers_dish_non_staple_required") and dish_slug:
        from apps.dishes.models import Dish

        try:
            dish = Dish.objects.get(slug=dish_slug)
            dish.refresh_from_db()
            non_staple = non_staple_required_ids(dish)
            pool_set = set(query.pool)
            missing = [iid for iid in non_staple if iid not in pool_set]
            if missing:
                failures.append(
                    f"pool_covers_dish_non_staple_required: pool is missing {missing} "
                    f"for dish '{dish_slug}'"
                )
        except Dish.DoesNotExist:
            failures.append(
                f"pool_covers_dish_non_staple_required: dish '{dish_slug}' not in DB. "
                "Run seed_all first."
            )

    # results_count — number of ResolveResult objects
    if "results_count" in expect:
        actual = len(query.results)
        if actual != expect["results_count"]:
            failures.append(f"results_count: expected {expect['results_count']}, got {actual}")

    # method_for_input — check method on specific input tokens
    if "method_for_input" in expect:
        result_map = {r.raw: r for r in query.results}
        for raw_input, expected_method in expect["method_for_input"].items():
            r = result_map.get(raw_input)
            if r is None:
                failures.append(f"method_for_input: no result found for input '{raw_input}'")
            elif r.method != expected_method:
                failures.append(
                    f"method_for_input['{raw_input}']: expected '{expected_method}', "
                    f"got '{r.method}'"
                )

    # confidence_min_for_input — confidence must be >= threshold
    if "confidence_min_for_input" in expect:
        result_map = {r.raw: r for r in query.results}
        for raw_input, min_conf in expect["confidence_min_for_input"].items():
            r = result_map.get(raw_input)
            if r is None:
                failures.append(
                    f"confidence_min_for_input: no result found for input '{raw_input}'"
                )
            elif r.confidence < min_conf:
                failures.append(
                    f"confidence_min_for_input['{raw_input}']: expected ≥{min_conf}, "
                    f"got {r.confidence}"
                )

    return failures
