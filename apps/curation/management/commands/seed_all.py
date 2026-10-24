"""
Management command: seed_all
-----------------------------
Loads seed data from data/seeds/ into the database.

Order of operations:
  1. IngredientCategory rows (derived from ingredients.csv)
  2. Ingredient rows
  3. Dish rows
  4. DishIngredient rows
  5. DishStep rows
  6. rebuild_search_arrays() on every touched dish

Usage:
  python manage.py seed_all
  python manage.py seed_all --env test   # used by nightly CI

Idempotent: uses get_or_create on slugs. Safe to run multiple times.
"""

from __future__ import annotations

import csv
import logging
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import StatusChoices
from apps.dishes.models import Dish, DishIngredient, DishStep
from apps.ingredients.models import Ingredient, IngredientCategory

logger = logging.getLogger(__name__)

SEEDS_DIR = Path(settings.BASE_DIR) / "data" / "seeds"

# ── field-value maps ──────────────────────────────────────────────────────────

SPICE_MAP = {
    "1": Dish.SpiceLevel.MILD,
    "2": Dish.SpiceLevel.MEDIUM,
    "3": Dish.SpiceLevel.MEDIUM,
    "4": Dish.SpiceLevel.HOT,
    "5": Dish.SpiceLevel.VERY_HOT,
}

VALID_MEAL_TYPES = {c[0] for c in Dish.MealType.choices}
VALID_COURSES = {c[0] for c in Dish.Course.choices}
VALID_DIFFICULTIES = {c[0] for c in Dish.Difficulty.choices}
VALID_ING_KINDS = {c[0] for c in Ingredient.Kind.choices}
VALID_ROLES = {c[0] for c in DishIngredient.Role.choices}


def _safe_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value)) if value else default
    except (ValueError, TypeError):
        return default


def _safe_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value) if value else default
    except (ValueError, TypeError):
        return default


