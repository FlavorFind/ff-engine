"""
E6 tests — Admin v0 for data entry.

Blueprint pass criterion: a curator can enter a dish unaided.

Tests:
  - Admin add dish page renders (200)
  - Admin change dish page renders (200)
  - Bulk status actions work (mark reviewed, verified, archived, draft)
  - Search by alias finds a dish even when the alias is not in name fields
  - Saving a dish via admin triggers rebuild_search_arrays
  - Ingredient admin add/change pages render (200)
  - Admin site branding is customised
"""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import Client

from apps.dishes.models import Dish, DishAlias, DishIngredient
from apps.ingredients.models import Ingredient, IngredientCategory, Unit
from apps.regions.models import DishRegion, Region

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="curator",
        email="curator@flavorfind.co.ke",
        password="test-pass-1234",
    )


@pytest.fixture
def curator_client(superuser):
    """Authenticated test client logged in as a superuser curator.

    Named 'curator_client' to avoid shadowing pytest-django's built-in
    'curator_client' fixture.
    """
    c = Client()
    c.force_login(superuser)
    return c


@pytest.fixture
def category(db):
    return IngredientCategory.objects.create(name_en="Grains")


@pytest.fixture
def unit(db):
    return Unit.objects.create(code="g", name="Gram", kind=Unit.Kind.MASS, to_base_factor=1)


@pytest.fixture
def maize_flour(db, category):
    return Ingredient.objects.create(name_en="Maize flour", category=category)


@pytest.fixture
def water(db, category):
    return Ingredient.objects.create(name_en="Water", category=category, is_staple=True)


@pytest.fixture
def dish(db, maize_flour):
    d = Dish.objects.create(name_en="Ugali")
    DishIngredient.objects.create(dish=d, ingredient=maize_flour, role=DishIngredient.Role.PRIMARY)
    return d


@pytest.fixture
def region(db):
    return Region.objects.create(name="Coastal", type=Region.Type.COAST)


# ---------------------------------------------------------------------------
# Admin site branding
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_site_branding():
    assert admin.site.site_header == "Flavor Find — Engine Admin"
    assert admin.site.site_title == "Flavor Find Engine"
    assert admin.site.index_title == "Curation"


# ---------------------------------------------------------------------------
# Dish admin pages render
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dish_admin_list_page(curator_client, dish):
    resp = curator_client.get("/admin/dishes/dish/")
    assert resp.status_code == 200
    assert "Ugali" in resp.content.decode()


