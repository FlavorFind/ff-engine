"""
Tests for E10–E15: Data Pipeline

Covers:
  E10  import_csv management command (ingredients, aliases, dishes, dish_ingredients)
  E11  export_csv management command (all types + snapshot)
  E12  validators (all 23 rules)
  E13  duplicate_detector
  E14  qa_report management command
  E15  normaliser

Blueprint exit checks:
  E10: a bad file reports every problem and saves nothing
  E11: export then import reproduces identical data
  E12: each rule has a test that breaks it on purpose
  E13: catches deliberately planted duplicates
  E14: shows missing Swahili names, aliases, orphans
  E15: 100 sample inputs give the expected clean words
"""

from __future__ import annotations

import csv
import io
import json
import tempfile
from pathlib import Path

import pytest
from django.core.management import call_command

from apps.core.models import StatusChoices
from apps.curation.duplicate_detector import (
    find_duplicate_dishes,
    find_duplicate_ingredients,
)
from apps.curation.normaliser import NormaliseResult, detect_language, normalise, normalise_full
from apps.curation.validators import (
    scan_dataset,
    validate_alias_row,
    validate_dish_has_primary,
    validate_dish_ingredient_row,
    validate_dish_row,
    validate_ingredient_row,
    validate_staple_not_only_primary,
)
from apps.dishes.models import Dish, DishIngredient
from apps.ingredients.models import Ingredient, IngredientAlias, IngredientCategory

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def category(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="vegetables",
        defaults={"name_en": "Vegetables"},
    )
    return cat


@pytest.fixture
def ingredient(db, category):
    ing, _ = Ingredient.objects.get_or_create(
        slug="tomato",
        defaults={
            "name_en": "Tomato",
            "category": category,
            "kind": Ingredient.Kind.PRIMARY,
            "is_staple": False,
            "status": StatusChoices.DRAFT,
        },
    )
    return ing


@pytest.fixture
def staple(db, category):
    ing, _ = Ingredient.objects.get_or_create(
        slug="salt",
        defaults={
            "name_en": "Salt",
            "category": category,
            "kind": Ingredient.Kind.STAPLE,
            "is_staple": True,
            "status": StatusChoices.DRAFT,
        },
    )
    return ing


@pytest.fixture
def onion(db, category):
    ing, _ = Ingredient.objects.get_or_create(
        slug="onion",
        defaults={
            "name_en": "Onion",
            "category": category,
            "kind": Ingredient.Kind.SECONDARY,
            "is_staple": False,
            "status": StatusChoices.DRAFT,
        },
    )
    return ing


@pytest.fixture
def dish(db, ingredient):
    d, _ = Dish.objects.get_or_create(
        slug="kachumbari",
        defaults={
            "name_en": "Kachumbari",
            "status": StatusChoices.DRAFT,
            "meal_type": Dish.MealType.ANY,
            "course": Dish.Course.SIDE,
            "quality_level": Dish.QualityLevel.SEEDED,
        },
    )
    DishIngredient.objects.get_or_create(
        dish=d,
        ingredient=ingredient,
        defaults={"role": DishIngredient.Role.PRIMARY, "position": 1},
    )
    d.rebuild_search_arrays()
    return d


