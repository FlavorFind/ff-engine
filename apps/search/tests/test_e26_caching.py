"""
E26 Tests — Search caching, dataset version tracking, ETag / Cache-Control.

Covers:
  - Cache hit / miss via X-Cache-Hit header
  - Deterministic cache keys (different inputs → different keys)
  - Dataset version invalidation
  - ETag returned and If-None-Match → 304
  - Cache-Control header
  - clear_search_cache() invalidation
  - get_dataset_version() fallback to settings
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.clients.keys import create_key
from apps.clients.models import ApiClient, ApiKey
from apps.core.models import StatusChoices
from apps.dishes.models import Dish, DishIngredient
from apps.ingredients.models import Ingredient, IngredientCategory
from apps.search.staples import invalidate_staple_cache


@pytest.fixture
def api_client(db):
    """Authenticated API client with read:search scope."""
    client_record = ApiClient.objects.create(
        name="_test_e26_client", type=ApiClient.ClientType.TEST
    )
    _, raw_key = create_key(client_record, scopes=[ApiKey.SCOPE_READ_SEARCH])
    c = APIClient()
    c.credentials(HTTP_X_API_KEY=raw_key)
    return c


# ===========================================================================
# Shared fixtures (mirror test_e21_e25.py to keep tests independent)
# ===========================================================================


@pytest.fixture
def veg_cat(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="vegetables-e26", defaults={"name_en": "Vegetables"}
    )
    return cat


@pytest.fixture
def grain_cat(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="grains-e26", defaults={"name_en": "Grains"}
    )
    return cat


@pytest.fixture
def liquid_cat(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="liquids-e26", defaults={"name_en": "Liquids"}
    )
    return cat


@pytest.fixture
def spice_cat(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="spices-e26", defaults={"name_en": "Spices"}
    )
    return cat


@pytest.fixture
def tomato(db, veg_cat):
    ing, _ = Ingredient.objects.get_or_create(
        slug="tomato-e26",
        defaults={
            "name_en": "Tomato E26",
            "category": veg_cat,
            "kind": Ingredient.Kind.PRIMARY,
            "is_staple": False,
            "status": StatusChoices.VERIFIED,
        },
    )
    return ing


@pytest.fixture
def onion(db, veg_cat):
    ing, _ = Ingredient.objects.get_or_create(
        slug="onion-e26",
        defaults={
            "name_en": "Onion E26",
            "category": veg_cat,
            "kind": Ingredient.Kind.PRIMARY,
            "is_staple": False,
            "status": StatusChoices.VERIFIED,
        },
    )
    return ing


@pytest.fixture
def maize_flour(db, grain_cat):
    ing, _ = Ingredient.objects.get_or_create(
        slug="maize-flour-e26",
        defaults={
            "name_en": "Maize Flour E26",
            "name_sw": "Unga wa mahindi E26",
            "category": grain_cat,
            "kind": Ingredient.Kind.PRIMARY,
            "is_staple": False,
            "status": StatusChoices.VERIFIED,
        },
    )
    return ing


@pytest.fixture
def salt(db, spice_cat):
    invalidate_staple_cache()
    ing, _ = Ingredient.objects.get_or_create(
        slug="salt-e26",
        defaults={
            "name_en": "Salt E26",
            "category": spice_cat,
            "kind": Ingredient.Kind.STAPLE,
            "is_staple": True,
            "status": StatusChoices.VERIFIED,
        },
    )
    invalidate_staple_cache()
    return ing


@pytest.fixture
def water(db, liquid_cat):
    invalidate_staple_cache()
    ing, _ = Ingredient.objects.get_or_create(
        slug="water-e26",
        defaults={
            "name_en": "Water E26",
            "category": liquid_cat,
            "kind": Ingredient.Kind.STAPLE,
            "is_staple": True,
            "status": StatusChoices.VERIFIED,
        },
    )
    invalidate_staple_cache()
    return ing


def _make_dish(slug, name, ing_roles, status=StatusChoices.VERIFIED):
    dish, _ = Dish.objects.get_or_create(
        slug=slug,
        defaults={
            "name_en": name,
            "meal_type": Dish.MealType.LUNCH,
            "course": Dish.Course.MAIN,
            "spice_level": Dish.SpiceLevel.MILD,
            "difficulty": Dish.Difficulty.EASY,
            "prep_min": 5,
            "cook_min": 20,
            "status": status,
            "popularity": 0.5,
            "quality_level": Dish.QualityLevel.VERIFIED,
        },
    )
    pos = 0
    for ing, role in ing_roles:
        DishIngredient.objects.get_or_create(
            dish=dish,
            ingredient=ing,
            defaults={"role": role, "quantity": 1, "position": pos},
        )
        pos += 1
    dish.rebuild_search_arrays()
    return dish


@pytest.fixture
def ugali(db, maize_flour, salt, water):
    return _make_dish(
        "ugali-e26",
        "Ugali E26",
        [
            (maize_flour, DishIngredient.Role.PRIMARY),
            (salt, DishIngredient.Role.OPTIONAL),
            (water, DishIngredient.Role.REQUIRED),
        ],
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure a clean cache before each test."""
    cache.clear()
    yield
    cache.clear()


