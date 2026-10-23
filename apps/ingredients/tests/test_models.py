"""
E4 tests — ingredient models integrity rules.

Blueprint pass criterion: migrations apply and reverse cleanly.
Architecture section 5: every integrity rule has a test.
"""

import pytest
from django.db import IntegrityError

from apps.curation.models import Source
from apps.ingredients.models import (
    Allergen,
    Ingredient,
    IngredientAlias,
    IngredientAllergen,
    IngredientCategory,
    Unit,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def category(db):
    return IngredientCategory.objects.create(name_en="Vegetables and greens")


@pytest.fixture
def unit(db):
    return Unit.objects.create(code="g", name="Gram", kind=Unit.Kind.MASS, to_base_factor=1)


@pytest.fixture
def source(db):
    return Source.objects.create(
        kind=Source.Kind.CHEF,
        title="Test source",
        permission_status=Source.PermissionStatus.GRANTED,
    )


@pytest.fixture
def ingredient(db, category):
    return Ingredient.objects.create(
        name_en="Tomato",
        name_sw="Nyanya",
        category=category,
    )


# ---------------------------------------------------------------------------
# IngredientCategory
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_category_slug_auto_generated(category):
    assert category.slug == "vegetables-and-greens"


@pytest.mark.django_db
def test_category_str(category):
    assert str(category) == "Vegetables and greens"


@pytest.mark.django_db
def test_category_parent_child(db, category):
    child = IngredientCategory.objects.create(name_en="Leafy greens", parent=category)
    assert child.parent == category
    assert child in category.children.all()


@pytest.mark.django_db
def test_category_slug_unique(db, category):
    with pytest.raises(IntegrityError):
        IngredientCategory.objects.create(
            name_en="Vegetables and greens",
            slug="vegetables-and-greens",
        )


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unit_str(unit):
    assert str(unit) == "g (Mass)"


@pytest.mark.django_db
def test_unit_code_unique(db, unit):
    with pytest.raises(IntegrityError):
        Unit.objects.create(code="g", name="Gram duplicate", kind=Unit.Kind.MASS, to_base_factor=1)


# ---------------------------------------------------------------------------
# Allergen
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_allergen_slug_auto_generated(db):
    allergen = Allergen.objects.create(name="Peanuts")
    assert allergen.slug == "peanuts"


@pytest.mark.django_db
def test_allergen_slug_unique(db):
    Allergen.objects.create(name="Peanuts")
    with pytest.raises(IntegrityError):
        Allergen.objects.create(name="Peanuts again", slug="peanuts")


# ---------------------------------------------------------------------------
# Ingredient
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ingredient_slug_auto_generated(ingredient):
    assert ingredient.slug == "tomato"


@pytest.mark.django_db
def test_ingredient_str(ingredient):
    assert str(ingredient) == "Tomato"


@pytest.mark.django_db
def test_ingredient_name_en_unique(db, category):
    Ingredient.objects.create(name_en="Onion", category=category)
    with pytest.raises(IntegrityError):
        Ingredient.objects.create(name_en="Onion", category=category)


@pytest.mark.django_db
def test_ingredient_default_status_is_draft(ingredient):
    assert ingredient.status == "draft"


@pytest.mark.django_db
def test_ingredient_is_staple_default_false(ingredient):
    assert ingredient.is_staple is False


@pytest.mark.django_db
def test_ingredient_staple_flag(db, category):
    water = Ingredient.objects.create(name_en="Water", category=category, is_staple=True)
    assert Ingredient.objects.filter(is_staple=True).count() == 1
    assert water.is_staple is True


@pytest.mark.django_db
def test_ingredient_with_source(ingredient, source):
    ingredient.source = source
    ingredient.save()
    assert ingredient.source == source


@pytest.mark.django_db
def test_ingredient_with_typical_unit(ingredient, unit):
    ingredient.typical_unit = unit
    ingredient.save()
    assert ingredient.typical_unit == unit


# ---------------------------------------------------------------------------
# IngredientAllergen (through table)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ingredient_allergen_link(db, ingredient):
    allergen = Allergen.objects.create(name="Nightshade")
    link = IngredientAllergen.objects.create(ingredient=ingredient, allergen=allergen)
    assert link in ingredient.allergen_links.all()
    assert allergen in ingredient.allergens.all()


@pytest.mark.django_db
def test_ingredient_allergen_unique_together(db, ingredient):
    allergen = Allergen.objects.create(name="Gluten")
    IngredientAllergen.objects.create(ingredient=ingredient, allergen=allergen)
    with pytest.raises(IntegrityError):
        IngredientAllergen.objects.create(ingredient=ingredient, allergen=allergen)


# ---------------------------------------------------------------------------
# IngredientAlias
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_alias_str(db, ingredient):
    alias = IngredientAlias.objects.create(
        ingredient=ingredient,
        alias="Nyanya",
        normalized_alias="nyanya",
        language=IngredientAlias.Language.SW,
    )
    assert "nyanya" in str(alias).lower()
    assert "tomato" in str(alias).lower()


@pytest.mark.django_db
def test_alias_misspelling_flag(db, ingredient):
    alias = IngredientAlias.objects.create(
        ingredient=ingredient,
        alias="tomatos",
        normalized_alias="tomatos",
        language=IngredientAlias.Language.EN,
        is_misspelling=True,
    )
    assert alias.is_misspelling is True
    assert "(misspelling)" in str(alias)


@pytest.mark.django_db
def test_alias_normalized_language_unique(db, ingredient, category):
    """One normalized alias + language combo maps to exactly one ingredient (dictionary rule)."""
    IngredientAlias.objects.create(
        ingredient=ingredient,
        alias="nyanya",
        normalized_alias="nyanya",
        language=IngredientAlias.Language.SW,
    )
    other = Ingredient.objects.create(name_en="Cherry Tomato", category=category)
    with pytest.raises(IntegrityError):
        IngredientAlias.objects.create(
            ingredient=other,
            alias="nyanya",
            normalized_alias="nyanya",
            language=IngredientAlias.Language.SW,
        )


# ---------------------------------------------------------------------------
# Source (curation)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_source_str(source):
    assert "Test source" in str(source)
    assert "Chef" in str(source)


@pytest.mark.django_db
def test_source_linked_to_ingredient(ingredient, source):
    ingredient.source = source
    ingredient.save()
    assert source.ingredients.filter(pk=ingredient.pk).exists()
