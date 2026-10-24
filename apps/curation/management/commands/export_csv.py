"""
E11 — Management command: export_csv

Exports ingredients, aliases, dishes, dish_ingredients, or a full dataset
snapshot (all four bundled in a timestamped directory) to CSV.

Usage::

    python manage.py export_csv --type ingredients
    python manage.py export_csv --type aliases
    python manage.py export_csv --type dishes
    python manage.py export_csv --type dish_ingredients
    python manage.py export_csv --type snapshot        # exports all four + manifest

    # Write to a specific directory:
    python manage.py export_csv --type snapshot --output-dir /tmp/exports/

Blueprint spec (E11):
    "Export then import reproduces identical data."
    "Full export of the library."
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

EXPORT_TYPES = ("ingredients", "aliases", "dishes", "dish_ingredients", "snapshot")

DEFAULT_OUTPUT_DIR = Path(settings.BASE_DIR) / "data" / "exports"


class Command(BaseCommand):
    help = "Export engine data to CSV files"

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            required=True,
            choices=EXPORT_TYPES,
            help="Data type to export",
        )
        parser.add_argument(
            "--output-dir",
            default=str(DEFAULT_OUTPUT_DIR),
            help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
        )
        parser.add_argument(
            "--status",
            default=None,
            choices=["draft", "reviewed", "verified", "archived"],
            help="Filter by status (default: all)",
        )

    def handle(self, *args, **options):
        export_type = options["type"]
        output_dir = Path(options["output_dir"])
        status_filter = options.get("status")

        output_dir.mkdir(parents=True, exist_ok=True)

        self.stdout.write(
            self.style.MIGRATE_HEADING(f"export_csv  type={export_type}  output={output_dir}")
        )

        if export_type == "snapshot":
            self._export_snapshot(output_dir, status_filter)
        else:
            dispatch = {
                "ingredients": self._export_ingredients,
                "aliases": self._export_aliases,
                "dishes": self._export_dishes,
                "dish_ingredients": self._export_dish_ingredients,
            }
            out_path = output_dir / f"{export_type}.csv"
            count = dispatch[export_type](out_path, status_filter)
            self.stdout.write(self.style.SUCCESS(f"Wrote {count} rows → {out_path}"))

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def _export_snapshot(self, base_dir: Path, status_filter: str | None) -> None:
        ts = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        snap_dir = base_dir / f"snapshot_{ts}"
        snap_dir.mkdir(parents=True, exist_ok=True)

        counts = {}
        for name, fn in [
            ("ingredients", self._export_ingredients),
            ("aliases", self._export_aliases),
            ("dishes", self._export_dishes),
            ("dish_ingredients", self._export_dish_ingredients),
        ]:
            out_path = snap_dir / f"{name}.csv"
            n = fn(out_path, status_filter)
            counts[name] = n
            self.stdout.write(f"  {name}: {n} rows → {out_path.name}")

        # Write manifest
        manifest = {
            "timestamp": ts,
            "status_filter": status_filter,
            "counts": counts,
            "total": sum(counts.values()),
        }
        manifest_path = snap_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2))
        self.stdout.write(self.style.SUCCESS(f"Snapshot complete → {snap_dir}"))
        self.stdout.write(f"  manifest: {manifest_path}")

    # ------------------------------------------------------------------
    # Individual exporters
    # ------------------------------------------------------------------

    def _export_ingredients(self, path: Path, status_filter: str | None) -> int:
        from apps.ingredients.models import Ingredient

        qs = Ingredient.objects.select_related("category", "typical_unit").order_by("slug")
        if status_filter:
            qs = qs.filter(status=status_filter)

        fieldnames = [
            "slug",
            "name_en",
            "name_sw",
            "category",
            "kind",
            "is_staple",
            "typical_unit",
            "status",
            "notes",
        ]
        count = 0
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for obj in qs:
                writer.writerow(
                    {
                        "slug": obj.slug,
                        "name_en": obj.name_en,
                        "name_sw": obj.name_sw or "",
                        "category": obj.category.name_en if obj.category else "",
                        "kind": obj.kind,
                        "is_staple": str(obj.is_staple),
                        "typical_unit": obj.typical_unit.code if obj.typical_unit else "",
                        "status": obj.status,
                        "notes": obj.notes or "",
                    }
                )
                count += 1
        return count

    def _export_aliases(self, path: Path, status_filter: str | None) -> int:
        from apps.ingredients.models import IngredientAlias

        # Aliases don't have a status field; status_filter is ignored
        qs = IngredientAlias.objects.select_related("ingredient").order_by(
            "ingredient__slug", "language", "alias"
        )

        fieldnames = ["ingredient_slug", "alias", "normalized_alias", "language", "is_misspelling"]
        count = 0
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for obj in qs:
                writer.writerow(
                    {
                        "ingredient_slug": obj.ingredient.slug,
                        "alias": obj.alias,
                        "normalized_alias": obj.normalized_alias,
                        "language": obj.language,
                        "is_misspelling": str(obj.is_misspelling),
                    }
                )
                count += 1
        return count

    def _export_dishes(self, path: Path, status_filter: str | None) -> int:
        from apps.dishes.models import Dish

        qs = Dish.objects.order_by("slug")
        if status_filter:
            qs = qs.filter(status=status_filter)

        fieldnames = [
            "slug",
            "name_en",
            "name_sw",
            "description",
            "meal_type",
            "course",
            "spice_level",
            "difficulty",
            "prep_min",
            "cook_min",
            "servings",
            "popularity",
            "quality_level",
            "status",
        ]
        count = 0
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for obj in qs:
                writer.writerow(
                    {
                        "slug": obj.slug,
                        "name_en": obj.name_en,
                        "name_sw": obj.name_sw or "",
                        "description": obj.description or "",
                        "meal_type": obj.meal_type,
                        "course": obj.course,
                        "spice_level": obj.spice_level,
                        "difficulty": obj.difficulty,
                        "prep_min": obj.prep_min,
                        "cook_min": obj.cook_min,
                        "servings": obj.servings,
                        "popularity": obj.popularity,
                        "quality_level": obj.quality_level,
                        "status": obj.status,
                    }
                )
                count += 1
        return count

    def _export_dish_ingredients(self, path: Path, status_filter: str | None) -> int:
        from apps.dishes.models import DishIngredient

        qs = DishIngredient.objects.select_related("dish", "ingredient", "unit").order_by(
            "dish__slug", "position"
        )
        if status_filter:
            qs = qs.filter(dish__status=status_filter)

        fieldnames = [
            "dish_slug",
            "ingredient_slug",
            "role",
            "quantity",
            "unit",
            "preparation_note",
            "position",
        ]
        count = 0
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for obj in qs:
                writer.writerow(
                    {
                        "dish_slug": obj.dish.slug,
                        "ingredient_slug": obj.ingredient.slug,
                        "role": obj.role,
                        "quantity": str(obj.quantity) if obj.quantity is not None else "",
                        "unit": obj.unit.code if obj.unit else "",
                        "preparation_note": obj.preparation_note or "",
                        "position": obj.position,
                    }
                )
                count += 1
        return count
