"""
Root conftest.py — pytest-django configuration and shared fixtures.

DJANGO_SETTINGS_MODULE is also declared in pyproject.toml [tool.pytest.ini_options]
so pytest picks it up automatically.

Performance
-----------
seed_all inserts 878 ingredients + 300 dishes + 1282 links + 750 steps.
Running it per-test-class takes 10+ minutes.
The `seeded_db` fixture is SESSION-scoped: it runs seed_all once for the
entire pytest session. Signals that fire on every DishIngredient insert are
disconnected during seeding and reconnected afterwards.

E59c adds a `mini_db` fixture: a tiny 5-ingredient / 2-dish dataset that
sets up in milliseconds, for tests that only need a working search pipeline
without the full 300-dish corpus.

Test marks
----------
@pytest.mark.fast  — no DB needed; should run in under 1 second
@pytest.mark.full  — requires seeded_db (300 dishes); expect 10-30 s for setup
"""

import os

import pytest
from django.core.management import call_command


def pytest_configure(config):
    """Called by pytest before collection begins."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
    os.environ.setdefault(
        "DATABASE_URL", "postgres://ff_engine:ff_engine_pass@localhost:5432/ff_engine_test"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Session-scoped seed fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def seeded_db(django_db_setup, django_db_blocker):
    """
    Seed the test database once per pytest session.

    Signals are disconnected during bulk seeding so that
    rebuild_search_arrays() and dietary re-derivation don't fire
    once per DishIngredient row (733 times).
    """
    with django_db_blocker.unblock():
        _disconnect_signals()
        try:
            call_command("seed_all", verbosity=0)
        finally:
            _reconnect_signals()


def _disconnect_signals():
    from django.db.models.signals import post_delete, post_save

    from apps.dishes.models import DishIngredient

    try:
        from apps.search.signals import on_dish_ingredient_delete, on_dish_ingredient_save

        post_save.disconnect(on_dish_ingredient_save, sender=DishIngredient)
        post_delete.disconnect(on_dish_ingredient_delete, sender=DishIngredient)
    except Exception:
        pass

    try:
        from apps.dietary.signals import (
            on_dish_ingredient_delete_dietary,
            on_dish_ingredient_save_dietary,
        )

        post_save.disconnect(on_dish_ingredient_save_dietary, sender=DishIngredient)
        post_delete.disconnect(on_dish_ingredient_delete_dietary, sender=DishIngredient)
    except Exception:
        pass


def _reconnect_signals():
    from django.db.models.signals import post_delete, post_save

    from apps.dishes.models import DishIngredient

    try:
        from apps.search.signals import on_dish_ingredient_delete, on_dish_ingredient_save

        post_save.connect(on_dish_ingredient_save, sender=DishIngredient)
        post_delete.connect(on_dish_ingredient_delete, sender=DishIngredient)
    except Exception:
        pass

    try:
        from apps.dietary.signals import (
            on_dish_ingredient_delete_dietary,
            on_dish_ingredient_save_dietary,
        )

        post_save.connect(on_dish_ingredient_save_dietary, sender=DishIngredient)
        post_delete.connect(on_dish_ingredient_delete_dietary, sender=DishIngredient)
    except Exception:
        pass

    # Rebuild search arrays once after all inserts
    try:
        from apps.dishes.models import Dish

        for dish in Dish.objects.prefetch_related("dish_ingredients__ingredient"):
            dish.rebuild_search_arrays()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# E59c — Mini dataset fixture
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def mini_db(django_db_setup, django_db_blocker):
    """
    A minimal dataset for tests that need some DB data but not all 300 dishes.

    Creates:
    - 5 ingredients: tomato, onion, maize-flour, water (staple), salt (staple)
    - 2 dishes: kachumbari-mini (requires tomato + onion), ugali-mini (requires maize-flour)
    - Correct GIN search arrays on both dishes

    Sets up in milliseconds vs the 30+ seconds for seeded_db.
    Use this fixture for tests that only need to verify pipeline / API structure.

    Usage::

        def test_something(mini_db):
            from apps.dishes.models import Dish
            assert Dish.objects.filter(slug='ugali-mini').exists()
    """
    with django_db_blocker.unblock():
        _create_mini_dataset()


def _create_mini_dataset() -> None:
    """Create the mini dataset rows. Idempotent — safe to call multiple times."""
    from apps.core.models import StatusChoices
    from apps.dishes.models import Dish, DishIngredient
    from apps.ingredients.models import Ingredient, IngredientCategory
    from apps.search.staples import invalidate_staple_cache

    # ── Categories ────────────────────────────────────────────────────────────
    veg_cat, _ = IngredientCategory.objects.get_or_create(
        slug="_mini-vegetables", defaults={"name_en": "Vegetables (mini)"}
    )
    grain_cat, _ = IngredientCategory.objects.get_or_create(
        slug="_mini-grains", defaults={"name_en": "Grains (mini)"}
    )
    liquid_cat, _ = IngredientCategory.objects.get_or_create(
        slug="_mini-liquids", defaults={"name_en": "Liquids (mini)"}
    )
    spice_cat, _ = IngredientCategory.objects.get_or_create(
        slug="_mini-spices", defaults={"name_en": "Spices (mini)"}
    )

    # ── Ingredients ───────────────────────────────────────────────────────────
    tomato, _ = Ingredient.objects.get_or_create(
        slug="_mini-tomato",
        defaults={
            "name_en": "Tomato (mini)",
            "category": veg_cat,
            "kind": "primary",
            "status": StatusChoices.REVIEWED,
        },
    )
    onion, _ = Ingredient.objects.get_or_create(
        slug="_mini-onion",
        defaults={
            "name_en": "Onion (mini)",
            "category": veg_cat,
            "kind": "primary",
            "status": StatusChoices.REVIEWED,
        },
    )
    maize, _ = Ingredient.objects.get_or_create(
        slug="_mini-maize-flour",
        defaults={
            "name_en": "Maize Flour (mini)",
            "category": grain_cat,
            "kind": "primary",
            "status": StatusChoices.REVIEWED,
        },
    )
    water, _ = Ingredient.objects.get_or_create(
        slug="_mini-water",
        defaults={
            "name_en": "Water (mini)",
            "category": liquid_cat,
            "kind": "liquid",
            "is_staple": True,
            "status": StatusChoices.REVIEWED,
        },
    )
    salt, _ = Ingredient.objects.get_or_create(
        slug="_mini-salt",
        defaults={
            "name_en": "Salt (mini)",
            "category": spice_cat,
            "kind": "seasoning",
            "is_staple": True,
            "status": StatusChoices.REVIEWED,
        },
    )

    invalidate_staple_cache()

    # ── Dishes ────────────────────────────────────────────────────────────────
    # Kachumbari: tomato=primary, onion=required → typing 'tomato,onion' → exact match
    kachumbari, created = Dish.objects.get_or_create(
        slug="_mini-kachumbari",
        defaults={
            "name_en": "Kachumbari (mini)",
            "status": StatusChoices.REVIEWED,
            "quality_level": "reviewed",
        },
    )
    if created:
        DishIngredient.objects.bulk_create(
            [
                DishIngredient(dish=kachumbari, ingredient=tomato, role="primary", position=1),
                DishIngredient(dish=kachumbari, ingredient=onion, role="required", position=2),
            ]
        )
        kachumbari.rebuild_search_arrays()

    # Ugali: maize-flour=required, water/salt=optional (both staples)
    # Typing 'maize flour' → exact match (water/salt are staples, never block)
    ugali, created = Dish.objects.get_or_create(
        slug="_mini-ugali",
        defaults={
            "name_en": "Ugali (mini)",
            "status": StatusChoices.REVIEWED,
            "quality_level": "reviewed",
        },
    )
    if created:
        DishIngredient.objects.bulk_create(
            [
                DishIngredient(dish=ugali, ingredient=maize, role="required", position=1),
                DishIngredient(dish=ugali, ingredient=water, role="optional", position=2),
                DishIngredient(dish=ugali, ingredient=salt, role="optional", position=3),
            ]
        )
        ugali.rebuild_search_arrays()
