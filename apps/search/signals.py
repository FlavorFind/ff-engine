"""
E19 — Search array signals.

Wires post_save and post_delete signals on DishIngredient so that the
denormalised search arrays on Dish (required_ids, optional_ids,
primary_ids, all_ids) are rebuilt automatically whenever an ingredient
link is added, changed or removed.

The GIN indexes on those arrays already exist (created in
dishes/0001_initial.py).  This module adds the live signal so the arrays
stay correct after every admin save or import.

Architecture section 5:
  "Denormalised search arrays on dishes … rebuilt automatically
   when a dish changes."

Blueprint E19 exit check:
  "Arrays rebuild automatically on every dish change (tested)."
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _rebuild(dish_ingredient) -> None:
    """Refresh the parent dish's search arrays from the current DB state."""
    dish = dish_ingredient.dish
    try:
        dish.refresh_from_db()
        dish.rebuild_search_arrays()
        logger.debug("Rebuilt search arrays for dish '%s'", dish.slug)
    except Exception as exc:  # pragma: no cover
        # Never let a signal crash a save — log and continue.
        logger.error(
            "Failed to rebuild search arrays for dish '%s': %s",
            getattr(dish, "slug", "?"),
            exc,
        )


@receiver(post_save, sender="dishes.DishIngredient")
def on_dish_ingredient_save(sender, instance, **kwargs):
    """Rebuild search arrays after a DishIngredient is created or updated."""
    _rebuild(instance)


@receiver(post_delete, sender="dishes.DishIngredient")
def on_dish_ingredient_delete(sender, instance, **kwargs):
    """Rebuild search arrays after a DishIngredient is removed."""
    _rebuild(instance)
