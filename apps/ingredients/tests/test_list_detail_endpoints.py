"""
Tests for P1-2 and P1-3:
  GET /v1/ingredients/         — ingredient list with autocomplete + category filter
  GET /v1/ingredients/{slug}/  — ingredient detail with aliases and allergens
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.clients.keys import create_key
from apps.clients.models import ApiClient, ApiKey


@pytest.fixture
def api(db):
    """Authenticated API client with read:catalog scope (required since PR #64)."""
    client_record = ApiClient.objects.create(
        name="_test_ingredients_client", type=ApiClient.ClientType.TEST
    )
    _, raw_key = create_key(client_record, scopes=[ApiKey.SCOPE_READ_CATALOG])
    c = APIClient()
    c.credentials(HTTP_X_API_KEY=raw_key)
    return c


# ─────────────────────────────────────────────────────────────────────────────
# List endpoint
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestIngredientList:
    def test_list_returns_200(self, api, seeded_db):
        resp = api.get("/v1/ingredients/")
        assert resp.status_code == 200

    def test_list_has_pagination_fields(self, api, seeded_db):
        data = api.get("/v1/ingredients/").json()
        for field in ["count", "limit", "offset", "results"]:
            assert field in data, f"Missing pagination field: {field}"

    def test_list_returns_many_ingredients(self, api, seeded_db):
        data = api.get("/v1/ingredients/?limit=1").json()
        assert data["count"] >= 878, f"Expected ≥878 ingredients, got {data['count']}"

    def test_list_result_has_required_fields(self, api, seeded_db):
        data = api.get("/v1/ingredients/?limit=1").json()
        ing = data["results"][0]
        for field in ["slug", "name_en", "name_sw", "kind", "is_staple", "category", "status"]:
            assert field in ing, f"Missing field: {field}"

    def test_list_excludes_draft_ingredients(self, api, seeded_db):
        data = api.get("/v1/ingredients/?limit=200").json()
        for ing in data["results"]:
            assert (
                ing["status"] != "draft"
            ), f"Draft ingredient {ing['slug']} returned by public list"

    def test_list_q_filter_english(self, api, seeded_db):
        """?q=tomato must return the tomato ingredient."""
        resp = api.get("/v1/ingredients/?q=tomato")
        assert resp.status_code == 200
        slugs = [i["slug"] for i in resp.json()["results"]]
        assert "tomato" in slugs

    def test_list_q_filter_swahili_alias(self, api, seeded_db):
        """?q=nyanya must find tomato via the seeded alias."""
        resp = api.get("/v1/ingredients/?q=nyanya")
        assert resp.status_code == 200
        slugs = [i["slug"] for i in resp.json()["results"]]
        assert "tomato" in slugs, f"tomato not found via nyanya alias; got: {slugs[:5]}"

    def test_list_category_filter(self, api, seeded_db):
        """?category=<slug> must return only ingredients in that category."""
        # Get a valid category slug from the first result
        all_data = api.get("/v1/ingredients/?limit=5").json()
        cat_slug = all_data["results"][0]["category"]
        if not cat_slug:
            pytest.skip("No category slug available in first result")

        resp = api.get(f"/v1/ingredients/?category={cat_slug}&limit=100")
        assert resp.status_code == 200
        for ing in resp.json()["results"]:
            assert ing["category"] == cat_slug

    def test_list_pagination(self, api, seeded_db):
        """Offset and limit must page through non-overlapping results."""
        p1 = api.get("/v1/ingredients/?limit=10&offset=0").json()
        p2 = api.get("/v1/ingredients/?limit=10&offset=10").json()
        slugs1 = {i["slug"] for i in p1["results"]}
        slugs2 = {i["slug"] for i in p2["results"]}
        assert slugs1.isdisjoint(slugs2), "Pages overlap — pagination is broken"

    def test_list_limit_capped_at_200(self, api, seeded_db):
        """Requesting limit=500 must return at most 200 results."""
        data = api.get("/v1/ingredients/?limit=500").json()
        assert len(data["results"]) <= 200


# ─────────────────────────────────────────────────────────────────────────────
# Detail endpoint
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestIngredientDetail:
    def test_detail_returns_200(self, api, seeded_db):
        resp = api.get("/v1/ingredients/tomato/")
        assert resp.status_code == 200

    def test_detail_unknown_slug_returns_404(self, api, seeded_db):
        resp = api.get("/v1/ingredients/no-such-ingredient-xyzzy/")
        assert resp.status_code == 404

    def test_detail_has_required_fields(self, api, seeded_db):
        data = api.get("/v1/ingredients/tomato/").json()
        for field in [
            "slug",
            "name_en",
            "name_sw",
            "kind",
            "is_staple",
            "category",
            "status",
            "aliases",
            "allergens",
        ]:
            assert field in data, f"Missing field: {field}"

    def test_detail_tomato_has_nyanya_alias(self, api, seeded_db):
        """Tomato detail must include the 'nyanya' Swahili alias."""
        data = api.get("/v1/ingredients/tomato/").json()
        alias_texts = [a["alias"] for a in data["aliases"]]
        assert "nyanya" in alias_texts, f"nyanya not in tomato aliases: {alias_texts}"

    def test_detail_alias_has_language_field(self, api, seeded_db):
        """Each alias must include language and is_misspelling fields."""
        data = api.get("/v1/ingredients/tomato/").json()
        assert len(data["aliases"]) > 0
        for alias in data["aliases"]:
            assert "alias" in alias
            assert "language" in alias
            assert "is_misspelling" in alias

    def test_detail_salt_is_staple(self, api, seeded_db):
        """Salt must be flagged as a staple ingredient."""
        data = api.get("/v1/ingredients/salt/").json()
        assert data["is_staple"] is True

    def test_detail_excludes_draft(self, api, seeded_db):
        """Draft ingredients must not be accessible via the detail endpoint."""
        from apps.ingredients.models import Ingredient

        Ingredient.objects.filter(slug="tomato").update(status="draft")
        resp = api.get("/v1/ingredients/tomato/")
        assert resp.status_code == 404
        # Restore
        Ingredient.objects.filter(slug="tomato").update(status="reviewed")
