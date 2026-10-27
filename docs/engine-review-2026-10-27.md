# Flavor Find Engine — Full Review
**Date:** 2026-10-27 | **Reviewer:** Kiro | **Engine version:** v1.0.0 (post E52–E59)

---

## Executive Summary

The engine is in good shape. All 59 build steps are either complete or
addressed. The core pipeline (resolver → staples → finder → judge → ranker →
explainer) is solid, well-tested, and matches the blueprint exactly. The gaps
below are real but none are critical blockers — the most important ones are the
two missing catalogue endpoints and the absent test coverage for three apps.

---

## 1. Missing API Endpoints

These are specified in the Architecture doc (section 7) and in the v1.0.0
CHANGELOG but are either absent or incomplete in the current code.

### 1a. `GET /v1/ingredients/` and `GET /v1/ingredients/{slug}/` — **MISSING**

The architecture specifies:
- `GET /v1/ingredients` — list with autocomplete (`q=`)
- `GET /v1/ingredients/{id}` — detail with aliases and allergens

Currently `apps/ingredients/urls.py` only has one route:
```
POST /v1/ingredients/resolve
```

The list and detail endpoints do not exist. The CHANGELOG at v1.0.0 lists them
as delivered. They are not. Consumer apps and the test console cannot browse the
ingredient catalogue.

**Fix needed:** Add `ingredient_list` and `ingredient_detail` views to
`apps/ingredients/views.py` and register them in `apps/ingredients/urls.py`.

---

### 1b. `GET /v1/dishes/{slug}/` detail endpoint — **MISSING**

`apps/dishes/urls.py` has:
```
GET  /v1/dishes/                         dish_catalogue  ✓
GET  /v1/dishes/<uuid>/pairings/         dish_pairings   ✓
GET  /v1/dishes/<uuid>/substitutions/    dish_substitutions ✓
POST /v1/dishes/<uuid>/missing/          dish_missing    ✓
```

There is no `GET /v1/dishes/{slug}/` detail endpoint returning the full dish
object (description, ingredients with roles, steps, region, tags). The
CHANGELOG lists it. It is not in the URL configuration or the views file.

Additionally, the URL pattern uses `<uuid:dish_id>` but the architecture spec
says `{slug}` (a string). The nutrition endpoint at `/v1/dishes/{slug}/nutrition/`
correctly uses `<slug:slug>`. There is an inconsistency.

**Fix needed:** Add `dish_detail` view, register `GET /v1/dishes/<slug:slug>/`
in `apps/dishes/urls.py`. Decide on slug vs UUID as the canonical identifier and
make it consistent across all dish sub-routes.

---

### 1c. `GET /v1/meta/version` returns static `DATASET_VERSION` — **BUG**

`apps/api/views.py` line 65:
```python
"dataset_version": getattr(settings, "DATASET_VERSION", "0.0.0")
```

The architecture specifies: *"Every answer says which dataset version produced
it."* The `DatasetRelease` model exists and `apps/search/cache.py::get_dataset_version()`
already does the correct DB lookup with a settings fallback. The version endpoint
should use the same function.

**Fix needed:** Import and call `get_dataset_version()` in `apps/api/views.py`.

---

### 1d. `GET /v1/dishes/` includes DRAFT dishes — **BUG**

`apps/dishes/views_catalogue.py` line:
```python
qs = Dish.objects.filter(
    status__in=[StatusChoices.DRAFT, StatusChoices.REVIEWED, StatusChoices.VERIFIED]
)
```

Drafts should never be served to external clients. The architecture is clear:
only `reviewed` and `verified` entries are live. The search endpoint (`finder.py`)
correctly restricts to `_LIVE_STATUSES = [REVIEWED, VERIFIED]`.

**Fix needed:** Remove `StatusChoices.DRAFT` from the catalogue query.

---

## 2. Missing Tests

### 2a. `apps/dietary/tests/` — **EMPTY**

The dietary app (`E31`/`E32`) has:
- `models.py` — DietaryTag, DishDietaryTag
- `services.py` — `derive_dietary_tags()`, `apply_derived_tags()` (8 derivation rules)
- `signals.py` — auto-rederive on DishIngredient change, ChangeLog audit on manual override

