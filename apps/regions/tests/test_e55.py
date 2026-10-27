"""
E55 — Regions and units seed tests.

Verifies data/seeds/regions.csv and data/seeds/units.csv contain the
expected content without touching the database.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

SEEDS_DIR = Path(__file__).resolve().parents[4] / "data" / "seeds"


@pytest.mark.fast
class TestRegionsCSV:
    def test_has_47_counties(self):
        with open(SEEDS_DIR / "regions.csv") as f:
            rows = list(csv.DictReader(f))
        counties = [r for r in rows if r["type"].strip() == "county"]
        assert (
            len(counties) == 47
        ), f"Expected 47 county rows, got {len(counties)}: {[r['slug'] for r in counties]}"

    def test_has_nairobi_county(self):
        with open(SEEDS_DIR / "regions.csv") as f:
            slugs = {r["slug"].strip() for r in csv.DictReader(f)}
        assert "nairobi" in slugs

    def test_has_coast_region(self):
        with open(SEEDS_DIR / "regions.csv") as f:
            rows = list(csv.DictReader(f))
        coast = [r for r in rows if r["type"].strip() == "coast"]
        assert len(coast) >= 1, "Expected at least one coast region"

    def test_has_cuisine_groups(self):
        with open(SEEDS_DIR / "regions.csv") as f:
            rows = list(csv.DictReader(f))
        cuisine = [r for r in rows if r["type"].strip() == "cuisine"]
        assert len(cuisine) >= 10, f"Expected at least 10 cuisine groups, got {len(cuisine)}"

    def test_known_cuisine_groups_present(self):
        with open(SEEDS_DIR / "regions.csv") as f:
            slugs = {r["slug"].strip() for r in csv.DictReader(f)}
        for expected in ("luo", "kikuyu", "luhya", "kalenjin", "ethiopian", "tanzanian"):
            assert expected in slugs, f"Cuisine group {expected!r} missing from regions.csv"

    def test_no_duplicate_slugs(self):
        with open(SEEDS_DIR / "regions.csv") as f:
            slugs = [r["slug"].strip() for r in csv.DictReader(f)]
        assert len(slugs) == len(set(slugs)), "Duplicate slugs found in regions.csv"

    def test_all_rows_have_required_fields(self):
        with open(SEEDS_DIR / "regions.csv") as f:
            for i, row in enumerate(csv.DictReader(f), start=2):
                assert row["slug"].strip(), f"Row {i}: empty slug"
                assert row["name"].strip(), f"Row {i}: empty name"
                assert row["type"].strip() in (
                    "county",
                    "coast",
                    "cuisine",
                ), f"Row {i}: invalid type {row['type']!r}"


@pytest.mark.fast
class TestUnitsCSV:
    def test_file_exists(self):
        assert (SEEDS_DIR / "units.csv").exists(), "data/seeds/units.csv not found"

    def test_core_mass_units_present(self):
        with open(SEEDS_DIR / "units.csv") as f:
            codes = {r["code"].strip() for r in csv.DictReader(f)}
        for expected in ("g", "kg"):
            assert expected in codes, f"Mass unit {expected!r} missing from units.csv"

    def test_core_volume_units_present(self):
        with open(SEEDS_DIR / "units.csv") as f:
            codes = {r["code"].strip() for r in csv.DictReader(f)}
        for expected in ("ml", "l", "tsp", "tbsp", "cup"):
            assert expected in codes, f"Volume unit {expected!r} missing from units.csv"

    def test_count_units_present(self):
        with open(SEEDS_DIR / "units.csv") as f:
            codes = {r["code"].strip() for r in csv.DictReader(f)}
        assert "pcs" in codes

    def test_to_base_factor_is_numeric(self):
        with open(SEEDS_DIR / "units.csv") as f:
            for i, row in enumerate(csv.DictReader(f), start=2):
                try:
                    float(row["to_base_factor"])
                except ValueError:
                    pytest.fail(f"Row {i}: to_base_factor {row['to_base_factor']!r} is not numeric")

    def test_gram_base_factor_is_one(self):
        with open(SEEDS_DIR / "units.csv") as f:
            for row in csv.DictReader(f):
                if row["code"].strip() == "g":
                    assert float(row["to_base_factor"]) == 1.0
                    return
        pytest.fail("Unit 'g' not found in units.csv")


@pytest.mark.django_db
def test_seed_all_creates_regions(seeded_db):
    """After seed_all, regions table has county + coast + cuisine rows."""
    from apps.regions.models import Region

    assert Region.objects.filter(type="county").count() == 47
    assert Region.objects.filter(type="coast").count() >= 1
    assert Region.objects.filter(type="cuisine").count() >= 10


@pytest.mark.django_db
def test_seed_all_creates_units(seeded_db):
    """After seed_all, the units table has the core culinary units."""
    from apps.ingredients.models import Unit

    assert Unit.objects.filter(code="g").exists()
    assert Unit.objects.filter(code="ml").exists()
    assert Unit.objects.filter(code="tsp").exists()