# ===========================================================================
# get_dataset_version
# ===========================================================================


@pytest.mark.django_db
class TestGetDatasetVersion:
    def test_returns_settings_default_when_no_releases(self, db) -> None:
        from apps.search.cache import get_dataset_version

        # No DatasetRelease rows → fallback to settings.DATASET_VERSION
        version = get_dataset_version()
        assert version == "0.0.0"

    def test_returns_latest_release_version(self, db) -> None:
        from apps.curation.models import DatasetRelease
        from apps.search.cache import get_dataset_version

        DatasetRelease.objects.create(version="2026.10.0")
        DatasetRelease.objects.create(version="2026.12.0")
        version = get_dataset_version()
        assert version == "2026.12.0"


# ===========================================================================
# Cache key building
# ===========================================================================


class TestCacheKey:
    def test_same_inputs_same_key(self) -> None:
        from apps.search.cache import build_cache_key

        key1 = build_cache_key("1.0.0", ["tomato", "onion"], [], "strict", None, None, "en", 20)
        key2 = build_cache_key("1.0.0", ["tomato", "onion"], [], "strict", None, None, "en", 20)
        assert key1 == key2

    def test_different_ingredients_different_keys(self) -> None:
        from apps.search.cache import build_cache_key

        key1 = build_cache_key("1.0.0", ["tomato"], [], "strict", None, None, "en", 20)
        key2 = build_cache_key("1.0.0", ["onion"], [], "strict", None, None, "en", 20)
        assert key1 != key2

    def test_ingredient_order_does_not_matter(self) -> None:
        from apps.search.cache import build_cache_key

        key1 = build_cache_key("1.0.0", ["tomato", "onion"], [], "strict", None, None, "en", 20)
        key2 = build_cache_key("1.0.0", ["onion", "tomato"], [], "strict", None, None, "en", 20)
        assert key1 == key2

    def test_different_mode_different_keys(self) -> None:
        from apps.search.cache import build_cache_key

        key1 = build_cache_key("1.0.0", ["tomato"], [], "strict", None, None, "en", 20)
        key2 = build_cache_key("1.0.0", ["tomato"], [], "explore", None, None, "en", 20)
        assert key1 != key2

    def test_different_limit_different_keys(self) -> None:
        from apps.search.cache import build_cache_key

        key1 = build_cache_key("1.0.0", ["tomato"], [], "strict", None, None, "en", 10)
        key2 = build_cache_key("1.0.0", ["tomato"], [], "strict", None, None, "en", 20)
        assert key1 != key2

    def test_different_dataset_version_different_keys(self) -> None:
        from apps.search.cache import build_cache_key

        key1 = build_cache_key("1.0.0", ["tomato"], [], "strict", None, None, "en", 20)
        key2 = build_cache_key("2.0.0", ["tomato"], [], "strict", None, None, "en", 20)
        assert key1 != key2

    def test_different_exclude_different_keys(self) -> None:
        from apps.search.cache import build_cache_key

        key1 = build_cache_key("1.0.0", ["tomato"], [], "strict", None, None, "en", 20)
        key2 = build_cache_key("1.0.0", ["tomato"], ["salt"], "strict", None, None, "en", 20)
        assert key1 != key2

    def test_different_lang_different_keys(self) -> None:
        from apps.search.cache import build_cache_key

        key1 = build_cache_key("1.0.0", ["tomato"], [], "strict", None, None, "en", 20)
        key2 = build_cache_key("1.0.0", ["tomato"], [], "strict", None, None, "sw", 20)
        assert key1 != key2


# ===========================================================================
# Search endpoint caching behaviour
# ===========================================================================


