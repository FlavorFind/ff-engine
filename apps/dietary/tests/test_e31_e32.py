"""
Tests for E31/E32 — Dietary safety filter.

Covers:
  E31  derive_dietary_tags()  — 8 derivation rules from ingredient flags
  E31  apply_derived_tags()   — persists derived DishDietaryTag rows
  E31  DishIngredient signal  — auto re-derives on ingredient add/remove
  E32  Manual override        — source=manual not overwritten by derivation
  E32  ChangeLog audit        — every manual override logged; derived tags are not

Blueprint section 8 (The Safety Filter):
  Lock 1 (automatic) — derived from ingredient flags, cannot be forgotten.
  Lock 2 (human)     — reviewer override with reason, every override audited.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from django.db.models.signals import post_delete, post_save

from apps.core.models import StatusChoices
from apps.curation.models import ChangeLog
from apps.dietary.models import DietaryTag, DishDietaryTag
from apps.dietary.services import apply_derived_tags, derive_dietary_tags
from apps.dishes.models import Dish, DishIngredient
from apps.ingredients.models import Allergen, Ingredient, IngredientAllergen, IngredientCategory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def category(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="e31-test-category",
        defaults={"name_en": "E31 Test Category"},
    )
    return cat


def _dish(slug: str) -> Dish:
    """Create or fetch a test dish with a unique slug/name."""
    dish, _ = Dish.objects.get_or_create(
        slug=slug,
        defaults={
            "name_en": slug.replace("-", " ").title(),
            "status": StatusChoices.DRAFT,
        },
    )
    return dish


def _ingredient(slug: str, name_en: str, category: IngredientCategory) -> Ingredient:
    """Create or fetch a test ingredient with a unique slug/name."""
    ing, _ = Ingredient.objects.get_or_create(
        slug=slug,
        defaults={
            "name_en": name_en,
            "category": category,
            "status": StatusChoices.DRAFT,
        },
    )
    return ing


def _link(
    dish: Dish, ingredient: Ingredient, role: str = DishIngredient.Role.REQUIRED
) -> DishIngredient:
    """Create a DishIngredient link (fires signals)."""
    return DishIngredient.objects.create(dish=dish, ingredient=ingredient, role=role)


@contextmanager
def _no_dietary_signals():
    """Temporarily disconnect the DishIngredient dietary re-derivation signals.

    Lets us set up ingredients without auto-derivation firing, so we can assert
    that apply_derived_tags() is what actually creates the rows.
    """
    from apps.dietary.signals import (
        on_dish_ingredient_delete_dietary,
        on_dish_ingredient_save_dietary,
    )

    post_save.disconnect(on_dish_ingredient_save_dietary, sender=DishIngredient)
    post_delete.disconnect(on_dish_ingredient_delete_dietary, sender=DishIngredient)
    try:
        yield
    finally:
        post_save.connect(on_dish_ingredient_save_dietary, sender=DishIngredient)
        post_delete.connect(on_dish_ingredient_delete_dietary, sender=DishIngredient)


# ===========================================================================
# E31: derive_dietary_tags()
# ===========================================================================


@pytest.mark.django_db
class TestDeriveDietaryTags:
    """derive_dietary_tags() returns the correct {tag_slug: bool} dict."""

    def test_vegetarian_true_for_vegetable_only_dish(self, category):
        dish = _dish("e31-veg-only")
        _link(dish, _ingredient("e31-spinach", "E31 Spinach", category))
        _link(dish, _ingredient("e31-kale", "E31 Kale", category))
        result = derive_dietary_tags(dish)
        assert result["vegetarian"] is True

    def test_vegetarian_false_when_dish_contains_beef(self, category):
        dish = _dish("e31-beef-dish")
        _link(dish, _ingredient("e31-beef", "E31 Beef", category))
        _link(dish, _ingredient("e31-spinach2", "E31 Spinach", category))
        result = derive_dietary_tags(dish)
        assert result["vegetarian"] is False

    def test_contains_pork_true_for_pork_dish(self, category):
        dish = _dish("e31-pork-dish")
        _link(dish, _ingredient("e31-pork", "E31 Pork", category))
        result = derive_dietary_tags(dish)
        assert result["contains-pork"] is True

    def test_gluten_free_true_when_no_wheat_barley_rye(self, category):
        dish = _dish("e31-no-gluten")
        _link(dish, _ingredient("e31-rice", "E31 Rice", category))
        _link(dish, _ingredient("e31-spinach3", "E31 Spinach", category))
        result = derive_dietary_tags(dish)
        assert result["gluten-free"] is True

    def test_gluten_free_false_when_wheat_present(self, category):
        dish = _dish("e31-wheat-dish")
        _link(dish, _ingredient("e31-wheat-flour", "E31 Wheat Flour", category))
        result = derive_dietary_tags(dish)
        assert result["gluten-free"] is False

    def test_vegan_true_for_vegetable_only_dish(self, category):
        dish = _dish("e31-vegan-veg")
        _link(dish, _ingredient("e31-spinach4", "E31 Spinach", category))
        _link(dish, _ingredient("e31-kale2", "E31 Kale", category))
        result = derive_dietary_tags(dish)
        assert result["vegan"] is True

    @pytest.mark.parametrize("name,slug", [("Milk", "milk"), ("Egg", "egg"), ("Honey", "honey")])
    def test_vegan_false_when_animal_product_present(self, category, name, slug):
        """Vegan requires no meat, dairy, eggs or honey — each blocker alone flips it."""
        dish = _dish(f"e31-vegan-block-{slug}")
        _link(dish, _ingredient(f"e31-veg-{slug}", "E31 Spinach", category))
        _link(dish, _ingredient(f"e31-block-{slug}", f"E31 {name}", category))
        result = derive_dietary_tags(dish)
        assert result["vegan"] is False

    def test_allergen_link_blocks_vegetarian_without_name_keyword(self, category):
        """An ingredient carrying a 'meat' allergen (but no meat keyword in its
        name) must still block vegetarian via the allergen-lookup path."""
        dish = _dish("e31-allergen-meat")
        steak = _ingredient("e31-steak", "E31 Steak Cut", category)
        meat_allergen, _ = Allergen.objects.get_or_create(slug="meat", defaults={"name": "Meat"})
        IngredientAllergen.objects.get_or_create(ingredient=steak, allergen=meat_allergen)
        _link(dish, steak)
        result = derive_dietary_tags(dish)
        assert result["vegetarian"] is False


# ===========================================================================
# E31: apply_derived_tags()
# ===========================================================================


@pytest.mark.django_db
class TestApplyDerivedTags:
    """apply_derived_tags() persists derived DishDietaryTag rows."""

    def test_creates_derived_tag_rows(self, category):
        with _no_dietary_signals():
            dish = _dish("e31-apply-veg")
            _link(dish, _ingredient("e31-spinach5", "E31 Spinach", category))
            # Signals suppressed → no dietary rows yet.
            assert DishDietaryTag.objects.filter(dish=dish).count() == 0
            applied = apply_derived_tags(dish)
        assert applied > 0
        derived = DishDietaryTag.objects.filter(dish=dish, source=DishDietaryTag.Source.DERIVED)
        assert derived.exists()
        assert derived.filter(tag__slug="vegetarian").exists()

    def test_idempotent(self, category):
        with _no_dietary_signals():
            dish = _dish("e31-apply-idem")
            _link(dish, _ingredient("e31-spinach6", "E31 Spinach", category))
            first = apply_derived_tags(dish)
            second = apply_derived_tags(dish)
        assert second == 0
        assert DishDietaryTag.objects.filter(dish=dish).count() == first

    def test_does_not_overwrite_manual_override(self, category):
        """A reviewer's manual tag must survive re-derivation even when the
        derived logic says the tag no longer applies."""
        with _no_dietary_signals():
            dish = _dish("e31-manual-override")
            _link(dish, _ingredient("e31-beef2", "E31 Beef", category))
            # Reviewer manually marks this beef dish as vegetarian.
            veg_tag, _ = DietaryTag.objects.get_or_create(
                slug="vegetarian", defaults={"name": "Vegetarian"}
            )
            DishDietaryTag.objects.create(
                dish=dish,
                tag=veg_tag,
                source=DishDietaryTag.Source.MANUAL,
                reason="Prepared vegetarian on request",
            )
            # Re-derive: vegetarian is False for beef, but the manual row survives.
            apply_derived_tags(dish)
        row = DishDietaryTag.objects.get(dish=dish, tag__slug="vegetarian")
        assert row.source == DishDietaryTag.Source.MANUAL
        assert row.reason == "Prepared vegetarian on request"


# ===========================================================================
# E31: DishIngredient signals
# ===========================================================================


@pytest.mark.django_db
class TestDietarySignals:
    """Adding or removing a DishIngredient auto re-derives dietary tags."""

    def test_adding_ingredient_rederives_tags(self, category):
        dish = _dish("e31-signal-add")
        # Start with a vegetable dish → vegetarian derived.
        _link(dish, _ingredient("e31-spinach7", "E31 Spinach", category))
        assert DishDietaryTag.objects.filter(
            dish=dish, tag__slug="vegetarian", source=DishDietaryTag.Source.DERIVED
        ).exists()
        # Add beef → re-derivation removes vegetarian.
        _link(dish, _ingredient("e31-beef3", "E31 Beef", category))
        assert not DishDietaryTag.objects.filter(dish=dish, tag__slug="vegetarian").exists()

    def test_removing_ingredient_rederives_tags(self, category):
        dish = _dish("e31-signal-remove")
        beef = _ingredient("e31-beef4", "E31 Beef", category)
        _link(dish, beef)
        _link(dish, _ingredient("e31-spinach8", "E31 Spinach", category))
        # Beef present → vegetarian not derived.
        assert not DishDietaryTag.objects.filter(dish=dish, tag__slug="vegetarian").exists()
        # Remove beef → only veg remains → vegetarian derived.
        DishIngredient.objects.get(dish=dish, ingredient=beef).delete()
        assert DishDietaryTag.objects.filter(
            dish=dish, tag__slug="vegetarian", source=DishDietaryTag.Source.DERIVED
        ).exists()


# ===========================================================================
# E32: Manual override audit trail
# ===========================================================================


@pytest.mark.django_db
class TestE32ManualOverrideAudit:
    """Manual overrides are logged to ChangeLog; derived tags are not."""

    def test_manual_override_logged_to_changelog(self, category):
        dish = _dish("e31-changelog-manual")
        veg_tag, _ = DietaryTag.objects.get_or_create(
            slug="vegetarian", defaults={"name": "Vegetarian"}
        )
        manual = DishDietaryTag.objects.create(
            dish=dish,
            tag=veg_tag,
            source=DishDietaryTag.Source.MANUAL,
            reason="Reviewer override",
        )
        log = ChangeLog.objects.filter(object_type="DishDietaryTag", object_id=str(manual.pk))
        assert log.exists()
        entry = log.first()
        assert entry.action == "create"
        assert entry.reason == "Reviewer override"

    def test_derived_tag_not_logged_to_changelog(self, category):
        """Derived tags are automatic (Lock 1) and must not spam the audit log."""
        dish = _dish("e31-changelog-derived")
        _link(dish, _ingredient("e31-spinach10", "E31 Spinach", category))
        derived = DishDietaryTag.objects.filter(
            dish=dish, tag__slug="vegetarian", source=DishDietaryTag.Source.DERIVED
        ).first()
        assert derived is not None
        assert (
            ChangeLog.objects.filter(
                object_type="DishDietaryTag", object_id=str(derived.pk)
            ).count()
            == 0
        )