Zero tests. This is the **safety filter** — allergen exclusion always wins — and
it has no test coverage at all. This is the highest-risk gap.

**Missing test cases:**
- `derive_dietary_tags()` returns `vegetarian=True` for a dish with no meat ingredients
- `derive_dietary_tags()` returns `vegetarian=False` for a dish with beef
- `derive_dietary_tags()` returns `contains-pork=True` for a dish with pork
- `apply_derived_tags()` creates DishDietaryTag rows (derived source)
- `apply_derived_tags()` does NOT overwrite manual overrides
- Signal: DishIngredient save triggers re-derivation
- Signal: Manual DishDietaryTag override writes to ChangeLog

---

### 2b. `apps/pairings/tests/` — **EMPTY**

The pairings app (`E28`/`E29`) has models, a service, and a serializer but no tests.

**Missing test cases:**
- `get_pairings_for_dish()` returns pairings ordered by strength descending
- `GET /v1/dishes/{id}/pairings/` returns correct shape
- Pairing model `pairing_has_dish_or_label` constraint: row with neither paired_dish nor paired_label is rejected
- Strength validator rejects values outside 1–5

---

### 2c. `apps/core/tests/` — **EMPTY**

`apps/core/models.py`, `apps/core/security.py`, `apps/core/middleware.py`,
`apps/core/exceptions.py`, `apps/core/pagination.py` have no tests.

**Missing test cases:**
- `SecurityHeadersMiddleware` sets `X-Content-Type-Options: nosniff`
- `SecurityHeadersMiddleware` sets `Cache-Control: no-store` on `/v1/` paths
- `RequestIDMiddleware` attaches a `X-Request-ID` header to every response
- `TimeStampedModel` sets `created_at` and `updated_at` correctly
- `custom_exception_handler` returns the standard error envelope

---

### 2d. E52/E53/E54 curation tests — **MISSING**

`apps/curation/tests/` has: `test_e10_e15.py`, `test_e49.py`, `test_seed_all.py`.

Missing:
- `test_e52.py` — community submissions endpoint (created in E52 but the
  test file was not written; only E57 tests the permission side of submissions)
- `test_e53.py` — `publish_release` command (version validation, dry-run, step-up gate)
- `test_e54.py` — dataset diff endpoint (since= param, unknown version, new dishes appear)

---

### 2e. E58 `compute_popularity` has no test for the `--min-quality` flag

`test_e58.py` does not cover:
- `--min-quality reviewed` skips seeded dishes entirely

Minor gap, low risk.

---

## 3. Logic Gaps

### 3a. `dish_catalogue` filter for `diet` is inverted — **BUG**

`apps/dishes/views_catalogue.py`:
```python
diet = request.query_params.get("diet", "").strip()
if diet:
    qs = qs.filter(
        dish_dietary_tags__tag__slug=diet,
    ).exclude(
        dish_dietary_tags__tag__is_allergen_tag=True,
    )
```

The `.exclude(is_allergen_tag=True)` line removes dishes that have ANY allergen
tag, not just the requested one. This will incorrectly exclude dishes that have
a different allergen but are still `vegetarian`. The exclude should be:
```python
).exclude(dish_dietary_tags__tag__slug=diet, dish_dietary_tags__tag__is_allergen_tag=True)
```
But even that logic is confused — `diet` filtering should simply be:
`qs.filter(dish_dietary_tags__tag__slug=diet)`. Allergen *exclusion* (contains-X
tags) is already handled by the Finder's hard filter in the search pipeline;
the catalogue endpoint just needs to filter by tag presence.

**Fix needed:** Simplify to `qs.filter(dish_dietary_tags__tag__slug=diet)`.

---

### 3b. `dish_catalogue` returns all statuses including DRAFT (covered in 1d above)

---

### 3c. `GET /v1/dishes/<uuid>/pairings/` — `AllowAny` but search requires authentication

The pairings, substitutions, missing, catalogue, nutrition and region endpoints
all use `AllowAny`. The search and resolve endpoints also use `AllowAny`.
**Only** `POST /v1/search/by-ingredients` requires `read:search` scope and
`POST /v1/internal/submissions` requires `internal:curation`.