class Command(BaseCommand):
    help = "Seed the database with East African recipe data from data/seeds/"

    def add_arguments(self, parser):
        parser.add_argument(
            "--env",
            default="dev",
            choices=["dev", "test", "prod"],
            help="Target environment (default: dev)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and validate without writing to the database",
        )

    def handle(self, *args, **options):
        env = options["env"]
        dry_run = options["dry_run"]

        self.stdout.write(self.style.MIGRATE_HEADING(f"seed_all  env={env}  dry_run={dry_run}"))

        if not SEEDS_DIR.exists():
            raise CommandError(f"Seeds directory not found: {SEEDS_DIR}")

        for name in ("ingredients.csv", "dishes.csv", "dish_ingredients.csv", "dish_steps.csv"):
            if not (SEEDS_DIR / name).exists():
                raise CommandError(f"Missing seed file: {SEEDS_DIR / name}")

        try:
            with transaction.atomic():
                counters = {}
                counters.update(self._seed_ingredients(dry_run))
                counters.update(self._seed_dishes(dry_run))
                counters.update(self._seed_dish_ingredients(dry_run))
                counters.update(self._seed_dish_steps(dry_run))
                if not dry_run:
                    rebuilt = self._rebuild_arrays()
                    counters["dishes_rebuilt"] = rebuilt
                if dry_run:
                    raise _DryRunRollback()
        except _DryRunRollback:
            self.stdout.write(self.style.WARNING("Dry run — all changes rolled back."))
        except Exception as exc:
            raise CommandError(f"Seed failed: {exc}") from exc

        self._report(counters, dry_run)

    # ── ingredient categories ─────────────────────────────────────────────────

    def _get_or_create_category(self, name_en: str, dry_run: bool) -> IngredientCategory | None:
        if dry_run:
            return None
        cat, _ = IngredientCategory.objects.get_or_create(
            slug=name_en.lower().replace(" ", "-").replace("&", "and"),
            defaults={"name_en": name_en},
        )
        return cat

    # ── ingredients ───────────────────────────────────────────────────────────

    def _seed_ingredients(self, dry_run: bool) -> dict:
        path = SEEDS_DIR / "ingredients.csv"
        created = skipped = 0
        category_cache: dict[str, IngredientCategory] = {}

        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                slug = row["slug"].strip()
                name_en = row["name_en"].strip()
                cat_name = row["category"].strip()
                kind = row["kind"].strip()
                is_staple = row["is_staple"].strip().lower() == "true"

                if not slug or not name_en:
                    skipped += 1
                    continue

                if kind not in VALID_ING_KINDS:
                    kind = Ingredient.Kind.SECONDARY

                if dry_run:
                    created += 1
                    continue

                # Category
                if cat_name not in category_cache:
                    category_cache[cat_name] = self._get_or_create_category(cat_name, dry_run)

                cat = category_cache[cat_name]

                obj, was_created = Ingredient.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "name_en": name_en,
                        "category": cat,
                        "kind": kind,
                        "is_staple": is_staple,
                        "status": StatusChoices.DRAFT,
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(f"  Ingredients  created={created}  skipped={skipped}")
        return {"ingredients_created": created, "ingredients_skipped": skipped}

    # ── dishes ────────────────────────────────────────────────────────────────

    def _seed_dishes(self, dry_run: bool) -> dict:
        path = SEEDS_DIR / "dishes.csv"
        created = skipped = 0

        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                slug = row["slug"].strip()
                name_en = row["name_en"].strip()

                if not slug or not name_en:
                    skipped += 1
                    continue

                meal_type = row["meal_type"].strip()
                if meal_type not in VALID_MEAL_TYPES:
                    meal_type = Dish.MealType.ANY

                course = row["course"].strip()
                if course not in VALID_COURSES:
                    course = Dish.Course.MAIN

                difficulty = row["difficulty"].strip()
                if difficulty not in VALID_DIFFICULTIES:
                    difficulty = Dish.Difficulty.MEDIUM

                spice_raw = row["spice_level"].strip()
                spice = SPICE_MAP.get(spice_raw, Dish.SpiceLevel.MEDIUM)

                if dry_run:
                    created += 1
                    continue

                _, was_created = Dish.objects.get_or_create(
                    slug=slug,
                    defaults={
                        "name_en": name_en,
                        "description": row["description"].strip(),
                        "meal_type": meal_type,
                        "course": course,
                        "spice_level": spice,
                        "difficulty": difficulty,
                        "prep_min": _safe_int(row.get("prep_min", "0")),
                        "cook_min": _safe_int(row.get("cook_min", "0")),
                        "servings": _safe_int(row.get("servings", "4"), 4),
                        "quality_level": Dish.QualityLevel.SEEDED,
                        "status": StatusChoices.DRAFT,
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(f"  Dishes       created={created}  skipped={skipped}")
        return {"dishes_created": created, "dishes_skipped": skipped}

    # ── quantity parsing ──────────────────────────────────────────────────────

    @staticmethod
    def _parse_quantity(raw: str) -> tuple[str | None, str]:
        """
        Split "1 kg" → (Decimal-compatible "1", "kg")
        Split "2 tbsp" → ("2", "tbsp")
        Split "1/2 cup" → (None, "1/2 cup")   # fractions stored as note only
        Returns (numeric_str_or_None, unit_note).
        """
        raw = raw.strip()
        if not raw:
            return None, ""
        m = re.match(r"^(\d+(?:\.\d+)?)\s*(.*)", raw)
        if m:
            return m.group(1), m.group(2).strip()
        return None, raw  # e.g. "a pinch", "to taste"

    # ── dish ingredients ──────────────────────────────────────────────────────

    def _seed_dish_ingredients(self, dry_run: bool) -> dict:
        path = SEEDS_DIR / "dish_ingredients.csv"
        created = skipped = missing_dish = missing_ing = 0

        # Cache lookups
        dish_cache: dict[str, Dish] = {}
        ing_cache: dict[str, Ingredient] = {}

        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                dish_slug = row["dish_slug"].strip()
                ing_slug = row["ingredient_slug"].strip()
                role = row["role"].strip()
                qty_raw = row["quantity"].strip()
                position = _safe_int(row.get("position", "1"), 1)

                if role not in VALID_ROLES:
                    role = DishIngredient.Role.REQUIRED

                if dry_run:
                    created += 1
                    continue

                # Dish lookup
                if dish_slug not in dish_cache:
                    try:
                        dish_cache[dish_slug] = Dish.objects.get(slug=dish_slug)
                    except Dish.DoesNotExist:
                        missing_dish += 1
                        continue

                # Ingredient lookup
                if ing_slug not in ing_cache:
                    try:
                        ing_cache[ing_slug] = Ingredient.objects.get(slug=ing_slug)
                    except Ingredient.DoesNotExist:
                        missing_ing += 1
                        continue

                dish = dish_cache[dish_slug]
                ing = ing_cache[ing_slug]

                qty_num, qty_note = self._parse_quantity(qty_raw)

                _, was_created = DishIngredient.objects.get_or_create(
                    dish=dish,
                    ingredient=ing,
                    defaults={
                        "role": role,
                        "quantity": qty_num,  # Decimal or None
                        "preparation_note": qty_raw,  # full string e.g. "1 kg"
                        "position": position,
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

        if missing_dish:
            logger.warning("dish_ingredients: %d rows skipped — dish not found", missing_dish)
        if missing_ing:
            logger.warning("dish_ingredients: %d rows skipped — ingredient not found", missing_ing)

        self.stdout.write(
            f"  DishIngredients  created={created}  skipped={skipped}"
            f"  missing_dish={missing_dish}  missing_ing={missing_ing}"
        )
        return {
            "dish_ingredients_created": created,
            "dish_ingredients_skipped": skipped,
        }

    # ── dish steps ────────────────────────────────────────────────────────────

    def _seed_dish_steps(self, dry_run: bool) -> dict:
        path = SEEDS_DIR / "dish_steps.csv"
        created = skipped = missing_dish = 0
        dish_cache: dict[str, Dish] = {}

        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                dish_slug = row["dish_slug"].strip()
                position = _safe_int(row.get("position", "1"), 1)
                text_en = row["text_en"].strip()

                if not text_en:
                    skipped += 1
                    continue

                if dry_run:
                    created += 1
                    continue

                if dish_slug not in dish_cache:
                    try:
                        dish_cache[dish_slug] = Dish.objects.get(slug=dish_slug)
                    except Dish.DoesNotExist:
                        missing_dish += 1
                        continue

                _, was_created = DishStep.objects.get_or_create(
                    dish=dish_cache[dish_slug],
                    position=position,
                    defaults={"text_en": text_en},
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

        if missing_dish:
            logger.warning("dish_steps: %d rows skipped — dish not found", missing_dish)

        self.stdout.write(f"  DishSteps    created={created}  skipped={skipped}")
        return {"dish_steps_created": created, "dish_steps_skipped": skipped}

    # ── rebuild search arrays ────────────────────────────────────────────────

    def _rebuild_arrays(self) -> int:
        count = 0
        for dish in Dish.objects.prefetch_related("dish_ingredients__ingredient"):
            dish.rebuild_search_arrays()
            count += 1
        return count

    # ── report ────────────────────────────────────────────────────────────────

    def _report(self, counters: dict, dry_run: bool) -> None:
        label = "(dry run)" if dry_run else ""
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"seed_all complete {label}"))
        for key, val in counters.items():
            self.stdout.write(f"  {key}: {val}")


class _DryRunRollback(Exception):
    """Sentinel to roll back the dry-run transaction."""
