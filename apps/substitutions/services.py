"""
E29 — Substitution service.

Business logic for substitution retrieval.
"""

from __future__ import annotations

from django.db import models

from apps.substitutions.models import Substitution


def get_substitutions_for_dish(
    dish_id: str,
    *,
    limit: int = 50,
) -> list[Substitution]:
    """
    Return all substitutions relevant to a dish.

    Includes:
    - General substitutions for any ingredient the dish uses.
    - Dish-specific substitutions (context_dish == dish).

    Ordered by quality (great → ok → emergency).
    """
    from apps.dishes.models import DishIngredient

    ingredient_ids = list(
        DishIngredient.objects.filter(dish_id=dish_id).values_list("ingredient_id", flat=True)
    )

    qs = (
        Substitution.objects.filter(ingredient_id__in=ingredient_ids)
        .filter(models.Q(context_dish__isnull=True) | models.Q(context_dish_id=dish_id))
        .select_related("ingredient", "substitute", "context_dish")
        .order_by("quality", "ingredient__name_en")
    )
    return list(qs[:limit])


def get_substitutions_for_ingredient(
    ingredient_id: str,
    *,
    context_dish_id: str | None = None,
    limit: int = 10,
) -> list[Substitution]:
    """
    Return substitutions for a specific ingredient.

    If context_dish_id is given, dish-specific substitutions are returned first.
    """
    qs = Substitution.objects.filter(ingredient_id=ingredient_id).select_related(
        "substitute", "context_dish"
    )
    if context_dish_id:
        qs = qs.filter(
            models.Q(context_dish_id=context_dish_id) | models.Q(context_dish__isnull=True)
        ).order_by(
            models.Case(
                models.When(context_dish_id=context_dish_id, then=0),
                default=1,
            ),
            "quality",
        )
    else:
        qs = qs.filter(context_dish__isnull=True).order_by("quality")
    return list(qs[:limit])
