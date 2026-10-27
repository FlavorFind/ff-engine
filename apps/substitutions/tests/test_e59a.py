"""
E59a — Substitution uniqueness tests.

Verifies:
1. The seed CSV has zero true constraint-violating duplicates
   (same ingredient + substitute + context_dish_slug triple).
2. The model's UniqueConstraint uses nulls_distinct=False (PostgreSQL 15+).
3. Context-specific rows (same pair, different context) are allowed.

Key finding: the 8 rows that share an (ingredient, substitute) pair each have
a DIFFERENT context_dish_slug, making them distinct under the
(ingredient, substitute, context_dish) constraint. They are not violations.
"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest
from django.db import IntegrityError

SEEDS_DIR = Path(__file__).resolve().parents[4] / "data" / "seeds"


# ---------------------------------------------------------------------------
# CSV-level checks (no DB needed)
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestSubstitutionSeedCSV:
    """Verify the seed CSV has no true constraint violations."""

    def test_no_exact_triple_duplicates(self):
        """
        No two rows share the same (ingredient_slug, substitute_slug, context_dish_slug).
        These are the rows that would violate the DB constraint.
        """
        seen: dict[tuple[str, str, str], int] = {}
        violations: list[str] = []

        with open(SEEDS_DIR / "substitutions.csv") as f:
            for lineno, row in enumerate(csv.DictReader(f), start=2):
                key = (
                    row["ingredient_slug"].strip(),
                    row["substitute_slug"].strip(),
                    row["context_dish_slug"].strip(),
                )
                if key in seen:
                    violations.append(
                        f"Line {lineno} duplicates line {seen[key]}: "
                        f"{key[0]} → {key[1]} (context={key[2]!r})"
                    )
                else:
                    seen[key] = lineno

        assert not violations, (
            f"Seed CSV has {len(violations)} constraint-violating duplicate(s):\n"
            + "\n".join(violations)
        )

    def test_context_specific_rows_are_permitted(self):
        """
        Rows with the same (ingredient, substitute) but different context_dish_slug
        are VALID and expected. Confirm they exist.
        """
        pairs: dict[tuple[str, str], list[str]] = {}

        with open(SEEDS_DIR / "substitutions.csv") as f:
            for row in csv.DictReader(f):
                key = (row["ingredient_slug"].strip(), row["substitute_slug"].strip())
                ctx = row["context_dish_slug"].strip()
                pairs.setdefault(key, []).append(ctx)

        multi_context = {k: v for k, v in pairs.items() if len(v) > 1}
        # We know butter→niter-kibbeh has 4 context variants; just assert some exist
        assert len(multi_context) > 0, (
            "Expected at least one (ingredient, substitute) pair with multiple contexts "
            "(these are valid context-specific substitutions, not duplicates)"
        )

    def test_total_row_count_is_200(self):
        with open(SEEDS_DIR / "substitutions.csv") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 200, f"Expected 200 substitution rows, got {len(rows)}"


# ---------------------------------------------------------------------------
# Model constraint check (no DB write needed)
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_model_has_nulls_distinct_false_constraint():
    """
    The Substitution model must declare the UniqueConstraint with
    nulls_distinct=False so that two NULL context_dish values are treated
    as equal (PostgreSQL 15+ semantics).
    """
    from apps.substitutions.models import Substitution

    constraints = Substitution._meta.constraints
    assert constraints, "Substitution model has no constraints"

    uc = next(
        (c for c in constraints if getattr(c, "name", "") == "unique_substitution_per_context"),
        None,
    )
    assert uc is not None, "UniqueConstraint 'unique_substitution_per_context' not found"
    assert getattr(uc, "nulls_distinct", True) is False, (
        "UniqueConstraint must have nulls_distinct=False (PostgreSQL 15+ required)"
    )


# ---------------------------------------------------------------------------
# DB-level constraint enforcement
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_null_context_duplicate_rejected_by_db():
    """
    Two rows with the same (ingredient, substitute, NULL context) must be
    rejected by the database constraint.
    """
    from apps.core.models import StatusChoices
    from apps.ingredients.models import Ingredient, IngredientCategory
    from apps.substitutions.models import Substitution

    cat, _ = IngredientCategory.objects.get_or_create(
        slug="_e59a-test-cat", defaults={"name_en": "_E59a Test Cat"}
    )
    ing_a, _ = Ingredient.objects.get_or_create(
        slug="_e59a-ing-a",
        defaults={
            "name_en": "_E59a Ingredient A",
            "category": cat,
            "status": StatusChoices.REVIEWED,
        },
    )
    ing_b, _ = Ingredient.objects.get_or_create(
        slug="_e59a-ing-b",
        defaults={
            "name_en": "_E59a Ingredient B",
            "category": cat,
            "status": StatusChoices.REVIEWED,
        },
    )

    # First row — no context (general substitution)
    Substitution.objects.create(ingredient=ing_a, substitute=ing_b, context_dish=None)

    # Second row — same pair, NULL context → must be rejected
    with pytest.raises((IntegrityError, Exception)):
        Substitution.objects.create(ingredient=ing_a, substitute=ing_b, context_dish=None)


@pytest.mark.django_db
def test_same_pair_different_context_is_allowed():
    """
    Two rows with the same (ingredient, substitute) but DIFFERENT contexts
    must succeed — this is the legitimate context-specific pattern.
    """
    from apps.core.models import StatusChoices
    from apps.dishes.models import Dish
    from apps.ingredients.models import Ingredient, IngredientCategory
    from apps.substitutions.models import Substitution

    cat, _ = IngredientCategory.objects.get_or_create(
        slug="_e59a-test-cat-ctx", defaults={"name_en": "_E59a Test Cat Ctx"}
    )
    ing_a, _ = Ingredient.objects.get_or_create(
        slug="_e59a-ctx-ing-a",
        defaults={
            "name_en": "_E59a Ctx Ingredient A",
            "category": cat,
            "status": StatusChoices.REVIEWED,
        },
    )
    ing_b, _ = Ingredient.objects.get_or_create(
        slug="_e59a-ctx-ing-b",
        defaults={
            "name_en": "_E59a Ctx Ingredient B",
            "category": cat,
            "status": StatusChoices.REVIEWED,
        },
    )
    dish_1, _ = Dish.objects.get_or_create(
        slug="_e59a-dish-1", defaults={"name_en": "_E59a Dish 1"}
    )
    dish_2, _ = Dish.objects.get_or_create(
        slug="_e59a-dish-2", defaults={"name_en": "_E59a Dish 2"}
    )

    # Both rows should be created without error
    Substitution.objects.create(ingredient=ing_a, substitute=ing_b, context_dish=dish_1)
    Substitution.objects.create(ingredient=ing_a, substitute=ing_b, context_dish=dish_2)

    count = Substitution.objects.filter(ingredient=ing_a, substitute=ing_b).count()
    assert count == 2
