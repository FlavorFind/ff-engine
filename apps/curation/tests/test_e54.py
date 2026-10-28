"""
E54 — Dataset diff endpoint tests.

GET /v1/datasets/diff?since=VERSION returns dishes and ingredients added,
changed or removed between the given dataset version and the current one.
Requires the read:catalog API key scope.

Coverage:
  - Scope gate: no key → 401; read:search key → 403; read:catalog key → 200
  - Missing 'since' parameter → 400
  - Unknown version → 404
  - Response shape (dishes/ingredients sections)
  - Dishes created after a release appear in "added"
  - Draft dishes are excluded from "added"
  - Dishes existing before the release are not in "added"
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.clients.keys import create_key
from apps.clients.models import ApiClient, ApiKey
from apps.core.models import StatusChoices
from apps.curation.models import DatasetRelease
from apps.dishes.models import Dish


def _make_key(scopes: list[str], name: str) -> tuple[APIClient, ApiClient]:
    client_rec = ApiClient.objects.create(name=name)
    _, raw_key = create_key(client_rec, scopes=scopes)
    api = APIClient()
    api.credentials(HTTP_X_API_KEY=raw_key)
    return api, client_rec


def _dish(slug: str, status: str = StatusChoices.REVIEWED) -> Dish:
    dish, _ = Dish.objects.get_or_create(
        slug=slug,
        defaults={"name_en": slug.replace("-", " ").title(), "status": status},
    )
    return dish


@pytest.mark.django_db
class TestDatasetDiffScope:
    def test_no_key_returns_401(self):
        api = APIClient()
        resp = api.get("/v1/datasets/diff/?since=2099.01.0")
        assert resp.status_code == 401

    def test_wrong_scope_returns_403(self):
        api, _ = _make_key([ApiKey.SCOPE_READ_SEARCH], "_e54-search")
        resp = api.get("/v1/datasets/diff/?since=2099.01.0")
        assert resp.status_code == 403

    def test_read_catalog_key_succeeds(self):
        api, _ = _make_key([ApiKey.SCOPE_READ_CATALOG], "_e54-catalog")
        DatasetRelease.objects.create(version="2099.01.0", counts={})
        resp = api.get("/v1/datasets/diff/?since=2099.01.0")
        assert resp.status_code == 200


@pytest.mark.django_db
class TestDatasetDiffBehaviour:
    def test_missing_since_returns_400(self):
        api, _ = _make_key([ApiKey.SCOPE_READ_CATALOG], "_e54-nosince")
        resp = api.get("/v1/datasets/diff/")
        assert resp.status_code == 400

    def test_unknown_version_returns_404(self):
        api, _ = _make_key([ApiKey.SCOPE_READ_CATALOG], "_e54-unknown")
        resp = api.get("/v1/datasets/diff/?since=0000.00.0")
        assert resp.status_code == 404

    def test_response_shape(self):
        api, _ = _make_key([ApiKey.SCOPE_READ_CATALOG], "_e54-shape")
        DatasetRelease.objects.create(version="2099.01.0", counts={})
        data = api.get("/v1/datasets/diff/?since=2099.01.0").json()
        assert data["since_version"] == "2099.01.0"
        assert "current_version" in data
        assert "generated_at" in data
        assert set(data["dishes"]) == {"added", "changed", "removed"}
        assert set(data["ingredients"]) == {"added", "removed"}

    def test_dishes_added_after_release(self):
        api, _ = _make_key([ApiKey.SCOPE_READ_CATALOG], "_e54-added")
        DatasetRelease.objects.create(version="2099.01.0", counts={})
        _dish("e54-new-1")
        _dish("e54-new-2")
        added = {
            d["slug"]
            for d in api.get("/v1/datasets/diff/?since=2099.01.0").json()["dishes"]["added"]
        }
        assert "e54-new-1" in added
        assert "e54-new-2" in added

    def test_draft_dishes_excluded_from_added(self):
        api, _ = _make_key([ApiKey.SCOPE_READ_CATALOG], "_e54-draft")
        DatasetRelease.objects.create(version="2099.01.0", counts={})
        _dish("e54-draft-dish", status=StatusChoices.DRAFT)
        added = {
            d["slug"]
            for d in api.get("/v1/datasets/diff/?since=2099.01.0").json()["dishes"]["added"]
        }
        assert "e54-draft-dish" not in added

    def test_existing_dish_not_in_added(self):
        api, _ = _make_key([ApiKey.SCOPE_READ_CATALOG], "_e54-existing")
        _dish("e54-old-dish")
        DatasetRelease.objects.create(version="2099.01.0", counts={})
        added = {
            d["slug"]
            for d in api.get("/v1/datasets/diff/?since=2099.01.0").json()["dishes"]["added"]
        }
        assert "e54-old-dish" not in added

    def test_added_item_has_fields(self):
        api, _ = _make_key([ApiKey.SCOPE_READ_CATALOG], "_e54-fields")
        DatasetRelease.objects.create(version="2099.01.0", counts={})
        _dish("e54-field-dish")
        added = api.get("/v1/datasets/diff/?since=2099.01.0").json()["dishes"]["added"]
        assert added, "expected at least one added dish"
        item = next(d for d in added if d["slug"] == "e54-field-dish")
        assert set(item) == {"slug", "name_en", "changed_at"}
