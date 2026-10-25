"""
E31/E32 — Dietary signals.

E31: Auto-derive dietary tags whenever a DishIngredient is saved or deleted.
     This keeps dietary tags in sync automatically — same pattern as E19
     which rebuilds search arrays on DishIngredient changes.

E32: Auto-log every manual DishDietaryTag override to ChangeLog.
     Ensures the audit trail is captured regardless of how the override
     was created (admin, API, management command).
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


# ── E31: Rebuild dietary tags when dish ingredients change ────────────────────


def _rederive(dish_ingredient) -> None:
    """Re-run dietary tag derivation for the parent dish."""
    from apps.dietary.services import apply_derived_tags

    dish = dish_ingredient.dish
    try:
        dish.refresh_from_db()
        apply_derived_tags(dish)
        logger.debug("Re-derived dietary tags for dish '%s'", dish.slug)
    except Exception as exc:
        # Never let a signal crash a save
        logger.error(
            "Failed to re-derive dietary tags for dish '%s': %s",
            getattr(dish, "slug", "?"),
            exc,
        )


@receiver(post_save, sender="dishes.DishIngredient")
def on_dish_ingredient_save_dietary(sender, instance, **kwargs):
    """Re-derive dietary tags after a DishIngredient is created or updated."""
    _rederive(instance)


@receiver(post_delete, sender="dishes.DishIngredient")
def on_dish_ingredient_delete_dietary(sender, instance, **kwargs):
    """Re-derive dietary tags after a DishIngredient is removed."""
    _rederive(instance)


# ── E32: Log manual DishDietaryTag overrides to ChangeLog ────────────────────


@receiver(post_save, sender="dietary.DishDietaryTag")
def on_dish_dietary_tag_save(sender, instance, created, **kwargs):
    """
    Log every manual override to ChangeLog.
    Derived tags are not logged — only source=manual.
    """
    from apps.dietary.models import DishDietaryTag

    if instance.source != DishDietaryTag.Source.MANUAL:
        return

    try:
        from apps.curation.models import ChangeLog

        ChangeLog.objects.create(
            object_type="DishDietaryTag",
            object_id=str(instance.pk),
            action="create" if created else "update",
            diff={
                "tag": instance.tag.slug,
                "dish": instance.dish.slug,
                "source": "manual",
                "reason": instance.reason,
                "set_by": str(instance.set_by_id) if instance.set_by_id else None,
            },
            reason=instance.reason,
        )
        logger.debug(
            "Logged manual dietary override: dish=%s tag=%s",
            instance.dish.slug,
            instance.tag.slug,
        )
    except Exception as exc:
        logger.error("Failed to log dietary override to ChangeLog: %s", exc)
