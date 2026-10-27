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

        counters = {}
        for label, seeder in [
            ("ingredients", self._seed_ingredients),
            ("dishes", self._seed_dishes),
            ("dish_ingredients", self._seed_dish_ingredients),
            ("dish_steps", self._seed_dish_steps),
            ("pairings", self._seed_pairings),
            ("substitutions", self._seed_substitutions),
            ("regions", self._seed_regions),
            ("units", self._seed_units),
        ]:
            try:
                with transaction.atomic():
                    counters.update(seeder(dry_run))
            except Exception as exc:
                logger.warning("seed_all: %s seeder failed — %s (continuing)", label, exc)

        if not dry_run:
            rebuilt = self._rebuild_arrays()
            counters["dishes_rebuilt"] = rebuilt
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — validation complete, nothing saved."))

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

                obj, was_created = DishIngredient.objects.get_or_create(
                    dish=dish,
                    ingredient=ing,
                    defaults={
                        "role": role,
                        "quantity": qty_num,
                        "preparation_note": qty_raw,
                        "position": position,
                    },
                )
                # If the row already exists but with a different role (e.g. a
                # CSV entry was added later to promote optional → primary),
                # update it so the seeded DB stays in sync with the CSV.
                if not was_created and obj.role != role:
                    obj.role = role
                    obj.save(update_fields=["role"])
                    was_created = True  # count as an effective change

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

    # ── pairings ──────────────────────────────────────────────────────────────

    def _seed_pairings(self, dry_run: bool) -> dict:
        path = SEEDS_DIR / "pairings.csv"
        if not path.exists():
            return {"pairings_created": 0, "pairings_skipped": 0}

        from apps.pairings.models import Pairing

        VALID_TYPES = {c[0] for c in Pairing.PairingType.choices}
        created = skipped = missing = 0
        dish_cache: dict[str, Dish] = {}

        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                dish_slug = row["dish_slug"].strip()
                paired_slug = row.get("paired_dish_slug", "").strip()
                paired_label = row.get("paired_label", "").strip()
                p_type = row["pairing_type"].strip()
                strength = _safe_int(row["strength"], 3)

                if p_type not in VALID_TYPES:
                    p_type = Pairing.PairingType.SIDE
                strength = max(1, min(5, strength))

                if dry_run:
                    created += 1
                    continue

                # Dish
                if dish_slug not in dish_cache:
                    try:
                        dish_cache[dish_slug] = Dish.objects.get(slug=dish_slug)
                    except Dish.DoesNotExist:
                        missing += 1
                        continue
                dish = dish_cache[dish_slug]

                # Paired dish (optional)
                paired_dish = None
                if paired_slug:
                    if paired_slug not in dish_cache:
                        try:
                            dish_cache[paired_slug] = Dish.objects.get(slug=paired_slug)
                        except Dish.DoesNotExist:
                            # Silently skip unknown paired dish slugs
                            pass
                    paired_dish = dish_cache.get(paired_slug)

                if not paired_dish and not paired_label:
                    skipped += 1
                    continue

                _, was_created = Pairing.objects.get_or_create(
                    dish=dish,
                    paired_dish=paired_dish,
                    paired_label=paired_label if not paired_dish else "",
                    pairing_type=p_type,
                    defaults={
                        "strength": strength,
                        "note": (row.get("note") or "").strip(),
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

        if missing:
            logger.warning("pairings: %d rows skipped — dish not found", missing)
        self.stdout.write(f"  Pairings     created={created}  skipped={skipped}")
        return {"pairings_created": created, "pairings_skipped": skipped}

    # ── substitutions ─────────────────────────────────────────────────────────

    def _seed_substitutions(self, dry_run: bool) -> dict:
        path = SEEDS_DIR / "substitutions.csv"
        if not path.exists():
            return {"substitutions_created": 0, "substitutions_skipped": 0}

        from apps.substitutions.models import Substitution

        VALID_QUALITIES = {c[0] for c in Substitution.Quality.choices}
        created = skipped = missing = 0
        ing_cache: dict[str, Ingredient] = {}
        dish_cache: dict[str, Dish] = {}

        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ing_slug = row["ingredient_slug"].strip()
                sub_slug = row["substitute_slug"].strip()
                quality = row["quality"].strip()
                context_slug = row.get("context_dish_slug", "").strip()
                ratio = _safe_float(row.get("ratio", "1.0"), 1.0)

                if quality not in VALID_QUALITIES:
                    quality = Substitution.Quality.OK

                if dry_run:
                    created += 1
                    continue

                # Ingredient
                if ing_slug not in ing_cache:
                    try:
                        ing_cache[ing_slug] = Ingredient.objects.get(slug=ing_slug)
                    except Ingredient.DoesNotExist:
                        missing += 1
                        continue

                # Substitute ingredient
                if sub_slug not in ing_cache:
                    try:
                        ing_cache[sub_slug] = Ingredient.objects.get(slug=sub_slug)
                    except Ingredient.DoesNotExist:
                        missing += 1
                        continue

                ingredient = ing_cache[ing_slug]
                substitute = ing_cache[sub_slug]

                # Context dish (optional)
                context_dish = None
                if context_slug:
                    if context_slug not in dish_cache:
                        try:
                            dish_cache[context_slug] = Dish.objects.get(slug=context_slug)
                        except Dish.DoesNotExist:
                            pass
                    context_dish = dish_cache.get(context_slug)

                try:
                    with transaction.atomic():
                        _, was_created = Substitution.objects.get_or_create(
                            ingredient=ingredient,
                            substitute=substitute,
                            context_dish=context_dish,
                            defaults={
                                "ratio": ratio,
                                "quality": quality,
                                "note": (row.get("note") or "").strip(),
                            },
                        )
                    if was_created:
                        created += 1
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1

        if missing:
            logger.warning("substitutions: %d rows skipped — ingredient not found", missing)
        self.stdout.write(f"  Substitutions created={created}  skipped={skipped}")
        return {"substitutions_created": created, "substitutions_skipped": skipped}

    # ── regions ───────────────────────────────────────────────────────────────

    def _seed_regions(self, dry_run: bool) -> dict:
        path = SEEDS_DIR / "regions.csv"
        if not path.exists():
            return {"regions_created": 0, "regions_skipped": 0}

        from apps.regions.models import Region

        created = skipped = 0
        # Two-pass: create parents first, then children
        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        if dry_run:
            self.stdout.write(f"  Regions      created={len(rows)}  skipped=0  (dry run)")
            return {"regions_created": len(rows), "regions_skipped": 0}

        # Pass 1 — rows with no parent
        for row in rows:
            if row.get("parent_slug", "").strip():
                continue
            _, was_created = Region.objects.get_or_create(
                slug=row["slug"].strip(),
                defaults={
                    "name": row["name"].strip(),
                    "type": row["type"].strip(),
                    "description": (row.get("description") or "").strip(),
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        # Pass 2 — rows with a parent
        for row in rows:
            parent_slug = row.get("parent_slug", "").strip()
            if not parent_slug:
                continue
            parent = Region.objects.filter(slug=parent_slug).first()
            _, was_created = Region.objects.get_or_create(
                slug=row["slug"].strip(),
                defaults={
                    "name": row["name"].strip(),
                    "type": row["type"].strip(),
                    "parent": parent,
                    "description": (row.get("description") or "").strip(),
                },
            )
            if was_created:
                created += 1
            else:
                skipped += 1

        self.stdout.write(f"  Regions      created={created}  skipped={skipped}")
        return {"regions_created": created, "regions_skipped": skipped}

    # ── units ─────────────────────────────────────────────────────────────────

    def _seed_units(self, dry_run: bool) -> dict:
        """
        E55 — Seed measurement units from data/seeds/units.csv.

        Format: code, name, kind, to_base_factor
        """
        path = SEEDS_DIR / "units.csv"
        if not path.exists():
            return {"units_created": 0, "units_skipped": 0}

        from apps.ingredients.models import Unit

        VALID_KINDS = {c[0] for c in Unit.Kind.choices}
        created = skipped = 0

        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                code = row["code"].strip()
                name = row["name"].strip()
                kind = row["kind"].strip()
                factor = _safe_float(row.get("to_base_factor", "1.0"), 1.0)

                if not code or not name:
                    skipped += 1
                    continue
                if kind not in VALID_KINDS:
                    kind = Unit.Kind.COUNT

                if dry_run:
                    created += 1
                    continue

                _, was_created = Unit.objects.get_or_create(
                    code=code,
                    defaults={
                        "name": name,
                        "kind": kind,
                        "to_base_factor": factor,
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(f"  Units        created={created}  skipped={skipped}")
        return {"units_created": created, "units_skipped": skipped}

    # ── units ─────────────────────────────────────────────────────────────────

    def _seed_units(self, dry_run: bool) -> dict:
        """
        E55 — Seed measurement units from data/seeds/units.csv.

        Format: code, name, kind, to_base_factor
        """
        path = SEEDS_DIR / "units.csv"
        if not path.exists():
            return {"units_created": 0, "units_skipped": 0}

        from apps.ingredients.models import Unit

        VALID_KINDS = {c[0] for c in Unit.Kind.choices}
        created = skipped = 0

        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                code = row["code"].strip()
                name = row["name"].strip()
                kind = row["kind"].strip()
                factor = _safe_float(row.get("to_base_factor", "1.0"), 1.0)

                if not code or not name:
                    skipped += 1
                    continue
                if kind not in VALID_KINDS:
                    kind = Unit.Kind.COUNT

                if dry_run:
                    created += 1
                    continue

                _, was_created = Unit.objects.get_or_create(
                    code=code,
                    defaults={
                        "name": name,
                        "kind": kind,
                        "to_base_factor": factor,
                    },
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

        self.stdout.write(f"  Units        created={created}  skipped={skipped}")
        return {"units_created": created, "units_skipped": skipped}

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
