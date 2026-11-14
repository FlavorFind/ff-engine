"""
Engine Admin API views.

All endpoints require the internal:admin scope.
Mounted at /v1/admin/ in config/urls.py.

Authentication: X-API-Key header with internal:admin scope.
"""

import logging
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status as http_status

from apps.clients.keys import create_key
from apps.clients.models import ApiClient, ApiKey, UsageRecord
from apps.clients.permissions import HasScope
from apps.curation.models import ChangeLog, CommunitySubmission, DatasetRelease
from apps.dishes.models import Dish, DishAlias
from apps.ingredients.models import Ingredient, IngredientAlias
from apps.search.models import ZeroResultQuery

from .serializers import (
    ApiClientDetailSerializer,
    ApiClientListSerializer,
    ChangeLogSerializer,
    CreateClientSerializer,
    DatasetReleaseSerializer,
    DishDetailSerializer,
    DishListSerializer,
    GenerateKeySerializer,
    IngredientDetailSerializer,
    IngredientListSerializer,
    PatchDishSerializer,
    PatchIngredientSerializer,
    PromoteDishSerializer,
    ReviewSubmissionSerializer,
    SubmissionDetailSerializer,
    SubmissionListSerializer,
    TriggerReleaseSerializer,
    UpdateClientSerializer,
    UsageRecordSerializer,
)

logger = logging.getLogger(__name__)

SCOPE = ApiKey.SCOPE_INTERNAL_ADMIN
_scope_perm = [HasScope(SCOPE)]


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


def _paginate(request, queryset, serializer_class):
    paginator = StandardPagination()
    page = paginator.paginate_queryset(queryset, request)
    serializer = serializer_class(page, many=True)
    return paginator.get_paginated_response(serializer.data)


# ---------------------------------------------------------------------------
# API Clients
# ---------------------------------------------------------------------------


@extend_schema(tags=["admin:clients"], summary="List all API clients")
@api_view(["GET"])
@permission_classes(_scope_perm)
def client_list(request):
    qs = (
        ApiClient.objects.annotate(
            key_count=Count("keys"),
            active_key_count=Count("keys", filter=Q(keys__revoked_at__isnull=True)),
            last_used_at=Max("keys__last_used_at"),
        )
        .order_by("name")
    )
    return _paginate(request, qs, ApiClientListSerializer)


@extend_schema(tags=["admin:clients"], summary="Create API client")
@api_view(["POST"])
@permission_classes(_scope_perm)
def client_create(request):
    ser = CreateClientSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    client = ApiClient.objects.create(**ser.validated_data)
    logger.info("admin_api: created client %s", client.name)
    return Response(ApiClientDetailSerializer(client).data, status=http_status.HTTP_201_CREATED)


@extend_schema(tags=["admin:clients"], summary="Get API client detail")
@api_view(["GET"])
@permission_classes(_scope_perm)
def client_detail(request, client_id):
    try:
        client = ApiClient.objects.prefetch_related("keys").get(pk=client_id)
    except ApiClient.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    return Response(ApiClientDetailSerializer(client).data)


@extend_schema(tags=["admin:clients"], summary="Update API client")
@api_view(["PATCH"])
@permission_classes(_scope_perm)
def client_update(request, client_id):
    try:
        client = ApiClient.objects.get(pk=client_id)
    except ApiClient.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    ser = UpdateClientSerializer(data=request.data, context={"client": client})
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    for field, value in ser.validated_data.items():
        setattr(client, field, value)
    client.save(update_fields=list(ser.validated_data.keys()) + ["updated_at"])
    return Response(ApiClientDetailSerializer(client).data)


@extend_schema(tags=["admin:clients"], summary="Generate a new API key for a client")
@api_view(["POST"])
@permission_classes(_scope_perm)
def client_generate_key(request, client_id):
    try:
        client = ApiClient.objects.get(pk=client_id)
    except ApiClient.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    ser = GenerateKeySerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    api_key_obj, raw_key = create_key(
        client,
        scopes=ser.validated_data["scopes"],
        rate_limit=ser.validated_data["rate_limit"],
    )
    logger.info("admin_api: generated key %s for client %s", api_key_obj.prefix, client.name)
    return Response(
        {
            "id": str(api_key_obj.id),
            "prefix": api_key_obj.prefix,
            "raw_key": raw_key,
            "scopes": api_key_obj.scopes,
            "rate_limit": api_key_obj.rate_limit,
            "created_at": api_key_obj.created_at,
            "warning": "Copy this key now. It will NOT be shown again.",
        },
        status=http_status.HTTP_201_CREATED,
    )


@extend_schema(tags=["admin:clients"], summary="Revoke an API key")
@api_view(["POST"])
@permission_classes(_scope_perm)
def key_revoke(request, key_id):
    try:
        api_key = ApiKey.objects.select_related("client").get(pk=key_id)
    except ApiKey.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    if api_key.is_revoked:
        return Response({"error": "Key is already revoked."}, status=http_status.HTTP_400_BAD_REQUEST)
    api_key.revoke()
    logger.info("admin_api: revoked key %s (client: %s)", api_key.prefix, api_key.client.name)
    return Response({"revoked": True, "revoked_at": api_key.revoked_at})


@extend_schema(tags=["admin:clients"], summary="Usage stats across all clients")
@api_view(["GET"])
@permission_classes(_scope_perm)
def usage_list(request):
    days = int(request.query_params.get("days", 7))
    since = date.today() - timedelta(days=days)
    qs = (
        UsageRecord.objects.select_related("client")
        .filter(date__gte=since)
        .order_by("-date", "client__name")
    )
    return _paginate(request, qs, UsageRecordSerializer)


@extend_schema(tags=["admin:clients"], summary="Usage stats for one client")
@api_view(["GET"])
@permission_classes(_scope_perm)
def usage_client(request, client_id):
    try:
        client = ApiClient.objects.get(pk=client_id)
    except ApiClient.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    days = int(request.query_params.get("days", 30))
    since = date.today() - timedelta(days=days)
    qs = UsageRecord.objects.filter(client=client, date__gte=since).order_by("-date")
    return _paginate(request, qs, UsageRecordSerializer)


# ---------------------------------------------------------------------------
# Dishes
# ---------------------------------------------------------------------------


