"""
E39 — Nutrition endpoint tests.

Tests:
  - GET /v1/dishes/{slug}/nutrition/ returns 200 with correct shape
  - Per-serving sums are correct when all ingredients have nutrition data
  - is_estimate=True when a DishIngredient has no quantity/unit
  - is_estimate=True when an ingredient has no NutritionFact row
  - coverage reflects fraction of ingredients with data
  - Unknown slug returns 404
  - Missing data handled gracefully (partial coverage, no crash)
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.dishes.models import Dish, DishIngredient
from apps.ingredients.models import Ingredient, IngredientCategory, Unit
from apps.nutrition.models import NutritionFact

# ── fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def category(db):
    return IngredientCategory.objects.get_or_create(
        slug="test-grains-e39",
        defaults={"name_en": "Test Grains E39"},
    )[0]


@pytest.fixture
def unit_g(db):
    return Unit.objects.get_or_create(
        code="g_e39",
        defaults={
            "name": "Grams (test)",
            "kind": Unit.Kind.MASS,
            "to_base_factor": Decimal("1.0"),
        },
    )[0]


@pytest.fixture
def ingredient_a(category):
    return Ingredient.objects.get_or_create(
        slug="test-maize-flour-e39",
        defaults={
            "name_en": "Test Maize Flour E39",
            "category": category,
        },
    )[0]


@pytest.fixture
def ingredient_b(category):
    return Ingredient.objects.get_or_create(
        slug="test-water-e39",
        defaults={
            "name_en": "Test Water E39",
            "category": category,
            "is_staple": True,
        },
    )[0]


@pytest.fixture
def nutrition_a(ingredient_a):
    return NutritionFact.objects.get_or_create(
        ingredient=ingredient_a,
        defaults={
            "kcal": Decimal("362"),
            "protein_g": Decimal("8.10"),
            "carbs_g": Decimal("76.80"),
            "fat_g": Decimal("3.60"),
            "fibre_g": Decimal("7.30"),
            "sodium_mg": Decimal("2.00"),
            "source": "USDA FoodData Central",
            "confidence": NutritionFact.Confidence.HIGH,
        },
    )[0]


@pytest.fixture
def dish(db):
    # Use a unique slug that won't clash with seeded data
    return Dish.objects.get_or_create(
        slug="test-ugali-e39",
        defaults={
            "name_en": "Test Ugali E39",
            "servings": 4,
        },
    )[0]


@pytest.fixture
def di_with_quantity(dish, ingredient_a, unit_g, nutrition_a):
    """DishIngredient with 400 g of maize flour → 400/100 * values / 4 servings."""
    return DishIngredient.objects.get_or_create(
        dish=dish,
        ingredient=ingredient_a,
        defaults={
            "role": DishIngredient.Role.PRIMARY,
            "quantity": Decimal("400"),
            "unit": unit_g,
        },
    )[0]


@pytest.fixture
def anon_client():
    return APIClient()


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDishNutritionEndpoint:
    def test_returns_200(self, anon_client, dish, di_with_quantity):
        resp = anon_client.get("/v1/dishes/test-ugali-e39/nutrition/")
        assert resp.status_code == 200

    def test_response_shape(self, anon_client, dish, di_with_quantity):
        resp = anon_client.get("/v1/dishes/test-ugali-e39/nutrition/")
        data = resp.json()
        assert data["dish"] == "test-ugali-e39"
        assert data["servings"] == 4
        assert "per_serving" in data
        assert "is_estimate" in data
        assert "coverage" in data
        for key in ("kcal", "protein_g", "carbs_g", "fat_g", "fibre_g", "sodium_mg"):
            assert key in data["per_serving"], f"missing key: {key}"

    def test_per_serving_sum_correct(self, anon_client, dish, di_with_quantity):
        """
        400 g maize flour → scale = 4.0
        kcal/serving = 362 * 4 / 4 servings = 362
        """
        resp = anon_client.get("/v1/dishes/test-ugali-e39/nutrition/")
        data = resp.json()
        assert float(data["per_serving"]["kcal"]) == pytest.approx(362.0, rel=0.01)

    def test_is_estimate_false_when_all_quantities_known(self, anon_client, dish, di_with_quantity):
        resp = anon_client.get("/v1/dishes/test-ugali-e39/nutrition/")
        assert resp.json()["is_estimate"] is False

    def test_is_estimate_true_when_no_quantity(self, anon_client, dish, ingredient_a, nutrition_a):
        """DishIngredient without quantity triggers is_estimate=True."""
        DishIngredient.objects.get_or_create(
            dish=dish,
            ingredient=ingredient_a,
            defaults={
                "role": DishIngredient.Role.PRIMARY,
                "quantity": None,
                "unit": None,
            },
        )
        resp = anon_client.get("/v1/dishes/test-ugali-e39/nutrition/")
        assert resp.json()["is_estimate"] is True

    def test_is_estimate_true_when_missing_nutrition(self, anon_client, dish, ingredient_b, unit_g):
        """ingredient_b has no NutritionFact — is_estimate should be True."""
        DishIngredient.objects.get_or_create(
            dish=dish,
            ingredient=ingredient_b,
            defaults={
                "role": DishIngredient.Role.REQUIRED,
                "quantity": Decimal("200"),
                "unit": unit_g,
            },
        )
        resp = anon_client.get("/v1/dishes/test-ugali-e39/nutrition/")
        assert resp.json()["is_estimate"] is True

    def test_coverage_with_partial_data(
        self, anon_client, dish, di_with_quantity, ingredient_b, unit_g
    ):
        """2 ingredients, 1 has nutrition → coverage = 0.5."""
        DishIngredient.objects.get_or_create(
            dish=dish,
            ingredient=ingredient_b,
            defaults={
                "role": DishIngredient.Role.REQUIRED,
                "quantity": Decimal("200"),
                "unit": unit_g,
            },
        )
        resp = anon_client.get("/v1/dishes/test-ugali-e39/nutrition/")
        assert resp.json()["coverage"] == pytest.approx(0.5)

    def test_unknown_slug_returns_404(self, anon_client, db):
        resp = anon_client.get("/v1/dishes/nonexistent-dish-xyz/nutrition/")
        assert resp.status_code == 404

    def test_dish_with_no_ingredients_returns_zeros(self, anon_client, dish):
        resp = anon_client.get("/v1/dishes/test-ugali-e39/nutrition/")
        data = resp.json()
        assert data["coverage"] == 0.0
        for v in data["per_serving"].values():
            assert float(v) == 0.0
