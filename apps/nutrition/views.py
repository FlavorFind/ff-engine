"""
E39 — Nutrition endpoint.

GET /v1/dishes/{slug}/nutrition/

Sums NutritionFact values across all DishIngredient rows for the dish,
scaled by (quantity / 100) so the result is per-serving.

When a DishIngredient has no quantity, a default of 100 g is assumed
and is_estimate is set to True in the response.

Response shape:
  {
    "dish":        "ugali",
    "servings":    4,
    "per_serving": {
      "kcal":      ...,
      "protein_g": ...,
      "carbs_g":   ...,
      "fat_g":     ...,
      "fibre_g":   ...,
      "sodium_mg": ...
    },
    "is_estimate": true | false,
    "coverage":    0.8           # fraction of ingredients with nutrition data
  }
"""

from __future__ import annotations

from decimal import Decimal

from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.dishes.models import Dish, DishIngredient

# Default gram weight assumed when DishIngredient.quantity is None
_DEFAULT_GRAMS = Decimal("100")


@api_view(["GET"])
@permission_classes([AllowAny])
def dish_nutrition(request: Request, slug: str) -> Response:
    """
    GET /v1/dishes/{slug}/nutrition/

    Returns per-serving nutrition totals for a dish.
    """
    try:
        dish = Dish.objects.get(slug=slug)
    except Dish.DoesNotExist:
        return Response({"error": "Dish not found."}, status=http_status.HTTP_404_NOT_FOUND)

    dish_ingredients = DishIngredient.objects.filter(dish=dish).select_related(
        "ingredient", "ingredient__nutrition", "unit"
    )

    totals = {
        "kcal": Decimal("0"),
        "protein_g": Decimal("0"),
        "carbs_g": Decimal("0"),
        "fat_g": Decimal("0"),
        "fibre_g": Decimal("0"),
        "sodium_mg": Decimal("0"),
    }

    is_estimate = False
    total_ingredients = 0
    covered = 0

    for di in dish_ingredients:
        total_ingredients += 1

        try:
            nf = di.ingredient.nutrition
        except AttributeError:
            # No NutritionFact for this ingredient — skip, mark estimate
            is_estimate = True
            continue

        covered += 1

        # Convert quantity to grams.
        # If no quantity or no unit, assume _DEFAULT_GRAMS.
        if di.quantity is not None and di.unit is not None:
            # unit.to_base_factor converts to grams (mass) or ml (volume).
            # For nutrition we treat volume units as ml ≈ g (density ≈ 1).
            grams = di.quantity * di.unit.to_base_factor
        else:
            grams = _DEFAULT_GRAMS
            is_estimate = True

        scale = grams / Decimal("100")

        totals["kcal"] += nf.kcal * scale
        totals["protein_g"] += nf.protein_g * scale
        totals["carbs_g"] += nf.carbs_g * scale
        totals["fat_g"] += nf.fat_g * scale
        totals["fibre_g"] += nf.fibre_g * scale
        totals["sodium_mg"] += nf.sodium_mg * scale

    # Divide by servings for per-serving values
    servings = dish.servings or 1
    per_serving = {k: round(v / servings, 2) for k, v in totals.items()}

    coverage = round(covered / total_ingredients, 2) if total_ingredients else 0.0

    return Response(
        {
            "dish": dish.slug,
            "servings": servings,
            "per_serving": per_serving,
            "is_estimate": is_estimate,
            "coverage": coverage,
        }
    )