@extend_schema(tags=["admin:dishes"], summary="List all dishes (all statuses)")
@api_view(["GET"])
@permission_classes(_scope_perm)
def dish_list(request):
    qs = Dish.objects.all().order_by("-updated_at")

    # Enum filters — these hit B-tree indexes directly.
    if status_f := request.query_params.get("status"):
        qs = qs.filter(status=status_f)
    if meal_type := request.query_params.get("meal_type"):
        qs = qs.filter(meal_type=meal_type)
    if course := request.query_params.get("course"):
        qs = qs.filter(course=course)

    # Text search — uses trgm GIN index on name_en / name_sw (migration 0003).
    # Also covers DishAlias so e.g. "Pilav" finds a dish aliased as "Pilau".
    if search := request.query_params.get("search", "").strip():
        # Collect IDs of dishes matched by alias first (separate query is faster
        # than a JOIN+DISTINCT when the alias table grows large).
        alias_dish_ids = DishAlias.objects.filter(
            alias__icontains=search
        ).values_list("dish_id", flat=True)
        qs = qs.filter(
            Q(name_en__icontains=search)
            | Q(name_sw__icontains=search)
            | Q(id__in=alias_dish_ids)
        )

    return _paginate(request, qs, DishListSerializer)


@extend_schema(tags=["admin:dishes"], summary="Get dish detail")
@api_view(["GET"])
@permission_classes(_scope_perm)
def dish_detail(request, slug):
    try:
        dish = (
            Dish.objects.prefetch_related(
                "dish_ingredients__ingredient",
                "dish_ingredients__unit",
                "steps",
                "regions",
            )
            .get(slug=slug)
        )
    except Dish.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    return Response(DishDetailSerializer(dish).data)


@extend_schema(tags=["admin:dishes"], summary="Update dish fields")
@api_view(["PATCH"])
@permission_classes(_scope_perm)
def dish_update(request, slug):
    try:
        dish = Dish.objects.get(slug=slug)
    except Dish.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    ser = PatchDishSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)

    data = ser.validated_data
    reason = data.pop("reason", "")
    before = {}
    after = {}
    update_fields = []
    for field, value in data.items():
        old_val = getattr(dish, field)
        if old_val != value:
            before[field] = str(old_val)
            after[field] = str(value)
            setattr(dish, field, value)
            update_fields.append(field)

    if update_fields:
        update_fields.append("updated_at")
        dish.save(update_fields=update_fields)
        ChangeLog.objects.create(
            object_type="dish",
            object_id=str(dish.id),
            action=ChangeLog.Action.UPDATE,
            diff={"before": before, "after": after},
            reason=reason or "Updated via FFCC admin API",
        )
    return Response(DishDetailSerializer(dish).data)


PROMOTION_MAP = {
    "draft": "reviewed",
    "reviewed": "verified",
}


@extend_schema(tags=["admin:dishes"], summary="Promote dish to next status")
@api_view(["POST"])
@permission_classes(_scope_perm)
def dish_promote(request, slug):
    try:
        dish = Dish.objects.get(slug=slug)
    except Dish.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    ser = PromoteDishSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    next_status = PROMOTION_MAP.get(dish.status)
    if not next_status:
        return Response(
            {"error": f"Dish with status '{dish.status}' cannot be promoted."},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    old_status = dish.status
    dish.status = next_status
    dish.save(update_fields=["status", "updated_at"])
    ChangeLog.objects.create(
        object_type="dish",
        object_id=str(dish.id),
        action=ChangeLog.Action.STATUS_CHANGE,
        diff={"before": {"status": old_status}, "after": {"status": next_status}},
        reason=ser.validated_data.get("reason") or f"Promoted via FFCC: {old_status} → {next_status}",
    )
    return Response({"slug": dish.slug, "old_status": old_status, "new_status": next_status})


@extend_schema(tags=["admin:dishes"], summary="ChangeLog for a dish")
@api_view(["GET"])
@permission_classes(_scope_perm)
def dish_changelog(request, slug):
    try:
        dish = Dish.objects.get(slug=slug)
    except Dish.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    qs = ChangeLog.objects.filter(object_type="dish", object_id=str(dish.id)).order_by(
        "-created_at"
    )
    return _paginate(request, qs, ChangeLogSerializer)


# ---------------------------------------------------------------------------
# Ingredients
# ---------------------------------------------------------------------------


@extend_schema(tags=["admin:ingredients"], summary="List all ingredients (all statuses)")
@api_view(["GET"])
@permission_classes(_scope_perm)
def ingredient_list(request):
    qs = Ingredient.objects.select_related("category").order_by("name_en")

    if status_f := request.query_params.get("status"):
        qs = qs.filter(status=status_f)
    if kind := request.query_params.get("kind"):
        qs = qs.filter(kind=kind)

    # Text search — uses trgm GIN indexes on name_en / name_sw (migration 0002).
    # Also covers IngredientAlias.normalized_alias (also trgm-indexed) so e.g.
    # "sukuma" finds "Kale" because the alias table has that mapping.
    if search := request.query_params.get("search", "").strip():
        alias_ingredient_ids = IngredientAlias.objects.filter(
            normalized_alias__icontains=search.lower()
        ).values_list("ingredient_id", flat=True)
        qs = qs.filter(
            Q(name_en__icontains=search)
            | Q(name_sw__icontains=search)
            | Q(id__in=alias_ingredient_ids)
        )

    return _paginate(request, qs, IngredientListSerializer)


@extend_schema(tags=["admin:ingredients"], summary="Get ingredient detail")
@api_view(["GET"])
@permission_classes(_scope_perm)
def ingredient_detail(request, slug):
    try:
        ingredient = Ingredient.objects.prefetch_related(
            "aliases", "allergen_links__allergen"
        ).get(slug=slug)
    except Ingredient.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    return Response(IngredientDetailSerializer(ingredient).data)


@extend_schema(tags=["admin:ingredients"], summary="Update ingredient fields")
@api_view(["PATCH"])
@permission_classes(_scope_perm)
def ingredient_update(request, slug):
    try:
        ingredient = Ingredient.objects.get(slug=slug)
    except Ingredient.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    ser = PatchIngredientSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)

    data = ser.validated_data
    reason = data.pop("reason", "")
    before = {}
    after = {}
    update_fields = []
    for field, value in data.items():
        old_val = getattr(ingredient, field)
        if old_val != value:
            before[field] = str(old_val)
            after[field] = str(value)
            setattr(ingredient, field, value)
            update_fields.append(field)

    if update_fields:
        update_fields.append("updated_at")
        ingredient.save(update_fields=update_fields)
        ChangeLog.objects.create(
            object_type="ingredient",
            object_id=str(ingredient.id),
            action=ChangeLog.Action.UPDATE,
            diff={"before": before, "after": after},
            reason=reason or "Updated via FFCC admin API",
        )
    return Response(IngredientDetailSerializer(ingredient).data)


