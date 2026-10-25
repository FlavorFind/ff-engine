"""
E5 tests — dish model integrity rules.

Blueprint pass criterion: integrity rules tested.
  - No duplicate ingredient on one dish
  - All four roles work correctly
  - DishStep positions unique per dish
  - DishAlias unique per dish
  - DishRegion unique per dish
  - Search arrays rebuilt correctly by rebuild_search_arrays()
  - Dish name_en unique
"""

import pytest
from django.db import IntegrityError

from apps.dishes.models import Dish, DishAlias, DishIngredient, DishStep
from apps.ingredients.models import Ingredient, IngredientCategory, Unit
from apps.regions.models import DishRegion, Region

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def category(db):
    return IngredientCategory.objects.get_or_create(name_en="_test_Grains")[0]


@pytest.fixture
def unit(db):
    return Unit.objects.get_or_create(
        code="_tg",
        defaults={"name": "_test_Gram", "kind": Unit.Kind.MASS, "to_base_factor": 1},
    )[0]


@pytest.fixture
def maize_flour(db, category):
    return Ingredient.objects.get_or_create(
        name_en="_test_Maize flour", defaults={"category": category}
    )[0]


@pytest.fixture
def water(db, category):
    return Ingredient.objects.get_or_create(
        name_en="_test_Water", defaults={"category": category, "is_staple": True}
    )[0]


@pytest.fixture
def salt(db, category):
    return Ingredient.objects.get_or_create(
        name_en="_test_Salt", defaults={"category": category, "is_staple": True}
    )[0]


@pytest.fixture
def tomato(db, category):
    return Ingredient.objects.get_or_create(
        name_en="_test_Tomato", defaults={"category": category}
    )[0]


@pytest.fixture
def onion(db, category):
    return Ingredient.objects.get_or_create(name_en="_test_Onion", defaults={"category": category})[
        0
    ]


@pytest.fixture
def dish(db):
    return Dish.objects.get_or_create(name_en="_test_Ugali")[0]


@pytest.fixture
def region(db):
    return Region.objects.get_or_create(name="_test_Coastal", defaults={"type": Region.Type.COAST})[
        0
    ]


# ---------------------------------------------------------------------------
# Dish model
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dish_slug_auto_generated(dish):
    assert dish.slug == "test-ugali"


@pytest.mark.django_db
def test_dish_str(dish):
    assert str(dish) == "_test_Ugali"


@pytest.mark.django_db
def test_dish_name_en_unique(db):
    Dish.objects.create(name_en="_test_Unique Dish")
    with pytest.raises(IntegrityError):
        Dish.objects.create(name_en="_test_Unique Dish")


@pytest.mark.django_db
def test_dish_default_status_is_draft(dish):
    assert dish.status == "draft"


@pytest.mark.django_db
def test_dish_default_quality_is_seeded(dish):
    assert dish.quality_level == "seeded"


@pytest.mark.django_db
def test_dish_search_arrays_default_empty(dish):
    assert dish.required_ids == []
    assert dish.optional_ids == []
    assert dish.primary_ids == []
    assert dish.all_ids == []


# ---------------------------------------------------------------------------
# DishIngredient — E5 pass criterion: no duplicate ingredient on one dish
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_no_duplicate_ingredient_on_one_dish(dish, maize_flour):
    """Core integrity rule: same ingredient cannot appear twice on one dish."""
    DishIngredient.objects.create(
        dish=dish, ingredient=maize_flour, role=DishIngredient.Role.PRIMARY
    )
    with pytest.raises(IntegrityError):
        DishIngredient.objects.create(
            dish=dish, ingredient=maize_flour, role=DishIngredient.Role.REQUIRED
        )


@pytest.mark.django_db
def test_same_ingredient_on_different_dishes_allowed(db, category, maize_flour):
    """Same ingredient can appear on different dishes — constraint is per-dish."""
    dish_a = Dish.objects.create(name_en="Ugali A")
    dish_b = Dish.objects.create(name_en="Ugali B")
    DishIngredient.objects.create(
        dish=dish_a, ingredient=maize_flour, role=DishIngredient.Role.PRIMARY
    )
    di = DishIngredient.objects.create(
        dish=dish_b, ingredient=maize_flour, role=DishIngredient.Role.PRIMARY
    )
    assert di.pk is not None


@pytest.mark.django_db
def test_all_four_roles(dish, maize_flour, tomato, onion, salt):
    """All four roles can be assigned; each maps to a different ingredient."""
    DishIngredient.objects.create(
        dish=dish, ingredient=maize_flour, role=DishIngredient.Role.PRIMARY
    )
    DishIngredient.objects.create(dish=dish, ingredient=tomato, role=DishIngredient.Role.REQUIRED)
    DishIngredient.objects.create(dish=dish, ingredient=onion, role=DishIngredient.Role.OPTIONAL)
    DishIngredient.objects.create(dish=dish, ingredient=salt, role=DishIngredient.Role.GARNISH)

    roles = set(dish.dish_ingredients.values_list("role", flat=True))
    assert roles == {"primary", "required", "optional", "garnish"}


@pytest.mark.django_db
def test_dish_ingredient_str(dish, maize_flour):
    di = DishIngredient.objects.create(
        dish=dish, ingredient=maize_flour, role=DishIngredient.Role.PRIMARY
    )
    assert "Ugali" in str(di)
    assert "Maize flour" in str(di)
    assert "primary" in str(di)


