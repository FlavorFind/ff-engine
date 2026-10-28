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
        """878 unique ingredients are seeded from the CSV (E44: grown to 878)."""
        from apps.ingredients.models import Ingredient

        call_command("seed_all", verbosity=0)
        assert Ingredient.objects.count() == 878

    def test_ingredient_categories_created(self):
        """At least one IngredientCategory is created per unique category name."""
        from apps.ingredients.models import IngredientCategory

        call_command("seed_all", verbosity=0)
        assert IngredientCategory.objects.count() >= 1

    def test_dishes_created(self):
        """300 dishes are seeded (E45: grown to 300)."""
        from apps.dishes.models import Dish

        call_command("seed_all", verbosity=0)
        assert Dish.objects.count() == 300

    def test_dish_ingredients_created(self):
        """At least 1250 DishIngredient rows are created (csv has 1282)."""
        from apps.dishes.models import DishIngredient

        call_command("seed_all", verbosity=0)
        assert DishIngredient.objects.count() >= 1250

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
        assert dish.status == "reviewed"
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

    def test_swahili_alias_nyanya_seeded(self):
        """seed_all must create the 'nyanya' alias pointing to the tomato ingredient."""
        from apps.ingredients.models import Ingredient, IngredientAlias

        call_command("seed_all", verbosity=0)
        tomato = Ingredient.objects.get(slug="tomato")
        alias = IngredientAlias.objects.filter(normalized_alias="nyanya", language="sw").first()
        assert alias is not None, "nyanya alias not found after seed_all"
        assert alias.ingredient == tomato, f"nyanya points to {alias.ingredient} not tomato"

    def test_seed_all_aliases_idempotent(self):
        """Running seed_all twice must not duplicate aliases."""
        from apps.ingredients.models import IngredientAlias

        call_command("seed_all", verbosity=0)
        count_after_first = IngredientAlias.objects.count()
        call_command("seed_all", verbosity=0)
        count_after_second = IngredientAlias.objects.count()
        assert (
            count_after_first == count_after_second
        ), f"Alias count changed from {count_after_first} to {count_after_second} on second run"

    def test_dietary_tags_derived_after_seed(self):
        """seed_all must derive at least one dietary tag for seeded dishes."""
        from apps.dietary.models import DishDietaryTag

        call_command("seed_all", verbosity=0)
        count = DishDietaryTag.objects.filter(source="derived").count()
        assert count > 0, "No derived dietary tags found after seed_all"

    def test_dish_regions_seeded(self):
        """seed_all must create DishRegion links so region filter works."""
        from apps.regions.models import DishRegion

        call_command("seed_all", verbosity=0)
        count = DishRegion.objects.count()
        assert count >= 300, f"Expected ≥300 dish-region links, got {count}"

    def test_dish_regions_idempotent(self):
        """Running seed_all twice must not duplicate dish-region links."""
        from apps.regions.models import DishRegion

        call_command("seed_all", verbosity=0)
        count1 = DishRegion.objects.count()
        call_command("seed_all", verbosity=0)
        count2 = DishRegion.objects.count()
        assert count1 == count2, f"DishRegion count changed: {count1} → {count2}"