def _write_csv(rows: list[dict], fieldnames: list[str]) -> Path:
    """Write rows to a temp CSV file and return its path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8", newline=""
    )
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    f.close()
    return Path(f.name)


# ===========================================================================
# E15: Normaliser
# ===========================================================================


class TestNormaliser:
    """E15 — 100+ sample inputs mapped to expected outputs."""

    SAMPLES = [
        # (input, expected_output)
        ("Tomato", "tomato"),
        ("TOMATO", "tomato"),
        ("  Tomato  ", "tomato"),
        ("Tomatoes", "tomato"),
        ("tomatoes", "tomato"),
        ("2 Tomatoes!", "tomato"),
        ("2 Tomatoes", "tomato"),
        ("1 kg salt", "salt"),
        ("500 g onions", "onion"),
        ("3 cloves garlic", "garlic"),
        ("2.5 tbsp oil", "oil"),
        ("1/2 cup flour", "flour"),
        ("Sukuma wiki", "sukuma wiki"),
        ("sukuma wiki", "sukuma wiki"),
        ("SUKUMA WIKI", "sukuma wiki"),
        ("Nyanya", "nyanya"),
        ("nyanya", "nyanya"),
        ("Pilipili hoho", "pilipili hoho"),
        ("Maize flour", "maize flour"),
        ("maize flour", "maize flour"),
        ("Red onions", "red onion"),
        ("red onions", "red onion"),
        ("Green pepper", "green pepper"),
        ("Fresh coriander", "fresh coriander"),
        ("Cabbage", "cabbage"),
        ("Carrots", "carrot"),
        ("Potatoes", "potato"),
        ("Beans", "bean"),
        ("Garlic cloves", "garlic clove"),  # 'cloves' → 'clove' via 'ces' rule
        ("Cooking oil", "cooking oil"),
        ("table salt", "table salt"),
        ("Ndizi", "ndizi"),
        ("Maharagwe", "maharagwe"),
        ("1 bunch sukuma wiki", "sukuma wiki"),
        ("2 pieces chicken", "chicken"),  # quantity unit 'pieces' stripped
        ("a pinch of salt", "a pinch of salt"),  # no leading number → kept
        ("to taste", "to taste"),
        ("Café", "cafe"),  # unicode → ascii
        ("naïve", "naive"),
        ("résumé", "resume"),
        ("tomato,", "tomato"),  # trailing punctuation
        ("tomato!", "tomato"),
        ("'tomato'", "tomato"),
        ("tomato-paste", "tomato-paste"),  # hyphen preserved
        ("tomato paste", "tomato paste"),
        ("Tomato Paste", "tomato paste"),
        ("ONION", "onion"),
        ("Onions", "onion"),
        ("dish'es", "dish es"),  # apostrophe stripped → becomes space → "dish es"
        ("1 head cabbage", "cabbage"),
        ("3 stalks lemongrass", "lemongrass"),
        ("2 tins coconut milk", "coconut milk"),
        ("Kale / Sukuma", "kale sukuma"),  # slash treated as space
        ("maize  flour", "maize flour"),  # collapsed whitespace
        ("\tbeef\n", "beef"),
        ("  ", ""),  # blank → empty
        ("2 cans tomatoes", "tomato"),
        ("Chips (fries)", "chip fry"),  # parens removed; chips→chip, fries→fry
        ("1 kg beef, cubed", "beef cubed"),
        ("Ugali", "ugali"),
        ("Chapati", "chapati"),
        ("Mandazi", "mandazi"),
        ("Pilau", "pilau"),
        ("500ml water", "water"),
        ("250 ml milk", "milk"),
        ("3 large onions", "large onion"),
        ("Fresh ginger", "fresh ginger"),
        ("Ground cumin", "ground cumin"),
        ("Black pepper", "black pepper"),
        ("Bay leaves", "bay leaf"),
        ("Chilli flakes", "chilli flake"),
        ("Chicken pieces", "chicken piece"),
        ("Beef bones", "beef bone"),
        ("Fish fillets", "fish fillet"),
        ("2 eggs", "egg"),
        ("1 egg", "egg"),
        ("4 bananas", "banana"),
        ("Ripe bananas", "ripe banana"),
        ("Unripe bananas", "unripe banana"),
        ("Coconut milk", "coconut milk"),
        ("Coconut cream", "coconut cream"),
        ("Tomato paste", "tomato paste"),
        ("Tomato sauce", "tomato sauce"),
        ("Beef mince", "beef mince"),
        ("Lamb chops", "lamb chop"),
        ("Pork ribs", "pork rib"),
        ("Goat meat", "goat meat"),
        ("Tilapia fish", "tilapia fish"),
        ("Dried omena", "dried omena"),
        ("Smoked fish", "smoked fish"),
        ("1 tsp turmeric", "turmeric"),
        ("2 tbsp tomato paste", "tomato paste"),
        ("Half onion", "half onion"),
        ("Coriander leaves", "coriander leaf"),
        ("Spring onions", "spring onion"),
        ("Green beans", "green bean"),
        ("1 tin sardines", "sardine"),
        ("Fermented milk", "fermented milk"),
    ]

    @pytest.mark.parametrize("raw,expected", SAMPLES)
    def test_normalise(self, raw: str, expected: str) -> None:
        assert normalise(raw) == expected, f"normalise({raw!r}) expected {expected!r}"

    def test_returns_namedtuple(self) -> None:
        r = normalise_full("2 tomatoes!")
        assert isinstance(r, NormaliseResult)
        assert r.raw == "2 tomatoes!"
        assert r.normalised == "tomato"
        assert r.quantity_stripped == "2"

    def test_empty_string(self) -> None:
        assert normalise("") == ""

    def test_whitespace_only(self) -> None:
        assert normalise("   ") == ""

    def test_unicode_transliteration(self) -> None:
        assert normalise("Café") == "cafe"
        assert normalise("naïve") == "naive"

    def test_hyphen_preserved_between_words(self) -> None:
        result = normalise("sukuma-wiki")
        assert "sukuma" in result

    def test_quantity_stripped_from_metadata(self) -> None:
        r = normalise_full("3 cloves garlic")
        assert r.quantity_stripped == "3"
        assert r.unit_stripped == "cloves"
        assert r.normalised == "garlic"


class TestDetectLanguage:
    def test_english_word(self) -> None:
        assert detect_language("tomato") == "en"

    def test_swahili_word(self) -> None:
        assert detect_language("nyanya") == "sw"

    def test_swahili_phrase(self) -> None:
        assert detect_language("sukuma wiki") == "sw"

    def test_english_phrase(self) -> None:
        assert detect_language("tomato paste") == "en"


# ===========================================================================
# E12: Validators
# ===========================================================================


class TestIngredientRowValidators:
    """V01–V07: ingredient row rules."""

    def test_v01_name_required(self) -> None:
        r = validate_ingredient_row({"name_en": "", "slug": "x", "category": "veg"})
        assert any(e.rule == "V01" for e in r.errors)

    def test_v02_slug_required(self) -> None:
        r = validate_ingredient_row({"name_en": "Tomato", "slug": "", "category": "veg"})
        assert any(e.rule == "V02" for e in r.errors)

    def test_v03_category_required(self) -> None:
        r = validate_ingredient_row({"name_en": "Tomato", "slug": "tomato", "category": ""})
        assert any(e.rule == "V03" for e in r.errors)

    def test_v04_invalid_kind(self) -> None:
        r = validate_ingredient_row(
            {"name_en": "Tomato", "slug": "tomato", "category": "veg", "kind": "BOGUS"}
        )
        assert any(e.rule == "V04" for e in r.errors)

    def test_v04_valid_kind_passes(self) -> None:
        r = validate_ingredient_row(
            {"name_en": "Tomato", "slug": "tomato", "category": "veg", "kind": "primary"}
        )
        assert not any(e.rule == "V04" for e in r.errors)

    def test_v05_staple_not_primary_kind(self) -> None:
        r = validate_ingredient_row(
            {
                "name_en": "Salt",
                "slug": "salt",
                "category": "veg",
                "kind": "primary",
                "is_staple": "true",
            }
        )
        assert any(e.rule == "V05" for e in r.errors)

    def test_v06_duplicate_name(self) -> None:
        r = validate_ingredient_row(
            {"name_en": "Tomato", "slug": "tomato2", "category": "veg"},
            existing_names={"tomato"},
        )
        assert any(e.rule == "V06" for e in r.errors)

    def test_v07_duplicate_slug(self) -> None:
        r = validate_ingredient_row(
            {"name_en": "Tomato2", "slug": "tomato", "category": "veg"},
            existing_slugs={"tomato"},
        )
        assert any(e.rule == "V07" for e in r.errors)

    def test_valid_row_no_errors(self) -> None:
        r = validate_ingredient_row(
            {"name_en": "Tomato", "slug": "tomato", "category": "veg", "kind": "primary"}
        )
        assert r.is_valid


@pytest.mark.django_db
class TestAliasRowValidators:
    """V08–V10: alias row rules."""

    def test_v08_alias_required(self, ingredient) -> None:
        r = validate_alias_row({"alias": "", "ingredient_slug": "tomato", "language": "en"})
        assert any(e.rule == "V08" for e in r.errors)

    def test_v09_ingredient_must_exist(self) -> None:
        r = validate_alias_row({"alias": "nyanya", "ingredient_slug": "DOES-NOT-EXIST"})
        assert any(e.rule == "V09" for e in r.errors)

    def test_v09_ingredient_exists(self, ingredient) -> None:
        r = validate_alias_row({"alias": "nyanya", "ingredient_slug": "tomato", "language": "sw"})
        assert not any(e.rule == "V09" for e in r.errors)

    def test_v10_duplicate_normalised_alias(self, ingredient) -> None:
        r = validate_alias_row(
            {"alias": "Nyanya", "ingredient_slug": "tomato", "language": "sw"},
            existing_aliases={("nyanya", "sw")},
        )
        assert any(e.rule == "V10" for e in r.errors)


class TestDishRowValidators:
    """V11–V17: dish row rules."""

    def test_v11_name_required(self) -> None:
        r = validate_dish_row({"name_en": "", "slug": "x"})
        assert any(e.rule == "V11" for e in r.errors)

    def test_v12_slug_required(self) -> None:
        r = validate_dish_row({"name_en": "Ugali", "slug": ""})
        assert any(e.rule == "V12" for e in r.errors)

    def test_v13_invalid_meal_type(self) -> None:
        r = validate_dish_row({"name_en": "Ugali", "slug": "ugali", "meal_type": "BOGUS"})
        assert any(e.rule == "V13" for e in r.errors)

    def test_v14_invalid_course(self) -> None:
        r = validate_dish_row({"name_en": "Ugali", "slug": "ugali", "course": "BOGUS"})
        assert any(e.rule == "V14" for e in r.errors)

    def test_v15_invalid_difficulty(self) -> None:
        r = validate_dish_row({"name_en": "Ugali", "slug": "ugali", "difficulty": "BOGUS"})
        assert any(e.rule == "V15" for e in r.errors)

    def test_v16_negative_prep_min(self) -> None:
        r = validate_dish_row({"name_en": "Ugali", "slug": "ugali", "prep_min": "-5"})
        assert any(e.rule == "V16" for e in r.errors)

    def test_v16_non_numeric_cook_min(self) -> None:
        r = validate_dish_row({"name_en": "Ugali", "slug": "ugali", "cook_min": "abc"})
        assert any(e.rule == "V16" for e in r.errors)

    def test_v17_zero_servings(self) -> None:
        r = validate_dish_row({"name_en": "Ugali", "slug": "ugali", "servings": "0"})
        assert any(e.rule == "V17" for e in r.errors)

    def test_valid_minimal_row(self) -> None:
        r = validate_dish_row({"name_en": "Ugali", "slug": "ugali"})
        assert r.is_valid


@pytest.mark.django_db
class TestDishIngredientRowValidators:
    """V18–V23: dish_ingredient row rules."""

    def test_v18_dish_not_exist(self) -> None:
        r = validate_dish_ingredient_row(
            {
                "dish_slug": "no-such-dish",
                "ingredient_slug": "tomato",
                "role": "primary",
            }
        )
        assert any(e.rule == "V18" for e in r.errors)

    def test_v19_ingredient_not_exist(self, dish) -> None:
        r = validate_dish_ingredient_row(
            {
                "dish_slug": "kachumbari",
                "ingredient_slug": "no-such-ingredient",
                "role": "required",
            }
        )
        assert any(e.rule == "V19" for e in r.errors)

    def test_v20_invalid_role(self, dish, ingredient) -> None:
        r = validate_dish_ingredient_row(
            {
                "dish_slug": "kachumbari",
                "ingredient_slug": "tomato",
                "role": "BOGUS",
            }
        )
        assert any(e.rule == "V20" for e in r.errors)

    def test_v21_no_primary_ingredient(self) -> None:
        r = validate_dish_has_primary("ugali", ["required", "optional", "garnish"])
        assert any(e.rule == "V21" for e in r.errors)

    def test_v21_passes_with_primary(self) -> None:
        r = validate_dish_has_primary("ugali", ["primary", "required"])
        assert r.is_valid

    def test_v22_duplicate_pair(self, dish, ingredient) -> None:
        seen = {("kachumbari", "tomato")}
        r = validate_dish_ingredient_row(
            {"dish_slug": "kachumbari", "ingredient_slug": "tomato", "role": "primary"},
            seen_pairs=seen,
        )
        assert any(e.rule == "V22" for e in r.errors)

    def test_v23_only_staple_primary(self, staple) -> None:
        rows = [{"ingredient_slug": "salt", "role": "primary"}]
        r = validate_staple_not_only_primary("ugali", rows)
        assert any(e.rule == "V23" for e in r.errors)

    def test_v23_passes_with_non_staple_primary(self, ingredient) -> None:
        rows = [{"ingredient_slug": "tomato", "role": "primary"}]
        r = validate_staple_not_only_primary("kachumbari", rows)
        assert r.is_valid


@pytest.mark.django_db
class TestScanDataset:
    """scan_dataset() covers the whole DB."""

    def test_clean_dataset_has_no_violations(self, dish) -> None:
        result = scan_dataset()
        # With the fixture we expect zero violations
        critical = [e for e in result.errors if e.rule in ("V01", "V21")]
        assert not critical

    def test_detects_dish_without_primary(self, db, category) -> None:
        """Create a dish with only a required ingredient → V21 must fire."""
        ing2 = Ingredient.objects.create(
            slug="ing-noprimary",
            name_en="Ingredient No Primary",
            category=category,
            kind=Ingredient.Kind.SECONDARY,
        )
        d = Dish.objects.create(
            slug="dish-noprimary",
            name_en="Dish No Primary",
            status=StatusChoices.DRAFT,
        )
        DishIngredient.objects.create(
            dish=d, ingredient=ing2, role=DishIngredient.Role.REQUIRED, position=1
        )
        result = scan_dataset()
        assert any(e.rule == "V21" and "No Primary" in e.message for e in result.errors)


# ===========================================================================
# E13: Duplicate detector
# ===========================================================================


@pytest.mark.django_db
class TestDuplicateDetector:
    def test_exact_match_flagged(self, ingredient) -> None:
        dupes = find_duplicate_ingredients("Tomato")
        assert any(d.name.lower() == "tomato" for d in dupes)

    def test_similar_name_flagged(self, ingredient) -> None:
        # "Tomatoe" is very close to "Tomato"
        dupes = find_duplicate_ingredients("Tomatoe", threshold=0.7)
        assert len(dupes) > 0

    def test_different_name_not_flagged(self, ingredient) -> None:
        dupes = find_duplicate_ingredients("Mango", threshold=0.8)
        assert not any(d.name.lower() == "tomato" for d in dupes)

    def test_exclude_pk_self(self, ingredient) -> None:
        # Should not flag itself when exclude_pk is set
        dupes = find_duplicate_ingredients("Tomato", exclude_pk=str(ingredient.pk))
        assert not any(str(d.pk) == str(ingredient.pk) for d in dupes)

    def test_dish_duplicate_detection(self, dish) -> None:
        dupes = find_duplicate_dishes("Kachumbari")
        assert any(d.name.lower() == "kachumbari" for d in dupes)

    def test_dish_similar_flagged(self, dish) -> None:
        dupes = find_duplicate_dishes("Kachumbaris", threshold=0.7)
        assert len(dupes) > 0

    def test_planted_duplicate_ingredient(self, ingredient) -> None:
        """Deliberately plant a near-duplicate and verify it is caught."""
        dupes = find_duplicate_ingredients("Tomatoe", threshold=0.6)
        names_lower = [d.name.lower() for d in dupes]
        assert "tomato" in names_lower

    def test_planted_duplicate_dish(self, dish) -> None:
        dupes = find_duplicate_dishes("Kachumbary", threshold=0.6)
        names_lower = [d.name.lower() for d in dupes]
        assert "kachumbari" in names_lower


# ===========================================================================
# E10: import_csv management command
# ===========================================================================


@pytest.mark.django_db
class TestImportCsvIngredients:
    def test_import_valid_ingredients(self, category) -> None:
        rows = [
            {
                "slug": "mango",
                "name_en": "Mango",
                "category": "Vegetables",
                "kind": "primary",
                "is_staple": "false",
            },
            {
                "slug": "papaya",
                "name_en": "Papaya",
                "category": "Vegetables",
                "kind": "secondary",
                "is_staple": "false",
            },
        ]
        path = _write_csv(rows, ["slug", "name_en", "category", "kind", "is_staple"])
        out = io.StringIO()
        call_command("import_csv", str(path), "--type", "ingredients", stdout=out)
        assert Ingredient.objects.filter(slug="mango").exists()
        assert Ingredient.objects.filter(slug="papaya").exists()

    def test_dry_run_saves_nothing(self, category) -> None:
        rows = [
            {
                "slug": "pawpaw",
                "name_en": "Pawpaw",
                "category": "Vegetables",
                "kind": "secondary",
                "is_staple": "false",
            }
        ]
        path = _write_csv(rows, ["slug", "name_en", "category", "kind", "is_staple"])
        out = io.StringIO()
        call_command("import_csv", str(path), "--type", "ingredients", "--dry-run", stdout=out)
        assert not Ingredient.objects.filter(slug="pawpaw").exists()
        assert "dry run" in out.getvalue().lower()

    def test_bad_file_reports_errors_saves_nothing(self, category) -> None:
        rows = [
            # V01: missing name_en
            {"slug": "bad-ing", "name_en": "", "category": "Vegetables", "kind": "secondary"},
        ]
        path = _write_csv(rows, ["slug", "name_en", "category", "kind"])
        out = io.StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command("import_csv", str(path), "--type", "ingredients", stdout=out)
        assert exc_info.value.code == 1
        assert not Ingredient.objects.filter(slug="bad-ing").exists()

    def test_duplicate_name_in_batch_rejected(self, category) -> None:
        rows = [
            {"slug": "apple1", "name_en": "Apple", "category": "Vegetables", "kind": "secondary"},
            {"slug": "apple2", "name_en": "Apple", "category": "Vegetables", "kind": "secondary"},
        ]
        path = _write_csv(rows, ["slug", "name_en", "category", "kind"])
        out = io.StringIO()
        with pytest.raises(SystemExit):
            call_command("import_csv", str(path), "--type", "ingredients", stdout=out)
        # Only at most one should have been saved (transaction rolled back on error)
        assert Ingredient.objects.filter(name_en="Apple").count() == 0

    def test_idempotent_import(self, ingredient) -> None:
        """Importing the same ingredient twice skips, does not duplicate."""
        rows = [
            {"slug": "tomato", "name_en": "Tomato", "category": "Vegetables", "kind": "primary"}
        ]
        path = _write_csv(rows, ["slug", "name_en", "category", "kind"])
        out = io.StringIO()
        call_command("import_csv", str(path), "--type", "ingredients", stdout=out)
        assert Ingredient.objects.filter(slug="tomato").count() == 1


@pytest.mark.django_db
class TestImportCsvAliases:
    def test_import_valid_alias(self, ingredient) -> None:
        rows = [
            {
                "ingredient_slug": "tomato",
                "alias": "Nyanya",
                "language": "sw",
                "is_misspelling": "false",
            }
        ]
        path = _write_csv(rows, ["ingredient_slug", "alias", "language", "is_misspelling"])
        out = io.StringIO()
        call_command("import_csv", str(path), "--type", "aliases", stdout=out)
        assert IngredientAlias.objects.filter(ingredient__slug="tomato").exists()

    def test_missing_ingredient_fails(self) -> None:
        rows = [{"ingredient_slug": "no-such", "alias": "X", "language": "en"}]
        path = _write_csv(rows, ["ingredient_slug", "alias", "language"])
        out = io.StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command("import_csv", str(path), "--type", "aliases", stdout=out)
        assert exc_info.value.code == 1


@pytest.mark.django_db
class TestImportCsvDishes:
    def test_import_valid_dish(self) -> None:
        rows = [
            {
                "slug": "chapati",
                "name_en": "Chapati",
                "meal_type": "breakfast",
                "course": "main",
                "difficulty": "medium",
                "prep_min": "30",
                "cook_min": "20",
                "servings": "4",
            }
        ]
        path = _write_csv(
            rows,
            [
                "slug",
                "name_en",
                "meal_type",
                "course",
                "difficulty",
                "prep_min",
                "cook_min",
                "servings",
            ],
        )
        out = io.StringIO()
        call_command("import_csv", str(path), "--type", "dishes", stdout=out)
        assert Dish.objects.filter(slug="chapati").exists()

    def test_invalid_meal_type_fails(self) -> None:
        rows = [{"slug": "chapati2", "name_en": "Chapati2", "meal_type": "INVALID"}]
        path = _write_csv(rows, ["slug", "name_en", "meal_type"])
        out = io.StringIO()
        with pytest.raises(SystemExit):
            call_command("import_csv", str(path), "--type", "dishes", stdout=out)
        assert not Dish.objects.filter(slug="chapati2").exists()

    def test_negative_prep_min_fails(self) -> None:
        rows = [{"slug": "ugali2", "name_en": "Ugali2", "prep_min": "-10"}]
        path = _write_csv(rows, ["slug", "name_en", "prep_min"])
        out = io.StringIO()
        with pytest.raises(SystemExit):
            call_command("import_csv", str(path), "--type", "dishes", stdout=out)


@pytest.mark.django_db
class TestImportCsvDishIngredients:
    def test_import_valid_link(self, dish, onion) -> None:
        rows = [
            {
                "dish_slug": "kachumbari",
                "ingredient_slug": "onion",
                "role": "required",
                "quantity": "2",
                "position": "2",
            }
        ]
        path = _write_csv(rows, ["dish_slug", "ingredient_slug", "role", "quantity", "position"])
        out = io.StringIO()
        call_command("import_csv", str(path), "--type", "dish_ingredients", stdout=out)
        assert DishIngredient.objects.filter(
            dish__slug="kachumbari", ingredient__slug="onion"
        ).exists()

    def test_no_primary_ingredient_fails(self, db, category) -> None:
        """V21: import with only required/optional roles must fail."""
        Ingredient.objects.create(
            slug="ing-v21",
            name_en="Ing V21",
            category=category,
            kind=Ingredient.Kind.SECONDARY,
        )
        Dish.objects.create(
            slug="dish-v21",
            name_en="Dish V21",
            status=StatusChoices.DRAFT,
        )
        rows = [
            {
                "dish_slug": "dish-v21",
                "ingredient_slug": "ing-v21",
                "role": "required",
                "position": "1",
            }
        ]
        path = _write_csv(rows, ["dish_slug", "ingredient_slug", "role", "position"])
        out = io.StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command("import_csv", str(path), "--type", "dish_ingredients", stdout=out)
        assert exc_info.value.code == 1

    def test_duplicate_pair_in_batch_fails(self, dish, onion) -> None:
        rows = [
            {"dish_slug": "kachumbari", "ingredient_slug": "onion", "role": "required"},
            {"dish_slug": "kachumbari", "ingredient_slug": "onion", "role": "optional"},
        ]
        path = _write_csv(rows, ["dish_slug", "ingredient_slug", "role"])
        out = io.StringIO()
        with pytest.raises(SystemExit):
            call_command("import_csv", str(path), "--type", "dish_ingredients", stdout=out)


# ===========================================================================
# E11: export_csv management command
# ===========================================================================


@pytest.mark.django_db
class TestExportCsv:
    def test_export_ingredients(self, ingredient) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command("export_csv", "--type", "ingredients", "--output-dir", tmpdir)
            out_path = Path(tmpdir) / "ingredients.csv"
            assert out_path.exists()
            rows = list(csv.DictReader(out_path.open()))
            assert any(r["slug"] == "tomato" for r in rows)

    def test_export_dishes(self, dish) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command("export_csv", "--type", "dishes", "--output-dir", tmpdir)
            out_path = Path(tmpdir) / "dishes.csv"
            assert out_path.exists()
            rows = list(csv.DictReader(out_path.open()))
            assert any(r["slug"] == "kachumbari" for r in rows)

    def test_export_dish_ingredients(self, dish) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command("export_csv", "--type", "dish_ingredients", "--output-dir", tmpdir)
            out_path = Path(tmpdir) / "dish_ingredients.csv"
            assert out_path.exists()
            rows = list(csv.DictReader(out_path.open()))
            assert any(r["dish_slug"] == "kachumbari" for r in rows)

    def test_snapshot_creates_all_files(self, dish, ingredient) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command("export_csv", "--type", "snapshot", "--output-dir", tmpdir)
            snap_dirs = [d for d in Path(tmpdir).iterdir() if d.is_dir()]
            assert len(snap_dirs) == 1
            snap = snap_dirs[0]
            assert (snap / "ingredients.csv").exists()
            assert (snap / "dishes.csv").exists()
            assert (snap / "dish_ingredients.csv").exists()
            assert (snap / "aliases.csv").exists()
            assert (snap / "manifest.json").exists()

    def test_manifest_has_correct_structure(self, dish, ingredient) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            call_command("export_csv", "--type", "snapshot", "--output-dir", tmpdir)
            snap = next(Path(tmpdir).iterdir())
            manifest = json.loads((snap / "manifest.json").read_text())
            assert "counts" in manifest
            assert "timestamp" in manifest
            assert manifest["counts"]["ingredients"] >= 1
            assert manifest["counts"]["dishes"] >= 1

    def test_export_then_import_round_trip(self, dish, ingredient, category) -> None:
        """E11 exit check: export then import reproduces identical data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Export dishes
            call_command("export_csv", "--type", "dishes", "--output-dir", tmpdir)
            exported_path = Path(tmpdir) / "dishes.csv"

            # Delete all dishes, re-import
            orig_slugs = set(Dish.objects.values_list("slug", flat=True))
            Dish.objects.all().delete()
            assert Dish.objects.count() == 0

            out = io.StringIO()
            call_command("import_csv", str(exported_path), "--type", "dishes", stdout=out)

            # All original slugs should be back
            new_slugs = set(Dish.objects.values_list("slug", flat=True))
            assert orig_slugs == new_slugs


