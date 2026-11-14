"""
Serializers for the Engine Admin API.

All serializers are explicitly declared — no magic auto-generation —
so that the FFCC knows exactly what shape of data it is receiving and sending.
"""

from rest_framework import serializers

from apps.clients.models import ApiClient, ApiKey, UsageRecord
from apps.curation.models import ChangeLog, CommunitySubmission, DatasetRelease
from apps.dishes.models import Dish, DishIngredient, DishStep
from apps.ingredients.models import Ingredient, IngredientAlias, IngredientAllergen


# ---------------------------------------------------------------------------
# API Clients & Keys
# ---------------------------------------------------------------------------


class ApiKeySerializer(serializers.ModelSerializer):
    is_revoked = serializers.BooleanField(read_only=True)

    class Meta:
        model = ApiKey
        fields = [
            "id",
            "prefix",
            "scopes",
            "rate_limit",
            "is_revoked",
            "created_at",
            "last_used_at",
            "revoked_at",
        ]
        read_only_fields = fields


class ApiClientListSerializer(serializers.ModelSerializer):
    key_count = serializers.IntegerField(read_only=True)
    active_key_count = serializers.IntegerField(read_only=True)
    last_used_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = ApiClient
        fields = [
            "id",
            "name",
            "type",
            "active",
            "key_count",
            "active_key_count",
            "last_used_at",
            "created_at",
        ]
        read_only_fields = fields


class ApiClientDetailSerializer(serializers.ModelSerializer):
    keys = ApiKeySerializer(many=True, read_only=True)

    class Meta:
        model = ApiClient
        fields = ["id", "name", "type", "active", "keys", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class CreateClientSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    type = serializers.ChoiceField(choices=ApiClient.ClientType.choices, default="internal")

    def validate_name(self, value):
        if ApiClient.objects.filter(name=value).exists():
            raise serializers.ValidationError("A client with this name already exists.")
        return value


class UpdateClientSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    active = serializers.BooleanField(required=False)

    def validate_name(self, value):
        client = self.context.get("client")
        qs = ApiClient.objects.filter(name=value)
        if client:
            qs = qs.exclude(pk=client.pk)
        if qs.exists():
            raise serializers.ValidationError("A client with this name already exists.")
        return value


class GenerateKeySerializer(serializers.Serializer):
    scopes = serializers.ListField(
        child=serializers.ChoiceField(choices=ApiKey.ALL_SCOPES),
        min_length=1,
    )
    rate_limit = serializers.IntegerField(min_value=0, default=60)


class UsageRecordSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)

    class Meta:
        model = UsageRecord
        fields = ["id", "client_name", "endpoint", "date", "calls", "errors", "p95_ms"]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Dishes
# ---------------------------------------------------------------------------


class DishStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = DishStep
        fields = ["position", "text_en", "text_sw"]
        read_only_fields = fields


class DishIngredientSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source="ingredient.name_en", read_only=True)
    ingredient_slug = serializers.SlugField(source="ingredient.slug", read_only=True)
    unit_code = serializers.CharField(source="unit.code", read_only=True, allow_null=True)

    class Meta:
        model = DishIngredient
        fields = [
            "ingredient_slug",
            "ingredient_name",
            "role",
            "quantity",
            "unit_code",
            "preparation_note",
            "position",
        ]
        read_only_fields = fields


class DishListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dish
        fields = [
            "id",
            "slug",
            "name_en",
            "name_sw",
            "meal_type",
            "course",
            "status",
            "quality_level",
            "difficulty",
            "prep_min",
            "cook_min",
            "servings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DishDetailSerializer(serializers.ModelSerializer):
    dish_ingredients = DishIngredientSerializer(many=True, read_only=True)
    steps = DishStepSerializer(many=True, read_only=True)
    region_names = serializers.SerializerMethodField()

    class Meta:
        model = Dish
        fields = [
            "id",
            "slug",
            "name_en",
            "name_sw",
            "description",
            "meal_type",
            "course",
            "spice_level",
            "difficulty",
            "prep_min",
            "cook_min",
            "servings",
            "popularity",
            "quality_level",
            "status",
            "region_names",
            "dish_ingredients",
            "steps",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_region_names(self, obj):
        return list(obj.regions.values_list("name", flat=True))


class PatchDishSerializer(serializers.Serializer):
    name_en = serializers.CharField(max_length=200, required=False)
    name_sw = serializers.CharField(max_length=200, required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=["draft", "reviewed", "verified", "archived"], required=False
    )
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


class PromoteDishSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


# ---------------------------------------------------------------------------
# Ingredients
# ---------------------------------------------------------------------------


class IngredientAliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngredientAlias
        fields = ["alias", "language", "is_misspelling"]
        read_only_fields = fields


class IngredientAllergenSerializer(serializers.ModelSerializer):
    allergen_name = serializers.CharField(source="allergen.name", read_only=True)
    allergen_slug = serializers.SlugField(source="allergen.slug", read_only=True)

    class Meta:
        model = IngredientAllergen
        fields = ["allergen_slug", "allergen_name", "notes"]
        read_only_fields = fields


class IngredientListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name_en", read_only=True)

    class Meta:
        model = Ingredient
        fields = [
            "id",
            "slug",
            "name_en",
            "name_sw",
            "category_name",
            "kind",
            "is_staple",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class IngredientDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name_en", read_only=True)
    aliases = IngredientAliasSerializer(many=True, read_only=True)
    allergen_links = IngredientAllergenSerializer(many=True, read_only=True)

    class Meta:
        model = Ingredient
        fields = [
            "id",
            "slug",
            "name_en",
            "name_sw",
            "category_name",
            "kind",
            "is_staple",
            "status",
            "notes",
            "aliases",
            "allergen_links",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PatchIngredientSerializer(serializers.Serializer):
    name_en = serializers.CharField(max_length=150, required=False)
    name_sw = serializers.CharField(max_length=150, required=False, allow_blank=True)
    status = serializers.ChoiceField(
        choices=["draft", "reviewed", "verified", "archived"], required=False
    )
    kind = serializers.ChoiceField(
        choices=["primary", "secondary", "seasoning", "staple", "liquid", "garnish"],
        required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True, default="")


# ---------------------------------------------------------------------------
# Community Submissions
# ---------------------------------------------------------------------------


class SubmissionListSerializer(serializers.ModelSerializer):
    submitter_client_name = serializers.CharField(
        source="submitter_client.name", read_only=True, allow_null=True
    )

    class Meta:
        model = CommunitySubmission
        fields = [
            "id",
            "submission_type",
            "status",
            "submitter_client_name",
            "submitter_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class SubmissionDetailSerializer(serializers.ModelSerializer):
    submitter_client_name = serializers.CharField(
        source="submitter_client.name", read_only=True, allow_null=True
    )

    class Meta:
        model = CommunitySubmission
        fields = [
            "id",
            "submission_type",
            "status",
            "payload",
            "submitter_client_name",
            "submitter_note",
            "reviewed_at",
            "rejection_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ReviewSubmissionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    reason = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")

    def validate(self, data):
        if data["action"] == "reject" and not data.get("reason", "").strip():
            raise serializers.ValidationError(
                {"reason": "A reason is required when rejecting a submission."}
            )
        return data


# ---------------------------------------------------------------------------
# Dataset Releases
# ---------------------------------------------------------------------------


class DatasetReleaseSerializer(serializers.ModelSerializer):
    released_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DatasetRelease
        fields = [
            "id",
            "version",
            "notes",
            "counts",
            "released_by_name",
            "created_at",
        ]
        read_only_fields = fields

    def get_released_by_name(self, obj):
        if obj.released_by:
            return str(obj.released_by)
        return "FFCC (via API)"


class TriggerReleaseSerializer(serializers.Serializer):
    version = serializers.RegexField(
        r"^\d{4}\.\d{1,2}\.\d+$",
        max_length=20,
        error_messages={"invalid": "Version must match YYYY.MM.N format, e.g. 2026.11.1"},
    )
    notes = serializers.CharField(max_length=5000, required=False, allow_blank=True, default="")
    confirm = serializers.BooleanField()

    def validate(self, data):
        if not data.get("confirm"):
            raise serializers.ValidationError(
                {"confirm": "Set confirm=true to trigger a dataset release."}
            )
        if DatasetRelease.objects.filter(version=data["version"]).exists():
            raise serializers.ValidationError(
                {"version": f"Release {data['version']} already exists."}
            )
        return data


# ---------------------------------------------------------------------------
# ChangeLog
# ---------------------------------------------------------------------------


class ChangeLogSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = ChangeLog
        fields = [
            "id",
            "object_type",
            "object_id",
            "action",
            "diff",
            "actor_name",
            "reason",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        if obj.actor:
            return str(obj.actor)
        return "FFCC (via API)"
