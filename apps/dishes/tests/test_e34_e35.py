"""
Tests for E34 + E35.

E34 — Golden set has 100 cases (file-level check only; full run is via run_golden_set command)
E35 — Regions list endpoint + Dishes catalogue endpoint
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from rest_framework.test import APIClient


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def api():
    return APIClient()


# ─────────────────────────────────────────────────────────────────────────────
# E34 — Golden set structure
# ─────────────────────────────────────────────────────────────────────────────

class TestGoldenSetStructure:
    def test_golden_set_has_100_cases(self):
        """golden_set_v0.json must have exactly 100 cases."""
        path = Path(__file__).parents[3] / "data" / "golden" / "golden_set_v0.json"
        data = json.loads(path.read_text())
        assert len(data["cases"]) == 100

    def test_golden_set_ids_are_sequential(self):
        """Case IDs must run G01–G100 with no gaps."""
        path = Path(__file__).parents[3] / "data" / "golden" / "golden_set_v0.json"
        data = json.loads(path.read_text())
        ids = [c["id"] for c in data["cases"]]
        expected = [f"G{i:02d}" for i in range(1, 101)]
        assert ids == expected

    def test_every_case_has_inputs_and_expect(self):
        """Every case must have inputs[] and expect{}. inputs may be empty (edge case tests)."""
        path = Path(__file__).parents[3] / "data" / "golden" / "golden_set_v0.json"
        data = json.loads(path.read_text())
        for case in data["cases"]:
            assert "inputs" in case, f"{case['id']} missing inputs"
            assert "expect" in case, f"{case['id']} missing expect"
            assert isinstance(case["inputs"], list), f"{case['id']} inputs must be a list"


# ─────────────────────────────────────────────────────────────────────────────
# E35 — Regions endpoint
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestRegionsList:
    def test_regions_returns_200(self, api, seeded_db):
        resp = api.get("/v1/regions/")
        assert resp.status_code == 200

    def test_regions_returns_count_and_results(self, api, seeded_db):
        resp = api.get("/v1/regions/")
        data = resp.json()
        assert "count" in data
        assert "results" in data
        assert data["count"] == len(data["results"])

    def test_regions_seeded_has_15_regions(self, api, seeded_db):
        resp = api.get("/v1/regions/")
        assert resp.json()["count"] == 15

    def test_region_has_expected_fields(self, api, seeded_db):
        resp = api.get("/v1/regions/")
        r = resp.json()["results"][0]
        for field in ["id", "slug", "name", "type", "parent_slug", "description"]:
            assert field in r, f"Missing field: {field}"

    def test_regions_filter_by_type_cuisine(self, api, seeded_db):
        resp = api.get("/v1/regions/?type=cuisine")
        data = resp.json()
        assert data["count"] > 0
        for r in data["results"]:
            assert r["type"] == "cuisine"

    def test_regions_filter_by_type_coast(self, api, seeded_db):
        resp = api.get("/v1/regions/?type=coast")
        data = resp.json()
        assert data["count"] > 0
        for r in data["results"]:
            assert r["type"] == "coast"

    def test_regions_parent_slug_set_for_children(self, api, seeded_db):
        resp = api.get("/v1/regions/")
        results = resp.json()["results"]
        # kenya-coast has parent kenya
        coast = next((r for r in results if r["slug"] == "kenya-coast"), None)
        assert coast is not None
        assert coast["parent_slug"] == "kenya"

    def test_regions_parent_slug_none_for_top_level(self, api, seeded_db):
        resp = api.get("/v1/regions/")
        results = resp.json()["results"]
        kenya = next((r for r in results if r["slug"] == "kenya"), None)
        assert kenya is not None
        assert kenya["parent_slug"] is None


# ─────────────────────────────────────────────────────────────────────────────
# E35 — Dishes catalogue endpoint
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestDishCatalogue:
    def test_catalogue_returns_200(self, api, seeded_db):
        resp = api.get("/v1/dishes/")
        assert resp.status_code == 200

    def test_catalogue_returns_count_and_results(self, api, seeded_db):
        data = api.get("/v1/dishes/").json()
        assert "count" in data
        assert "results" in data
        assert "limit" in data
        assert "offset" in data

    def test_catalogue_default_limit_is_50(self, api, seeded_db):
        data = api.get("/v1/dishes/").json()
        assert len(data["results"]) <= 50

    def test_catalogue_dish_has_expected_fields(self, api, seeded_db):
        data = api.get("/v1/dishes/").json()
        d = data["results"][0]
        for field in ["id", "slug", "name_en", "meal_type", "course", "difficulty", "status"]:
            assert field in d, f"Missing field: {field}"

    def test_catalogue_filter_meal_type(self, api, seeded_db):
        resp = api.get("/v1/dishes/?meal_type=breakfast")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] > 0
        for d in data["results"]:
            assert d["meal_type"] == "breakfast"

    def test_catalogue_filter_course_main(self, api, seeded_db):
        resp = api.get("/v1/dishes/?course=main")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] > 0
        for d in data["results"]:
            assert d["course"] == "main"

    def test_catalogue_invalid_meal_type_returns_400(self, api, seeded_db):
        resp = api.get("/v1/dishes/?meal_type=invalid_type")
        assert resp.status_code == 400

    def test_catalogue_invalid_course_returns_400(self, api, seeded_db):
        resp = api.get("/v1/dishes/?course=invalid_course")
        assert resp.status_code == 400

    def test_catalogue_q_filter_returns_matching_dishes(self, api, seeded_db):
        resp = api.get("/v1/dishes/?q=ugali")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        slugs = [d["slug"] for d in data["results"]]
        assert "ugali" in slugs

    def test_catalogue_q_filter_no_match_returns_empty(self, api, seeded_db):
        resp = api.get("/v1/dishes/?q=xyzzy_no_such_dish_9999")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0

    def test_catalogue_limit_and_offset(self, api, seeded_db):
        all_data = api.get("/v1/dishes/?limit=200").json()
        total = all_data["count"]
        page1 = api.get("/v1/dishes/?limit=10&offset=0").json()
        page2 = api.get("/v1/dishes/?limit=10&offset=10").json()
        assert len(page1["results"]) == 10
        assert len(page2["results"]) == 10
        slugs1 = {d["slug"] for d in page1["results"]}
        slugs2 = {d["slug"] for d in page2["results"]}
        assert slugs1.isdisjoint(slugs2)
        assert page1["count"] == total

    def test_catalogue_total_dishes_is_219_or_more(self, api, seeded_db):
        data = api.get("/v1/dishes/?limit=1").json()
        assert data["count"] >= 219
