"""
Tests for POST /v1/ingredients/resolve endpoint.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.core.models import StatusChoices
from apps.ingredients.models import Ingredient, IngredientAlias, IngredientCategory


@pytest.fixture
def cat(db):
    c, _ = IngredientCategory.objects.get_or_create(
        slug="veg-resolve-test", defaults={"name_en": "Vegetables"}
    )
    return c


@pytest.fixture
def tomato(db, cat):
    ing, _ = Ingredient.objects.get_or_create(
        slug="tomato-resolve",
        defaults={
            "name_en": "Tomato Resolve",
            "name_sw": "Nyanya Resolve",
            "category": cat,
            "kind": Ingredient.Kind.PRIMARY,
            "is_staple": False,
            "status": StatusChoices.VERIFIED,
        },
    )
    return ing


@pytest.fixture
def nyanya_alias(db, tomato):
    alias, _ = IngredientAlias.objects.get_or_create(
        ingredient=tomato,
        alias="nyanya-resolve",
        defaults={"normalized_alias": "nyanya resolve", "language": "sw"},
    )
    return alias


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
class TestResolveEndpoint:
    def test_returns_200(self, client, tomato) -> None:
        resp = client.post(
            "/v1/ingredients/resolve",
            {"ingredients": ["Tomato Resolve"]},
            format="json",
        )
        assert resp.status_code == 200

    def test_matched_token(self, client, tomato) -> None:
        resp = client.post(
            "/v1/ingredients/resolve",
            {"ingredients": ["Tomato Resolve"]},
            format="json",
        )
        data = resp.json()
        assert data["matched_count"] == 1
        assert data["unmatched_count"] == 0
        result = data["results"][0]
        assert result["status"] == "matched"
        assert result["ingredient_id"] == str(tomato.id)
        assert result["confidence"] == 1.0

    def test_swahili_name_resolved(self, client, tomato) -> None:
        resp = client.post(
            "/v1/ingredients/resolve",
            {"ingredients": ["Nyanya Resolve"]},
            format="json",
        )
        data = resp.json()
        assert data["matched_count"] == 1
        assert data["results"][0]["ingredient_id"] == str(tomato.id)

    def test_unmatched_token(self, client, db) -> None:
        resp = client.post(
            "/v1/ingredients/resolve",
            {"ingredients": ["xyzzy_no_match_99999"]},
            format="json",
        )
        data = resp.json()
        assert resp.status_code == 200
        assert data["unmatched_count"] == 1
        assert data["matched_count"] == 0
        assert data["results"][0]["status"] == "unmatched"

    def test_multiple_tokens(self, client, tomato, db) -> None:
        resp = client.post(
            "/v1/ingredients/resolve",
            {"ingredients": ["Tomato Resolve", "xyzzy_unknown_456"]},
            format="json",
        )
        data = resp.json()
        assert len(data["results"]) == 2
        assert data["matched_count"] == 1
        assert data["unmatched_count"] == 1

    def test_response_has_required_fields(self, client, tomato) -> None:
        resp = client.post(
            "/v1/ingredients/resolve",
            {"ingredients": ["Tomato Resolve"]},
            format="json",
        )
        data = resp.json()
        for key in ("results", "matched_count", "ambiguous_count", "unmatched_count"):
            assert key in data
        r = data["results"][0]
        for key in (
            "token",
            "normalised",
            "status",
            "ingredient_id",
            "method",
            "confidence",
            "options",
        ):
            assert key in r

    def test_empty_list_returns_400(self, client, db) -> None:
        resp = client.post(
            "/v1/ingredients/resolve",
            {"ingredients": []},
            format="json",
        )
        assert resp.status_code == 400

    def test_too_many_ingredients_returns_400(self, client, db) -> None:
        resp = client.post(
            "/v1/ingredients/resolve",
            {"ingredients": [f"item{i}" for i in range(35)]},
            format="json",
        )
        assert resp.status_code == 400

    def test_method_field_set(self, client, tomato) -> None:
        resp = client.post(
            "/v1/ingredients/resolve",
            {"ingredients": ["Tomato Resolve"]},
            format="json",
        )
        r = resp.json()["results"][0]
        assert r["method"] in ("exact_name", "exact_alias", "fuzzy")
