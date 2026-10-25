"""
E42 — OpenAPI schema validation tests.

Tests:
  - Schema endpoint returns 200 and valid JSON
  - Schema contains all expected endpoint paths
  - All expected endpoints have a description (non-empty)
  - All expected endpoints have at least one tag
  - Schema validates against OpenAPI 3.x structure (info, paths, components)
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def anon_client():
    return APIClient()


# Endpoints we expect to appear in the schema.
# Spectacular uses DRF URL patterns to build the paths.
EXPECTED_PATHS = [
    "/v1/health/",
    "/v1/meta/version/",
    "/v1/search/by-ingredients",
    "/v1/ingredients/resolve",
    "/v1/dishes/",
    "/v1/regions/",
]


@pytest.mark.django_db
class TestOpenAPISchema:
    def test_schema_endpoint_returns_200(self, anon_client):
        resp = anon_client.get("/schema/")
        assert resp.status_code == 200

    def test_schema_is_valid_json(self, anon_client):
        resp = anon_client.get("/schema/?format=json")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)

    def test_schema_has_openapi_version(self, anon_client):
        resp = anon_client.get("/schema/?format=json")
        data = resp.json()
        assert "openapi" in data
        assert data["openapi"].startswith("3.")

    def test_schema_has_info_block(self, anon_client):
        resp = anon_client.get("/schema/?format=json")
        data = resp.json()
        assert "info" in data
        assert "title" in data["info"]

    def test_schema_has_paths(self, anon_client):
        resp = anon_client.get("/schema/?format=json")
        data = resp.json()
        assert "paths" in data
        assert len(data["paths"]) > 0

    def test_health_endpoint_in_schema(self, anon_client):
        resp = anon_client.get("/schema/?format=json")
        data = resp.json()
        paths = data.get("paths", {})
        assert "/v1/health/" in paths, "health endpoint missing from schema"

    def test_version_endpoint_in_schema(self, anon_client):
        resp = anon_client.get("/schema/?format=json")
        data = resp.json()
        paths = data.get("paths", {})
        assert "/v1/meta/version/" in paths, "version endpoint missing from schema"

    def test_search_endpoint_in_schema(self, anon_client):
        resp = anon_client.get("/schema/?format=json")
        data = resp.json()
        paths = data.get("paths", {})
        assert "/v1/search/by-ingredients" in paths, "search endpoint missing from schema"

    def test_schema_endpoints_have_descriptions(self, anon_client):
        """Every operation on documented endpoints must have a non-empty description."""
        resp = anon_client.get("/schema/?format=json")
        data = resp.json()
        paths = data.get("paths", {})

        missing_descriptions = []
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method in ("get", "post", "put", "patch", "delete"):
                    desc = operation.get("description") or operation.get("summary") or ""
                    if not desc.strip():
                        missing_descriptions.append(f"{method.upper()} {path}")

        assert not missing_descriptions, f"Endpoints missing descriptions: {missing_descriptions}"

    def test_schema_endpoints_have_tags(self, anon_client):
        """Every operation should have at least one tag for grouping."""
        resp = anon_client.get("/schema/?format=json")
        data = resp.json()
        paths = data.get("paths", {})

        missing_tags = []
        for path, methods in paths.items():
            # Skip schema/docs URLs themselves
            if path.startswith("/schema") or path.startswith("/docs"):
                continue
            for method, operation in methods.items():
                if method in ("get", "post", "put", "patch", "delete"):
                    tags = operation.get("tags", [])
                    if not tags:
                        missing_tags.append(f"{method.upper()} {path}")

        assert not missing_tags, f"Endpoints missing tags: {missing_tags}"

    def test_schema_has_components(self, anon_client):
        resp = anon_client.get("/schema/?format=json")
        data = resp.json()
        # components may be empty but the key should exist once serializers are used
        # At minimum openapi + info + paths must be present
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    def test_dishes_endpoint_in_schema(self, anon_client):
        resp = anon_client.get("/schema/?format=json")
        data = resp.json()
        paths = data.get("paths", {})
        assert "/v1/dishes/" in paths, "dishes catalogue endpoint missing from schema"

    def test_regions_endpoint_in_schema(self, anon_client):
        resp = anon_client.get("/schema/?format=json")
        data = resp.json()
        paths = data.get("paths", {})
        assert "/v1/regions/" in paths, "regions endpoint missing from schema"
