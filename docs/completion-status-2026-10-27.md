# Flavor Find Engine — Completion Status
**Date:** 2026-10-27 | **Current state:** v1.0.0 code built, data not production-ready  
**Working directory:** `/home/jarvis/Documents/GitHub/ff-engine`

---

## The One-Line Truth

The engine **code is complete**. The engine **data is broken**. A fresh `seed_all` + search
produces zero results because all 300 dishes are `status=draft` and the matcher only
returns `reviewed`/`verified` dishes. Fixing that one thing makes the engine functional.
Everything else below is a prioritised list of what remains to reach "truly complete."

---

## Section 1 — What Is Complete and Working

These are solid. Do not touch them.

| Area | Evidence |
|------|----------|
| Search pipeline | resolver → staples → finder → judge → ranker → explainer — clean, tested, deterministic |
| API key auth | SHA-256 hashed, scoped, rate-limited, metered, revocable |
| 2FA admin | AdminSiteOTPRequired enforced; TOTP + security key supported |
| Security headers | X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy |
| Curation workflow | Source, ChangeLog (append-only), DatasetRelease, 23 validators |
| Dietary safety filter | derive_dietary_tags() + apply_derived_tags() + two-lock principle |
| Substitution constraint | nulls_distinct=False on (ingredient, substitute, context_dish) — PG15+ correct |
| Staples list | Exactly 6 correct staples, locked by migration 0003 |
| CI pipeline | lint, SAST, secret scan, tests, golden set (resolver only), image scan |
| 555 passing tests | All pass in isolation; seeded_db suite requires a live DB |
| CSV data files | 300 dishes, 878 ingredients, 1282 links, 750 steps, 150 pairings, 200 substitutions |
| Community submissions (E52) | POST /v1/internal/submissions — pending-queue intake |
| Dataset release tooling (E53) | publish_release command with --confirm-stepup gate |
| What-changed endpoint (E54) | GET /v1/datasets/diff?since=VERSION |
| Regions + units seeded (E55) | 47 counties + 15 cuisine groups + 23 units in CSV |
| Category word expansion (E56) | 'greens'/'nyama'/'samaki' expand to ingredient IDs |
| Security verification (E57) | AdminSiteOTPRequired, ChangeLog audit, scope matrix tested |
| Popularity signal (E58) | compute_popularity command + Celery task |
| Test speed-up (E59c) | fast/full marks, statement_timeout, mini_db fixture |

---

## Section 2 — The Blockers (Engine Returns Zero Results)

These must be fixed before a single search works on a fresh deployment.

---

### BLOCKER 1 — All 300 dishes are `status=draft`

**What:** `seed_all` creates every dish with `status=StatusChoices.DRAFT`.  
The Finder only queries `status__in=[REVIEWED, VERIFIED]`.  
Result: `POST /v1/search/by-ingredients` returns zero results for every query.

**How it was handled on staging:** Status was promoted manually via the Django admin.  
There is no automated step in `seed_all` that does this.

**Fix (3 lines):**  
In `apps/curation/management/commands/seed_all.py`, after `_rebuild_arrays()` is called,
add a promotion step:
```python
def _promote_draft_to_reviewed(self) -> int:
    from apps.dishes.models import Dish
    from apps.ingredients.models import Ingredient
    count = Dish.objects.filter(status='draft').update(status='reviewed', quality_level='reviewed')
    Ingredient.objects.filter(status='draft').update(status='reviewed')
    return count
```
And call it in `handle()` after `_rebuild_arrays()`.

**Alternatively:** Add `--promote` flag so it is opt-in for production.

---

### BLOCKER 2 — No Swahili or Sheng aliases seeded

**What:** `IngredientAlias` table is empty after `seed_all`. The resolver's step 1
(exact alias lookup) returns nothing. Typing `nyanya`, `sukuma`, `maharagwe`,
`vitunguu`, `unga`, or any Swahili name returns unmatched.

The engine claims Swahili/Sheng support. It does not work without alias data.

**What's missing:** `data/seeds/aliases.csv` does not exist.  
`seed_all` has no `_seed_aliases()` method.