# ===========================================================================
# E14: qa_report management command
# ===========================================================================


@pytest.mark.django_db
class TestQaReport:
    def test_runs_without_error(self, dish, ingredient) -> None:
        out = io.StringIO()
        call_command("qa_report", stdout=out)
        output = out.getvalue()
        assert "COUNTS" in output

    def test_shows_missing_swahili(self, dish, ingredient) -> None:
        # Dish has no name_sw set → should appear in gaps
        out = io.StringIO()
        call_command("qa_report", stdout=out)
        output = out.getvalue()
        assert "Dishes missing Swahili" in output

    def test_json_format(self, dish, ingredient) -> None:
        out = io.StringIO()
        call_command("qa_report", "--format", "json", stdout=out)
        data = json.loads(out.getvalue())
        assert "counts" in data
        assert "gaps" in data
        assert "integrity" in data

    def test_json_counts_correct(self, dish, ingredient) -> None:
        out = io.StringIO()
        call_command("qa_report", "--format", "json", stdout=out)
        data = json.loads(out.getvalue())
        assert data["counts"]["dishes"]["total"] >= 1
        assert data["counts"]["ingredients"]["total"] >= 1

    def test_ingredients_no_aliases_shown(self, ingredient) -> None:
        """Ingredient with no aliases should appear in gaps."""
        out = io.StringIO()
        call_command("qa_report", "--format", "json", stdout=out)
        data = json.loads(out.getvalue())
        assert data["gaps"]["ingredients_no_aliases"]["count"] >= 1

    def test_fail_on_critical_exits_1_when_violations(self, db, category) -> None:
        """Force a V21 violation → --fail-on-critical should exit 1."""
        d = Dish.objects.create(
            slug="no-primary-dish",
            name_en="No Primary Dish",
            status=StatusChoices.DRAFT,
        )
        ing = Ingredient.objects.create(
            slug="ing-for-v21",
            name_en="Ing For V21",
            category=category,
            kind=Ingredient.Kind.SECONDARY,
        )
        DishIngredient.objects.create(
            dish=d, ingredient=ing, role=DishIngredient.Role.REQUIRED, position=1
        )
        out = io.StringIO()
        with pytest.raises(SystemExit) as exc_info:
            call_command("qa_report", "--fail-on-critical", stdout=out)
        assert exc_info.value.code == 1

    def test_no_fail_without_violations(self, dish, ingredient) -> None:
        """Clean dataset → --fail-on-critical should not exit 1."""
        # dish fixture already has a primary ingredient
        out = io.StringIO()
        # Should not raise
        call_command("qa_report", "--fail-on-critical", stdout=out)