This is inconsistent with the architecture spec, which says:
*"Every caller has its own client record and key."*

The current state effectively means the catalogue, pairings, substitutions and
nutrition can be scraped without a key — defeating the rate-limit, metering
and canary-entry protection.

The architecture doc distinguishes:
- Public (open) vs key-gated per-client endpoints
- The engine holds the data moat; per-key quotas protect it

**Recommendation (not a critical bug):** Decide the access policy explicitly.
If catalogue/pairings/nutrition are meant to be open, document it. If they
should require at minimum `read:catalog` scope, add `HasScope(SCOPE_READ_CATALOG)`
to those views. The current mixed state is undocumented.

---

### 3d. Category expander (E56) — `_CATEGORY_ALIASES` uses hardcoded category slugs that may not match seeded data

The alias map in `apps/search/category_expander.py` tries slugs like
`"vegetables"`, `"vegetables-and-greens"`, `"vegetables-greens"` — whichever
is first to return results wins. But the actual seeded category slugs (derived
from `name_en` via `slugify` in `seed_all`) are `"vegetables"`,
`"meat-offal-and-poultry"`, `"fish-and-seafood"`, etc.

The fallback chain means `"greens"` will likely resolve to nothing if the
seeded slug is `"vegetables-and-greens"` and `"vegetables"` returns no results.
The `test_e56.py` test accommodates this ambiguity with:
```python
if ids:
    assert "greens" not in remaining
else:
    assert "greens" in remaining
```

**Fix needed:** Run `_get_category_ingredient_ids` for each candidate slug
in the actual seeded DB and pin the alias map to the real slugs. Add a
management command `validate_category_aliases` or add a test that asserts at
least N ids expand from `"greens"` in the seeded DB.

---

### 3e. `ResolvedQuery.is_empty` does not account for category_expanded_ids

`apps/search/pipeline.py`:
```python
@property
def is_empty(self) -> bool:
    """True if no user ingredients resolved (staples are assumed, not real matches)."""
    return not self.matched_ids
```

After E56, `matched_ids` includes both resolver-matched and
category-expanded IDs. This property is still correct — if
`matched_ids` is empty then no useful input was resolved — but the
docstring is stale. Minor documentation fix.

---

## 4. Architecture Compliance Gaps

### 4a. `GET /v1/ingredients/` autocomplete (`q=`) — **NOT IMPLEMENTED**

The architecture spec: *"GET /v1/ingredients — List, autocomplete (q=), detail
with aliases and allergens."* The ingredient list endpoint does not exist at all
(see 1a above), so autocomplete is also absent.

---

### 4b. Ingredient detail does not include aliases or allergens

When `GET /v1/ingredients/{slug}/` is eventually built, it should include:
- All aliases with language tags
- Linked allergens
- `is_staple` flag
- `kind`

The architecture specifies this explicitly.

---

### 4c. Dish detail does not include steps, regions, or dietary tags

When `GET /v1/dishes/{slug}/` is built, the architecture specifies it should
return: *"Description, ingredients with roles, steps, region, tags."* The
current `dish_catalogue` list view returns only basic metadata.

---

### 4d. `POST /v1/internal/submissions` URL naming inconsistency

The endpoint is registered at both:
- `/v1/internal/submissions/` — correct path per architecture
- `/v1/datasets/diff/` — correct path per architecture (E54)

But `api/urls.py` routes both through `include("apps.curation.urls")`, which
means `/v1/datasets/submissions/` is **also** accidentally routable (the
diff and submission URLs are on the same include prefix). This should use
separate URL modules or prefixes.

---

### 4e. `publish_release` does not update `settings.DATASET_VERSION`

After running `publish_release`, the new version is in the `DatasetRelease`
table and `get_dataset_version()` will return it correctly from the DB. But
`settings.DATASET_VERSION` (used as the fallback in version endpoint) remains
at its initial value. This is fine for production (the DB always wins) but
could cause confusing state in tests. Document this clearly.

---

## 5. Test Quality Issues

### 5a. Golden set runner is not integrated into the CI pipeline test output

