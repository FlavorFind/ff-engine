"""
E25 — Search request and response serializers.

POST /v1/search/by-ingredients

Request fields (Architecture section 7):
  ingredients  list[str]   Words typed by the user (up to ~30)
  exclude      list[str]   Ingredient slugs/IDs to leave out
  mode         str         "strict" (default) or "explore"
  meal_type    str         Optional meal type filter
  course       str         Optional course filter
  lang         str         "en" (default) or "sw"
  limit        int         Max results per tier (default 20, max 50)

Response fields (per dish):
  slug, name_en, name_sw, score, tier, matched, missing, unused,
  staples_assumed, quality_level, score_breakdown
"""

from __future__ import annotations

import re

from rest_framework import serializers


class StrictStringField(serializers.CharField):
    """CharField that rejects non-string input (DRF's CharField coerces ints)."""

    def to_internal_value(self, data):
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


# ──────────────────────────────────────────────────────────────────────────────
# Request
# ──────────────────────────────────────────────────────────────────────────────


class SearchRequestSerializer(serializers.Serializer):
    ingredients = serializers.ListField(
        child=StrictStringField(max_length=200, allow_blank=False),
        min_length=0,
        max_length=30,
        help_text="Ingredient names or phrases typed by the user.",
    )
    exclude = serializers.ListField(
        child=serializers.CharField(max_length=200),
        default=list,
        required=False,
        help_text="Ingredient slugs to exclude from the search pool.",
    )
    mode = serializers.ChoiceField(
        choices=["strict", "explore"],
        default="strict",
        required=False,
        help_text="strict (default): exact + can_make only. explore: adds almost tier.",
    )
    meal_type = serializers.ChoiceField(
        choices=[
            "breakfast",
            "lunch",
            "dinner",
            "snack",
            "dessert",
            "drink",
            "any",
        ],
        required=False,
        allow_null=True,
        default=None,
    )
    course = serializers.ChoiceField(
        choices=[
            "starter",
            "main",
            "side",
            "dessert",
            "drink",
            "snack",
            "condiment",
        ],
        required=False,
        allow_null=True,
        default=None,
    )
    lang = serializers.ChoiceField(
        choices=["en", "sw"],
        default="en",
        required=False,
    )
    limit = serializers.IntegerField(
        default=20,
        min_value=1,
        max_value=50,
        required=False,
    )
    diet = serializers.ListField(
        child=serializers.CharField(max_length=100),
        default=list,
        required=False,
        help_text=(
            "Dietary tag slugs to filter by (e.g. 'vegetarian', 'gluten-free', 'nut-free'). "
            "Allergen exclusions always win — a dish tagged contains-pork is excluded "
            "when 'contains-pork' is in this list."
        ),
    )

    def validate_ingredients(self, value: list) -> list:
        """Strip whitespace, drop blank entries, and strip HTML tags."""
        _tag_re = re.compile(r"<[^>]+>")
        return [_tag_re.sub("", v).strip() for v in value if v.strip()]


# ──────────────────────────────────────────────────────────────────────────────
# Response
# ──────────────────────────────────────────────────────────────────────────────


class IngredientRefSerializer(serializers.Serializer):
    id = serializers.CharField()
    slug = serializers.CharField()
    name_en = serializers.CharField()
    name_sw = serializers.CharField()


class SearchResultItemSerializer(serializers.Serializer):
    dish_id = serializers.CharField()
    slug = serializers.CharField()
    name_en = serializers.CharField()
    name_sw = serializers.CharField()
    tier = serializers.CharField()
    score = serializers.FloatField()
    score_breakdown = serializers.DictField(child=serializers.FloatField())
    matched = IngredientRefSerializer(many=True)
    missing = IngredientRefSerializer(many=True)
    unused = IngredientRefSerializer(many=True)
    staples_assumed = IngredientRefSerializer(many=True)
    quality_level = serializers.CharField()


class ResolvedInputSerializer(serializers.Serializer):
    """Summary of how each input token was understood."""

    token = serializers.CharField()
    status = serializers.CharField()  # matched | ambiguous | unmatched
    ingredient_id = serializers.CharField(allow_null=True)
    method = serializers.CharField(allow_blank=True)
    confidence = serializers.FloatField()


class SearchResponseSerializer(serializers.Serializer):
    """Full search response envelope."""

    dataset_version = serializers.CharField()
    mode = serializers.CharField()
    candidate_count = serializers.IntegerField()
    total_results = serializers.IntegerField()
    resolved = ResolvedInputSerializer(many=True)
    ambiguous = serializers.ListField(child=serializers.CharField())
    unmatched = serializers.ListField(child=serializers.CharField())
    results = serializers.DictField()  # {"exact": [...], "can_make": [...], "almost": [...]}
