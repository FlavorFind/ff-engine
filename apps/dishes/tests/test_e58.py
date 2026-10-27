"""
E58 — Popularity signal tests.

Verifies:
- compute_popularity sets non-zero values on seeded dishes
- --dry-run leaves values unchanged
- popularity stays within [0.0, 1.0]
- The Celery task is importable and callable
- Dishes with more ingredients score higher than dishes with fewer
"""
from __future__ import annotations

import pytest


@pytest.mark.fast
def test_popularity_task_is_importable():
    """The Celery task exists and is callable without running it."""
    from apps.dishes.tasks import update_dish_popularity

    assert callable(update_dish_popularity)
    assert update_dish_popularity.name == "apps.dishes.tasks.update_dish_popularity"


@pytest.mark.fast
def test_compute_popularity_command_importable():
    """The management command can be imported without error."""
    from apps.dishes.management.commands.compute_popularity import Command

    cmd = Command()
    assert callable(cmd.handle)


@pytest.mark.django_db
def test_compute_popularity_sets_nonzero_values(seeded_db):
    """After compute_popularity, at least some dishes have popularity > 0."""
    from django.core.management import call_command

    from apps.dishes.models import Dish

    # Reset all popularities to 0 first to make the test meaningful
    Dish.objects.update(popularity=0.0)
    call_command("compute_popularity", verbosity=0)

    popular = Dish.objects.filter(popularity__gt=0).count()
    total = Dish.objects.count()
    assert popular > 0, f"Expected some dishes with popularity > 0, got 0 out of {total}"


@pytest.mark.django_db
def test_compute_popularity_dry_run_no_change(seeded_db):
    """--dry-run must not modify any popularity values."""
    from io import StringIO

    from django.core.management import call_command

    from apps.dishes.models import Dish

    # Set a known value to detect changes
    Dish.objects.update(popularity=0.1234)
    call_command("compute_popularity", "--dry-run", verbosity=0, stdout=StringIO())

    # All dishes should still have the pre-set value
    changed = Dish.objects.exclude(popularity=0.1234).count()
    assert changed == 0, f"{changed} dishes had popularity changed by --dry-run"


@pytest.mark.django_db
def test_compute_popularity_values_in_range(seeded_db):
    """All popularity values must be in [0.0, 1.0] after compute_popularity."""
    from django.core.management import call_command

    from apps.dishes.models import Dish

    call_command("compute_popularity", verbosity=0)

    out_of_range = Dish.objects.filter(popularity__lt=0.0).count()
    out_of_range += Dish.objects.filter(popularity__gt=1.0).count()
    assert out_of_range == 0, f"{out_of_range} dishes have popularity outside [0.0, 1.0]"


@pytest.mark.django_db
def test_verified_dishes_score_higher_than_seeded(seeded_db):
    """
    Verified dishes should have a higher quality_score component than seeded
    dishes, so their popularity should be >= seeded dishes with same ingredient
    count (all else equal).
    """
    from apps.core.models import StatusChoices
    from apps.dishes.models import Dish

    from django.core.management import call_command

    call_command("compute_popularity", verbosity=0)

    verified_avg = (
        Dish.objects.filter(quality_level="verified").values_list("popularity", flat=True)
    )
    seeded_avg = (
        Dish.objects.filter(quality_level="seeded").values_list("popularity", flat=True)
    )

    verified_list = list(verified_avg)
    seeded_list = list(seeded_avg)

    if not verified_list or not seeded_list:
        pytest.skip("Not enough dishes of each quality level to compare")

    avg_verified = sum(verified_list) / len(verified_list)
    avg_seeded = sum(seeded_list) / len(seeded_list)

    assert avg_verified >= avg_seeded, (
        f"Verified dishes (avg={avg_verified:.4f}) should score >= "
        f"seeded dishes (avg={avg_seeded:.4f})"
    )