`apps/search/management/commands/run_golden_set.py` exists and works. But
`apps/search/tests/test_e18_golden_set.py` runs the golden set *as a pytest
test* by importing the runner. Check whether CI actually runs the golden set
and reports the 95% pass-rate threshold as a failing build gate.

---

### 5b. `seeded_db` fixture depends on signals being disconnected and reconnected

`conftest.py` manually disconnects and reconnects `post_save`/`post_delete`
signals during seeding. If a future app adds a new signal on `DishIngredient`,
the conftest will silently not disconnect it, and the session-scoped seed will
run it ~1,282 times (once per link), potentially causing slow or inconsistent
test behaviour. The fix is to make `_disconnect_signals` pull the signal
receivers dynamically rather than by name.

---

### 5c. `test_e56.py` — two tests use `import` statements inside try/finally

The test `test_category_expanded_ids_in_pool` imports
`resolve_ingredients` inside a try/finally that mutates a module-level dict.
If the import fails (due to a module error introduced elsewhere), the
`finally` block will run but the dict cleanup may leave `_CATEGORY_ALIASES`
in a mutated state for subsequent tests in the same process. This is a
test-isolation risk.

---

## 6. Data Gaps

### 6a. Dietary tags not seeded for the 300 dishes

`apply_derived_tags_for_all_dishes()` exists in `apps/dietary/services.py`
but there is no management command or seed step that calls it. The 300 seeded
dishes have no `DishDietaryTag` rows, so:
- `GET /v1/dishes/?diet=vegetarian` returns zero results
- Allergen filtering in search (`contains-X` tags) has nothing to filter

**Fix needed:** Call `apply_derived_tags_for_all_dishes()` at the end of
`seed_all`, or add a `manage.py derive_dietary_tags` command.

---

### 6b. Dishes are not linked to regions after seeding

`seed_all` loads `regions.csv` into `Region` objects but does not create any
`DishRegion` links. The 300 dishes have `regions = []`. This means:
- `GET /v1/dishes/?region=nairobi` returns zero results
- The `region_pref` scoring signal in the ranker always returns 0
- The "Taste of 47 counties" brand promise is not backed by data

**Fix needed:** Either add a `dish_regions.csv` seed file, or add a `region`
column to `dishes.csv` and map it in `seed_all._seed_dishes()`.

---

### 6c. `popularity` is 0.0 for all dishes until `compute_popularity` is run manually

`seed_all` does not call `compute_popularity`. All dishes start with
`popularity=0.0`, which means the popularity signal in the ranker is
meaningless until an operator runs `python manage.py compute_popularity`.
The Celery task `update_dish_popularity` is registered but not scheduled
in `CELERY_BEAT_SCHEDULE`.

**Fix needed:** Call `compute_popularity` at the end of `seed_all`, and/or
add a `CrontabSchedule` + `PeriodicTask` for `update_dish_popularity` in a
data migration or the seed command.

---

### 6d. Aliases (Swahili / Sheng names) not seeded

`data/seeds/` has no `aliases.csv`. The `IngredientAlias` table is empty after
seeding. This means:
- Typing `nyanya` returns nothing (no alias → tomato)
- Typing `sukuma` returns nothing
- The resolver's exact alias step (step 1) is effectively dead
- The Swahili/Sheng support claimed in the architecture is not functional

This is the most serious data gap. The resolver falls back to fuzzy matching
which may still work for close spellings, but the dictionary design depends on
aliases being populated.

**Fix needed:** Create `data/seeds/aliases.csv` and add `_seed_aliases()` to
`seed_all`. At minimum, add the Swahili names for the top 50 ingredients
(nyanya, vitunguu, sukuma wiki, mahindi, maharagwe, viazi, nyama, kuku, samaki,
ndengu, unga, mchele, ndimu, pilipili, mafuta, chumvi, chai, maziwa, mayai, siagi).

---

## 7. Minor / Housekeeping Issues

