# Changelog — Flavor Find Engine

All notable changes to this project will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
Versions follow [Semantic Versioning](https://semver.org/).

---

## [1.1.0] — 2026-10-28

**Post-release fixes and test coverage pass (Tasks 1–18).**

### Fixed

- **Dish catalogue** — seeded dishes were left in `status=draft`; the Finder and catalogue
  endpoint excluded them. `seed_all` now calls `_promote_seeded_to_reviewed()` unconditionally
  on every non-dry-run execution. (PR #44)
- **Dietary tags** — `seed_all` was not deriving dietary tags after seeding; all dishes showed
  no dietary information. Tags are now derived as part of every seed run. (PR #44)
- **Swahili ingredient names** — aliases CSV was missing; search in Swahili (`lang=sw`) always
  returned zero results. Added `aliases.csv` and wired it into `seed_all`. (PR #45)
- **Dish-region links** — region associations were not seeded; `GET /v1/dishes/?region=…`
  always returned zero results. Added region seed step to `seed_all`. (PR #53)
- **Popularity scores** — nutrition data was not loaded; `compute_popularity` had no input data
  and all dishes scored 0. Added nutrition seed step and wired `compute_popularity` into
  `seed_all`. (PR #54)
- **Version endpoint** — `GET /v1/meta/version/` returned a hardcoded `"dev"` string instead
  of reading the current `DatasetRelease` from the database. (PR #50)
- **Dataset diff endpoint** — `GET /v1/datasets/diff/` returned HTTP 500 on every request.
  `datetime.now(tz=datetime.UTC)` referenced `datetime.UTC` on the imported `datetime` *class*,
  which has no `UTC` attribute; should reference the module. Fixed to
  `datetime.datetime.now(tz=datetime.UTC)`. (PR #57)
- **URL routing conflict** — `api/urls.py` included `apps.curation.urls` under both `internal/`
  and `datasets/`, making `/v1/datasets/submissions/` accidentally resolvable. Split into
  `urls_submissions.py` (internal only) and `urls_diff.py` (datasets only). (PR #58)
- **Dish sub-route path parameters** — pairings, substitutions, and missing endpoints used
  `<uuid:dish_id>` while the architecture and dish detail both use `<slug:slug>`.
  Standardised to slug throughout. (PR #58)
- **Nightly CI seed step** — stale iteration-gate guard (`if manage.py help seed_all`) was
  never removed after `seed_all` was built; the step logged a spurious "skipped" notice on
  every nightly run. Guard removed; step now calls `seed_all` directly. (PR #61)
- **Celery beat schedule** — `update_dish_popularity` task existed but was never scheduled;
  popularity scores went stale immediately after the initial seed. Now runs daily at 03:00
  Nairobi time. (PR #59)

### Added

- `GET /v1/dishes/{slug}/` — dish detail endpoint (PR #51)
- `GET /v1/ingredients/` — ingredient list endpoint (PR #52)
- `GET /v1/ingredients/{slug}/` — ingredient detail endpoint (PR #52)
- `GET /v1/meta/version/` — now returns live `DatasetRelease` from DB (PR #50)

### Removed

- Dead `STAPLES_LIST` env var from `config/settings/base.py` — `staples.py` always queries
  the database; the setting was never read. (PR #60)

### Tests added

- Dietary safety filter tests — E33/E34 derivation and override rules (PR #55)
- Pairings tests — E28/E29 service layer and endpoint (PR #56)
- Curation E52/E53/E54 tests — submission intake, `publish_release` command, dataset diff
  endpoint (PR #57)
- Core middleware tests — `SecurityHeadersMiddleware`, `RequestIDMiddleware`,
  `custom_exception_handler`, `TimeStampedModel` (PR #62)

### API endpoints at v1.1.0

| Method | Path | Description |
|--------|------|-------------|
| GET | /v1/health/ | Health check (unauthenticated) |
| GET | /v1/meta/version/ | Current dataset version (reads from DB) |
| POST | /v1/search/by-ingredients | Ingredient-based dish search |
| GET | /v1/dishes/ | Dish catalogue with filters |
| GET | /v1/dishes/{slug}/ | Dish detail |
| GET | /v1/dishes/{slug}/pairings/ | Dish pairings |
| GET | /v1/dishes/{slug}/substitutions/ | Ingredient substitutions for a dish |
| POST | /v1/dishes/{slug}/missing/ | Missing ingredients given what you have |
| GET | /v1/dishes/{slug}/nutrition/ | Per-serving nutrition estimate |
| GET | /v1/ingredients/ | Ingredient list |
| GET | /v1/ingredients/{slug}/ | Ingredient detail |
| GET | /v1/regions/ | Cuisine regions |
| GET | /v1/datasets/diff/ | Dataset diff since a given version |
| POST | /v1/internal/submissions/ | Community submission intake (internal scope) |
| GET | /v1/schema/ | OpenAPI schema |

---

## [1.0.0] — 2026-10-26

**Sprint 1 complete. First production release of the isolated recipe engine.**

### Dataset v1.0.0

- **878 ingredients** across 12 categories (Vegetables, Fruit, Meat, Poultry, Fish & Seafood, Grains, Legumes, Dairy & Eggs, Fats & Oils, Spices & Seasonings, Liquids, Other)
- **300 dishes** covering Kenyan, Tanzanian, Ethiopian, Ugandan, Rwandan, Burundian, Cameroonian, West African, North African and Somali cuisine
- **1,282 dish-ingredient links** with primary/required/optional/garnish roles
- **150 pairings** (dish-to-dish and dish-to-label)
- **200 substitutions** with quality ratings and ratio guidance
- **200 golden set cases** (G01–G200) — resolver accuracy ≥ 95%

### Engine v1.0.0

**E1–E9 — Foundations**
- Django project with split settings (dev/test/prod)
- PostgreSQL + Redis + Celery infrastructure
- Core models: Ingredient, IngredientCategory, IngredientAlias
- Dish models: Dish, DishIngredient (4 roles), DishAlias, DishStep, Region, DishRegion
- GIN-indexed search arrays (required_ids, optional_ids, primary_ids, all_ids)
- Admin with 2FA (django-otp, django-two-factor-auth)
- Staging on Render with auto-deploy on main push
- Seed pipeline: 300 dishes, 878 ingredients

**E10–E18 — Data Pipeline**
- CSV importers and exporters with dry-run and snapshot modes
- 23 integrity validators (V01–V23) with full test coverage
- Duplicate detector (pg_trgm similarity + Python SequenceMatcher fallback)
- QA report: missing fields, integrity violations, status gaps
- Normaliser: unicode, lowercase, trim, quantity strip, deplural, language detection
- Resolver: exact alias → exact name → fuzzy (pg_trgm / SequenceMatcher), ambiguity detection
- Golden set runner with 8 assertion types, --fail-fast / --json / --fixture flags

**E19–E27 — Matching v1**
- Search arrays with auto-rebuild on DishIngredient change (signals)
- Staples handling: auto-expand pool, never listed as missing
- Finder: GIN overlap query, hard filters (status, meal_type, course, diet)
- Judge: Exact / Can Make / Almost tiers (explore mode)
- Ranker: 7-weight scoring (coverage, primary_hit, usage_ratio, popularity, quality_bonus, region_pref, missing_penalty)
- Explainer: matched/missing/unused/staples_assumed per result with score breakdown
- POST /v1/search/by-ingredients: strict + explore modes, diet filter, language, exclusions
- Redis dataset-version-keyed cache with ETag, 304 Not Modified, X-Cache-Hit header

**E28–E35 — Advisor and Safety**
- Pairing model and pairings endpoint
- Substitution model and substitutions endpoint
- Missing-ingredients endpoint with substitute suggestions
- Dietary tags: 8 derivation rules (vegetarian, vegan, halal-friendly, gluten-free, nut-free, dairy-free, egg-free, contains-pork)
- Manual dietary overrides with ChangeLog audit trail
- Regions and catalogue API: GET /v1/dishes/ with filters

**E36–E43 — Platform Features**
- API clients, keys and scopes (hashed SHA-256, prefix lookup, revocable)
- Per-key rate limiting (DRF SimpleRateThrottle, rpm, unlimited=0)
- Usage metering: RequestLog + UsageRecord daily rollup Celery task
- Nutrition facts: GET /v1/dishes/{slug}/nutrition/ with per-serving sums
- Performance tuning: GIN indexes, connection pooling, p95 < 150 ms test
- Internal test console (React + Vite, served at /console/)
- OpenAPI schema via drf-spectacular, schema validation in CI
- Zero-result observatory: ZeroResultQuery model, qa_zero_results command

**E44–E46 — Data Expansion**
- Ingredients: 504 → 878 (+374)
- Dishes: 150 → 300 (+150)
- Golden set: 20 → 200 cases

**E47–E51 — Hardening and Release**
- Load tests: SearchUser, SoakUser, BurstUser (locust)
- Failure tests: cache failure, malformed payloads, injection attempts, auth failures
- Security headers middleware (X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy)
- Bandit static analysis config
- Backup drill: export snapshot, verify row counts, restore with --confirm
- Rollback drill: read-only command prints Render + migration rollback steps
- Docs: operations runbook, data style guide, incident log template, release checklist

**E52–E59 — Community and Curation**
- Community submission intake: POST /v1/internal/submissions/
- Dataset release pipeline: publish_release management command
- Dataset diff endpoint: GET /v1/datasets/diff/
- Step-up authentication for high-risk curation actions
- Rate limiting for community endpoints

### API endpoints shipped at v1.0.0

*Note: the endpoints below were present in the codebase at v1.0.0 but some were not
reachable until the post-release fixes in v1.1.0 (dish detail, ingredients, version
endpoint were wired up; seeded dishes were not promoted to reviewed status).*

| Method | Path | Description |
|--------|------|-------------|
| GET | /v1/health/ | Health check (unauthenticated) |
| POST | /v1/search/by-ingredients | Ingredient-based dish search |
| GET | /v1/dishes/ | Dish catalogue with filters |
| GET | /v1/dishes/{slug}/pairings/ | Dish pairings |
| GET | /v1/dishes/{slug}/substitutions/ | Ingredient substitutions for a dish |
| POST | /v1/dishes/{slug}/missing/ | Missing ingredients given what you have |
| GET | /v1/dishes/{slug}/nutrition/ | Per-serving nutrition estimate |
| GET | /v1/regions/ | Cuisine regions |
| GET | /v1/schema/ | OpenAPI schema |

---

## [0.0.0] — 2026-10-23

Initial repository setup (E1–E2): repo structure, Docker environment, CI/CD scaffolding.