# ---------------------------------------------------------------------------
# rebuild_search_arrays
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_rebuild_search_arrays_required_excludes_staples(dish, maize_flour, water):
    """Staple ingredients must NOT appear in required_ids."""
    DishIngredient.objects.create(
        dish=dish, ingredient=maize_flour, role=DishIngredient.Role.REQUIRED
    )
    DishIngredient.objects.create(dish=dish, ingredient=water, role=DishIngredient.Role.REQUIRED)
    dish.rebuild_search_arrays()
    dish.refresh_from_db()

    # water is a staple — must not be in required_ids
    assert water.pk not in dish.required_ids
    # maize flour is not a staple — must be in required_ids
    assert maize_flour.pk in dish.required_ids


@pytest.mark.django_db
def test_rebuild_search_arrays_all_ids_includes_everything(dish, maize_flour, tomato, water):
    """all_ids must contain every ingredient regardless of role or staple status."""
    DishIngredient.objects.create(
        dish=dish, ingredient=maize_flour, role=DishIngredient.Role.PRIMARY
    )
    DishIngredient.objects.create(dish=dish, ingredient=water, role=DishIngredient.Role.REQUIRED)
    DishIngredient.objects.create(dish=dish, ingredient=tomato, role=DishIngredient.Role.OPTIONAL)
    dish.rebuild_search_arrays()
    dish.refresh_from_db()

    assert maize_flour.pk in dish.all_ids
    assert water.pk in dish.all_ids
    assert tomato.pk in dish.all_ids


@pytest.mark.django_db
def test_rebuild_search_arrays_primary_ids(dish, maize_flour, tomato):
    DishIngredient.objects.create(
        dish=dish, ingredient=maize_flour, role=DishIngredient.Role.PRIMARY
    )
    DishIngredient.objects.create(dish=dish, ingredient=tomato, role=DishIngredient.Role.REQUIRED)
    dish.rebuild_search_arrays()
    dish.refresh_from_db()

    assert maize_flour.pk in dish.primary_ids
    assert tomato.pk not in dish.primary_ids


@pytest.mark.django_db
def test_rebuild_search_arrays_optional_ids(dish, maize_flour, onion):
    DishIngredient.objects.create(
        dish=dish, ingredient=maize_flour, role=DishIngredient.Role.REQUIRED
    )
    DishIngredient.objects.create(dish=dish, ingredient=onion, role=DishIngredient.Role.OPTIONAL)
    dish.rebuild_search_arrays()
    dish.refresh_from_db()

    assert onion.pk in dish.optional_ids
    assert maize_flour.pk not in dish.optional_ids


# ---------------------------------------------------------------------------
# DishAlias
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dish_alias_unique_per_dish(dish):
    DishAlias.objects.create(dish=dish, alias="Ugali wa mahindi", language="sw")
    with pytest.raises(IntegrityError):
        DishAlias.objects.create(dish=dish, alias="Ugali wa mahindi", language="en")


@pytest.mark.django_db
def test_dish_alias_same_alias_different_dishes(db):
    d1 = Dish.objects.create(name_en="Dish One")
    d2 = Dish.objects.create(name_en="Dish Two")
    DishAlias.objects.create(dish=d1, alias="Shared alias")
    a = DishAlias.objects.create(dish=d2, alias="Shared alias")
    assert a.pk is not None


@pytest.mark.django_db
def test_dish_alias_str(dish):
    alias = DishAlias.objects.create(dish=dish, alias="Uji wa mahindi", language="sw")
    assert "Uji wa mahindi" in str(alias)
    assert "Ugali" in str(alias)


# ---------------------------------------------------------------------------
# DishStep
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dish_step_position_unique_per_dish(dish):
    DishStep.objects.create(dish=dish, position=1, text_en="Boil water.")
    with pytest.raises(IntegrityError):
        DishStep.objects.create(dish=dish, position=1, text_en="Another step.")


@pytest.mark.django_db
def test_dish_step_ordered_by_position(dish):
    DishStep.objects.create(dish=dish, position=3, text_en="Serve hot.")
    DishStep.objects.create(dish=dish, position=1, text_en="Boil water.")
    DishStep.objects.create(dish=dish, position=2, text_en="Add maize flour.")
    steps = list(dish.steps.values_list("position", flat=True))
    assert steps == [1, 2, 3]


@pytest.mark.django_db
def test_dish_step_str(dish):
    step = DishStep.objects.create(dish=dish, position=1, text_en="Boil water.")
    assert "Ugali" in str(step)
    assert "1" in str(step)


# ---------------------------------------------------------------------------
# Region and DishRegion
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_region_slug_auto_generated(region):
    assert region.slug == "test-coastal"


@pytest.mark.django_db
def test_region_str(region):
    assert "Coastal" in str(region)
    assert "Coast" in str(region)


@pytest.mark.django_db
def test_dish_region_unique_per_dish(dish, region):
    DishRegion.objects.create(dish=dish, region=region)
    with pytest.raises(IntegrityError):
        DishRegion.objects.create(dish=dish, region=region)


@pytest.mark.django_db
def test_dish_linked_to_region_via_m2m(dish, region):
    DishRegion.objects.create(dish=dish, region=region)
    assert region in dish.regions.all()
    assert dish in region.dishes.all()
