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
from apps.dishes.models import Dish
from apps.ingredients.models import Ingredient
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
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


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
    # Filters
    if status_f := request.query_params.get("status"):
        qs = qs.filter(status=status_f)
    if meal_type := request.query_params.get("meal_type"):
        qs = qs.filter(meal_type=meal_type)
    if course := request.query_params.get("course"):
        qs = qs.filter(course=course)
    if search := request.query_params.get("search"):
        qs = qs.filter(Q(name_en__icontains=search) | Q(name_sw__icontains=search))
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
    if search := request.query_params.get("search"):
        qs = qs.filter(Q(name_en__icontains=search) | Q(name_sw__icontains=search))
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