# ---------------------------------------------------------------------------
# Community Submissions
# ---------------------------------------------------------------------------


@extend_schema(tags=["admin:submissions"], summary="List community submissions")
@api_view(["GET"])
@permission_classes(_scope_perm)
def submission_list(request):
    qs = CommunitySubmission.objects.select_related("submitter_client").order_by("-created_at")
    if status_f := request.query_params.get("status"):
        qs = qs.filter(status=status_f)
    if sub_type := request.query_params.get("submission_type"):
        qs = qs.filter(submission_type=sub_type)
    return _paginate(request, qs, SubmissionListSerializer)


@extend_schema(tags=["admin:submissions"], summary="Get submission detail")
@api_view(["GET"])
@permission_classes(_scope_perm)
def submission_detail(request, submission_id):
    try:
        sub = CommunitySubmission.objects.select_related("submitter_client").get(pk=submission_id)
    except CommunitySubmission.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    return Response(SubmissionDetailSerializer(sub).data)


@extend_schema(tags=["admin:submissions"], summary="Approve or reject a submission")
@api_view(["PATCH"])
@permission_classes(_scope_perm)
def submission_review(request, submission_id):
    try:
        sub = CommunitySubmission.objects.get(pk=submission_id)
    except CommunitySubmission.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    if sub.status != CommunitySubmission.SubmissionStatus.PENDING:
        return Response(
            {"error": f"Submission is already '{sub.status}', cannot review again."},
            status=http_status.HTTP_400_BAD_REQUEST,
        )
    ser = ReviewSubmissionSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)

    action = ser.validated_data["action"]
    reason = ser.validated_data.get("reason", "")
    with transaction.atomic():
        if action == "approve":
            sub.status = CommunitySubmission.SubmissionStatus.APPROVED
        else:
            sub.status = CommunitySubmission.SubmissionStatus.REJECTED
            sub.rejection_reason = reason
        sub.reviewed_at = timezone.now()
        sub.save(update_fields=["status", "rejection_reason", "reviewed_at", "updated_at"])
        ChangeLog.objects.create(
            object_type="community_submission",
            object_id=str(sub.id),
            action=ChangeLog.Action.STATUS_CHANGE,
            diff={"action": action, "reason": reason},
            reason=reason or f"Submission {action}d via FFCC",
        )
    return Response(SubmissionDetailSerializer(sub).data)


# ---------------------------------------------------------------------------
# Dataset Releases
# ---------------------------------------------------------------------------


@extend_schema(tags=["admin:dataset"], summary="List dataset releases")
@api_view(["GET"])
@permission_classes(_scope_perm)
def release_list(request):
    qs = DatasetRelease.objects.order_by("-created_at")
    return _paginate(request, qs, DatasetReleaseSerializer)


