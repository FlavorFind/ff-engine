"""
Root conftest.py — pytest-django configuration and shared fixtures.

DJANGO_SETTINGS_MODULE is also declared in pyproject.toml [tool.pytest.ini_options]
so pytest picks it up automatically.

Performance
-----------
seed_all inserts 638 ingredients + 219 dishes + 733 links + 750 steps.
Running it per-test-class takes 10+ minutes.
The `seeded_db` fixture is SESSION-scoped: it runs seed_all once for the
entire pytest session. Signals that fire on every DishIngredient insert are
disconnected during seeding and reconnected afterwards.
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
        from apps.search.signals import on_dish_ingredient_save, on_dish_ingredient_delete
        post_save.disconnect(on_dish_ingredient_save, sender=DishIngredient)
        post_delete.disconnect(on_dish_ingredient_delete, sender=DishIngredient)
    except Exception:
        pass

    try:
        from apps.dietary.signals import on_dish_ingredient_save_dietary, on_dish_ingredient_delete_dietary
        post_save.disconnect(on_dish_ingredient_save_dietary, sender=DishIngredient)
        post_delete.disconnect(on_dish_ingredient_delete_dietary, sender=DishIngredient)
    except Exception:
        pass


def _reconnect_signals():
    from django.db.models.signals import post_delete, post_save
    from apps.dishes.models import DishIngredient

    try:
        from apps.search.signals import on_dish_ingredient_save, on_dish_ingredient_delete
        post_save.connect(on_dish_ingredient_save, sender=DishIngredient)
        post_delete.connect(on_dish_ingredient_delete, sender=DishIngredient)
    except Exception:
        pass

    try:
        from apps.dietary.signals import on_dish_ingredient_save_dietary, on_dish_ingredient_delete_dietary
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
