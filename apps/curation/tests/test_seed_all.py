"""
Tests for the seed_all management command.

Verifies:
  - seed_all runs without errors on a clean database
  - Ingredients and categories are created with correct counts
  - Dishes are created with correct counts
  - DishIngredient links are created
  - DishSteps are created
  - rebuild_search_arrays populates all_ids for seeded dishes
  - Re-running seed_all is idempotent (no duplicates)
  - --dry-run makes no DB changes
"""

import pytest
from django.core.management import call_command


@pytest.mark.django_db(transaction=True)
class TestSeedAll:
    def test_seed_runs_without_error(self):
        """seed_all completes without raising."""
        call_command("seed_all", verbosity=0)

    def test_ingredients_created(self):
        """638 unique ingredients are seeded from the CSV (E33: grown to 638)."""
        from apps.ingredients.models import Ingredient

        call_command("seed_all", verbosity=0)
        assert Ingredient.objects.count() == 638

    def test_ingredient_categories_created(self):
        """At least one IngredientCategory is created per unique category name."""
        from apps.ingredients.models import IngredientCategory

        call_command("seed_all", verbosity=0)
        assert IngredientCategory.objects.count() >= 1

    def test_dishes_created(self):
        """219 dishes are seeded (E33: grown to 219)."""
        from apps.dishes.models import Dish

        call_command("seed_all", verbosity=0)
        assert Dish.objects.count() == 219

    def test_dish_ingredients_created(self):
        """At least 700 DishIngredient rows are created (csv has 733)."""
        from apps.dishes.models import DishIngredient

        call_command("seed_all", verbosity=0)
        assert DishIngredient.objects.count() >= 700

    def test_dish_steps_created(self):
        """At least 700 DishStep rows are created (csv has 750)."""
        from apps.dishes.models import DishStep

        call_command("seed_all", verbosity=0)
        assert DishStep.objects.count() >= 700

    def test_search_arrays_populated(self):
        """Every dish that has ingredients should have at least one UUID in all_ids after seeding."""
        from apps.dishes.models import Dish

        call_command("seed_all", verbosity=0)
        # Only check dishes that actually have DishIngredient rows —
        # dishes in the CSV without matching ingredient links will have empty arrays.
        dishes_with_ingredients = Dish.objects.filter(dish_ingredients__isnull=False).distinct()
        empty = dishes_with_ingredients.filter(all_ids=[]).count()
        assert empty == 0, f"{empty} dishes with ingredients still have empty all_ids after seed"

    def test_idempotent(self):
        """Running seed_all twice produces the same counts."""
        from apps.dishes.models import Dish, DishIngredient, DishStep
        from apps.ingredients.models import Ingredient

        call_command("seed_all", verbosity=0)
        c1 = {
            "dishes": Dish.objects.count(),
            "ingredients": Ingredient.objects.count(),
            "di": DishIngredient.objects.count(),
            "steps": DishStep.objects.count(),
        }

        call_command("seed_all", verbosity=0)
        c2 = {
            "dishes": Dish.objects.count(),
            "ingredients": Ingredient.objects.count(),
            "di": DishIngredient.objects.count(),
            "steps": DishStep.objects.count(),
        }

        assert c1 == c2, f"Counts changed on second run: {c1} → {c2}"

    def test_dry_run_makes_no_changes(self):
        """--dry-run should not persist anything to the database."""
        from apps.dishes.models import Dish
        from apps.ingredients.models import Ingredient

        call_command("seed_all", dry_run=True, verbosity=0)
        assert Dish.objects.count() == 0
        assert Ingredient.objects.count() == 0

    def test_known_dish_exists(self):
        """Spot-check: 'Nyama Choma' is seeded correctly."""
        from apps.dishes.models import Dish

        call_command("seed_all", verbosity=0)
        dish = Dish.objects.get(slug="nyama-choma")
        assert dish.name_en == "Nyama Choma"
        assert dish.status == "draft"
        assert dish.quality_level == "seeded"
        assert dish.cook_min == 120  # PT2H

    def test_known_ingredient_is_staple(self):
        """Spot-check: 'salt' is flagged as a staple ingredient."""
        from apps.ingredients.models import Ingredient

        call_command("seed_all", verbosity=0)
        salt = Ingredient.objects.get(slug="salt")
        assert salt.is_staple is True

    def test_dish_has_steps(self):
        """Nyama Choma should have multiple steps."""
        from apps.dishes.models import Dish

        call_command("seed_all", verbosity=0)
        dish = Dish.objects.get(slug="nyama-choma")
        assert dish.steps.count() >= 3

    def test_dish_has_primary_ingredient(self):
        """Nyama Choma's first ingredient should have role=primary."""
        from apps.dishes.models import Dish, DishIngredient

        call_command("seed_all", verbosity=0)
        dish = Dish.objects.get(slug="nyama-choma")
        primary = DishIngredient.objects.filter(dish=dish, role=DishIngredient.Role.PRIMARY)
        assert primary.exists(), "No primary ingredient found for Nyama Choma"
