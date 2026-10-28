"""
Tests for E28/E29 — Pairing model, service and endpoint.

Focuses on the pairings-specific gaps not already covered by
apps/dishes/tests/test_e28_e32.py:

  E28  Pairing model constraints:
       - pairing_has_dish_or_label check rejects a row with neither target
       - strength validator rejects values outside 1–5 (and accepts 1–5)
  E29  get_pairings_for_dish() service:
       - ordered by strength descending
       - min_strength and pairing_type filters
  E29  GET /v1/dishes/{uuid}/pairings/:
       - correct JSON shape (fields present, count matches, ordered)
       - a label-only pairing (e.g. "chai") is returned with null dish fields

These tests are self-contained (no seeded_db) so they run in milliseconds.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.core.models import StatusChoices
from apps.dishes.models import Dish
from apps.pairings.models import Pairing
from apps.pairings.services import get_pairings_for_dish

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def api():
    return APIClient()


def _dish(slug: str) -> Dish:
    dish, _ = Dish.objects.get_or_create(
        slug=slug,
        defaults={
            "name_en": slug.replace("-", " ").title(),
            "status": StatusChoices.DRAFT,
        },
    )
    return dish


def _pairing(
    dish: Dish,
    *,
    strength: int,
    paired_label: str = "",
    paired_dish=None,
    pairing_type: str = Pairing.PairingType.SIDE,
) -> Pairing:
    return Pairing.objects.create(
        dish=dish,
        paired_dish=paired_dish,
        paired_label=paired_label,
        pairing_type=pairing_type,
        strength=strength,
    )


# ===========================================================================
# E28 — Pairing model constraints
# ===========================================================================


@pytest.mark.django_db
class TestPairingModelConstraints:
    def test_rejects_row_with_neither_dish_nor_label(self):
        """The pairing_has_dish_or_label check constraint must reject a row that
        has no paired_dish and an empty paired_label."""
        from django.db import IntegrityError, transaction

        dish = _dish("e28-no-target")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Pairing.objects.create(
                    dish=dish,
                    paired_dish=None,
                    paired_label="",
                    pairing_type=Pairing.PairingType.SIDE,
                    strength=3,
                )

    @pytest.mark.parametrize("strength", [0, 6])
    def test_strength_validator_rejects_outside_range(self, strength):
        """Strength outside 1–5 must fail model validation."""
        from django.core.exceptions import ValidationError

        dish = _dish(f"e28-invalid-{strength}")
        p = Pairing(
            dish=dish,
            paired_label="test",
            pairing_type=Pairing.PairingType.SIDE,
            strength=strength,
        )
        with pytest.raises(ValidationError):
            p.full_clean()

    @pytest.mark.parametrize("strength", [1, 2, 3, 4, 5])
    def test_strength_validator_accepts_in_range(self, strength):
        """Strength 1–5 must pass model validation."""
        dish = _dish(f"e28-valid-{strength}")
        p = Pairing(
            dish=dish,
            paired_label="test",
            pairing_type=Pairing.PairingType.SIDE,
            strength=strength,
        )
        p.full_clean()  # must not raise

    def test_label_only_pairing_is_valid(self):
        """A pairing with only paired_label (no paired_dish) is valid."""
        dish = _dish("e28-label-only")
        p = _pairing(dish, strength=3, paired_label="chai", pairing_type=Pairing.PairingType.DRINK)
        p.refresh_from_db()
        assert p.paired_dish is None
        assert p.paired_label == "chai"


# ===========================================================================
# E29 — get_pairings_for_dish() service
# ===========================================================================


@pytest.mark.django_db
class TestGetPairingsForDish:
    def test_ordered_by_strength_descending(self):
        dish = _dish("e28-service-order")
        _pairing(dish, strength=2, paired_label="a")
        _pairing(dish, strength=5, paired_label="b")
        _pairing(dish, strength=3, paired_label="c")
        result = get_pairings_for_dish(str(dish.id))
        strengths = [p.strength for p in result]
        assert strengths == [5, 3, 2]

    def test_min_strength_filter(self):
        dish = _dish("e28-service-min")
        _pairing(dish, strength=1, paired_label="a")
        _pairing(dish, strength=4, paired_label="b")
        result = get_pairings_for_dish(str(dish.id), min_strength=3)
        assert [p.strength for p in result] == [4]

    def test_pairing_type_filter(self):
        dish = _dish("e28-service-type")
        _pairing(dish, strength=5, paired_label="side", pairing_type=Pairing.PairingType.SIDE)
        _pairing(dish, strength=5, paired_label="chai", pairing_type=Pairing.PairingType.DRINK)
        result = get_pairings_for_dish(str(dish.id), pairing_type="drink")
        assert len(result) == 1
        assert result[0].paired_label == "chai"

    def test_limit(self):
        dish = _dish("e28-service-limit")
        for i in range(5):
            _pairing(dish, strength=i + 1, paired_label=f"l{i}")
        result = get_pairings_for_dish(str(dish.id), limit=2)
        assert len(result) == 2
        assert [p.strength for p in result] == [5, 4]

    def test_other_dish_pairings_excluded(self):
        a = _dish("e28-dish-a")
        b = _dish("e28-dish-b")
        _pairing(a, strength=5, paired_label="a1")
        _pairing(b, strength=5, paired_label="b1")
        result = get_pairings_for_dish(str(a.id))
        assert len(result) == 1
        assert result[0].paired_label == "a1"


# ===========================================================================
# E29 — GET /v1/dishes/{uuid}/pairings/ endpoint
# ===========================================================================


@pytest.mark.django_db
class TestPairingsEndpoint:
    def test_correct_json_shape(self, api):
        dish = _dish("e28-endpoint-shape")
        _pairing(dish, strength=5, paired_label="kachumbari", pairing_type=Pairing.PairingType.SIDE)
        resp = api.get(f"/v1/dishes/{dish.id}/pairings/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dish_slug"] == "e28-endpoint-shape"
        assert data["count"] == 1
        assert len(data["pairings"]) == 1
        p = data["pairings"][0]
        for field in (
            "id",
            "pairing_type",
            "strength",
            "paired_dish_slug",
            "paired_dish_name",
            "paired_label",
            "note",
        ):
            assert field in p
        assert p["pairing_type"] == "side"
        assert p["strength"] == 5

    def test_ordered_by_strength_descending(self, api):
        dish = _dish("e28-endpoint-order")
        _pairing(dish, strength=2, paired_label="a")
        _pairing(dish, strength=5, paired_label="b")
        _pairing(dish, strength=3, paired_label="c")
        resp = api.get(f"/v1/dishes/{dish.id}/pairings/")
        strengths = [p["strength"] for p in resp.json()["pairings"]]
        assert strengths == [5, 3, 2]

    def test_label_only_pairing_returned_with_null_dish_fields(self, api):
        """A label-only pairing (e.g. 'chai') must come back with null dish fields."""
        dish = _dish("e28-endpoint-label")
        _pairing(dish, strength=4, paired_label="chai", pairing_type=Pairing.PairingType.DRINK)
        resp = api.get(f"/v1/dishes/{dish.id}/pairings/")
        p = resp.json()["pairings"][0]
        assert p["paired_label"] == "chai"
        assert p["paired_dish_slug"] is None
        assert p["paired_dish_name"] is None

    def test_min_strength_param(self, api):
        dish = _dish("e28-endpoint-min")
        _pairing(dish, strength=1, paired_label="a")
        _pairing(dish, strength=4, paired_label="b")
        resp = api.get(f"/v1/dishes/{dish.id}/pairings/?min_strength=3")
        pairings = resp.json()["pairings"]
        assert len(pairings) == 1
        assert pairings[0]["strength"] == 4

    def test_type_param(self, api):
        dish = _dish("e28-endpoint-type")
        _pairing(dish, strength=5, paired_label="side", pairing_type=Pairing.PairingType.SIDE)
        _pairing(dish, strength=5, paired_label="chai", pairing_type=Pairing.PairingType.DRINK)
        resp = api.get(f"/v1/dishes/{dish.id}/pairings/?type=drink")
        pairings = resp.json()["pairings"]
        assert len(pairings) == 1
        assert pairings[0]["paired_label"] == "chai"

    def test_404_for_unknown_dish(self, api):
        resp = api.get("/v1/dishes/00000000-0000-0000-0000-000000000000/pairings/")
        assert resp.status_code == 404

    def test_dish_with_no_pairings_returns_empty(self, api):
        dish = _dish("e28-endpoint-empty")
        resp = api.get(f"/v1/dishes/{dish.id}/pairings/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["pairings"] == []