**Fix:** Create `data/seeds/aliases.csv` with this format:
```
ingredient_slug,alias,language,is_misspelling
tomato,nyanya,sw,false
tomato,tomatos,en,true
onion,vitunguu,sw,false
...
```
Then add `_seed_aliases()` to `seed_all`.

**Minimum viable aliases (top-priority ingredients in Swahili):**

| English | Swahili | Sheng |
|---------|---------|-------|
| tomato | nyanya | — |
| onion | vitunguu | — |
| collard greens | sukuma wiki | sukuma |
| maize flour | unga wa mahindi | unga |
| beans | maharagwe | — |
| potato | viazi | — |
| meat (general) | nyama | nyam |
| chicken | kuku | — |
| fish | samaki | — |
| rice | mchele / wali (cooked) | — |
| salt | chumvi | — |
| cooking oil | mafuta | — |
| avocado | parachichi | — |
| banana | ndizi | — |
| egg | yai (pl. mayai) | — |
| milk | maziwa | — |
| flour (generic) | unga | — |
| water | maji | — |
| coconut | nazi | — |
| lime | ndimu | — |
| chilli | pilipili | pili |
| coriander | dhania | — |
| garlic | vitunguu saumu | — |
| ginger | tangawizi | — |
| spinach / amaranth | mchicha | — |
| cassava | muhogo | — |
| plantain / banana | ndizi (green) | — |
| sweet potato | viazi vitamu | — |

---

### BLOCKER 3 — Dietary tags not derived for the 300 seeded dishes

**What:** `apply_derived_tags_for_all_dishes()` exists in `apps/dietary/services.py`
but is never called during seeding. The `DishDietaryTag` table is empty.

Result:
- `GET /v1/dishes/?diet=vegetarian` → zero results
- Allergen exclusion in search (e.g. `diet=contains-pork`) → no filtering happens
- The safety filter — "allergen exclusion always wins" — cannot win if it has nothing to filter

**Fix:** At the end of `seed_all`, after `_promote_draft_to_reviewed()`:
```python
from apps.dietary.services import apply_derived_tags_for_all_dishes
apply_derived_tags_for_all_dishes()
```

---

## Section 3 — Missing API Endpoints

The CHANGELOG lists these as delivered. They are not in the code.

---

### MISSING: `GET /v1/dishes/{slug}/` — dish detail

**What the architecture says:**  
*"GET /v1/dishes/{id} — Dish detail: description, ingredients with roles, steps, region, tags"*

**What exists:** Only `GET /v1/dishes/` (list) and sub-routes for pairings/substitutions/missing.  
The URL pattern for pairings uses `<uuid:dish_id>` but the architecture uses slug. Inconsistent.

**Fix:** Add to `apps/dishes/views_catalogue.py`:
- `dish_detail(request, slug)` view returning full dish object:
  name_en, name_sw, description, meal_type, course, spice_level, difficulty,
  prep_min, cook_min, servings, quality_level, status,
  ingredients (with role + quantity), steps (ordered), regions, dietary_tags

Add to `apps/dishes/urls.py`:
```python
path("<slug:slug>/", dish_detail, name="dish-detail"),
```

Also standardise the pairings/substitutions/missing URLs to use `<slug:slug>` instead of `<uuid:dish_id>`.

---

### MISSING: `GET /v1/ingredients/` and `GET /v1/ingredients/{slug}/`

**What the architecture says:**  
*"GET /v1/ingredients — List, autocomplete (q=), detail with aliases and allergens"*

**What exists:** Only `POST /v1/ingredients/resolve`.

**Fix:** Add to `apps/ingredients/views.py`:
- `ingredient_list(request)` — paginated list with `q=` autocomplete, `category=` filter
- `ingredient_detail(request, slug)` — full detail with aliases (all languages), allergens, is_staple, kind

Add to `apps/ingredients/urls.py`:
```python
path("", ingredient_list, name="ingredient-list"),
path("<slug:slug>/", ingredient_detail, name="ingredient-detail"),
```

---

### BUG: `GET /v1/meta/version/` returns hardcoded version

**What:** `apps/api/views.py` line 65 reads `settings.DATASET_VERSION` (a static env var).  
`get_dataset_version()` in `apps/search/cache.py` already does the correct DB lookup.

