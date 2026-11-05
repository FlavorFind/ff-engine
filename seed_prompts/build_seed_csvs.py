#!/usr/bin/env python3
"""
FF-Engine Seed Loader
======================
Converts the 150 validated JSON dishes into the CSV files that seed_all
expects, archives the current seed CSVs, then calls seed_all to load them.

Usage:
    python seed_prompts/build_seed_csvs.py [--dry-run] [--no-seed]

Flags:
    --dry-run   Build CSVs but do not call seed_all
    --no-seed   Same as --dry-run
    --wipe      Also DELETE existing Dish + DishIngredient + DishStep +
                DishRegion rows before seeding (keeps ingredients intact)

Steps:
    1. Archive current data/seeds/ CSVs to data/seeds/archive_<timestamp>/
    2. Read all batch_0*.json from seed_prompts/outputs/
    3. Write 4 new CSVs:
         data/seeds/dishes.csv
         data/seeds/dish_ingredients.csv
         data/seeds/dish_steps.csv
         data/seeds/dish_regions.csv
    4. Optionally wipe dish rows from DB
    5. Call:  python manage.py seed_all
"""

import argparse
import csv
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent  # repo root
OUTPUTS_DIR = ROOT / "seed_prompts" / "outputs"
SEEDS_DIR = ROOT / "data" / "seeds"
ARCHIVE_DIR = ROOT / "data" / "seeds" / f"archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

BATCH_FILES = sorted(OUTPUTS_DIR.glob("batch_*.json"))

# Region slug — all our dishes are Kenya, mapped to east-african which exists
REGION_SLUG = "east-african"

# CSVs we will overwrite (others like ingredients.csv are left untouched)
TARGET_CSVS = ["dishes.csv", "dish_ingredients.csv", "dish_steps.csv", "dish_regions.csv"]

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def load_all_dishes() -> list[dict]:
    dishes = []
    seen_slugs: set[str] = set()
    seen_names: set[str] = set()
    skipped = 0
    for batch_file in BATCH_FILES:
        batch = json.loads(batch_file.read_text(encoding="utf-8"))
        kept = 0
        for d in batch:
            slug = d["slug"]
            name = d["name_en"]
            if slug in seen_slugs or name in seen_names:
                skipped += 1
                continue
            seen_slugs.add(slug)
            seen_names.add(name)
            dishes.append(d)
            kept += 1
        print(f"  Loaded {kept:>3} dishes from {batch_file.name}")
    print(f"  Total: {len(dishes)} unique dishes  ({skipped} duplicates removed)")
    return dishes


def archive_existing_csvs():
    """Copy current target CSVs to archive dir before overwriting."""
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    for name in TARGET_CSVS:
        src = SEEDS_DIR / name
        if src.exists():
            shutil.copy2(src, ARCHIVE_DIR / name)
            print(f"  Archived: {name}")
    print(f"  Archive saved to: {ARCHIVE_DIR}")


def write_dishes_csv(dishes: list[dict]):
    path = SEEDS_DIR / "dishes.csv"
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
        "calories",
        "protein_g",
        "fat_g",
        "carbs_g",
        "fiber_g",
        "sugar_g",
        "cholesterol_mg",
        "sodium_mg",
        "keywords",
        "status",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in dishes:
            n = d.get("nutrition_per_serving", {})
            row = {
                "slug": d["slug"],
                "name_en": d["name_en"],
                "name_sw": d.get("name_sw", ""),
                "description": d.get("description", ""),
                "meal_type": d.get("meal_type", "lunch"),
                "course": d.get("course", "main"),
                "spice_level": d.get("spice_level", "mild"),
                "difficulty": d.get("difficulty", "easy"),
                "prep_min": d.get("prep_min", 0),
                "cook_min": d.get("cook_min", 0),
                "servings": d.get("servings", 4),
                "calories": n.get("calories", ""),
                "protein_g": n.get("protein_g", ""),
                "fat_g": n.get("fat_g", ""),
                "carbs_g": n.get("carbs_g", ""),
                "fiber_g": n.get("fiber_g", ""),
                "sugar_g": "",
                "cholesterol_mg": "",
                "sodium_mg": "",
                "keywords": "Kenyan",
                "status": "draft",
            }
            writer.writerow(row)
    print(f"  Wrote {len(dishes)} rows → {path.name}")