@extend_schema(tags=["admin:dataset"], summary="Trigger a new dataset release")
@api_view(["POST"])
@permission_classes(_scope_perm)
def release_create(request):
    ser = TriggerReleaseSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)

    version = ser.validated_data["version"]
    notes = ser.validated_data.get("notes", "")

    counts = {
        "dishes": {
            "total": Dish.objects.count(),
            "verified": Dish.objects.filter(status="verified").count(),
            "reviewed": Dish.objects.filter(status="reviewed").count(),
            "draft": Dish.objects.filter(status="draft").count(),
        },
        "ingredients": {
            "total": Ingredient.objects.count(),
            "verified": Ingredient.objects.filter(status="verified").count(),
            "reviewed": Ingredient.objects.filter(status="reviewed").count(),
            "draft": Ingredient.objects.filter(status="draft").count(),
        },
    }

    release = DatasetRelease.objects.create(version=version, notes=notes, counts=counts)
    ChangeLog.objects.create(
        object_type="dataset_release",
        object_id=str(release.id),
        action=ChangeLog.Action.CREATE,
        diff={"version": version, "counts": counts},
        reason=f"Dataset release {version} triggered via FFCC",
    )
    logger.info("admin_api: created dataset release %s", version)
    return Response(DatasetReleaseSerializer(release).data, status=http_status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# ChangeLog
# ---------------------------------------------------------------------------


@extend_schema(tags=["admin:changelog"], summary="Paginated ChangeLog")
@api_view(["GET"])
@permission_classes(_scope_perm)
def changelog_list(request):
    qs = ChangeLog.objects.order_by("-created_at")
    if obj_type := request.query_params.get("object_type"):
        qs = qs.filter(object_type=obj_type)
    if action := request.query_params.get("action"):
        qs = qs.filter(action=action)
    return _paginate(request, qs, ChangeLogSerializer)


# ---------------------------------------------------------------------------
# Zero-result queries (QA Observatory)
# ---------------------------------------------------------------------------


@extend_schema(tags=["admin:qa"], summary="Zero-result query list")
@api_view(["GET"])
@permission_classes(_scope_perm)
def zero_results_list(request):
    from rest_framework import serializers as drf_serializers

    qs = ZeroResultQuery.objects.order_by("-count", "-last_seen")

    class ZeroResultSerializer(drf_serializers.ModelSerializer):
        class Meta:
            model = ZeroResultQuery
            fields = ["id", "raw_input", "normalised_input", "count", "last_seen"]
            read_only_fields = fields

    return _paginate(request, qs, ZeroResultSerializer)


# ---------------------------------------------------------------------------
# Cache controls
# ---------------------------------------------------------------------------


@extend_schema(tags=["admin:cache"], summary="Clear search cache")
@api_view(["POST"])
@permission_classes(_scope_perm)
def cache_clear(request):
    from django.core.cache import cache
    cache.clear()
    logger.info("admin_api: search cache cleared")
    return Response({"cleared": True, "timestamp": timezone.now()})


# ===========================================================================
# REGIONS
# ===========================================================================

from apps.dietary.models import DietaryTag, DishDietaryTag  # noqa: E402
from apps.nutrition.models import NutritionFact  # noqa: E402
from apps.pairings.models import Pairing  # noqa: E402
from apps.regions.models import DishRegion, Region  # noqa: E402
from apps.substitutions.models import Substitution  # noqa: E402
from apps.curation.models import Source  # noqa: E402
from apps.dishes.models import DishAlias  # noqa: E402
from apps.ingredients.models import IngredientCategory  # noqa: E402

from .serializers import (  # noqa: E402
    CreateDietaryTagSerializer,
    CreateDishAliasSerializer,
    CreatePairingSerializer,
    CreateRegionSerializer,
    CreateSourceSerializer,
    CreateSubstitutionSerializer,
    DietaryTagSerializer,
    DishAliasSerializer,
    DishDietaryTagSerializer,
    DishRegionAssignSerializer,
    IngredientCategorySerializer,
    NutritionFactSerializer,
    PairingSerializer as AdminPairingSerializer,
    PatchPairingSerializer,
    PatchRegionSerializer,
    PatchSubstitutionSerializer,
    RegionSerializer,
    SetDishDietaryTagSerializer,
    SourceSerializer,
    SubstitutionSerializer as AdminSubstitutionSerializer,
    UpsertNutritionSerializer,
)


@extend_schema(tags=["admin:regions"], summary="List all regions")
@api_view(["GET"])
@permission_classes(_scope_perm)
def region_list_admin(request):
    from django.db.models import Count
    qs = Region.objects.annotate(dish_count=Count("dish_regions")).order_by("type", "name")
    if rtype := request.query_params.get("type"):
        qs = qs.filter(type=rtype)
    return _paginate(request, qs, RegionSerializer)


@extend_schema(tags=["admin:regions"], summary="Create a region")
@api_view(["POST"])
@permission_classes(_scope_perm)
def region_create(request):
    ser = CreateRegionSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    d = ser.validated_data
    parent = None
    if d.get("parent_slug"):
        try:
            parent = Region.objects.get(slug=d["parent_slug"])
        except Region.DoesNotExist:
            return Response({"errors": {"parent_slug": "Region not found."}}, status=http_status.HTTP_400_BAD_REQUEST)
    region = Region.objects.create(
        name=d["name"], type=d["type"], description=d.get("description", ""), parent=parent
    )
    ChangeLog.objects.create(
        object_type="region", object_id=str(region.id),
        action=ChangeLog.Action.CREATE,
        diff={"name": region.name, "type": region.type},
        reason="Created via FFCC",
    )
    from django.db.models import Count
    region.dish_count = 0
    return Response(RegionSerializer(region).data, status=http_status.HTTP_201_CREATED)


@extend_schema(tags=["admin:regions"], summary="Get region detail")
@api_view(["GET"])
@permission_classes(_scope_perm)
def region_detail_admin(request, slug):
    from django.db.models import Count
    try:
        region = Region.objects.annotate(dish_count=Count("dish_regions")).get(slug=slug)
    except Region.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    dishes = Dish.objects.filter(dish_regions__region=region).values("slug", "name_en", "status")[:50]
    data = RegionSerializer(region).data
    data["dishes"] = list(dishes)
    return Response(data)


@extend_schema(tags=["admin:regions"], summary="Update a region")
@api_view(["PATCH"])
@permission_classes(_scope_perm)
def region_update(request, slug):
    try:
        region = Region.objects.get(slug=slug)
    except Region.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    ser = PatchRegionSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    for field, value in ser.validated_data.items():
        setattr(region, field, value)
    region.save()
    from django.db.models import Count
    region.dish_count = DishRegion.objects.filter(region=region).count()
    return Response(RegionSerializer(region).data)


@extend_schema(tags=["admin:regions"], summary="Assign a dish to a region")
@api_view(["POST"])
@permission_classes(_scope_perm)
def region_assign_dish(request, slug):
    try:
        region = Region.objects.get(slug=slug)
    except Region.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    dish_slug = request.data.get("dish_slug", "").strip()
    try:
        dish = Dish.objects.get(slug=dish_slug)
    except Dish.DoesNotExist:
        return Response({"error": f"Dish '{dish_slug}' not found."}, status=http_status.HTTP_404_NOT_FOUND)
    _, created = DishRegion.objects.get_or_create(dish=dish, region=region)
    return Response({"assigned": created, "dish_slug": dish.slug, "region_slug": region.slug})


@extend_schema(tags=["admin:regions"], summary="Remove a dish from a region")
@api_view(["POST"])
@permission_classes(_scope_perm)
def region_remove_dish(request, slug):
    try:
        region = Region.objects.get(slug=slug)
    except Region.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    dish_slug = request.data.get("dish_slug", "").strip()
    deleted, _ = DishRegion.objects.filter(dish__slug=dish_slug, region=region).delete()
    return Response({"removed": deleted > 0})


# ===========================================================================
# DIETARY TAGS
# ===========================================================================


@extend_schema(tags=["admin:dietary"], summary="List all dietary tags")
@api_view(["GET"])
@permission_classes(_scope_perm)
def dietary_tag_list(request):
    from django.db.models import Count
    qs = DietaryTag.objects.annotate(dish_count=Count("dish_links")).order_by("name")
    return _paginate(request, qs, DietaryTagSerializer)


@extend_schema(tags=["admin:dietary"], summary="Create a dietary tag")
@api_view(["POST"])
@permission_classes(_scope_perm)
def dietary_tag_create(request):
    ser = CreateDietaryTagSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    tag = DietaryTag.objects.create(**ser.validated_data)
    tag.dish_count = 0
    return Response(DietaryTagSerializer(tag).data, status=http_status.HTTP_201_CREATED)


@extend_schema(tags=["admin:dietary"], summary="List dietary tags for a dish")
@api_view(["GET"])
@permission_classes(_scope_perm)
def dish_dietary_tags(request, slug):
    try:
        dish = Dish.objects.get(slug=slug)
    except Dish.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    tags = DishDietaryTag.objects.filter(dish=dish).select_related("tag")
    return Response(DishDietaryTagSerializer(tags, many=True).data)


@extend_schema(tags=["admin:dietary"], summary="Set a manual dietary tag on a dish")
@api_view(["POST"])
@permission_classes(_scope_perm)
def dish_dietary_tag_set(request, slug):
    try:
        dish = Dish.objects.get(slug=slug)
    except Dish.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    ser = SetDishDietaryTagSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    try:
        tag = DietaryTag.objects.get(slug=ser.validated_data["tag_slug"])
    except DietaryTag.DoesNotExist:
        return Response({"error": "Tag not found."}, status=http_status.HTTP_404_NOT_FOUND)
    obj, created = DishDietaryTag.objects.update_or_create(
        dish=dish, tag=tag,
        defaults={"source": DishDietaryTag.Source.MANUAL, "reason": ser.validated_data.get("reason", "")},
    )
    ChangeLog.objects.create(
        object_type="dish_dietary_tag", object_id=str(dish.id),
        action=ChangeLog.Action.UPDATE,
        diff={"tag": tag.slug, "source": "manual", "action": "set"},
        reason=ser.validated_data.get("reason") or "Manual tag set via FFCC",
    )
    return Response(DishDietaryTagSerializer(obj).data)


@extend_schema(tags=["admin:dietary"], summary="Remove a dietary tag from a dish")
@api_view(["POST"])
@permission_classes(_scope_perm)
def dish_dietary_tag_remove(request, slug):
    try:
        dish = Dish.objects.get(slug=slug)
    except Dish.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    tag_slug = request.data.get("tag_slug", "").strip()
    deleted, _ = DishDietaryTag.objects.filter(dish=dish, tag__slug=tag_slug).delete()
    return Response({"removed": deleted > 0})


@extend_schema(tags=["admin:dietary"], summary="Re-derive all dietary tags for a dish")
@api_view(["POST"])
@permission_classes(_scope_perm)
def dish_dietary_rederive(request, slug):
    try:
        dish = Dish.objects.get(slug=slug)
    except Dish.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    from apps.dietary.services import apply_derived_tags
    count = apply_derived_tags(dish)
    return Response({"derived_tags_applied": count, "dish_slug": dish.slug})


# ===========================================================================
# PAIRINGS
# ===========================================================================


@extend_schema(tags=["admin:pairings"], summary="List all pairings")
@api_view(["GET"])
@permission_classes(_scope_perm)
def pairing_list(request):
    qs = Pairing.objects.select_related("dish", "paired_dish").order_by("-strength", "dish__name_en")
    if dish_slug := request.query_params.get("dish_slug"):
        qs = qs.filter(dish__slug=dish_slug)
    if ptype := request.query_params.get("type"):
        qs = qs.filter(pairing_type=ptype)
    if min_str := request.query_params.get("min_strength"):
        qs = qs.filter(strength__gte=int(min_str))
    return _paginate(request, qs, AdminPairingSerializer)


@extend_schema(tags=["admin:pairings"], summary="Create a pairing")
@api_view(["POST"])
@permission_classes(_scope_perm)
def pairing_create(request):
    ser = CreatePairingSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    d = ser.validated_data
    try:
        dish = Dish.objects.get(slug=d["dish_slug"])
    except Dish.DoesNotExist:
        return Response({"error": f"Dish '{d['dish_slug']}' not found."}, status=http_status.HTTP_404_NOT_FOUND)
    paired_dish = None
    if d.get("paired_dish_slug"):
        try:
            paired_dish = Dish.objects.get(slug=d["paired_dish_slug"])
        except Dish.DoesNotExist:
            return Response({"error": f"Paired dish '{d['paired_dish_slug']}' not found."}, status=http_status.HTTP_404_NOT_FOUND)
    pairing = Pairing.objects.create(
        dish=dish, paired_dish=paired_dish,
        paired_label=d.get("paired_label", ""),
        pairing_type=d["pairing_type"],
        strength=d["strength"],
        note=d.get("note", ""),
    )
    ChangeLog.objects.create(
        object_type="pairing", object_id=str(pairing.id),
        action=ChangeLog.Action.CREATE,
        diff={"dish": dish.slug, "type": pairing.pairing_type, "strength": pairing.strength},
        reason="Created via FFCC",
    )
    return Response(AdminPairingSerializer(pairing).data, status=http_status.HTTP_201_CREATED)


@extend_schema(tags=["admin:pairings"], summary="Update a pairing")
@api_view(["PATCH"])
@permission_classes(_scope_perm)
def pairing_update(request, pairing_id):
    try:
        pairing = Pairing.objects.select_related("dish", "paired_dish").get(pk=pairing_id)
    except Pairing.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    ser = PatchPairingSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    for field, value in ser.validated_data.items():
        setattr(pairing, field, value)
    pairing.save()
    return Response(AdminPairingSerializer(pairing).data)


@extend_schema(tags=["admin:pairings"], summary="Delete a pairing")
@api_view(["DELETE"])
@permission_classes(_scope_perm)
def pairing_delete(request, pairing_id):
    try:
        pairing = Pairing.objects.get(pk=pairing_id)
    except Pairing.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    pairing.delete()
    return Response(status=http_status.HTTP_204_NO_CONTENT)


# ===========================================================================
# SUBSTITUTIONS
# ===========================================================================


@extend_schema(tags=["admin:substitutions"], summary="List all substitutions")
@api_view(["GET"])
@permission_classes(_scope_perm)
def substitution_list(request):
    qs = Substitution.objects.select_related("ingredient", "substitute", "context_dish").order_by("quality", "ingredient__name_en")
    if ing_slug := request.query_params.get("ingredient_slug"):
        qs = qs.filter(ingredient__slug=ing_slug)
    if quality := request.query_params.get("quality"):
        qs = qs.filter(quality=quality)
    if search := request.query_params.get("search", "").strip():
        from django.db.models import Q
        qs = qs.filter(Q(ingredient__name_en__icontains=search) | Q(substitute__name_en__icontains=search))
    return _paginate(request, qs, AdminSubstitutionSerializer)


@extend_schema(tags=["admin:substitutions"], summary="Create a substitution")
@api_view(["POST"])
@permission_classes(_scope_perm)
def substitution_create(request):
    ser = CreateSubstitutionSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    d = ser.validated_data
    try:
        ingredient = Ingredient.objects.get(slug=d["ingredient_slug"])
        substitute = Ingredient.objects.get(slug=d["substitute_slug"])
    except Ingredient.DoesNotExist as e:
        return Response({"error": str(e)}, status=http_status.HTTP_404_NOT_FOUND)
    context_dish = None
    if d.get("context_dish_slug"):
        try:
            context_dish = Dish.objects.get(slug=d["context_dish_slug"])
        except Dish.DoesNotExist:
            return Response({"error": f"Dish '{d['context_dish_slug']}' not found."}, status=http_status.HTTP_404_NOT_FOUND)
    sub = Substitution.objects.create(
        ingredient=ingredient, substitute=substitute,
        ratio=d["ratio"], quality=d["quality"],
        context_dish=context_dish, note=d.get("note", ""),
    )
    ChangeLog.objects.create(
        object_type="substitution", object_id=str(sub.id),
        action=ChangeLog.Action.CREATE,
        diff={"ingredient": ingredient.slug, "substitute": substitute.slug, "quality": sub.quality},
        reason="Created via FFCC",
    )
    return Response(AdminSubstitutionSerializer(sub).data, status=http_status.HTTP_201_CREATED)


@extend_schema(tags=["admin:substitutions"], summary="Update a substitution")
@api_view(["PATCH"])
@permission_classes(_scope_perm)
def substitution_update(request, sub_id):
    try:
        sub = Substitution.objects.select_related("ingredient", "substitute", "context_dish").get(pk=sub_id)
    except Substitution.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    ser = PatchSubstitutionSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    for field, value in ser.validated_data.items():
        setattr(sub, field, value)
    sub.save()
    return Response(AdminSubstitutionSerializer(sub).data)


@extend_schema(tags=["admin:substitutions"], summary="Delete a substitution")
@api_view(["DELETE"])
@permission_classes(_scope_perm)
def substitution_delete(request, sub_id):
    try:
        sub = Substitution.objects.get(pk=sub_id)
    except Substitution.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    sub.delete()
    return Response(status=http_status.HTTP_204_NO_CONTENT)


# ===========================================================================
# NUTRITION FACTS
# ===========================================================================


@extend_schema(tags=["admin:nutrition"], summary="List ingredients with/without nutrition data")
@api_view(["GET"])
@permission_classes(_scope_perm)
def nutrition_list(request):
    missing = request.query_params.get("missing", "").lower() == "true"
    if missing:
        # Ingredients that have NO nutrition fact
        from django.db.models import OuterRef, Subquery
        qs = Ingredient.objects.filter(
            ~Q(id__in=NutritionFact.objects.values("ingredient_id"))
        ).select_related("category").order_by("name_en")
        if search := request.query_params.get("search", "").strip():
            qs = qs.filter(Q(name_en__icontains=search) | Q(name_sw__icontains=search))
        return _paginate(request, qs, IngredientListSerializer)
    else:
        qs = NutritionFact.objects.select_related("ingredient").order_by("ingredient__name_en")
        if search := request.query_params.get("search", "").strip():
            qs = qs.filter(
                Q(ingredient__name_en__icontains=search) | Q(ingredient__name_sw__icontains=search)
            )
        return _paginate(request, qs, NutritionFactSerializer)


@extend_schema(tags=["admin:nutrition"], summary="Get or upsert nutrition for an ingredient")
@api_view(["GET", "PUT"])
@permission_classes(_scope_perm)
def nutrition_ingredient(request, slug):
    try:
        ingredient = Ingredient.objects.get(slug=slug)
    except Ingredient.DoesNotExist:
        return Response({"error": "Ingredient not found."}, status=http_status.HTTP_404_NOT_FOUND)
    if request.method == "GET":
        try:
            nf = ingredient.nutrition
        except NutritionFact.DoesNotExist:
            return Response({"error": "No nutrition data for this ingredient."}, status=http_status.HTTP_404_NOT_FOUND)
        return Response(NutritionFactSerializer(nf).data)
    # PUT — upsert
    ser = UpsertNutritionSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    nf, created = NutritionFact.objects.update_or_create(
        ingredient=ingredient, defaults=ser.validated_data
    )
    ChangeLog.objects.create(
        object_type="nutrition_fact", object_id=str(nf.id),
        action=ChangeLog.Action.CREATE if created else ChangeLog.Action.UPDATE,
        diff={"ingredient": ingredient.slug},
        reason="Upserted via FFCC",
    )
    return Response(NutritionFactSerializer(nf).data, status=http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK)


@extend_schema(tags=["admin:nutrition"], summary="Delete nutrition fact for an ingredient")
@api_view(["DELETE"])
@permission_classes(_scope_perm)
def nutrition_delete(request, slug):
    try:
        ingredient = Ingredient.objects.get(slug=slug)
        nf = ingredient.nutrition
    except (Ingredient.DoesNotExist, NutritionFact.DoesNotExist):
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    nf.delete()
    return Response(status=http_status.HTTP_204_NO_CONTENT)


# ===========================================================================
# SOURCES
# ===========================================================================


@extend_schema(tags=["admin:sources"], summary="List all sources")
@api_view(["GET"])
@permission_classes(_scope_perm)
def source_list(request):
    qs = Source.objects.order_by("title")
    if kind := request.query_params.get("kind"):
        qs = qs.filter(kind=kind)
    if search := request.query_params.get("search", "").strip():
        qs = qs.filter(title__icontains=search)
    return _paginate(request, qs, SourceSerializer)


@extend_schema(tags=["admin:sources"], summary="Create a source")
@api_view(["POST"])
@permission_classes(_scope_perm)
def source_create(request):
    ser = CreateSourceSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    source = Source.objects.create(**ser.validated_data)
    return Response(SourceSerializer(source).data, status=http_status.HTTP_201_CREATED)


@extend_schema(tags=["admin:sources"], summary="Update a source")
@api_view(["PATCH"])
@permission_classes(_scope_perm)
def source_update(request, source_id):
    try:
        source = Source.objects.get(pk=source_id)
    except Source.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    for field, value in request.data.items():
        if hasattr(source, field):
            setattr(source, field, value)
    source.save()
    return Response(SourceSerializer(source).data)


@extend_schema(tags=["admin:sources"], summary="Delete a source")
@api_view(["DELETE"])
@permission_classes(_scope_perm)
def source_delete(request, source_id):
    try:
        Source.objects.get(pk=source_id).delete()
    except Source.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    return Response(status=http_status.HTTP_204_NO_CONTENT)


# ===========================================================================
# DISH ALIASES
# ===========================================================================


@extend_schema(tags=["admin:dishes"], summary="List aliases for a dish")
@api_view(["GET"])
@permission_classes(_scope_perm)
def dish_aliases(request, slug):
    try:
        dish = Dish.objects.get(slug=slug)
    except Dish.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    aliases = DishAlias.objects.filter(dish=dish).order_by("language", "alias")
    return Response(DishAliasSerializer(aliases, many=True).data)


@extend_schema(tags=["admin:dishes"], summary="Add an alias to a dish")
@api_view(["POST"])
@permission_classes(_scope_perm)
def dish_alias_add(request, slug):
    try:
        dish = Dish.objects.get(slug=slug)
    except Dish.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    ser = CreateDishAliasSerializer(data=request.data)
    if not ser.is_valid():
        return Response({"errors": ser.errors}, status=http_status.HTTP_400_BAD_REQUEST)
    alias_text = ser.validated_data["alias"].strip()
    if DishAlias.objects.filter(dish=dish, alias__iexact=alias_text).exists():
        return Response({"error": "Alias already exists for this dish."}, status=http_status.HTTP_400_BAD_REQUEST)
    alias = DishAlias.objects.create(dish=dish, **ser.validated_data)
    return Response(DishAliasSerializer(alias).data, status=http_status.HTTP_201_CREATED)


@extend_schema(tags=["admin:dishes"], summary="Delete a dish alias")
@api_view(["DELETE"])
@permission_classes(_scope_perm)
def dish_alias_delete(request, alias_id):
    try:
        DishAlias.objects.get(pk=alias_id).delete()
    except DishAlias.DoesNotExist:
        return Response({"error": "Not found."}, status=http_status.HTTP_404_NOT_FOUND)
    return Response(status=http_status.HTTP_204_NO_CONTENT)


# ===========================================================================
# INGREDIENT CATEGORIES
# ===========================================================================


@extend_schema(tags=["admin:ingredients"], summary="List ingredient categories")
@api_view(["GET"])
@permission_classes(_scope_perm)
def ingredient_category_list(request):
    from django.db.models import Count
    qs = IngredientCategory.objects.annotate(ingredient_count=Count("ingredients")).select_related("parent").order_by("name_en")
    return _paginate(request, qs, IngredientCategorySerializer)


# ===========================================================================
# QA REPORT
# ===========================================================================


@extend_schema(tags=["admin:qa"], summary="Full QA data-quality report")
@api_view(["GET"])
@permission_classes(_scope_perm)
def qa_report(request):
    """Run the full qa_report logic and return JSON."""
    from apps.dishes.models import DishIngredient, DishStep
    from apps.ingredients.models import IngredientAlias
    from apps.curation.validators import scan_dataset
    from django.db.models import Count
    from datetime import datetime, timezone as _tz

    ing_total = Ingredient.objects.count()
    dish_total = Dish.objects.count()

    def _by_status(model):
        return {r["status"]: r["n"] for r in model.objects.values("status").annotate(n=Count("id"))}

    dishes_no_sw = list(
        Dish.objects.filter(name_sw="").order_by("name_en").values("name_en", "slug")[:100]
    )
    ings_no_sw = list(
        Ingredient.objects.filter(name_sw="").order_by("name_en").values("name_en", "slug")[:100]
    )
    ings_no_aliases = list(
        Ingredient.objects.annotate(ac=Count("aliases")).filter(ac=0).order_by("name_en").values("name_en", "slug")[:100]
    )
    dishes_with_steps = set(DishStep.objects.values_list("dish_id", flat=True))
    dishes_no_steps = list(
        Dish.objects.exclude(id__in=dishes_with_steps).values("name_en", "slug")[:100]
    )
    dishes_with_ings = set(DishIngredient.objects.values_list("dish_id", flat=True))
    dishes_no_ings = list(
        Dish.objects.exclude(id__in=dishes_with_ings).values("name_en", "slug")[:100]
    )
    dishes_with_primary = set(
        DishIngredient.objects.filter(role=DishIngredient.Role.PRIMARY).values_list("dish_id", flat=True)
    )
    dishes_no_primary = list(
        Dish.objects.exclude(id__in=dishes_with_primary).values("name_en", "slug")[:100]
    )
    validation_result = scan_dataset()
    violations_by_rule = {}
    for err in validation_result.errors:
        violations_by_rule.setdefault(err.rule, []).append(err.message)

    return Response({
        "generated_at": datetime.now(tz=_tz.utc).isoformat(),
        "counts": {
            "ingredients": {"total": ing_total, "by_status": _by_status(Ingredient)},
            "dishes": {"total": dish_total, "by_status": _by_status(Dish)},
            "aliases": IngredientAlias.objects.count(),
            "dish_ingredients": DishIngredient.objects.count(),
            "dish_steps": DishStep.objects.count(),
            "pairings": Pairing.objects.count(),
            "substitutions": Substitution.objects.count(),
        },
        "gaps": {
            "dishes_missing_swahili": {"count": len(dishes_no_sw), "items": dishes_no_sw},
            "ingredients_missing_swahili": {"count": len(ings_no_sw), "items": ings_no_sw},
            "ingredients_no_aliases": {"count": len(ings_no_aliases), "items": ings_no_aliases},
            "dishes_no_steps": {"count": len(dishes_no_steps), "items": dishes_no_steps},
            "dishes_no_ingredients": {"count": len(dishes_no_ings), "items": dishes_no_ings},
            "dishes_no_primary_ingredient": {"count": len(dishes_no_primary), "items": dishes_no_primary},
        },
        "integrity": {
            "total_violations": len(validation_result.errors),
            "by_rule": {
                rule: {"count": len(msgs), "examples": msgs[:5]}
                for rule, msgs in sorted(violations_by_rule.items())
            },
        },
    })


# ===========================================================================
# CACHE WARM
# ===========================================================================


@extend_schema(tags=["admin:cache"], summary="Warm search cache")
@api_view(["POST"])
@permission_classes(_scope_perm)
def cache_warm(request):
    """Warm the Redis search cache with common queries."""
    try:
        from apps.search.cache import build_cache_key, get_dataset_version, set_cached_result, compute_etag
        from apps.search.engine import search
        from apps.search.pipeline import resolve_ingredients
        from apps.search.serializers import SearchResultItemSerializer
        from apps.search.management.commands.warm_search_cache import _BASELINE_QUERIES

        dataset_version = get_dataset_version()
        warmed = 0
        skipped = 0

        for ingredients in _BASELINE_QUERIES:
            try:
                query = resolve_ingredients(ingredients)
                result = search(query)

                def _ser(items):
                    return SearchResultItemSerializer(items, many=True).data

                payload = {
                    "dataset_version": dataset_version,
                    "mode": "strict",
                    "candidate_count": result.candidate_count,
                    "total_results": result.total_results,
                    "results": {"exact": _ser(result.exact), "can_make": _ser(result.can_make), "almost": _ser(result.almost)},
                }
                etag = compute_etag(payload)
                cache_key = build_cache_key(
                    dataset_version=dataset_version, ingredients=ingredients,
                    exclude=[], mode="strict", meal_type=None, course=None, lang="en", limit=20,
                )
                set_cached_result(cache_key, payload, etag, dataset_version)
                warmed += 1
            except Exception:
                skipped += 1

        return Response({"warmed": warmed, "skipped": skipped, "dataset_version": dataset_version})
    except Exception as e:
        return Response({"error": str(e)}, status=http_status.HTTP_500_INTERNAL_SERVER_ERROR)


# ===========================================================================
# CSV EXPORT
# ===========================================================================


@extend_schema(tags=["admin:data"], summary="Export dataset as CSV (download)")
@api_view(["GET"])
@permission_classes(_scope_perm)
def csv_export(request):
    """
    Export type selected via ?type=ingredients|aliases|dishes|dish_ingredients|snapshot
    Returns a JSON object with row counts and a download token for each file.
    For snapshot, returns counts for all four files.
    For now returns JSON data inline (browser download via FFCC UI).
    """
    import csv
    import io
    from django.http import HttpResponse

    export_type = request.query_params.get("type", "dishes")
    status_filter = request.query_params.get("status")

    valid = {"ingredients", "aliases", "dishes", "dish_ingredients"}
    if export_type not in valid:
        return Response({"error": f"type must be one of {sorted(valid)}"}, status=http_status.HTTP_400_BAD_REQUEST)

    buf = io.StringIO()

    if export_type == "ingredients":
        from apps.ingredients.models import Ingredient
        qs = Ingredient.objects.select_related("category", "typical_unit").order_by("slug")
        if status_filter:
            qs = qs.filter(status=status_filter)
        fieldnames = ["slug", "name_en", "name_sw", "category", "kind", "is_staple", "typical_unit", "status", "notes"]
        w = csv.DictWriter(buf, fieldnames=fieldnames)
        w.writeheader()
        for obj in qs:
            w.writerow({"slug": obj.slug, "name_en": obj.name_en, "name_sw": obj.name_sw or "",
                        "category": obj.category.name_en if obj.category else "", "kind": obj.kind,
                        "is_staple": str(obj.is_staple), "typical_unit": obj.typical_unit.code if obj.typical_unit else "",
                        "status": obj.status, "notes": obj.notes or ""})

    elif export_type == "aliases":
        from apps.ingredients.models import IngredientAlias
        qs = IngredientAlias.objects.select_related("ingredient").order_by("ingredient__slug", "language", "alias")
        fieldnames = ["ingredient_slug", "alias", "normalized_alias", "language", "is_misspelling"]
        w = csv.DictWriter(buf, fieldnames=fieldnames)
        w.writeheader()
        for obj in qs:
            w.writerow({"ingredient_slug": obj.ingredient.slug, "alias": obj.alias,
                        "normalized_alias": obj.normalized_alias, "language": obj.language,
                        "is_misspelling": str(obj.is_misspelling)})

    elif export_type == "dishes":
        qs = Dish.objects.order_by("slug")
        if status_filter:
            qs = qs.filter(status=status_filter)
        fieldnames = ["slug", "name_en", "name_sw", "description", "meal_type", "course",
                      "spice_level", "difficulty", "prep_min", "cook_min", "servings", "quality_level", "status"]
        w = csv.DictWriter(buf, fieldnames=fieldnames)
        w.writeheader()
        for obj in qs:
            w.writerow({"slug": obj.slug, "name_en": obj.name_en, "name_sw": obj.name_sw or "",
                        "description": obj.description or "", "meal_type": obj.meal_type, "course": obj.course,
                        "spice_level": obj.spice_level, "difficulty": obj.difficulty,
                        "prep_min": obj.prep_min, "cook_min": obj.cook_min, "servings": obj.servings,
                        "quality_level": obj.quality_level, "status": obj.status})

    elif export_type == "dish_ingredients":
        from apps.dishes.models import DishIngredient
        qs = DishIngredient.objects.select_related("dish", "ingredient", "unit").order_by("dish__slug", "position")
        if status_filter:
            qs = qs.filter(dish__status=status_filter)
        fieldnames = ["dish_slug", "ingredient_slug", "role", "quantity", "unit", "preparation_note", "position"]
        w = csv.DictWriter(buf, fieldnames=fieldnames)
        w.writeheader()
        for obj in qs:
            w.writerow({"dish_slug": obj.dish.slug, "ingredient_slug": obj.ingredient.slug, "role": obj.role,
                        "quantity": str(obj.quantity) if obj.quantity else "", "unit": obj.unit.code if obj.unit else "",
                        "preparation_note": obj.preparation_note or "", "position": obj.position})

    response = HttpResponse(buf.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{export_type}.csv"'
    return response


# ===========================================================================
# DUPLICATE CHECK
# ===========================================================================


@extend_schema(tags=["admin:qa"], summary="Check for duplicate dishes or ingredients")
@api_view(["GET"])
@permission_classes(_scope_perm)
def duplicate_check(request):
    name = request.query_params.get("name", "").strip()
    entity = request.query_params.get("entity", "dish")
    if not name:
        return Response({"error": "name is required."}, status=http_status.HTTP_400_BAD_REQUEST)
    from apps.curation.duplicate_detector import find_duplicate_dishes, find_duplicate_ingredients
    if entity == "ingredient":
        matches = find_duplicate_ingredients(name)
    else:
        matches = find_duplicate_dishes(name)
    return Response({
        "name": name,
        "entity": entity,
        "matches": [{"name": m.name, "similarity": m.similarity, "pk": m.pk} for m in matches],
    })
