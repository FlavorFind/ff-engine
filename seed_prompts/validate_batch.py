#!/usr/bin/env python3
"""
Validates a DeepSeek-generated dish batch JSON file.

Usage:
    python validate_batch.py batch_01_output.json

Checks:
    - Valid JSON
    - Required fields present
    - All ingredient slugs are in the allowed list
    - Primary ingredient count is exactly 1
    - Steps present (min 3)
    - Nutrition fields present
    - No duplicate slugs within the batch or against existing batches
"""

import json
import sys
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# ALLOWED INGREDIENT SLUGS — loaded from the trimmed ingredients.csv (98 items)
# ─────────────────────────────────────────────────────────────────────────────

_ROOT = Path(__file__).resolve().parent.parent
_SEEDS = _ROOT / "data" / "seeds"

ALLOWED_SLUGS: set[str] = set()
with open(_SEEDS / "ingredients.csv", encoding="utf-8") as _f:
    import csv as _csv

    for _row in _csv.DictReader(_f):
        ALLOWED_SLUGS.add(_row["slug"])


REQUIRED_FIELDS = [
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
    "regions",
    "ingredients",
    "steps",
    "nutrition_per_serving",
    "dietary_tags",
    "serving_suggestion",
]

NUTRITION_FIELDS = ["calories", "protein_g", "carbs_g", "fat_g", "fiber_g"]

VALID_ROLES = {"primary", "required", "optional", "staple"}
VALID_DIETARY = {
    "halal-friendly",
    "vegetarian",
    "vegan",
    "gluten-free",
    "dairy-free",
    "egg-free",
    "nut-free",
}

# ─────────────────────────────────────────────────────────────────────────────


def validate_file(path: Path, seen_slugs: set) -> tuple[int, int]:
    """Returns (pass_count, fail_count). Updates seen_slugs in place."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"❌  INVALID JSON in {path.name}: {e}")
        return 0, 1

    if not isinstance(data, list):
        print(f"❌  {path.name}: top-level must be a JSON array, got {type(data).__name__}")
        return 0, 1

    passed = 0
    failed = 0

    for i, dish in enumerate(data):
        errors = []
        tag = f"dish[{i}] '{dish.get('slug', '?')}'"

        # Required fields
        for f in REQUIRED_FIELDS:
            if f not in dish:
                errors.append(f"missing field: {f}")

        if errors:
            print(f"❌  {tag}: {'; '.join(errors)}")
            failed += 1
            continue

        slug = dish["slug"]

        # Duplicate slug check
        if slug in seen_slugs:
            errors.append(f"duplicate slug '{slug}'")
        else:
            seen_slugs.add(slug)

        # Regions
        if dish.get("regions") != ["kenya"]:
            errors.append(f"regions must be [\"kenya\"], got {dish.get('regions')}")

        # Ingredients
        ings = dish.get("ingredients", [])
        if not ings:
            errors.append("ingredients list is empty")
        else:
            primary_count = 0
            for ing in ings:
                s = ing.get("slug", "")
                role = ing.get("role", "")
                if s not in ALLOWED_SLUGS:
                    errors.append(f"ingredient slug not allowed: '{s}'")
                if role not in VALID_ROLES:
                    errors.append(f"invalid role '{role}' on ingredient '{s}'")
                if role == "primary":
                    primary_count += 1
            if primary_count != 1:
                errors.append(f"must have exactly 1 primary ingredient, found {primary_count}")

        # Steps
        steps = dish.get("steps", [])
        if len(steps) < 3:
            errors.append(f"need at least 3 steps, got {len(steps)}")

        # Nutrition
        nutrition = dish.get("nutrition_per_serving", {})
        for nf in NUTRITION_FIELDS:
            if nf not in nutrition:
                errors.append(f"nutrition missing field: {nf}")

        # Dietary tags
        bad_tags = [t for t in dish.get("dietary_tags", []) if t not in VALID_DIETARY]
        if bad_tags:
            errors.append(f"invalid dietary_tags: {bad_tags}")

        if errors:
            print(f"❌  {tag}: {'; '.join(errors)}")
            failed += 1
        else:
            print(f"✅  {tag}")
            passed += 1

    return passed, failed


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_batch.py <batch_output.json> [batch_output2.json ...]")
        print("       python validate_batch.py outputs/          # validates all .json in folder")
        sys.exit(1)

    paths = []
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.json")))
        else:
            paths.append(p)

    if not paths:
        print("No JSON files found.")
        sys.exit(1)

    seen_slugs: set = set()
    total_pass = 0
    total_fail = 0

    for path in paths:
        print(f"\n── {path.name} ──────────────────────────────")
        p, f = validate_file(path, seen_slugs)
        total_pass += p
        total_fail += f

    print(f"\n{'═'*60}")
    print(
        f"  TOTAL  ✅ {total_pass} passed    ❌ {total_fail} failed    📦 {total_pass + total_fail} dishes"
    )
    print(f"  Unique slugs seen: {len(seen_slugs)}")

    if total_fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