| # | Location | Issue |
|---|----------|-------|
| M1 | `apps/api/urls.py` | `datasets/` and `internal/` both include the same `apps.curation.urls` — accidental cross-routing (see 4d) |
| M2 | `apps/curation/views_diff.py` | `AllowAny` was not applied (uses `HasScope(READ_CATALOG)` which is correct, but the nutrition and pairings endpoints are inconsistently `AllowAny`) |
| M3 | `apps/search/pipeline.py` | `ResolvedQuery.is_empty` docstring is stale after E56 |
| M4 | `apps/clients/metering.py` | `MeteringMiddleware` logs to `RequestLog` — verify it does not log `AllowAny` endpoints (and thus double-count unauth requests) |
| M5 | `apps/dishes/views_advisor.py` | Pairings/substitutions/missing use `AllowAny` — no metering, no rate-limit, no canary protection |
| M6 | `CHANGELOG.md` | Lists `GET /v1/dishes/{slug}/` and `GET /v1/ingredients/` as delivered — they are not |
| M7 | `docs/PROGRESS.md` | Says v1.0.0 is complete — should note the post-v1.0 gaps documented here |
| M8 | `config/settings/base.py` | `STAPLES_LIST` env var exists but `staples.py` never reads it — it always queries the DB. Either wire it or remove it. |
| M9 | `apps/search/category_expander.py` | `chicken` is in `_CATEGORY_ALIASES` with value `None` to skip it. This is confusing — would be clearer as a comment or a separate `_SKIP_TOKENS` set. |
| M10 | `apps/curation/management/commands/publish_release.py` | The `released_by` field on `DatasetRelease` is never set by the command (no `--user` argument, and CLI has no active user session). It will always be NULL in CLI publishes. |

---

## 8. Priority Order for Fixes

| Priority | Item | Effort |
|----------|------|--------|
| **P0 — Fix immediately** | 6d: Seed aliases.csv (Swahili names) | Medium |
| **P0 — Fix immediately** | 6a: Call `apply_derived_tags` in seed_all | Small |
| **P0 — Fix immediately** | 1b: Dish detail endpoint (slug-based) | Small |
| **P0 — Fix immediately** | 1a: Ingredient list + detail endpoints | Small |
| **P1 — Fix soon** | 1d: Remove DRAFT from catalogue query | Tiny |
| **P1 — Fix soon** | 3a: Fix diet filter in dish_catalogue | Tiny |
| **P1 — Fix soon** | 1c: Version endpoint use DB DatasetRelease | Tiny |
| **P1 — Fix soon** | 6b: Dish-region links in seed data | Medium |
| **P1 — Fix soon** | 6c: Run compute_popularity in seed_all, schedule Celery task | Small |
| **P1 — Fix soon** | 2a: Dietary app tests | Medium |
| **P1 — Fix soon** | 2b: Pairings tests | Small |
| **P2 — Next iteration** | 3d: Validate category alias slugs against seeded DB | Small |
| **P2 — Next iteration** | 2c: Core app tests | Small |
| **P2 — Next iteration** | 2d: E52/E53/E54 curation tests | Medium |
| **P2 — Next iteration** | 4d: Fix accidental cross-routing in api/urls.py | Tiny |
| **P2 — Next iteration** | M8: Wire or remove STAPLES_LIST env var | Tiny |
| **P3 — Document/decide** | 3c: Decide access policy for catalogue/pairings/nutrition | Decision |
| **P3 — Document/decide** | M10: released_by on publish_release | Small |

---

## 9. What is Solid and Should Not Be Changed

- **The matching pipeline** — resolver → staples → finder → judge → ranker → explainer
  is clean, well-tested, deterministic, and exactly matches the blueprint.
- **Security layer** — API key auth, HasScope permissions, 2FA admin, security
  headers middleware, rate limiting, metering, ChangeLog audit.
- **Search caching** — dataset-version-keyed Redis cache with ETag/304 support.
- **Data validation** — 23 integrity rules, duplicate detector, QA report.
- **CI pipeline** — lint, type checks, secret scanning, SAST, golden set, API
  contract, image scanning. The pipeline structure is solid.
- **Curation workflow** — Source, ChangeLog, DatasetRelease, two-lock dietary
  derivation, audit trail.
- **Substitution constraint** — `nulls_distinct=False` is correct for PG15+.
- **Staples list** — exactly 6, correctly classified, migration enforces it.
