"""E29 — Substitution serializers."""
from rest_framework import serializers

from apps.substitutions.models import Substitution


class SubstitutionSerializer(serializers.ModelSerializer):
    ingredient_slug = serializers.SlugRelatedField(
        source="ingredient", slug_field="slug", read_only=True
    )
    ingredient_name = serializers.SerializerMethodField()
    substitute_slug = serializers.SlugRelatedField(
        source="substitute", slug_field="slug", read_only=True
    )
    substitute_name = serializers.SerializerMethodField()
    context_dish_slug = serializers.SerializerMethodField()

    class Meta:
        model = Substitution
        fields = [
            "id",
            "ingredient_slug",
            "ingredient_name",
            "substitute_slug",
            "substitute_name",
            "ratio",
            "quality",
            "context_dish_slug",
            "note",
        ]

    def get_ingredient_name(self, obj: Substitution) -> str:
        lang = self.context.get("lang", "en")
        if lang == "sw" and obj.ingredient.name_sw:
            return obj.ingredient.name_sw
        return obj.ingredient.name_en

    def get_substitute_name(self, obj: Substitution) -> str:
        lang = self.context.get("lang", "en")
        if lang == "sw" and obj.substitute.name_sw:
            return obj.substitute.name_sw
        return obj.substitute.name_en

    def get_context_dish_slug(self, obj: Substitution) -> str | None:
        return obj.context_dish.slug if obj.context_dish else None