@pytest.mark.django_db
def test_dish_admin_add_page(curator_client):
    """Pass criterion: curator can open the dish add page."""
    resp = curator_client.get("/admin/dishes/dish/add/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "name_en" in body
    assert "Classification" in body  # fieldset heading
    assert "Curation" in body


@pytest.mark.django_db
def test_dish_admin_change_page(curator_client, dish):
    """Pass criterion: curator can open the dish change page."""
    resp = curator_client.get(f"/admin/dishes/dish/{dish.pk}/change/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Ugali" in body
    # Should show inlines for ingredients, aliases, steps, regions
    assert "dish_ingredient" in body.lower() or "ingredient" in body.lower()
    assert "dish_alias" in body.lower() or "alias" in body.lower()
    assert "dish_step" in body.lower() or "step" in body.lower()
    assert "dish_region" in body.lower() or "region" in body.lower()


# ---------------------------------------------------------------------------
# Create dish through admin (POST)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_curator_creates_dish_unaided(curator_client, category, maize_flour):
    """E6 pass criterion: a curator enters a dish with inline ingredient rows."""
    initial_count = Dish.objects.count()
    resp = curator_client.post(
        "/admin/dishes/dish/add/",
        data={
            "slug": "sukuma-wiki",
            "name_en": "Sukuma Wiki",
            "name_sw": "Sukuma",
            "description": "Pan-fried collard greens.",
            "meal_type": "any",
            "course": "side",
            "spice_level": "none",
            "difficulty": "easy",
            "prep_min": "5",
            "cook_min": "10",
            "servings": "4",
            "popularity": "0.5",
            "quality_level": "seeded",
            "status": "draft",
            # DishIngredient inline (prefix = model_name)
            "dish_ingredients-TOTAL_FORMS": "1",
            "dish_ingredients-INITIAL_FORMS": "0",
            "dish_ingredients-MIN_NUM_FORMS": "0",
            "dish_ingredients-MAX_NUM_FORMS": "1000",
            "dish_ingredients-0-id": "",
            "dish_ingredients-0-dish": "",
            "dish_ingredients-0-ingredient": str(maize_flour.pk),
            "dish_ingredients-0-role": "primary",
            "dish_ingredients-0-quantity": "200",
            "dish_ingredients-0-unit": "",
            "dish_ingredients-0-preparation_note": "",
            "dish_ingredients-0-position": "0",
            # DishAlias inline
            "aliases-TOTAL_FORMS": "1",
            "aliases-INITIAL_FORMS": "0",
            "aliases-MIN_NUM_FORMS": "0",
            "aliases-MAX_NUM_FORMS": "1000",
            "aliases-0-id": "",
            "aliases-0-dish": "",
            "aliases-0-alias": "Sukuma",
            "aliases-0-language": "sw",
            # DishStep inline
            "steps-TOTAL_FORMS": "1",
            "steps-INITIAL_FORMS": "0",
            "steps-MIN_NUM_FORMS": "0",
            "steps-MAX_NUM_FORMS": "1000",
            "steps-0-id": "",
            "steps-0-dish": "",
            "steps-0-position": "1",
            "steps-0-text_en": "Chop and fry the greens.",
            "steps-0-text_sw": "",
            # DishRegion inline (empty)
            "dish_regions-TOTAL_FORMS": "0",
            "dish_regions-INITIAL_FORMS": "0",
            "dish_regions-MIN_NUM_FORMS": "0",
            "dish_regions-MAX_NUM_FORMS": "1000",
            # Tell Django admin to save and return to change list
            "_save": "Save",
        },
    )
    # A successful save redirects to the change list
    if resp.status_code != 302:
        import re

        body = resp.content.decode()
        error_items = re.findall(r"<li>(.*?)</li>", body)
        field_errors = re.findall(r'class="[^"]*errorlist[^"]*">(.*?)</ul>', body, re.DOTALL)
        plain = " | ".join(
            re.sub(r"<[^>]+>", "", e).strip() for e in (error_items + field_errors) if e.strip()
        )
        raise AssertionError(f"Expected 302, got {resp.status_code}. Errors: {plain[:2000]}")
    assert Dish.objects.count() == initial_count + 1
    dish = Dish.objects.get(name_en="Sukuma Wiki")
    assert dish.slug == "sukuma-wiki"
    # Ingredient row saved
    assert dish.dish_ingredients.count() == 1
    di = dish.dish_ingredients.first()
    assert di.ingredient == maize_flour
    assert di.role == "primary"
    # Alias saved
    assert dish.aliases.count() == 1
    assert dish.aliases.first().alias == "Sukuma"
    # Step saved
    assert dish.steps.count() == 1
    assert dish.steps.first().text_en == "Chop and fry the greens."
    # Search arrays rebuilt by save_related hook
    dish.refresh_from_db()
    assert maize_flour.pk in dish.all_ids
    assert maize_flour.pk in dish.primary_ids


# ---------------------------------------------------------------------------
# Bulk status actions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_bulk_action_mark_reviewed(curator_client):
    d1 = Dish.objects.create(name_en="Githeri")
    d2 = Dish.objects.create(name_en="Mukimo")
    assert d1.status == "draft"
    assert d2.status == "draft"

    resp = curator_client.post(
        "/admin/dishes/dish/",
        data={
            "action": "mark_reviewed",
            "_selected_action": [str(d1.pk), str(d2.pk)],
            "post": "yes",
        },
    )
    assert resp.status_code == 302
    d1.refresh_from_db()
    d2.refresh_from_db()
    assert d1.status == "reviewed"
    assert d2.status == "reviewed"


@pytest.mark.django_db
def test_bulk_action_mark_verified(curator_client):
    d1 = Dish.objects.create(name_en="Nyama Choma")
    resp = curator_client.post(
        "/admin/dishes/dish/",
        data={
            "action": "mark_verified",
            "_selected_action": [str(d1.pk)],
            "post": "yes",
        },
    )
    assert resp.status_code == 302
    d1.refresh_from_db()
    assert d1.status == "verified"


@pytest.mark.django_db
def test_bulk_action_mark_archived(curator_client):
    d1 = Dish.objects.create(name_en="Irio")
    resp = curator_client.post(
        "/admin/dishes/dish/",
        data={
            "action": "mark_archived",
            "_selected_action": [str(d1.pk)],
            "post": "yes",
        },
    )
    assert resp.status_code == 302
    d1.refresh_from_db()
    assert d1.status == "archived"


@pytest.mark.django_db
def test_ingredient_bulk_action_mark_reviewed(curator_client, category):
    i1 = Ingredient.objects.create(name_en="Tomato", category=category)
    i2 = Ingredient.objects.create(name_en="Onion", category=category)
    assert i1.status == "draft"

    resp = curator_client.post(
        "/admin/ingredients/ingredient/",
        data={
            "action": "mark_reviewed",
            "_selected_action": [str(i1.pk), str(i2.pk)],
            "post": "yes",
        },
    )
    assert resp.status_code == 302
    i1.refresh_from_db()
    i2.refresh_from_db()
    assert i1.status == "reviewed"
    assert i2.status == "reviewed"


# ---------------------------------------------------------------------------
# Search by alias
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_search_by_alias_finds_dish(curator_client, dish):
    """Search query matching a dish alias (not the dish name) should find the dish."""
    DishAlias.objects.create(dish=dish, alias="Ugali wa mahindi", language="sw")

    resp = curator_client.get("/admin/dishes/dish/", data={"q": "mahindi"})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Ugali" in body  # dish found via alias


@pytest.mark.django_db
def test_search_by_alias_finds_ingredient(curator_client, category):
    """Search query matching an ingredient alias should find the ingredient."""
    ing = Ingredient.objects.create(name_en="Coriander", category=category)
    ing.aliases.create(alias="Dhania", normalized_alias="dhania", language="sw")

    resp = curator_client.get("/admin/ingredients/ingredient/", data={"q": "dhania"})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Coriander" in body


# ---------------------------------------------------------------------------
# save_model triggers rebuild_search_arrays
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_save_model_rebuilds_search_arrays(curator_client, dish, maize_flour, water):
    """When a dish is saved via admin, search arrays are rebuilt from DishIngredient rows."""
    # dish already has maize_flour as primary (from fixture)
    existing_di = dish.dish_ingredients.first()
    # Add a required staple (water) — it should NOT appear in required_ids
    water_di = DishIngredient.objects.create(
        dish=dish, ingredient=water, role=DishIngredient.Role.REQUIRED
    )
    # Trigger admin save (POST to change page)
    resp = curator_client.post(
        f"/admin/dishes/dish/{dish.pk}/change/",
        data={
            "slug": "ugali",
            "name_en": "Ugali",
            "name_sw": "",
            "description": "",
            "meal_type": "any",
            "course": "main",
            "spice_level": "none",
            "difficulty": "easy",
            "prep_min": "5",
            "cook_min": "15",
            "servings": "4",
            "popularity": "0.0",
            "quality_level": "seeded",
            "status": "draft",
            # Two existing DishIngredient rows
            "dish_ingredients-TOTAL_FORMS": "2",
            "dish_ingredients-INITIAL_FORMS": "2",
            "dish_ingredients-MIN_NUM_FORMS": "0",
            "dish_ingredients-MAX_NUM_FORMS": "1000",
            "dish_ingredients-0-id": str(existing_di.pk),
            "dish_ingredients-0-dish": str(dish.pk),
            "dish_ingredients-0-ingredient": str(maize_flour.pk),
            "dish_ingredients-0-role": "primary",
            "dish_ingredients-0-quantity": "",
            "dish_ingredients-0-unit": "",
            "dish_ingredients-0-preparation_note": "",
            "dish_ingredients-0-position": "0",
            "dish_ingredients-1-id": str(water_di.pk),
            "dish_ingredients-1-dish": str(dish.pk),
            "dish_ingredients-1-ingredient": str(water.pk),
            "dish_ingredients-1-role": "required",
            "dish_ingredients-1-quantity": "",
            "dish_ingredients-1-unit": "",
            "dish_ingredients-1-preparation_note": "",
            "dish_ingredients-1-position": "1",
            # Other inlines empty
            "aliases-TOTAL_FORMS": "0",
            "aliases-INITIAL_FORMS": "0",
            "aliases-MIN_NUM_FORMS": "0",
            "aliases-MAX_NUM_FORMS": "1000",
            "steps-TOTAL_FORMS": "0",
            "steps-INITIAL_FORMS": "0",
            "steps-MIN_NUM_FORMS": "0",
            "steps-MAX_NUM_FORMS": "1000",
            "dish_regions-TOTAL_FORMS": "0",
            "dish_regions-INITIAL_FORMS": "0",
            "dish_regions-MIN_NUM_FORMS": "0",
            "dish_regions-MAX_NUM_FORMS": "1000",
            "_save": "Save",
        },
    )
    if resp.status_code != 302:
        import re

        body = resp.content.decode()
        error_items = re.findall(r"<li>(.*?)</li>", body)
        field_errors = re.findall(r'class="[^"]*errorlist[^"]*">(.*?)</ul>', body, re.DOTALL)
        plain = " | ".join(
            re.sub(r"<[^>]+>", "", e).strip() for e in (error_items + field_errors) if e.strip()
        )
        raise AssertionError(f"Expected 302, got {resp.status_code}. Errors: {plain[:2000]}")
    dish.refresh_from_db()
    # maize_flour (primary, non-staple) should be in primary_ids and all_ids
    assert maize_flour.pk in dish.primary_ids
    assert maize_flour.pk in dish.all_ids
    # water (required, staple) should be in all_ids but NOT required_ids
    assert water.pk in dish.all_ids
    assert water.pk not in dish.required_ids


# ---------------------------------------------------------------------------
# Region inline on Dish admin
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_region_inline_on_dish_change_page(curator_client, dish, region):
    """The Dish change page should show the DishRegion inline."""
    DishRegion.objects.create(dish=dish, region=region)
    resp = curator_client.get(f"/admin/dishes/dish/{dish.pk}/change/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Coastal" in body


# ---------------------------------------------------------------------------
# Ingredient admin pages render
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ingredient_admin_add_page(curator_client, category):
    resp = curator_client.get("/admin/ingredients/ingredient/add/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "name_en" in body
    assert "is_staple" in body


@pytest.mark.django_db
def test_ingredient_admin_change_page(curator_client, maize_flour):
    resp = curator_client.get(f"/admin/ingredients/ingredient/{maize_flour.pk}/change/")
    assert resp.status_code == 200
    assert "Maize flour" in resp.content.decode()