**Fix (1 line):**
```python
from apps.search.cache import get_dataset_version
# replace:
"dataset_version": getattr(settings, "DATASET_VERSION", "0.0.0"),
# with:
"dataset_version": get_dataset_version(),
```

---

### BUG: `GET /v1/dishes/` returns DRAFT dishes

**What:** `apps/dishes/views_catalogue.py` includes `StatusChoices.DRAFT` in the queryset filter.  
Public catalogue should only show reviewed + verified.

**Fix (1 line):** Remove `StatusChoices.DRAFT` from the filter.

---

### BUG: `GET /v1/dishes/?diet=vegetarian` broken (inverted filter logic)

**What:** The diet filter in `views_catalogue.py`:
```python
.exclude(dish_dietary_tags__tag__is_allergen_tag=True)
```
This excludes dishes that have ANY allergen tag, not just the requested one.
A vegetarian dish with a nut-free tag would be excluded.

**Fix:**
```python
qs = qs.filter(dish_dietary_tags__tag__slug=diet)
# remove the .exclude() entirely — allergen exclusion is handled by the search Finder
```

---

## Section 4 — Data Gaps

---

### DATA GAP 1 — No dish-region links

**What:** `seed_all` loads `regions.csv` (63 regions) but creates zero `DishRegion` rows.  
All 300 dishes have `regions = []`.

Result:
- `GET /v1/dishes/?region=nairobi` → zero results
- `GET /v1/regions/` returns regions, but they link to no dishes
- The `region_pref` signal in the ranker always contributes 0 to every score
- "Taste of 47 counties" has no backing data

**Fix:**  
Add a `region` column to `dishes.csv` with the cuisine/region slug for each dish,
then add a `_seed_dish_regions()` step in `seed_all`.

For the 300 dishes, approximate region assignments:
- Kenyan dishes → luo / kikuyu / kalenjin / kamba / luhya / kenyan-coast
- Ethiopian dishes → ethiopian
- Tanzanian dishes → tanzanian
- Ugandan dishes → ugandan
- Rwandan/Burundian → rwandan
- West African → west-african
- Somali → somali-kenyan
- Coastal dishes → kenyan-coast

---

### DATA GAP 2 — Only 150 of 300 dishes have cooking steps

`dish_steps.csv` has steps for 150 dishes. The other 150 have zero steps.

**Result:** `GET /v1/dishes/{slug}/` (once built) will return empty steps for half the library.

**Fix:** Add steps for the remaining 150 dishes. Even 2–3 generic steps per dish is better than none.

---

### DATA GAP 3 — Only 50 of 878 ingredients have nutrition data

`nutrition_ingredients.csv` has 50 rows. `seed_all` does not load this file into `NutritionFact`.

**Result:** `GET /v1/dishes/{slug}/nutrition/` returns zeroed-out estimates for almost all dishes.

**Two fixes needed:**
1. Add `_seed_nutrition()` to `seed_all` that reads `nutrition_ingredients.csv` and creates `NutritionFact` rows
2. Expand `nutrition_ingredients.csv` to cover the 50–100 most common ingredients

---

### DATA GAP 4 — 68 dishes have only a `primary` role ingredient, no `required`

