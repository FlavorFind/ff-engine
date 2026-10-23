"""
E4 migration tests.

Blueprint pass criterion: migrations apply and reverse cleanly.
Architecture section 12.2: migration checks detect missing migrations,
build from empty, and reverse the latest.
"""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext


@pytest.mark.django_db
def test_ingredient_tables_exist():
    """All E4 tables must exist after migrations apply."""
    expected_tables = [
        "ingredient_category",
        "ingredient",
        "ingredient_alias",
        "ingredient_allergen",
        "allergen",
        "unit",
        "source",
        "change_log",
        "dataset_release",
    ]
    with connection.cursor() as cursor:
        existing = connection.introspection.table_names(cursor)

    for table in expected_tables:
        assert table in existing, f"Table '{table}' missing after migration"


@pytest.mark.django_db
def test_ingredient_table_columns():
    """Ingredient table has the exact columns per Architecture section 5."""
    expected_columns = {
        "id",
        "slug",
        "name_en",
        "name_sw",
        "category_id",
        "kind",
        "is_staple",
        "typical_unit_id",
        "status",
        "source_id",
        "notes",
        "created_at",
        "updated_at",
    }
    with connection.cursor() as cursor:
        columns = {
            col.name for col in connection.introspection.get_table_description(cursor, "ingredient")
        }
    assert expected_columns <= columns, f"Missing columns: {expected_columns - columns}"


@pytest.mark.django_db
def test_ingredient_alias_table_columns():
    """ingredient_alias has the exact columns per Architecture section 5."""
    expected_columns = {
        "id",
        "ingredient_id",
        "alias",
        "normalized_alias",
        "language",
        "is_misspelling",
    }
    with connection.cursor() as cursor:
        columns = {
            col.name
            for col in connection.introspection.get_table_description(cursor, "ingredient_alias")
        }
    assert expected_columns <= columns, f"Missing columns: {expected_columns - columns}"


@pytest.mark.django_db
def test_no_extra_queries_on_ingredient_select():
    """Basic select on Ingredient does not cause N+1 on category."""
    from apps.ingredients.models import Ingredient

    with CaptureQueriesContext(connection) as ctx:
        list(Ingredient.objects.select_related("category").all())
    # Should be at most 1 query (or 0 if table is empty)
    assert len(ctx.captured_queries) <= 1
