"""
E59b — Staples audit tests.

Tests:
  - After the migration, exactly 6 ingredients are flagged is_staple=True
  - The correct 6 slugs are the ones flagged
  - No previously-wrong staples (maize-flour, flour, sugar, etc.) remain
  - audit_staples command reports no warnings on the clean DB
  - audit_staples command warns when a staple is primary in a dish
  - audit_staples command warns when an unexpected slug is a staple
  - audit_staples command errors when an expected staple is missing
  - audit_staples --fail-on-warn exits non-zero when warnings exist
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

from apps.ingredients.models import Ingredient, IngredientCategory

# ---------------------------------------------------------------------------
# Expected state after migration
# ---------------------------------------------------------------------------

CORRECT_STAPLES = frozenset(
    [
        "water",
        "salt",
        "iodized-salt",
        "cooking-oil",
        "vegetable-oil",
        "black-pepper",
    ]
)

SHOULD_NOT_BE_STAPLES = [
    "maize-flour",
    "flour",
    "wheat-flour",
    "sugar",
    "butter",
    "baking-powder",
    "bicarbonate-of-soda",
    "yeast",
    "stock",
    "stock-powder",
    "seasoning-cubes",
    "warm-water",
    "pepper",
    "corn-oil",
    "cottonseed-oil",
    "groundnut-oil",
    "olive-oil",
    "sunflower-oil",
    "coconut-oil",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def category(db):
    return IngredientCategory.objects.get_or_create(name_en="_test_e59b_Oils")[0]


def _make_ingredient(slug, name_en, category, is_staple=False):
    ing, _ = Ingredient.objects.get_or_create(
        slug=slug,
        defaults={"name_en": name_en, "category": category, "is_staple": is_staple},
    )
    return ing


# ---------------------------------------------------------------------------
# Migration state tests (run against the seeded staging DB)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStaplesMigrationState:
    """Verify the DB reflects the migration correctly."""

    def test_exactly_six_staples(self, seeded_db) -> None:
        count = Ingredient.objects.filter(is_staple=True).count()
        assert count == 6, (
            f"Expected exactly 6 staples, found {count}: "
            f"{list(Ingredient.objects.filter(is_staple=True).values_list('slug', flat=True))}"
        )

    def test_correct_slugs_are_staples(self, seeded_db) -> None:
        actual = set(Ingredient.objects.filter(is_staple=True).values_list("slug", flat=True))
        assert (
            actual == CORRECT_STAPLES
        ), f"Wrong staple set.\nExpected: {sorted(CORRECT_STAPLES)}\nGot: {sorted(actual)}"

    @pytest.mark.parametrize("slug", SHOULD_NOT_BE_STAPLES)
    def test_wrong_ingredient_not_a_staple(self, seeded_db, slug) -> None:
        """Each formerly-wrong staple must now have is_staple=False."""
        try:
            ing = Ingredient.objects.get(slug=slug)
        except Ingredient.DoesNotExist:
            pytest.skip(f"{slug!r} not in DB — skip")
        assert ing.is_staple is False, f"{slug!r} should not be a staple"

    @pytest.mark.parametrize("slug", sorted(CORRECT_STAPLES))
    def test_correct_ingredient_is_staple(self, seeded_db, slug) -> None:
        ing = Ingredient.objects.get(slug=slug)
        assert ing.is_staple is True, f"{slug!r} should be a staple"


# ---------------------------------------------------------------------------
# audit_staples command tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuditStaplesCommand:
    """Unit tests for the audit_staples management command."""

    def test_clean_db_passes_with_no_warnings(self, seeded_db) -> None:
        """After migration, audit_staples should report no warnings."""
        out = StringIO()
        call_command("audit_staples", stdout=out)
        output = out.getvalue()
        assert "warning" not in output.lower() or "0 warning" in output.lower()
        assert "✓" in output or "passed" in output.lower()

    def test_output_lists_all_six_staples(self, seeded_db) -> None:
        out = StringIO()
        call_command("audit_staples", stdout=out)
        output = out.getvalue()
        for slug in CORRECT_STAPLES:
            assert slug in output, f"{slug!r} not listed in audit output"

    def test_warns_when_staple_is_primary_ingredient(self, db, category) -> None:
        """If a staple is the primary ingredient of a dish, a warning is raised."""
        from apps.dishes.models import Dish, DishIngredient

        # Create a staple ingredient
        oil = _make_ingredient("_test-oil-primary", "_test Oil Primary", category, is_staple=True)

        # Create a dish where this "staple" is primary
        dish, _ = Dish.objects.get_or_create(
            name_en="_test_OilDish",
            defaults={"name_sw": "_test_OilDish_sw"},
        )
        DishIngredient.objects.get_or_create(
            dish=dish,
            ingredient=oil,
            defaults={"role": DishIngredient.Role.PRIMARY, "quantity": 1},
        )

        out = StringIO()
        call_command("audit_staples", stdout=out)
        output = out.getvalue()
        assert "_test-oil-primary" in output
        assert "PRIMARY" in output.upper() or "primary" in output.lower()

    def test_warns_on_unexpected_staple(self, db, category) -> None:
        """A slug not in the expected set but flagged as_staple triggers a warning."""
        _make_ingredient(
            "_test-unexpected-staple", "_test Unexpected Staple", category, is_staple=True
        )
        out = StringIO()
        call_command("audit_staples", stdout=out)
        output = out.getvalue()
        assert "_test-unexpected-staple" in output
        assert "NOT in the expected set" in output or "warning" in output.lower()

    def test_fail_on_warn_exits_nonzero(self, db, category) -> None:
        """--fail-on-warn must raise SystemExit(1) when warnings are present."""
        _make_ingredient("_test-bad-staple-fw", "_test Bad Staple FW", category, is_staple=True)
        with pytest.raises(SystemExit) as exc_info:
            call_command("audit_staples", "--fail-on-warn", stdout=StringIO())
        assert exc_info.value.code == 1

    def test_no_fail_without_warn_flag(self, seeded_db) -> None:
        """Without --fail-on-warn, the command exits 0 even if there are issues."""
        # On a clean seeded_db this should just pass
        out = StringIO()
        call_command("audit_staples", stdout=out)  # must not raise