@pytest.mark.django_db
class TestSearchCachingEndpoint:
    def test_first_request_is_cache_miss(self, api_client, ugali, maize_flour, salt, water) -> None:
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Maize Flour E26"]},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.headers["X-Cache-Hit"] == "false"

    def test_second_request_is_cache_hit(self, api_client, ugali, maize_flour, salt, water) -> None:
        invalidate_staple_cache()
        body = {"ingredients": ["Maize Flour E26"]}
        api_client.post("/v1/search/by-ingredients", body, format="json")
        resp = api_client.post("/v1/search/by-ingredients", body, format="json")
        assert resp.status_code == 200
        assert resp.headers["X-Cache-Hit"] == "true"

    def test_cache_hit_returns_same_result(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        invalidate_staple_cache()
        body = {"ingredients": ["Maize Flour E26"]}
        first = api_client.post("/v1/search/by-ingredients", body, format="json").json()
        second = api_client.post("/v1/search/by-ingredients", body, format="json").json()
        assert first == second

    def test_different_inputs_different_cache_entries(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        invalidate_staple_cache()
        # First request: maize flour
        resp1 = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Maize Flour E26"]},
            format="json",
        )
        # Second request: tomato (different input) — should be a miss
        resp2 = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Tomato E26"]},
            format="json",
        )
        assert resp1.headers["X-Cache-Hit"] == "false"
        assert resp2.headers["X-Cache-Hit"] == "false"

    def test_cache_control_header_present(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Maize Flour E26"]},
            format="json",
        )
        assert resp.status_code == 200
        assert "cache-control" in {k.lower() for k in resp.headers}
        assert resp.headers["Cache-Control"] == "private, max-age=300"

    def test_etag_header_present(self, api_client, ugali, maize_flour, salt, water) -> None:
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Maize Flour E26"]},
            format="json",
        )
        assert resp.status_code == 200
        etag = resp.headers.get("ETag")
        assert etag
        assert len(etag) > 0

    def test_if_none_match_returns_304(self, api_client, ugali, maize_flour, salt, water) -> None:
        invalidate_staple_cache()
        body = {"ingredients": ["Maize Flour E26"]}
        # First request to populate cache and get ETag
        resp1 = api_client.post("/v1/search/by-ingredients", body, format="json")
        etag = resp1.headers["ETag"]

        # Second request with If-None-Match → 304
        resp2 = api_client.post(
            "/v1/search/by-ingredients",
            body,
            format="json",
            HTTP_IF_NONE_MATCH=etag,
        )
        assert resp2.status_code == 304

    def test_if_none_match_mismatch_returns_200(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        invalidate_staple_cache()
        body = {"ingredients": ["Maize Flour E26"]}
        api_client.post("/v1/search/by-ingredients", body, format="json")

        resp = api_client.post(
            "/v1/search/by-ingredients",
            body,
            format="json",
            HTTP_IF_NONE_MATCH='"bogus-etag-xyz"',
        )
        assert resp.status_code == 200

    def test_etag_consistent_across_requests(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        invalidate_staple_cache()
        body = {"ingredients": ["Maize Flour E26"]}
        resp1 = api_client.post("/v1/search/by-ingredients", body, format="json")
        resp2 = api_client.post("/v1/search/by-ingredients", body, format="json")
        assert resp1.headers["ETag"] == resp2.headers["ETag"]


# ===========================================================================
# Cache invalidation
# ===========================================================================


@pytest.mark.django_db
class TestCacheInvalidation:
    def test_clear_search_cache_allows_recompute(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        from apps.search.cache import clear_search_cache

        invalidate_staple_cache()
        body = {"ingredients": ["Maize Flour E26"]}
        # Prime cache
        api_client.post("/v1/search/by-ingredients", body, format="json")
        # Invalidate
        clear_search_cache()
        # Next request should be a miss
        resp = api_client.post("/v1/search/by-ingredients", body, format="json")
        assert resp.headers["X-Cache-Hit"] == "false"

    def test_clear_search_cache_specific_version(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        from apps.search.cache import (
            build_cache_key,
            clear_search_cache,
            compute_etag,
            get_dataset_version,
            set_cached_result,
        )

        version = get_dataset_version()
        key = build_cache_key(version, ["tomato"], [], "strict", None, None, "en", 20)
        payload = {"dataset_version": version, "total_results": 0}
        etag = compute_etag(payload)
        set_cached_result(key, payload, etag, version)

        clear_search_cache(version)
        from django.core.cache import cache as django_cache

        assert django_cache.get(key) is None

    def test_dataset_release_creates_clears_cache(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        from apps.curation.models import DatasetRelease

        invalidate_staple_cache()
        body = {"ingredients": ["Maize Flour E26"]}
        # Prime cache
        resp1 = api_client.post("/v1/search/by-ingredients", body, format="json")
        assert resp1.headers["X-Cache-Hit"] == "false"

        # Create a DatasetRelease → triggers clear_search_cache signal
        DatasetRelease.objects.create(version="2026.12.0")

        # Next request should be a miss (cache was cleared)
        resp2 = api_client.post("/v1/search/by-ingredients", body, format="json")
        assert resp2.headers["X-Cache-Hit"] == "false"


# ===========================================================================
# Dataset version in response
# ===========================================================================


@pytest.mark.django_db
class TestDatasetVersionInResponse:
    def test_response_reports_dataset_version(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Maize Flour E26"]},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["dataset_version"] == "0.0.0"

    def test_response_reports_release_version_when_exists(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        from apps.curation.models import DatasetRelease

        DatasetRelease.objects.create(version="2026.12.0")
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Maize Flour E26"]},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.json()["dataset_version"] == "2026.12.0"