Dishes with `primary` role only have empty `required_ids` arrays (rebuild_search_arrays excludes `primary`
from `required_ids`). This means they can only be found if the user types their exact primary ingredient
and they end up in `can_make` tier (since all their required_ids are empty = nothing missing, but
the user's ingredient is in `all_ids`).

These 68 dishes would benefit from having their primary ingredient also listed as `required`.

---

### DATA GAP 5 — `popularity` is 0.0 for all dishes on fresh seed

`compute_popularity` is not called by `seed_all`. The `update_dish_popularity` Celery
task exists but is not scheduled.

**Fix:**  
1. Call `compute_popularity` at end of `seed_all`
2. Add a `PeriodicTask` or `CELERY_BEAT_SCHEDULE` entry for daily popularity refresh

---

### DATA GAP 6 — `nutrition_ingredients.csv` not loaded by `seed_all`

`seed_all` has no `_seed_nutrition()` method. The file exists but is never imported.

---

## Section 5 — Missing Tests

| App | Missing | Priority |
|-----|---------|----------|
| `apps/dietary/tests/` | Empty — zero tests on the safety filter (the most critical feature) | HIGH |
| `apps/pairings/tests/` | Empty — no tests on pairing retrieval, constraint, or endpoint | MEDIUM |
| `apps/core/tests/` | Empty — security headers, request ID, exception handler untested | LOW |
| `apps/curation/tests/` | Missing test_e52.py, test_e53.py, test_e54.py | MEDIUM |

---

## Section 6 — Infrastructure Issues

---

### INFRA 1 — Nightly CI golden set runs before seed_all

In `.github/workflows/nightly.yml`, the step order is:
```
Seed data (E9)  →  Golden set (E18)  →  QA report (E14)
```
But the golden set (`run_golden_set`) only tests the **resolver/pipeline** (it does not
require seeded dishes — it creates its own inline test ingredients). This is correct
behaviour. The comment in the workflow saying it is gated behind E9 is misleading.

The real issue: the nightly CI does `seed_all` but never promotes dishes to `reviewed`,
so nightly QA results will always show zero live dishes.

**Fix:** Add `python manage.py seed_all --promote` (after the promote step is added).

---

### INFRA 2 — `render.yaml` build command does not promote dishes

The Render build command is:
```
seed_all && ensure_superuser
```
No status promotion step. On every fresh Render deploy, the DB is populated with
300 draft dishes and search returns zero results.

**Fix:** Add status promotion to the build command or to `seed_all` itself.

---

### INFRA 3 — URL routing conflict in `api/urls.py`

Both `path("internal/", include("apps.curation.urls"))` and
`path("datasets/", include("apps.curation.urls"))` point to the same URL module.

This means:
- `/v1/internal/submissions/` ✅ correct
- `/v1/internal/diff/` ✅ works (correct for diff access under internal/)
- `/v1/datasets/diff/` ✅ correct
- `/v1/datasets/submissions/` ❌ accidentally also resolves to the submission endpoint

**Fix:** Use separate URL modules: `urls_submissions.py` and `urls_diff.py`.

---

### INFRA 4 — `STAPLES_LIST` env var is wired to nothing

`config/settings/base.py` defines:
```python
STAPLES_LIST = env.list("STAPLES_LIST", default=["water", "salt", ...])
```
But `apps/search/staples.py` never reads `settings.STAPLES_LIST`. It always queries
the DB. The env var is dead code. Either wire it or remove it.

---

## Section 7 — Complete Checklist to Call the Engine "Done"

Priority order. Each row is a discrete, shippable task.

### 🔴 P0 — Required for basic functionality (nothing works without these)

| # | Task | File(s) | Effort |
|---|------|---------|--------|
| P0-1 | Promote seeded dishes to `status=reviewed` in `seed_all` | `seed_all.py` | 30 min |
| P0-2 | Create `data/seeds/aliases.csv` with Swahili names for top ~50 ingredients | new CSV | 2 hrs |
| P0-3 | Add `_seed_aliases()` to `seed_all` | `seed_all.py` | 1 hr |
| P0-4 | Call `apply_derived_tags_for_all_dishes()` in `seed_all` | `seed_all.py` | 30 min |
| P0-5 | Fix `GET /v1/dishes/` to exclude DRAFT dishes | `views_catalogue.py` | 10 min |

---

### 🟠 P1 — Required for a complete, spec-compliant API

| # | Task | File(s) | Effort |
|---|------|---------|--------|
| P1-1 | Add `GET /v1/dishes/{slug}/` detail endpoint | `views_catalogue.py`, `urls.py` | 2 hrs |
| P1-2 | Add `GET /v1/ingredients/` list endpoint (with `q=` autocomplete) | `views.py`, `urls.py` | 1 hr |
| P1-3 | Add `GET /v1/ingredients/{slug}/` detail endpoint (aliases + allergens) | `views.py`, `urls.py` | 1 hr |
| P1-4 | Fix version endpoint to use DB `DatasetRelease` | `apps/api/views.py` | 10 min |
| P1-5 | Fix diet filter in `GET /v1/dishes/` (inverted logic) | `views_catalogue.py` | 10 min |
| P1-6 | Add `dish_regions.csv` seed data and `_seed_dish_regions()` | CSV + `seed_all.py` | 3 hrs |
| P1-7 | Add `_seed_nutrition()` to `seed_all` (load `nutrition_ingredients.csv`) | `seed_all.py` | 1 hr |
| P1-8 | Call `compute_popularity` in `seed_all` after promotion | `seed_all.py` | 20 min |

---

### 🟡 P2 — Required for data quality and test coverage

| # | Task | File(s) | Effort |
|---|------|---------|--------|
| P2-1 | Write `apps/dietary/tests/test_e31_e32.py` (8 derivation rules, signals, overrides) | new file | 2 hrs |
| P2-2 | Write `apps/pairings/tests/test_e28_e29.py` (service, endpoint, constraint) | new file | 1 hr |
| P2-3 | Write `apps/curation/tests/test_e52.py` (submission endpoint) | new file | 1 hr |
| P2-4 | Write `apps/curation/tests/test_e53.py` (publish_release command) | new file | 1 hr |
| P2-5 | Write `apps/curation/tests/test_e54.py` (dataset diff endpoint) | new file | 1 hr |
| P2-6 | Add steps for the 150 dishes that have none | `dish_steps.csv` | 3 hrs |
| P2-7 | Standardise dish sub-routes to use `<slug:slug>` not `<uuid:dish_id>` | `urls.py`, `views_advisor.py` | 1 hr |
| P2-8 | Fix URL routing conflict (split `urls.py` into `urls_submissions.py` + `urls_diff.py`) | `apps/curation/`, `apps/api/urls.py` | 30 min |
| P2-9 | Schedule `update_dish_popularity` Celery task (CELERY_BEAT_SCHEDULE or data migration) | `settings/base.py` or migration | 30 min |

---

### 🟢 P3 — Polish (for full architecture compliance)

| # | Task | File(s) | Effort |
|---|------|---------|--------|
| P3-1 | Validate and fix category expander slugs against actual seeded DB categories | `category_expander.py`, test | 1 hr |
| P3-2 | Write `apps/core/tests/test_core.py` (security headers, request ID, exception handler) | new file | 1 hr |
| P3-3 | Remove dead `STAPLES_LIST` env var or wire it to `staples.py` | `settings/base.py` | 20 min |
| P3-4 | Add `released_by` population to `publish_release` command (`--user` arg) | `publish_release.py` | 30 min |
| P3-5 | Fix nightly CI step order / add `--promote` flag | `nightly.yml`, `seed_all.py` | 30 min |
| P3-6 | Fix `render.yaml` build command to include status promotion | `render.yaml` | 10 min |
| P3-7 | Decide and document access policy for catalogue/pairings/nutrition (AllowAny vs scoped) | `views_*.py` + docs | 1 hr |
| P3-8 | Update `CHANGELOG.md` to remove falsely-claimed endpoints | `CHANGELOG.md` | 20 min |

---

## Section 8 — Summary Scorecard

| Category | Status |
|----------|--------|
| Core search pipeline | ✅ Complete |
| Security & auth | ✅ Complete |
| CI/CD infrastructure | ✅ Complete (minor nightly fix needed) |
| Curation tools | ✅ Complete |
| E52–E59 gap steps | ✅ Complete |
| **Search returns results on fresh deploy** | ❌ Broken (dishes are draft) |
| **Swahili name support** | ❌ Broken (no aliases seeded) |
| **Dietary filtering** | ❌ Broken (no tags derived) |
| Dish detail endpoint | ❌ Missing |
| Ingredient list/detail endpoint | ❌ Missing |
| Dish-region links | ❌ Missing |
| Dietary app tests | ❌ Missing |
| Pairings tests | ❌ Missing |
| E52–E54 tests | ❌ Missing |

**Rough completion: ~75% complete.**  
The code architecture is excellent. The data pipeline is the unfinished piece.  
P0 fixes (5 tasks, ~4 hours) make the engine functional.  
P0 + P1 (13 tasks, ~13 hours) make it spec-compliant and production-ready.
