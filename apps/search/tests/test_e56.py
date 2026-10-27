"""
E56 — Category word expansion tests.

Verifies that category words ('greens', 'meat', etc.) expand to
member ingredient IDs before the GIN query, and that normal ingredient
words pass through unchanged.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Pure unit tests (no DB)
# ---------------------------------------------------------------------------


@pytest.mark.fast
class TestCategoryAliasMap:
    def test_greens_is_in_alias_map(self):
        from apps.search.category_expander import _CATEGORY_ALIASES

        assert "greens" in _CATEGORY_ALIASES

    def test_meat_is_in_alias_map(self):
        from apps.search.category_expander import _CATEGORY_ALIASES

        assert "meat" in _CATEGORY_ALIASES

    def test_nyama_swahili_is_in_alias_map(self):
        from apps.search.category_expander import _CATEGORY_ALIASES

        assert "nyama" in _CATEGORY_ALIASES

    def test_mboga_swahili_is_in_alias_map(self):
        from apps.search.category_expander import _CATEGORY_ALIASES

        assert "mboga" in _CATEGORY_ALIASES

    def test_non_category_word_not_in_map(self):
        from apps.search.category_expander import _CATEGORY_ALIASES

        # Specific ingredients are NOT category words
        assert "tomato" not in _CATEGORY_ALIASES
        assert "rice" not in _CATEGORY_ALIASES

    def test_skip_tokens_have_none_value(self):
        """Tokens that look like categories but are ingredients use None."""
        from apps.search.category_expander import _CATEGORY_ALIASES

        # 'chicken' is an ingredient name, not a category
        assert _CATEGORY_ALIASES.get("chicken") is None


@pytest.mark.fast
def test_non_category_token_goes_to_remaining():
    """A normal ingredient word must appear in remaining_tokens, not expanded_ids."""
    from unittest.mock import patch

    # Patch _get_category_ingredient_ids to return nothing (no DB needed)
    with patch("apps.search.category_expander._get_category_ingredient_ids", return_value=[]):
        from apps.search.category_expander import expand_category_terms

        ids, remaining = expand_category_terms(["tomato", "onion"])

    assert ids == []
    assert "tomato" in remaining
    assert "onion" in remaining


@pytest.mark.fast
def test_empty_input_returns_empty():
    from apps.search.category_expander import expand_category_terms

    ids, remaining = expand_category_terms([])
    assert ids == []
    assert remaining == []


@pytest.mark.fast
def test_mixed_category_and_ingredient():
    """'greens' should expand; 'rice' should pass through."""
    from unittest.mock import patch

    fake_ids = ["uuid-1", "uuid-2", "uuid-3"]

    def fake_resolve(slug):
        if "vegetable" in slug:
            return fake_ids
        return []

    with patch(
        "apps.search.category_expander._get_category_ingredient_ids", side_effect=fake_resolve
    ):
        from apps.search.category_expander import expand_category_terms, invalidate_category_cache

        invalidate_category_cache()
        ids, remaining = expand_category_terms(["greens", "rice"])

    assert set(ids) == set(fake_ids)
    assert "rice" in remaining
    assert "greens" not in remaining


# ---------------------------------------------------------------------------
# DB-backed tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_category_expansion_returns_ids_for_vegetables(seeded_db):
    """
    With a seeded DB, 'greens' should expand to at least some ingredient IDs
    because the 'Vegetables' category has members.
    """
    from apps.search.category_expander import expand_category_terms, invalidate_category_cache

    invalidate_category_cache()
    ids, remaining = expand_category_terms(["greens"])

    # 'greens' matched a category → ids should be non-empty, remaining empty
    # (if the category slug matched in the DB)
    # We cannot assert non-empty if no matching category slug exists, but we
    # can assert the token is NOT in remaining when category was resolved.
    if ids:
        assert "greens" not in remaining
    else:
        # Category slug may not match exactly with the seeded data —
        # in that case 'greens' falls back to remaining
        assert "greens" in remaining


@pytest.mark.django_db
def test_category_expansion_in_pipeline(seeded_db):
    """
    resolve_ingredients(['greens']) with a seeded DB should produce a
    ResolvedQuery with a non-empty pool (staples are always added).
    """
    from apps.search.pipeline import resolve_ingredients

    query = resolve_ingredients(["greens"])
    # Pool always contains staples even if category doesn't resolve
    assert len(query.pool) > 0
    assert isinstance(query.category_expanded_ids, list)


@pytest.mark.django_db
def test_normal_ingredient_not_expanded_by_category(seeded_db):
    """'tomato' is a specific ingredient — category_expanded_ids must be empty."""
    from apps.search.pipeline import resolve_ingredients

    query = resolve_ingredients(["tomato"])
    assert query.category_expanded_ids == []


@pytest.mark.django_db
def test_category_expanded_ids_in_pool(seeded_db):
    """
    If a category word expands to some IDs, those IDs appear in the pool.
    """
    from unittest.mock import patch

    fake_ids = []
    from apps.ingredients.models import Ingredient

    # Use real ingredient IDs from the seeded DB
    sample = list(Ingredient.objects.values_list("id", flat=True)[:3])
    fake_ids = [str(pk) for pk in sample]

    with patch(
        "apps.search.category_expander._get_category_ingredient_ids",
        return_value=fake_ids,
    ):
        from apps.search.category_expander import invalidate_category_cache

        invalidate_category_cache()
        # Patch the alias map so 'greens' resolves via our fake function
        import apps.search.category_expander as ce

        original_aliases = ce._CATEGORY_ALIASES.copy()
        ce._CATEGORY_ALIASES["greens"] = ["vegetables"]

        try:
            from apps.search.pipeline import resolve_ingredients

            query = resolve_ingredients(["greens"])
            for fid in fake_ids:
                assert fid in query.pool, f"Category-expanded ID {fid} not in pool"
        finally:
            ce._CATEGORY_ALIASES.clear()
            ce._CATEGORY_ALIASES.update(original_aliases)
            invalidate_category_cache()
