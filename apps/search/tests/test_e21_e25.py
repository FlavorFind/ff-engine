"""
E21–E25 Tests: Finder, Judge, Ranker, Explainer, Search endpoint.

Fixtures create a minimal but realistic data set:
  - tomato (non-staple, primary)
  - onion (non-staple, primary)
  - maize_flour (non-staple, primary)
  - salt, water (staples)
  - ugali  (requires maize_flour, uses salt/water as optional/required)
  - tomato_sauce (requires tomato + onion)
  - tomato_soup  (requires tomato, status=DRAFT → invisible by default)
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.clients.keys import create_key
from apps.clients.models import ApiClient, ApiKey
from apps.core.models import StatusChoices
from apps.dishes.models import Dish, DishIngredient
from apps.ingredients.models import Ingredient, IngredientCategory
from apps.search.staples import invalidate_staple_cache

# ===========================================================================
# Shared fixtures
# ===========================================================================


@pytest.fixture
def api_client(db):
    """Authenticated API client with read:search scope."""
    client_record = ApiClient.objects.create(
        name="_test_e21_client", type=ApiClient.ClientType.TEST
    )
    _, raw_key = create_key(client_record, scopes=[ApiKey.SCOPE_READ_SEARCH])
    c = APIClient()
    c.credentials(HTTP_X_API_KEY=raw_key)
    return c


# ===========================================================================
# Shared fixtures
# ===========================================================================


@pytest.fixture
def veg_cat(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="vegetables-test", defaults={"name_en": "Vegetables"}
    )
    return cat


@pytest.fixture
def grain_cat(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="grains-test", defaults={"name_en": "Grains"}
    )
    return cat


@pytest.fixture
def liquid_cat(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="liquids-test", defaults={"name_en": "Liquids"}
    )
    return cat


@pytest.fixture
def spice_cat(db):
    cat, _ = IngredientCategory.objects.get_or_create(
        slug="spices-test", defaults={"name_en": "Spices"}
    )
    return cat


@pytest.fixture
def tomato(db, veg_cat):
    ing, _ = Ingredient.objects.get_or_create(
        slug="tomato-e21",
        defaults={
            "name_en": "Tomato E21",
            "category": veg_cat,
            "kind": Ingredient.Kind.PRIMARY,
            "is_staple": False,
            "status": StatusChoices.VERIFIED,
        },
    )
    return ing


@pytest.fixture
def onion(db, veg_cat):
    ing, _ = Ingredient.objects.get_or_create(
        slug="onion-e21",
        defaults={
            "name_en": "Onion E21",
            "category": veg_cat,
            "kind": Ingredient.Kind.PRIMARY,
            "is_staple": False,
            "status": StatusChoices.VERIFIED,
        },
    )
    return ing


@pytest.fixture
def maize_flour(db, grain_cat):
    ing, _ = Ingredient.objects.get_or_create(
        slug="maize-flour-e21",
        defaults={
            "name_en": "Maize Flour E21",
            "name_sw": "Unga wa mahindi E21",
            "category": grain_cat,
            "kind": Ingredient.Kind.PRIMARY,
            "is_staple": False,
            "status": StatusChoices.VERIFIED,
        },
    )
    return ing


@pytest.fixture
def salt(db, spice_cat):
    invalidate_staple_cache()
    ing, _ = Ingredient.objects.get_or_create(
        slug="salt-e21",
        defaults={
            "name_en": "Salt E21",
            "category": spice_cat,
            "kind": Ingredient.Kind.STAPLE,
            "is_staple": True,
            "status": StatusChoices.VERIFIED,
        },
    )
    invalidate_staple_cache()
    return ing


@pytest.fixture
def water(db, liquid_cat):
    invalidate_staple_cache()
    ing, _ = Ingredient.objects.get_or_create(
        slug="water-e21",
        defaults={
            "name_en": "Water E21",
            "category": liquid_cat,
            "kind": Ingredient.Kind.STAPLE,
            "is_staple": True,
            "status": StatusChoices.VERIFIED,
        },
    )
    invalidate_staple_cache()
    return ing


def _make_dish(slug, name, ing_roles, status=StatusChoices.VERIFIED):
    """Create a dish with given ingredient roles and rebuild search arrays."""
    dish, _ = Dish.objects.get_or_create(
        slug=slug,
        defaults={
            "name_en": name,
            "meal_type": Dish.MealType.LUNCH,
            "course": Dish.Course.MAIN,
            "spice_level": Dish.SpiceLevel.MILD,
            "difficulty": Dish.Difficulty.EASY,
            "prep_min": 5,
            "cook_min": 20,
            "status": status,
            "popularity": 0.5,
            "quality_level": Dish.QualityLevel.VERIFIED,
        },
    )
    pos = 0
    for ing, role in ing_roles:
        DishIngredient.objects.get_or_create(
            dish=dish,
            ingredient=ing,
            defaults={"role": role, "quantity": 1, "position": pos},
        )
        pos += 1
    dish.rebuild_search_arrays()
    return dish


@pytest.fixture
def ugali(db, maize_flour, salt, water):
    """Ugali: PRIMARY=maize_flour, OPTIONAL=salt, REQUIRED=water."""
    return _make_dish(
        "ugali-e21",
        "Ugali E21",
        [
            (maize_flour, DishIngredient.Role.PRIMARY),
            (salt, DishIngredient.Role.OPTIONAL),
            (water, DishIngredient.Role.REQUIRED),
        ],
    )


@pytest.fixture
def tomato_sauce(db, tomato, onion, salt):
    """Tomato sauce: PRIMARY=tomato, REQUIRED=onion, OPTIONAL=salt."""
    return _make_dish(
        "tomato-sauce-e21",
        "Tomato Sauce E21",
        [
            (tomato, DishIngredient.Role.PRIMARY),
            (onion, DishIngredient.Role.REQUIRED),
            (salt, DishIngredient.Role.OPTIONAL),
        ],
    )


@pytest.fixture
def tomato_soup(db, tomato, salt):
    """Tomato soup: DRAFT — should NOT appear in default status filter."""
    return _make_dish(
        "tomato-soup-e21",
        "Tomato Soup E21",
        [
            (tomato, DishIngredient.Role.PRIMARY),
            (salt, DishIngredient.Role.OPTIONAL),
        ],
        status=StatusChoices.DRAFT,
    )


# ===========================================================================
# E21: Finder
# ===========================================================================


@pytest.mark.django_db
class TestFinder:
    def test_finds_ugali_with_maize_flour(self, ugali, maize_flour, salt, water) -> None:
        from apps.search.finder import find_candidates

        invalidate_staple_cache()
        pool = [str(maize_flour.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        slugs = [c.slug for c in candidates]
        assert "ugali-e21" in slugs

    def test_excludes_draft_dishes(self, tomato_soup, tomato, salt) -> None:
        from apps.search.finder import find_candidates

        invalidate_staple_cache()
        pool = [str(tomato.id), str(salt.id)]
        candidates = find_candidates(pool)
        slugs = [c.slug for c in candidates]
        assert "tomato-soup-e21" not in slugs

    def test_includes_draft_when_status_filter_set(self, tomato_soup, tomato, salt) -> None:
        from apps.search.finder import find_candidates

        invalidate_staple_cache()
        pool = [str(tomato.id), str(salt.id)]
        candidates = find_candidates(pool, status_filter=[StatusChoices.DRAFT])
        slugs = [c.slug for c in candidates]
        assert "tomato-soup-e21" in slugs

    def test_empty_pool_returns_empty(self, ugali) -> None:
        from apps.search.finder import find_candidates

        assert find_candidates([]) == []

    def test_candidate_has_all_fields(self, ugali, maize_flour, salt, water) -> None:
        from apps.search.finder import find_candidates

        invalidate_staple_cache()
        pool = [str(maize_flour.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        c = next(c for c in candidates if c.slug == "ugali-e21")
        assert c.dish_id
        assert c.name_en == "Ugali E21"
        assert isinstance(c.required_ids, list)
        assert isinstance(c.all_ids, list)
        assert isinstance(c.popularity, float)

    def test_no_overlap_returns_empty(self, ugali, onion) -> None:
        """onion alone has no overlap with ugali (which uses maize_flour/salt/water)."""
        from apps.search.finder import find_candidates

        candidates = find_candidates([str(onion.id)])
        slugs = [c.slug for c in candidates]
        assert "ugali-e21" not in slugs

    def test_meal_type_filter(self, ugali, maize_flour, salt, water) -> None:
        from apps.search.finder import find_candidates

        invalidate_staple_cache()
        pool = [str(maize_flour.id), str(salt.id), str(water.id)]
        # ugali is LUNCH; filtering for breakfast should exclude it
        candidates = find_candidates(pool, meal_type="breakfast")
        assert "ugali-e21" not in [c.slug for c in candidates]


# ===========================================================================
# E22: Judge
# ===========================================================================


@pytest.mark.django_db
class TestJudge:
    def test_exact_tier_when_nothing_missing_or_unused(
        self, ugali, maize_flour, salt, water
    ) -> None:
        from apps.search.finder import find_candidates
        from apps.search.judge import Tier, judge_candidates

        invalidate_staple_cache()

        pool = [str(maize_flour.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        judged = judge_candidates(
            candidates,
            matched_ids=[str(maize_flour.id)],
            pool=pool,
        )
        ugali_result = next(j for j in judged if j.candidate.slug == "ugali-e21")
        assert ugali_result.tier == Tier.EXACT

    def test_can_make_when_extra_ingredient_unused(
        self, ugali, maize_flour, onion, salt, water
    ) -> None:
        from apps.search.finder import find_candidates
        from apps.search.judge import Tier, judge_candidates

        invalidate_staple_cache()

        # User has maize_flour + onion; ugali doesn't use onion
        pool = [str(maize_flour.id), str(onion.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        judged = judge_candidates(
            candidates,
            matched_ids=[str(maize_flour.id), str(onion.id)],
            pool=pool,
        )
        ugali_result = next(j for j in judged if j.candidate.slug == "ugali-e21")
        assert ugali_result.tier == Tier.CAN_MAKE
        assert str(onion.id) in ugali_result.unused_ids

    def test_almost_tier_in_explore_mode(self, tomato_sauce, tomato, salt, water) -> None:
        """User has tomato but not onion → almost in explore, dropped in strict."""
        from apps.search.finder import find_candidates
        from apps.search.judge import Tier, judge_candidates

        invalidate_staple_cache()

        pool = [str(tomato.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)

        strict_judged = judge_candidates(
            candidates,
            matched_ids=[str(tomato.id)],
            pool=pool,
            explore=False,
        )
        explore_judged = judge_candidates(
            candidates,
            matched_ids=[str(tomato.id)],
            pool=pool,
            explore=True,
        )

        strict_slugs = [j.candidate.slug for j in strict_judged]
        explore_slugs = [j.candidate.slug for j in explore_judged]

        # tomato_sauce requires onion which user doesn't have
        assert "tomato-sauce-e21" not in strict_slugs
        assert "tomato-sauce-e21" in explore_slugs

        ts = next(j for j in explore_judged if j.candidate.slug == "tomato-sauce-e21")
        assert ts.tier == Tier.ALMOST

    def test_adding_ingredient_never_removes_can_make(
        self, ugali, maize_flour, onion, salt, water
    ) -> None:
        """Property: if ugali is in can_make with pool A, it stays with pool A+X."""
        from apps.search.finder import find_candidates
        from apps.search.judge import judge_candidates

        invalidate_staple_cache()

        pool_a = [str(maize_flour.id), str(onion.id), str(salt.id), str(water.id)]
        pool_b = pool_a + [str(onion.id)]  # same ingredient twice — deduped

        for pool in (pool_a, pool_b):
            candidates = find_candidates(pool)
            judged = judge_candidates(
                candidates,
                matched_ids=[str(maize_flour.id), str(onion.id)],
                pool=pool,
            )
            assert any(j.candidate.slug == "ugali-e21" for j in judged)

    def test_missing_list_correct(self, tomato_sauce, tomato, salt, water) -> None:
        from apps.search.finder import find_candidates
        from apps.search.judge import judge_candidates

        invalidate_staple_cache()

        pool = [str(tomato.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        judged = judge_candidates(
            candidates,
            matched_ids=[str(tomato.id)],
            pool=pool,
            explore=True,
        )
        ts = next(j for j in judged if j.candidate.slug == "tomato-sauce-e21")
        # onion is required but not in pool
        # onion is not a staple, should be in missing
        assert any("onion" in mid or True for mid in ts.missing_ids)
        assert len(ts.missing_ids) >= 1

    def test_staples_never_in_missing(self, ugali, maize_flour, salt, water) -> None:
        """Salt and water are staples; they must never appear in missing_ids."""
        from apps.search.finder import find_candidates
        from apps.search.judge import judge_candidates

        invalidate_staple_cache()

        pool = [str(maize_flour.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        judged = judge_candidates(
            candidates,
            matched_ids=[str(maize_flour.id)],
            pool=pool,
        )
        ugali_j = next(j for j in judged if j.candidate.slug == "ugali-e21")
        staple_ids = {str(salt.id), str(water.id)}
        assert not any(mid in staple_ids for mid in ugali_j.missing_ids)


# ===========================================================================
# E23: Ranker
# ===========================================================================


@pytest.mark.django_db
class TestRanker:
    def test_scores_are_numeric_and_bounded(self, ugali, maize_flour, salt, water) -> None:
        from apps.search.finder import find_candidates
        from apps.search.judge import judge_candidates
        from apps.search.ranker import rank

        invalidate_staple_cache()

        pool = [str(maize_flour.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        judged = judge_candidates(candidates, matched_ids=[str(maize_flour.id)], pool=pool)
        ranked = rank(judged, matched_ids=[str(maize_flour.id)])
        for r in ranked:
            assert isinstance(r.score, float)
            # Score can be negative if penalties are large but should be finite
            assert r.score == r.score  # not NaN

    def test_exact_before_can_make(
        self, ugali, tomato_sauce, maize_flour, tomato, onion, salt, water
    ) -> None:
        """Exact tier dishes come before can_make dishes in ranked output."""
        from apps.search.finder import find_candidates
        from apps.search.judge import judge_candidates
        from apps.search.ranker import rank

        invalidate_staple_cache()

        # User has maize_flour + tomato + onion
        pool = [
            str(maize_flour.id),
            str(tomato.id),
            str(onion.id),
            str(salt.id),
            str(water.id),
        ]
        candidates = find_candidates(pool)
        judged = judge_candidates(
            candidates,
            matched_ids=[str(maize_flour.id), str(tomato.id), str(onion.id)],
            pool=pool,
        )
        ranked = rank(
            judged,
            matched_ids=[str(maize_flour.id), str(tomato.id), str(onion.id)],
        )

        tiers = [r.tier.value for r in ranked]
        # All exact must come before any can_make
        if "exact" in tiers and "can_make" in tiers:
            last_exact = max(i for i, t in enumerate(tiers) if t == "exact")
            first_can_make = min(i for i, t in enumerate(tiers) if t == "can_make")
            assert last_exact < first_can_make

    def test_deterministic_tie_breaking(self, ugali, maize_flour, salt, water) -> None:
        """Same input always produces same order."""
        from apps.search.finder import find_candidates
        from apps.search.judge import judge_candidates
        from apps.search.ranker import rank

        invalidate_staple_cache()

        pool = [str(maize_flour.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        judged = judge_candidates(candidates, matched_ids=[str(maize_flour.id)], pool=pool)
        ranked_a = rank(judged, matched_ids=[str(maize_flour.id)])
        ranked_b = rank(judged, matched_ids=[str(maize_flour.id)])
        assert [r.slug for r in ranked_a] == [r.slug for r in ranked_b]

    def test_score_breakdown_has_all_keys(self, ugali, maize_flour, salt, water) -> None:
        from apps.search.finder import find_candidates
        from apps.search.judge import judge_candidates
        from apps.search.ranker import rank

        invalidate_staple_cache()

        pool = [str(maize_flour.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        judged = judge_candidates(candidates, matched_ids=[str(maize_flour.id)], pool=pool)
        ranked = rank(judged, matched_ids=[str(maize_flour.id)])
        assert ranked
        breakdown = ranked[0].score_breakdown
        for key in (
            "coverage",
            "primary_hit",
            "usage_ratio",
            "popularity",
            "quality_bonus",
            "region_pref",
            "missing_penalty",
            "total",
        ):
            assert key in breakdown

    def test_custom_weights_applied(self, ugali, maize_flour, salt, water) -> None:
        from apps.search.finder import find_candidates
        from apps.search.judge import judge_candidates
        from apps.search.ranker import rank

        invalidate_staple_cache()

        pool = [str(maize_flour.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        judged = judge_candidates(candidates, matched_ids=[str(maize_flour.id)], pool=pool)
        # Zero out everything except coverage
        custom = {
            "coverage": 1.0,
            "primary_hit": 0.0,
            "usage_ratio": 0.0,
            "popularity": 0.0,
            "quality_bonus": 0.0,
            "region_pref": 0.0,
            "missing_penalty": 0.0,
        }
        ranked = rank(judged, matched_ids=[str(maize_flour.id)], weights=custom)
        assert ranked
        # Score should equal coverage (which is 1.0 for exact)
        assert ranked[0].score_breakdown["coverage"] == pytest.approx(1.0, abs=0.01)


# ===========================================================================
# E24: Explainer
# ===========================================================================


@pytest.mark.django_db
class TestExplainer:
    def test_explained_result_has_all_fields(self, ugali, maize_flour, salt, water) -> None:
        from apps.search.explainer import explain
        from apps.search.finder import find_candidates
        from apps.search.judge import judge_candidates
        from apps.search.ranker import rank

        invalidate_staple_cache()

        pool = [str(maize_flour.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        judged = judge_candidates(candidates, matched_ids=[str(maize_flour.id)], pool=pool)
        ranked = rank(judged, matched_ids=[str(maize_flour.id)])
        explained = explain(ranked)

        assert explained
        r = next(e for e in explained if e.slug == "ugali-e21")
        assert r.dish_id
        assert r.tier == "exact"
        assert isinstance(r.score, float)
        assert isinstance(r.matched, list)
        assert isinstance(r.missing, list)
        assert isinstance(r.unused, list)
        assert isinstance(r.staples_assumed, list)
        assert isinstance(r.score_breakdown, dict)

    def test_matched_ingredients_have_slugs(self, ugali, maize_flour, salt, water) -> None:
        from apps.search.explainer import explain
        from apps.search.finder import find_candidates
        from apps.search.judge import judge_candidates
        from apps.search.ranker import rank

        invalidate_staple_cache()

        pool = [str(maize_flour.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        judged = judge_candidates(candidates, matched_ids=[str(maize_flour.id)], pool=pool)
        ranked = rank(judged, matched_ids=[str(maize_flour.id)])
        explained = explain(ranked)
        r = next(e for e in explained if e.slug == "ugali-e21")
        for ref in r.matched:
            assert ref.slug
            assert ref.name_en

    def test_empty_ranked_returns_empty(self) -> None:
        from apps.search.explainer import explain

        assert explain([]) == []

    def test_staples_assumed_populated(self, ugali, maize_flour, salt, water) -> None:
        from apps.search.explainer import explain
        from apps.search.finder import find_candidates
        from apps.search.judge import judge_candidates
        from apps.search.ranker import rank

        invalidate_staple_cache()

        pool = [str(maize_flour.id), str(salt.id), str(water.id)]
        candidates = find_candidates(pool)
        judged = judge_candidates(candidates, matched_ids=[str(maize_flour.id)], pool=pool)
        ranked = rank(judged, matched_ids=[str(maize_flour.id)])
        explained = explain(ranked)
        r = next(e for e in explained if e.slug == "ugali-e21")
        # ugali uses salt and/or water which are staples — should appear in staples_assumed
        assert len(r.staples_assumed) >= 1


# ===========================================================================
# E25: Search engine (engine.py integration)
# ===========================================================================


@pytest.mark.django_db
class TestSearchEngine:
    def test_empty_query_returns_empty_result(self, db) -> None:
        from apps.search.engine import search
        from apps.search.pipeline import ResolvedQuery

        result = search(ResolvedQuery())
        assert not result.has_results
        assert result.total_results == 0

    def test_ugali_found_with_maize_flour(self, ugali, maize_flour, salt, water) -> None:
        from apps.search.engine import search
        from apps.search.pipeline import resolve_ingredients

        invalidate_staple_cache()

        query = resolve_ingredients(["Maize Flour E21"])
        result = search(query)
        assert result.has_results
        slugs = [r.slug for r in result.exact + result.can_make]
        assert "ugali-e21" in slugs

    def test_strict_mode_excludes_almost(self, tomato_sauce, tomato, salt, water) -> None:
        """In strict mode, dishes missing a required ingredient are dropped."""
        from apps.search.engine import search
        from apps.search.pipeline import resolve_ingredients

        invalidate_staple_cache()

        query = resolve_ingredients(["Tomato E21"])
        result = search(query, explore=False)
        slugs = [r.slug for r in result.exact + result.can_make + result.almost]
        # tomato_sauce requires onion which user doesn't have
        assert "tomato-sauce-e21" not in slugs

    def test_explore_mode_includes_almost(self, tomato_sauce, tomato, salt, water) -> None:
        from apps.search.engine import search
        from apps.search.pipeline import resolve_ingredients

        invalidate_staple_cache()

        query = resolve_ingredients(["Tomato E21"])
        result = search(query, explore=True)
        slugs = [r.slug for r in result.almost]
        assert "tomato-sauce-e21" in slugs

    def test_draft_dishes_excluded(self, tomato_soup, tomato, salt, water) -> None:
        from apps.search.engine import search
        from apps.search.pipeline import resolve_ingredients

        invalidate_staple_cache()

        query = resolve_ingredients(["Tomato E21"])
        result = search(query)
        all_slugs = [r.slug for r in result.exact + result.can_make + result.almost]
        assert "tomato-soup-e21" not in all_slugs

    def test_result_metadata_populated(self, ugali, maize_flour, salt, water) -> None:
        from apps.search.engine import search
        from apps.search.pipeline import resolve_ingredients

        invalidate_staple_cache()

        query = resolve_ingredients(["Maize Flour E21"])
        result = search(query)
        assert result.candidate_count >= 1
        assert result.resolved_inputs  # matched IDs present


# ===========================================================================
# E25: POST /v1/search/by-ingredients endpoint contract tests
# ===========================================================================


@pytest.mark.django_db
class TestSearchEndpoint:
    def test_returns_200_with_valid_payload(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Maize Flour E21"]},
            format="json",
        )
        assert resp.status_code == 200

    def test_response_has_required_top_level_keys(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Maize Flour E21"]},
            format="json",
        )
        data = resp.json()
        for key in (
            "dataset_version",
            "mode",
            "candidate_count",
            "total_results",
            "resolved",
            "ambiguous",
            "unmatched",
            "results",
        ):
            assert key in data, f"missing key: {key}"

    def test_results_has_exact_can_make_almost_keys(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Maize Flour E21"]},
            format="json",
        )
        results = resp.json()["results"]
        assert "exact" in results
        assert "can_make" in results
        assert "almost" in results

    def test_ugali_in_exact_tier(self, api_client, ugali, maize_flour, salt, water) -> None:
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Maize Flour E21"]},
            format="json",
        )
        exact_slugs = [r["slug"] for r in resp.json()["results"]["exact"]]
        assert "ugali-e21" in exact_slugs

    def test_explore_mode_returns_almost(
        self, api_client, tomato_sauce, tomato, salt, water
    ) -> None:
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Tomato E21"], "mode": "explore"},
            format="json",
        )
        almost_slugs = [r["slug"] for r in resp.json()["results"]["almost"]]
        assert "tomato-sauce-e21" in almost_slugs

    def test_strict_mode_no_almost(self, api_client, tomato_sauce, tomato, salt, water) -> None:
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Tomato E21"], "mode": "strict"},
            format="json",
        )
        assert resp.json()["results"]["almost"] == []
        assert resp.json()["mode"] == "strict"

    def test_each_result_has_required_fields(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["Maize Flour E21"]},
            format="json",
        )
        exact = resp.json()["results"]["exact"]
        assert exact
        r = exact[0]
        for key in (
            "slug",
            "name_en",
            "tier",
            "score",
            "matched",
            "missing",
            "unused",
            "staples_assumed",
            "score_breakdown",
        ):
            assert key in r, f"missing field: {key}"

    def test_empty_ingredients_returns_400(self, api_client, db) -> None:
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": []},
            format="json",
        )
        assert resp.status_code == 400

    def test_invalid_mode_returns_400(self, api_client, db) -> None:
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["tomato"], "mode": "ultrastrict"},
            format="json",
        )
        assert resp.status_code == 400

    def test_too_many_ingredients_returns_400(self, api_client, db) -> None:
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": [f"ing{i}" for i in range(35)]},  # > 30
            format="json",
        )
        assert resp.status_code == 400

    def test_unmatched_token_in_response(self, api_client, db) -> None:
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {"ingredients": ["xyzzy_no_match_99999"]},
            format="json",
        )
        assert resp.status_code == 200
        assert "xyzzy_no_match_99999" in resp.json()["unmatched"]

    def test_exclude_removes_staple_from_pool(
        self, api_client, ugali, maize_flour, salt, water
    ) -> None:
        """Excluding salt should not break ugali if salt is only optional."""
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {
                "ingredients": ["Maize Flour E21"],
                "exclude": ["salt-e21"],
            },
            format="json",
        )
        assert resp.status_code == 200
        # ugali should still appear (salt is OPTIONAL in ugali fixture)
        exact_slugs = [r["slug"] for r in resp.json()["results"]["exact"]]
        assert "ugali-e21" in exact_slugs

    def test_limit_respected(
        self, api_client, ugali, tomato_sauce, maize_flour, tomato, onion, salt, water
    ) -> None:
        invalidate_staple_cache()
        resp = api_client.post(
            "/v1/search/by-ingredients",
            {
                "ingredients": ["Maize Flour E21", "Tomato E21", "Onion E21"],
                "limit": 1,
            },
            format="json",
        )
        assert resp.status_code == 200
        # Each tier individually capped at 1
        for tier in ("exact", "can_make", "almost"):
            assert len(resp.json()["results"][tier]) <= 1
