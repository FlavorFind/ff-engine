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
    return IngredientCategory.objects.get_or_create(name_en="_test_Vegetables and greens")[0]


@pytest.fixture
def unit(db):
    return Unit.objects.get_or_create(
        code="_tg",
        defaults={"name": "_test_Gram", "kind": Unit.Kind.MASS, "to_base_factor": 1},
    )[0]


@pytest.fixture
def source(db):
    return Source.objects.get_or_create(
        title="_test_source",
        defaults={
            "kind": Source.Kind.CHEF,
            "permission_status": Source.PermissionStatus.GRANTED,
        },
    )[0]


@pytest.fixture
def ingredient(db, category):
    return Ingredient.objects.get_or_create(
        name_en="_test_Tomato",
        defaults={"name_sw": "_test_Nyanya", "category": category},
    )[0]


# ---------------------------------------------------------------------------
# IngredientCategory
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_category_slug_auto_generated(category):
    assert category.slug == "test_vegetables-and-greens"


@pytest.mark.django_db
def test_category_str(category):
    assert str(category) == "_test_Vegetables and greens"


@pytest.mark.django_db
def test_category_parent_child(db, category):
    child = IngredientCategory.objects.create(name_en="_test_Leafy greens", parent=category)
    assert child.parent == category
    assert child in category.children.all()


@pytest.mark.django_db
def test_category_slug_unique(db, category):
    with pytest.raises(IntegrityError):
        IngredientCategory.objects.create(
            name_en="_test_Vegetables and greens",
            slug="test_vegetables-and-greens",
        )


# ---------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_unit_str(unit):
    assert str(unit) == "_tg (Mass)"


@pytest.mark.django_db
def test_unit_code_unique(db, unit):
    with pytest.raises(IntegrityError):
        Unit.objects.create(
            code="_tg", name="_test_Gram duplicate", kind=Unit.Kind.MASS, to_base_factor=1
        )


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
    assert ingredient.slug == "test_tomato"


@pytest.mark.django_db
def test_ingredient_str(ingredient):
    assert str(ingredient) == "_test_Tomato"


@pytest.mark.django_db
def test_ingredient_name_en_unique(db, category):
    Ingredient.objects.create(name_en="_test_Onion", category=category)
    with pytest.raises(IntegrityError):
        Ingredient.objects.create(name_en="_test_Onion", category=category)


@pytest.mark.django_db
def test_ingredient_default_status_is_draft(ingredient):
    assert ingredient.status == "draft"


@pytest.mark.django_db
def test_ingredient_is_staple_default_false(ingredient):
    assert ingredient.is_staple is False


@pytest.mark.django_db
def test_ingredient_staple_flag(db, category):
    water = Ingredient.objects.get_or_create(
        name_en="_test_Water_staple", defaults={"category": category, "is_staple": True}
    )[0]
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
        alias="_test_Nyanya",
        normalized_alias="_test_nyanya",
        language=IngredientAlias.Language.SW,
    )
    assert "_test_nyanya" in str(alias).lower()
    assert "_test_tomato" in str(alias).lower()


@pytest.mark.django_db
def test_alias_misspelling_flag(db, ingredient):
    alias = IngredientAlias.objects.create(
        ingredient=ingredient,
        alias="_test_tomatos",
        normalized_alias="_test_tomatos",
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
        alias="_test_nyanya",
        normalized_alias="_test_nyanya",
        language=IngredientAlias.Language.SW,
    )
    other = Ingredient.objects.create(name_en="_test_Cherry Tomato", category=category)
    with pytest.raises(IntegrityError):
        IngredientAlias.objects.create(
            ingredient=other,
            alias="_test_nyanya",
            normalized_alias="_test_nyanya",
            language=IngredientAlias.Language.SW,
        )


# ---------------------------------------------------------------------------
# Source (curation)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_source_str(source):
    assert "_test_source" in str(source)
    assert "Chef" in str(source)


@pytest.mark.django_db
def test_source_linked_to_ingredient(ingredient, source):
    ingredient.source = source
    ingredient.save()
    assert source.ingredients.filter(pk=ingredient.pk).exists()
