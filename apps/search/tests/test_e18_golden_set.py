"""
E18 — Golden set runner tests.

Tests for the run_golden_set management command and its helpers.
Fixtures are kept lightweight — just tomato + maize-flour + salt/water +
the ugali dish, seeded inline rather than relying on seed_all.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.core.models import StatusChoices
from apps.dishes.models import Dish, DishIngredient
from apps.ingredients.models import Ingredient, IngredientAlias, IngredientCategory

# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def category(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="vegetables", defaults={"name_en": "Vegetables"}
    )
    return cat


@pytest.fixture
def grains_cat(db):
    cat, _ = IngredientCategory.objects.get_or_create(slug="grains", defaults={"name_en": "Grains"})
    return cat


@pytest.fixture
def liquid_cat(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="liquids", defaults={"name_en": "Liquids"}
    )
    return cat


@pytest.fixture
def seasoning_cat(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="spices-seasonings", defaults={"name_en": "Spices & Seasonings"}
    )
    return cat


@pytest.fixture
def tomato(db, category):
    ing, _ = Ingredient.objects.get_or_create(
        slug="tomato",
        defaults={
            "name_en": "Tomato",
            "name_sw": "Nyanya",
            "category": category,
            "kind": Ingredient.Kind.PRIMARY,
            "is_staple": False,
            "status": StatusChoices.DRAFT,
        },
    )
    # Ensure name_sw is set even if the seeded ingredient has an empty value
    if not ing.name_sw:
        ing.name_sw = "Nyanya"
        ing.save(update_fields=["name_sw"])
    return ing


@pytest.fixture
def onion(db, category):
    ing, _ = Ingredient.objects.get_or_create(
        slug="onion",
        defaults={
            "name_en": "Onion",
            "category": category,
            "kind": Ingredient.Kind.PRIMARY,
            "is_staple": False,
            "status": StatusChoices.DRAFT,
        },
    )
    return ing


@pytest.fixture
def maize_flour(db, grains_cat):
    ing, _ = Ingredient.objects.get_or_create(
        slug="maize-flour",
        defaults={
            "name_en": "Maize flour",
            "name_sw": "Unga wa mahindi",
            "category": grains_cat,
            "kind": Ingredient.Kind.PRIMARY,
            "is_staple": False,
            "status": StatusChoices.DRAFT,
        },
    )
    return ing


@pytest.fixture
def salt(db, seasoning_cat):
    ing, _ = Ingredient.objects.get_or_create(
        slug="salt",
        defaults={
            "name_en": "Salt",
            "category": seasoning_cat,
            "kind": Ingredient.Kind.STAPLE,
            "is_staple": True,
            "status": StatusChoices.DRAFT,
        },
    )
    return ing


@pytest.fixture
def water(db, liquid_cat):
    ing, _ = Ingredient.objects.get_or_create(
        slug="water",
        defaults={
            "name_en": "Water",
            "category": liquid_cat,
            "kind": Ingredient.Kind.STAPLE,
            "is_staple": True,
            "status": StatusChoices.DRAFT,
        },
    )
    return ing


@pytest.fixture
def ugali(db, maize_flour, salt, water):
    dish, _ = Dish.objects.get_or_create(
        slug="ugali",
        defaults={
            "name_en": "Ugali",
            "meal_type": Dish.MealType.LUNCH,
            "course": Dish.Course.MAIN,
            "spice_level": Dish.SpiceLevel.MILD,
            "difficulty": Dish.Difficulty.EASY,
            "prep_min": 5,
            "cook_min": 20,
            "status": StatusChoices.DRAFT,
        },
    )
    DishIngredient.objects.get_or_create(
        dish=dish,
        ingredient=maize_flour,
        defaults={"role": DishIngredient.Role.PRIMARY, "quantity": 2},
    )
    DishIngredient.objects.get_or_create(
        dish=dish,
        ingredient=salt,
        defaults={"role": DishIngredient.Role.OPTIONAL, "quantity": 1},
    )
    DishIngredient.objects.get_or_create(
        dish=dish,
        ingredient=water,
        defaults={"role": DishIngredient.Role.REQUIRED, "quantity": 3},
    )
    dish.rebuild_search_arrays()
    return dish


@pytest.fixture
def tomato_alias(db, tomato):
    alias, _ = IngredientAlias.objects.get_or_create(
        ingredient=tomato,
        alias="nyanya",
        defaults={"normalized_alias": "nyanya", "language": "sw"},
    )
    return alias


# ===========================================================================
# Helper: minimal in-memory fixture
# ===========================================================================


def _make_fixture(cases: list[dict]) -> dict:
    return {"version": "0", "description": "test", "cases": cases}


# ===========================================================================
# Tests for _run_case
# ===========================================================================


@pytest.mark.django_db
class TestRunCaseExact:
    def test_exact_name_match_passes(self, tomato) -> None:
        from apps.search.management.commands.run_golden_set import _run_case

        case = {
            "id": "T01",
            "description": "exact name",
            "inputs": ["Tomato"],
            "expect": {
                "matched_slugs": ["tomato"],
                "is_empty": False,
            },
        }
        result = _run_case(case)
        assert result["passed"], result["failures"]

    def test_swahili_name_match_passes(self, tomato) -> None:
        from apps.search.management.commands.run_golden_set import _run_case

        case = {
            "id": "T02",
            "description": "swahili name",
            "inputs": ["Nyanya"],
            "expect": {
                "matched_slugs": ["tomato"],
                "is_empty": False,
            },
        }
        result = _run_case(case)
        assert result["passed"], result["failures"]

    def test_alias_created_and_rolled_back(self, tomato, db) -> None:
        """aliases_required are created for the case then rolled back."""
        from apps.search.management.commands.run_golden_set import _run_case

        assert not IngredientAlias.objects.filter(alias="testalias99").exists()

        case = {
            "id": "T03",
            "description": "alias rollback",
            "inputs": ["testalias99"],
            "aliases_required": [
                {
                    "ingredient_slug": "tomato",
                    "alias": "testalias99",
                    "normalized_alias": "testalias",
                    "language": "en",
                }
            ],
            "expect": {"is_empty": False},
        }
        _run_case(case)

        # Alias must have been rolled back after the case
        assert not IngredientAlias.objects.filter(alias="testalias99").exists()

    def test_unmatched_token_fails_if_expected_matched(self, db) -> None:
        from apps.search.management.commands.run_golden_set import _run_case

        case = {
            "id": "T04",
            "description": "expect matched but unmatched",
            "inputs": ["xyzzy_nope"],
            "expect": {"matched_slugs": ["tomato"]},
        }
        result = _run_case(case)
        assert not result["passed"]
        assert any("matched_slugs" in f for f in result["failures"])


@pytest.mark.django_db
class TestRunCaseEmpty:
    def test_empty_input_is_empty(self, db) -> None:
        from apps.search.management.commands.run_golden_set import _run_case

        case = {
            "id": "T05",
            "description": "empty input",
            "inputs": [],
            "expect": {"is_empty": True, "has_ambiguity": False},
        }
        result = _run_case(case)
        assert result["passed"], result["failures"]

    def test_is_empty_false_when_matched(self, tomato) -> None:
        from apps.search.management.commands.run_golden_set import _run_case

        case = {
            "id": "T06",
            "description": "not empty",
            "inputs": ["Tomato"],
            "expect": {"is_empty": False},
        }
        result = _run_case(case)
        assert result["passed"], result["failures"]


@pytest.mark.django_db
class TestRunCaseStaples:
    def test_staples_added_to_pool(self, tomato, salt, water) -> None:
        from apps.search.management.commands.run_golden_set import _run_case
        from apps.search.staples import invalidate_staple_cache

        invalidate_staple_cache()

        case = {
            "id": "T07",
            "description": "staples added",
            "inputs": ["Tomato"],
            "expect": {"staples_added_min": 1},
        }
        result = _run_case(case)
        assert result["passed"], result["failures"]

    def test_excluded_staple_not_in_pool(self, tomato, salt, water) -> None:
        from apps.search.management.commands.run_golden_set import _run_case
        from apps.search.staples import invalidate_staple_cache

        invalidate_staple_cache()

        case = {
            "id": "T08",
            "description": "excluded staple absent",
            "inputs": ["Tomato"],
            "excluded_slugs": ["salt"],
            "expect": {"pool_excludes_slugs": ["salt"]},
        }
        result = _run_case(case)
        assert result["passed"], result["failures"]


@pytest.mark.django_db
class TestRunCasePoolCompleteness:
    def test_pool_covers_ugali_non_staple_required(self, ugali, maize_flour, salt, water) -> None:
        from apps.search.management.commands.run_golden_set import _run_case
        from apps.search.staples import invalidate_staple_cache

        invalidate_staple_cache()
        ugali.refresh_from_db()

        case = {
            "id": "T09",
            "description": "pool covers ugali",
            "inputs": ["maize flour"],
            "dish_slug": "ugali",
            "expect": {
                "matched_slugs": ["maize-flour"],
                "pool_covers_dish_non_staple_required": True,
            },
        }
        result = _run_case(case)
        assert result["passed"], result["failures"]

    def test_missing_dish_reports_failure(self, tomato) -> None:
        from apps.search.management.commands.run_golden_set import _run_case

        case = {
            "id": "T10",
            "description": "dish not found",
            "inputs": ["Tomato"],
            "dish_slug": "no-such-dish",
            "expect": {"pool_covers_dish_non_staple_required": True},
        }
        result = _run_case(case)
        assert not result["passed"]
        assert any(
            "not in DB" in f or "DoesNotExist" in f.lower() or "no-such-dish" in f
            for f in result["failures"]
        )


@pytest.mark.django_db
class TestRunCaseMethodAndConfidence:
    def test_method_exact_name(self, tomato) -> None:
        from apps.search.management.commands.run_golden_set import _run_case

        case = {
            "id": "T11",
            "description": "method exact_name",
            "inputs": ["Tomato"],
            "expect": {"method_for_input": {"Tomato": "exact_name"}},
        }
        result = _run_case(case)
        assert result["passed"], result["failures"]

    def test_method_mismatch_fails(self, tomato) -> None:
        from apps.search.management.commands.run_golden_set import _run_case

        case = {
            "id": "T12",
            "description": "wrong method assertion",
            "inputs": ["Tomato"],
            "expect": {"method_for_input": {"Tomato": "fuzzy"}},
        }
        result = _run_case(case)
        assert not result["passed"]

    def test_confidence_exact_name(self, tomato) -> None:
        from apps.search.management.commands.run_golden_set import _run_case

        case = {
            "id": "T13",
            "description": "confidence 1.0",
            "inputs": ["Tomato"],
            "expect": {"confidence_min_for_input": {"Tomato": 1.0}},
        }
        result = _run_case(case)
        assert result["passed"], result["failures"]

    def test_confidence_too_high_fails(self, tomato) -> None:
        from apps.search.management.commands.run_golden_set import _run_case

        case = {
            "id": "T14",
            "description": "confidence above 1.0 — impossible",
            "inputs": ["Tomato"],
            "expect": {"confidence_min_for_input": {"Tomato": 1.1}},
        }
        result = _run_case(case)
        assert not result["passed"]


@pytest.mark.django_db
class TestRunCaseResultsCount:
    def test_results_count(self, tomato, onion) -> None:
        from apps.search.management.commands.run_golden_set import _run_case

        case = {
            "id": "T15",
            "description": "results count",
            "inputs": ["Tomato", "Onion", "xyzzy_unk"],
            "expect": {"results_count": 3},
        }
        result = _run_case(case)
        assert result["passed"], result["failures"]

    def test_deduplication(self, tomato) -> None:
        from apps.search.management.commands.run_golden_set import _run_case

        case = {
            "id": "T16",
            "description": "dedup — one match from three identical inputs",
            "inputs": ["Tomato", "tomato", "TOMATO"],
            "expect": {"matched_count": 1},
        }
        result = _run_case(case)
        assert result["passed"], result["failures"]


# ===========================================================================
# Management command integration tests
# ===========================================================================


@pytest.mark.django_db
class TestRunGoldenSetCommand:
    def _write_fixture(self, tmp_path: Path, cases: list[dict]) -> Path:
        fixture = tmp_path / "test_golden.json"
        fixture.write_text(json.dumps({"version": "0", "description": "test", "cases": cases}))
        return fixture

    def test_command_passes_with_all_passing_cases(self, tmp_path, tomato) -> None:
        fixture = self._write_fixture(
            tmp_path,
            [
                {
                    "id": "X01",
                    "description": "should pass",
                    "inputs": ["Tomato"],
                    "expect": {"matched_slugs": ["tomato"], "is_empty": False},
                }
            ],
        )
        out = StringIO()
        # Should not raise (exit 0)
        call_command("run_golden_set", fixture=str(fixture), stdout=out)
        assert "1/1" in out.getvalue()

    def test_command_exits_1_on_failure(self, tmp_path, db) -> None:
        fixture = self._write_fixture(
            tmp_path,
            [
                {
                    "id": "X02",
                    "description": "should fail",
                    "inputs": ["xyzzy_nope"],
                    "expect": {"matched_slugs": ["tomato"]},
                }
            ],
        )
        out = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command("run_golden_set", fixture=str(fixture), stdout=out)
        assert exc_info.value.code == 1

    def test_command_json_output(self, tmp_path, tomato) -> None:
        fixture = self._write_fixture(
            tmp_path,
            [
                {
                    "id": "X03",
                    "description": "json output",
                    "inputs": ["Tomato"],
                    "expect": {"is_empty": False},
                }
            ],
        )
        out = StringIO()
        call_command("run_golden_set", fixture=str(fixture), json_output=True, stdout=out)
        data = json.loads(out.getvalue())
        assert data["passed"] == 1
        assert data["failed"] == 0
        assert len(data["cases"]) == 1

    def test_command_fail_fast_stops_early(self, tmp_path, tomato, db) -> None:
        fixture = self._write_fixture(
            tmp_path,
            [
                {
                    "id": "X04",
                    "description": "first fails",
                    "inputs": ["xyzzy"],
                    "expect": {"matched_slugs": ["tomato"]},
                },
                {
                    "id": "X05",
                    "description": "second would pass",
                    "inputs": ["Tomato"],
                    "expect": {"matched_slugs": ["tomato"]},
                },
            ],
        )
        out = StringIO()
        with pytest.raises(SystemExit):
            call_command("run_golden_set", fixture=str(fixture), fail_fast=True, stdout=out)
        # Only 1 result should be reported (stopped after first failure)
        output = out.getvalue()
        assert "X04" in output
        assert "X05" not in output

    def test_command_missing_fixture_exits_1(self, tmp_path) -> None:
        err = StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command(
                "run_golden_set",
                fixture=str(tmp_path / "nonexistent.json"),
                stderr=err,
            )
        assert exc_info.value.code == 1
