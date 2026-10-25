"""E29 — Pairing serializers."""

from rest_framework import serializers

from apps.pairings.models import Pairing


class PairingSerializer(serializers.ModelSerializer):
    paired_dish_slug = serializers.SerializerMethodField()
    paired_dish_name = serializers.SerializerMethodField()

    class Meta:
        model = Pairing
        fields = [
            "id",
            "pairing_type",
            "strength",
            "paired_dish_slug",
            "paired_dish_name",
            "paired_label",
            "note",
        ]

    def get_paired_dish_slug(self, obj: Pairing) -> str | None:
        return obj.paired_dish.slug if obj.paired_dish else None

    def get_paired_dish_name(self, obj: Pairing) -> str | None:
        if obj.paired_dish:
            lang = self.context.get("lang", "en")
            if lang == "sw" and obj.paired_dish.name_sw:
                return obj.paired_dish.name_sw
            return obj.paired_dish.name_en
        return None
