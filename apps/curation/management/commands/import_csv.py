"""
E10 — Management command: import_csv

Imports ingredients, ingredient aliases, dishes, or dish_ingredients from a
CSV file.  Dry-run mode reports every problem without writing anything.

Usage::

    python manage.py import_csv --type ingredients path/to/ingredients.csv
    python manage.py import_csv --type aliases path/to/aliases.csv
    python manage.py import_csv --type dishes path/to/dishes.csv
    python manage.py import_csv --type dish_ingredients path/to/links.csv

    # Dry-run (shows all errors, saves nothing):
    python manage.py import_csv --type ingredients --dry-run path/to/file.csv

    # Check for duplicates during import:
    python manage.py import_csv --type ingredients --check-duplicates path/to/file.csv

Exit codes:
    0 — success (or dry-run with no errors)
    1 — validation errors found (nothing was saved)

Blueprint spec (E10):
    "Import tool with dry-run.  A bad file reports every problem and saves nothing."
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import StatusChoices
from apps.curation.duplicate_detector import find_duplicate_dishes, find_duplicate_ingredients
from apps.curation.normaliser import normalise
from apps.curation.validators import (
    ValidationResult,
    validate_alias_row,
    validate_dish_has_primary,
    validate_dish_ingredient_row,
    validate_dish_row,
    validate_ingredient_row,
    validate_staple_not_only_primary,
)
from apps.dishes.models import Dish, DishIngredient
from apps.ingredients.models import Ingredient, IngredientAlias, IngredientCategory

VALID_TYPES = ("ingredients", "aliases", "dishes", "dish_ingredients")


class Command(BaseCommand):
    help = "Import data from a CSV file into the engine database"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to the CSV file")
        parser.add_argument(
            "--type",
            required=True,
            choices=VALID_TYPES,
            help="Type of data to import",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report without saving",
        )
        parser.add_argument(
            "--check-duplicates",
            action="store_true",
            help="Warn about potential duplicates (uses similarity check)",
        )
        parser.add_argument(
            "--skip-errors",
            action="store_true",
            help="Skip invalid rows and continue (default: abort on first error batch)",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_file"])
        import_type = options["type"]
        dry_run = options["dry_run"]
        check_dupes = options["check_duplicates"]

        if not csv_path.exists():
            raise CommandError(f"File not found: {csv_path}")

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"import_csv  type={import_type}  dry_run={dry_run}  file={csv_path.name}"
            )
        )

        rows = self._read_csv(csv_path)
        if not rows:
            self.stdout.write(self.style.WARNING("File is empty — nothing to import."))
            return

        # Dispatch to the right importer
        dispatch = {
            "ingredients": self._import_ingredients,
            "aliases": self._import_aliases,
            "dishes": self._import_dishes,
            "dish_ingredients": self._import_dish_ingredients,
        }
        result = dispatch[import_type](rows, dry_run=dry_run, check_dupes=check_dupes)

        self._report(result, dry_run)

        if not result.is_valid:
            sys.exit(1)

    # ------------------------------------------------------------------
    # CSV reader
    # ------------------------------------------------------------------

    def _read_csv(self, path: Path) -> list[dict]:
        rows = []
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append({k.strip(): v.strip() for k, v in row.items()})
        return rows

    # ------------------------------------------------------------------
    # Ingredients importer
    # ------------------------------------------------------------------

    def _import_ingredients(
        self, rows: list[dict], dry_run: bool, check_dupes: bool
    ) -> ValidationResult:
        result = ValidationResult()

        # Pre-load existing slugs for idempotency check
        existing_slugs_in_db: set[str] = set(Ingredient.objects.values_list("slug", flat=True))

        # Track names/slugs seen within this batch (to catch intra-file dupes)
        batch_names: set[str] = set()
        batch_slugs: set[str] = set()

        valid_rows: list[dict] = []

        for i, row in enumerate(rows, start=2):  # row 1 = header
            slug = row.get("slug", "").strip()
            name_en = row.get("name_en", "").strip()

            # Idempotent: skip rows that already exist in the DB
            if slug and slug in existing_slugs_in_db:
                continue

            # Only check intra-batch uniqueness (not against DB — those are skipped above)
            row_result = validate_ingredient_row(
                row,
                row_num=i,
                existing_names=batch_names,
                existing_slugs=batch_slugs,
            )
            result.merge(row_result)

            if row_result.is_valid:
                valid_rows.append(row)
                batch_names.add(name_en.lower())
                batch_slugs.add(slug)

            if check_dupes and row_result.is_valid:
                dupes = find_duplicate_ingredients(name_en)
                for dupe in dupes:
                    self.stdout.write(
                        self.style.WARNING(f"  Row {i}: possible duplicate of {dupe}")
                    )

        if result.errors:
            self._print_errors(result)
            return result

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run: {len(valid_rows)} ingredient row(s) valid, nothing saved."
                )
            )
            return result

        # Save inside a transaction
        created = skipped = 0
        category_cache: dict[str, IngredientCategory] = {}

        with transaction.atomic():
            for row in valid_rows:
                cat_name = row.get("category", "").strip()
                if cat_name not in category_cache:
                    cat, _ = IngredientCategory.objects.get_or_create(
                        slug=cat_name.lower().replace(" ", "-").replace("&", "and"),
                        defaults={"name_en": cat_name},
                    )
                    category_cache[cat_name] = cat

                kind = row.get("kind", "").strip()
                if kind not in {c[0] for c in Ingredient.Kind.choices}:
                    kind = Ingredient.Kind.SECONDARY

                is_staple = row.get("is_staple", "").strip().lower() in ("true", "1", "yes")

                obj, was_created = Ingredient.objects.get_or_create(
                    slug=row["slug"].strip(),
                    defaults={
                        "name_en": row["name_en"].strip(),
                        "name_sw": row.get("name_sw", "").strip(),
                        "category": category_cache[cat_name],
                        "kind": kind,
                        "is_staple": is_staple,
                        "status": StatusChoices.DRAFT,
                        "notes": row.get("notes", "").strip(),
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Ingredients: {created} created, {skipped} skipped (already exist)."
            )
        )
        return result

    # ------------------------------------------------------------------
    # Aliases importer
    # ------------------------------------------------------------------

    def _import_aliases(
        self, rows: list[dict], dry_run: bool, check_dupes: bool
    ) -> ValidationResult:
        result = ValidationResult()

        existing_aliases: set[tuple[str, str]] = set(
            IngredientAlias.objects.values_list("normalized_alias", "language")
        )
        batch_aliases: set[tuple[str, str]] = set()
        valid_rows: list[dict] = []

        for i, row in enumerate(rows, start=2):
            combined = existing_aliases | batch_aliases
            row_result = validate_alias_row(row, row_num=i, existing_aliases=combined)
            result.merge(row_result)

            if row_result.is_valid:
                valid_rows.append(row)
                lang = row.get("language", "en").strip()
                norm = normalise(row.get("alias", ""))
                batch_aliases.add((norm, lang))

        if result.errors:
            self._print_errors(result)
            return result

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Dry run: {len(valid_rows)} alias row(s) valid, nothing saved.")
            )
            return result

        created = skipped = 0
        ing_cache: dict[str, Ingredient] = {}

        with transaction.atomic():
            for row in valid_rows:
                ing_slug = row["ingredient_slug"].strip()
                if ing_slug not in ing_cache:
                    ing_cache[ing_slug] = Ingredient.objects.get(slug=ing_slug)

                alias_text = row["alias"].strip()
                lang = row.get("language", "en").strip()
                norm = normalise(alias_text)
                is_misspelling = row.get("is_misspelling", "").strip().lower() in (
                    "true",
                    "1",
                    "yes",
                )

                obj, was_created = IngredientAlias.objects.get_or_create(
                    normalized_alias=norm,
                    language=lang,
                    defaults={
                        "ingredient": ing_cache[ing_slug],
                        "alias": alias_text,
                        "is_misspelling": is_misspelling,
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Aliases: {created} created, {skipped} skipped."))
        return result

    # ------------------------------------------------------------------
    # Dishes importer
    # ------------------------------------------------------------------

    def _import_dishes(
        self, rows: list[dict], dry_run: bool, check_dupes: bool
    ) -> ValidationResult:
        from apps.dishes.models import Dish

        result = ValidationResult()
        existing_names: set[str] = {
            n.lower() for n in Dish.objects.values_list("name_en", flat=True)
        }
        existing_slugs: set[str] = set(Dish.objects.values_list("slug", flat=True))
        batch_names: set[str] = set()
        batch_slugs: set[str] = set()
        valid_rows: list[dict] = []

        for i, row in enumerate(rows, start=2):
            combined_names = existing_names | {n.lower() for n in batch_names}
            combined_slugs = existing_slugs | batch_slugs
            row_result = validate_dish_row(
                row,
                row_num=i,
                existing_names=combined_names,
                existing_slugs=combined_slugs,
            )
            result.merge(row_result)

            if row_result.is_valid:
                valid_rows.append(row)
                batch_names.add(row.get("name_en", "").strip())
                batch_slugs.add(row.get("slug", "").strip())

            if check_dupes and row_result.is_valid:
                dupes = find_duplicate_dishes(row.get("name_en", ""))
                for dupe in dupes:
                    self.stdout.write(
                        self.style.WARNING(f"  Row {i}: possible duplicate of {dupe}")
                    )

        if result.errors:
            self._print_errors(result)
            return result

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Dry run: {len(valid_rows)} dish row(s) valid, nothing saved.")
            )
            return result

        created = skipped = 0
        spice_map = {
            "1": Dish.SpiceLevel.MILD,
            "2": Dish.SpiceLevel.MEDIUM,
            "3": Dish.SpiceLevel.MEDIUM,
            "4": Dish.SpiceLevel.HOT,
            "5": Dish.SpiceLevel.VERY_HOT,
        }

        with transaction.atomic():
            for row in valid_rows:
                meal_type = row.get("meal_type", "").strip()
                if meal_type not in {c[0] for c in Dish.MealType.choices}:
                    meal_type = Dish.MealType.ANY

                course = row.get("course", "").strip()
                if course not in {c[0] for c in Dish.Course.choices}:
                    course = Dish.Course.MAIN

                difficulty = row.get("difficulty", "").strip()
                if difficulty not in {c[0] for c in Dish.Difficulty.choices}:
                    difficulty = Dish.Difficulty.MEDIUM

                spice = spice_map.get(row.get("spice_level", "").strip(), Dish.SpiceLevel.NONE)

                def _int(v, default=0):
                    try:
                        return max(0, int(float(v))) if v else default
                    except (ValueError, TypeError):
                        return default

                obj, was_created = Dish.objects.get_or_create(
                    slug=row["slug"].strip(),
                    defaults={
                        "name_en": row["name_en"].strip(),
                        "name_sw": row.get("name_sw", "").strip(),
                        "description": row.get("description", "").strip(),
                        "meal_type": meal_type,
                        "course": course,
                        "spice_level": spice,
                        "difficulty": difficulty,
                        "prep_min": _int(row.get("prep_min"), 0),
                        "cook_min": _int(row.get("cook_min"), 0),
                        "servings": max(1, _int(row.get("servings"), 4)),
                        "quality_level": Dish.QualityLevel.SEEDED,
                        "status": StatusChoices.DRAFT,
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(self.style.SUCCESS(f"Dishes: {created} created, {skipped} skipped."))
        return result

    # ------------------------------------------------------------------
    # Dish ingredients importer
    # ------------------------------------------------------------------

    def _import_dish_ingredients(
        self, rows: list[dict], dry_run: bool, check_dupes: bool
    ) -> ValidationResult:
        result = ValidationResult()
        seen_pairs: set[tuple[str, str]] = set()

        # Group rows by dish for V21/V23 dish-level checks
        dish_rows: dict[str, list[dict]] = {}

        valid_rows: list[dict] = []

        for i, row in enumerate(rows, start=2):
            row_result = validate_dish_ingredient_row(row, row_num=i, seen_pairs=seen_pairs)
            result.merge(row_result)

            if row_result.is_valid:
                dish_slug = row.get("dish_slug", "").strip()
                ing_slug = row.get("ingredient_slug", "").strip()
                seen_pairs.add((dish_slug, ing_slug))
                dish_rows.setdefault(dish_slug, []).append(row)
                valid_rows.append(row)

        # V21/V23 per-dish checks.
        # Include EXISTING roles in the DB so importing additional rows
        # to a dish that already has a primary ingredient does not fail.
        for dish_slug, d_rows in dish_rows.items():
            roles = [r.get("role", "").strip() for r in d_rows]

            # Pull existing roles for this dish from the DB
            try:
                from apps.dishes.models import DishIngredient as _DI

                existing_roles = list(
                    _DI.objects.filter(dish__slug=dish_slug).values_list("role", flat=True)
                )
            except Exception:
                existing_roles = []

            all_roles = existing_roles + roles
            result.merge(validate_dish_has_primary(dish_slug, all_roles))
            result.merge(validate_staple_not_only_primary(dish_slug, d_rows))

        if result.errors:
            self._print_errors(result)
            return result

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run: {len(valid_rows)} dish_ingredient row(s) valid, nothing saved."
                )
            )
            return result

        created = skipped = 0
        dish_cache: dict[str, Dish] = {}
        ing_cache: dict[str, Ingredient] = {}

        with transaction.atomic():
            for row in valid_rows:
                dish_slug = row["dish_slug"].strip()
                ing_slug = row["ingredient_slug"].strip()
                role = row.get("role", DishIngredient.Role.REQUIRED).strip()
                if role not in {c[0] for c in DishIngredient.Role.choices}:
                    role = DishIngredient.Role.REQUIRED

                if dish_slug not in dish_cache:
                    dish_cache[dish_slug] = Dish.objects.get(slug=dish_slug)
                if ing_slug not in ing_cache:
                    ing_cache[ing_slug] = Ingredient.objects.get(slug=ing_slug)

                qty_raw = row.get("quantity", "").strip()
                try:
                    qty = float(qty_raw) if qty_raw else None
                except ValueError:
                    qty = None

                position_raw = row.get("position", "1").strip()
                try:
                    position = max(1, int(float(position_raw))) if position_raw else 1
                except (ValueError, TypeError):
                    position = 1

                obj, was_created = DishIngredient.objects.get_or_create(
                    dish=dish_cache[dish_slug],
                    ingredient=ing_cache[ing_slug],
                    defaults={
                        "role": role,
                        "quantity": qty,
                        "preparation_note": qty_raw,
                        "position": position,
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

            # Rebuild search arrays for affected dishes
            for dish in dish_cache.values():
                dish.refresh_from_db()
                dish.rebuild_search_arrays()

        self.stdout.write(
            self.style.SUCCESS(f"DishIngredients: {created} created, {skipped} skipped.")
        )
        return result

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _print_errors(self, result: ValidationResult) -> None:
        self.stdout.write(self.style.ERROR(f"\n{len(result.errors)} validation error(s) found:\n"))
        for err in result.errors:
            row_info = f"row {err.row}: " if err.row else ""
            self.stdout.write(
                self.style.ERROR(f"  [{err.rule}] {row_info}{err.field}: {err.message}")
            )
        self.stdout.write("")
        self.stdout.write(self.style.ERROR("Nothing was saved (dry-run or validation failed)."))

    def _report(self, result: ValidationResult, dry_run: bool) -> None:
        if result.is_valid:
            label = " (dry run — nothing saved)" if dry_run else ""
            self.stdout.write(self.style.SUCCESS(f"\nimport_csv complete{label}"))
        else:
            self.stdout.write(
                self.style.ERROR(f"\nimport_csv failed: {len(result.errors)} error(s)")
            )