def write_dish_ingredients_csv(dishes: list[dict]):
    path = SEEDS_DIR / "dish_ingredients.csv"
    fieldnames = ["dish_slug", "ingredient_slug", "role", "quantity", "unit", "position"]
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in dishes:
            for pos, ing in enumerate(d.get("ingredients", []), start=1):
                # Quantity: combine quantity + unit into a single string for
                # the preparation_note column (matches how seed_all parses it)
                qty = ing.get("quantity", "")
                unit = ing.get("unit", "")
                qty_str = f"{qty} {unit}".strip() if qty else unit

                writer.writerow(
                    {
                        "dish_slug": d["slug"],
                        "ingredient_slug": ing["slug"],
                        "role": ing["role"],
                        "quantity": qty_str,
                        "unit": "",  # unit FK resolved by seed_all via preparation_note
                        "position": pos,
                    }
                )
                count += 1
    print(f"  Wrote {count} rows → {path.name}")


def write_dish_steps_csv(dishes: list[dict]):
    path = SEEDS_DIR / "dish_steps.csv"
    fieldnames = ["dish_slug", "position", "text_en"]
    count = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in dishes:
            for step in d.get("steps", []):
                writer.writerow(
                    {
                        "dish_slug": d["slug"],
                        "position": step["order"],
                        "text_en": step["instruction"],
                    }
                )
                count += 1
    print(f"  Wrote {count} rows → {path.name}")


def write_dish_regions_csv(dishes: list[dict]):
    path = SEEDS_DIR / "dish_regions.csv"
    fieldnames = ["dish_slug", "region_slug"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for d in dishes:
            # Use regions from JSON if present, else default to east-african
            regions = d.get("regions", ["kenya"])
            for r in regions:
                # Map "kenya" → "east-african" (our existing region slug)
                region_slug = "east-african" if r == "kenya" else r
                writer.writerow(
                    {
                        "dish_slug": d["slug"],
                        "region_slug": region_slug,
                    }
                )
    print(f"  Wrote {len(dishes)} rows → {path.name}")


def wipe_dish_data():
    """
    Delete all Dish rows (and cascade to DishIngredient, DishStep, DishRegion)
    via Django shell. Keeps Ingredient rows intact.
    """
    print("\n  Wiping existing dish data from DB...")
    cmd = [
        sys.executable,
        "manage.py",
        "shell",
        "--command",
        (
            "from apps.dishes.models import Dish; "
            "n = Dish.objects.all().delete(); "
            "print(f'Deleted: {n}')"
        ),
    ]
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR wiping dishes:\n{result.stderr}")
        sys.exit(1)
    print(f"  {result.stdout.strip()}")


def run_seed_all():
    """Call seed_all management command directly."""
    print("\n  Running: python manage.py seed_all")
    cmd = [sys.executable, "manage.py", "seed_all"]
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print("\n  ❌  seed_all failed")
        sys.exit(1)
    print("\n  ✅  seed_all complete")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Build seed CSVs from JSON batches and load them")
    parser.add_argument(
        "--dry-run", "--no-seed", action="store_true", help="Build CSVs only, do not call seed_all"
    )
    parser.add_argument(
        "--wipe", action="store_true", help="Delete existing Dish rows before seeding"
    )
    args = parser.parse_args()

    print("\n╔══════════════════════════════════════════════════════════╗")
    print("║         FF-Engine  Seed Loader                          ║")
    print("╚══════════════════════════════════════════════════════════╝\n")

    # ── 1. Load JSON batches ──────────────────────────────────────────────────
    print("► Loading JSON batches...")
    if not BATCH_FILES:
        print(f"  ERROR: no batch files found in {OUTPUTS_DIR}")
        sys.exit(1)
    dishes = load_all_dishes()

    # ── 2. Archive existing CSVs ─────────────────────────────────────────────
    print("\n► Archiving existing seed CSVs...")
    archive_existing_csvs()

    # ── 3. Write new CSVs ────────────────────────────────────────────────────
    print("\n► Writing new seed CSVs...")
    write_dishes_csv(dishes)
    write_dish_ingredients_csv(dishes)
    write_dish_steps_csv(dishes)
    write_dish_regions_csv(dishes)

    if args.dry_run:
        print("\n  --dry-run flag set. CSVs written, seed_all skipped.")
        print(f"\n  CSVs are in: {SEEDS_DIR}")
        return

    # ── 4. Optionally wipe dish rows ─────────────────────────────────────────
    if args.wipe:
        wipe_dish_data()

    # ── 5. Run seed_all ───────────────────────────────────────────────────────
    print("\n► Running seed_all...")
    run_seed_all()

    print(f"\n  Archive of old CSVs: {ARCHIVE_DIR}")
    print("  Done.\n")


if __name__ == "__main__":
    main()
