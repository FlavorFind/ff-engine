# Changelog — Flavor Find Engine

All notable changes to this project will be documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
Versions follow [Semantic Versioning](https://semver.org/).

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
- Pairing model and GET /v1/dishes/{id}/pairings endpoint
- Substitution model and GET /v1/dishes/{id}/substitutions endpoint
- POST /v1/dishes/{id}/missing endpoint with substitute suggestions
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

### API endpoints at v1.0.0

| Method | Path | Description |
|--------|------|-------------|
| GET | /v1/health/ | Health check (unauthenticated) |
| POST | /v1/search/by-ingredients | Ingredient-based dish search |
| GET | /v1/dishes/ | Dish catalogue with filters |
| GET | /v1/dishes/{slug}/ | Dish detail |
| GET | /v1/dishes/{slug}/pairings/ | Dish pairings |
| GET | /v1/dishes/{slug}/substitutions/ | Ingredient substitutions for a dish |
| POST | /v1/dishes/{slug}/missing/ | What's missing from a dish given my ingredients |
| GET | /v1/dishes/{slug}/nutrition/ | Per-serving nutrition estimate |
| GET | /v1/ingredients/ | Ingredient list |
| GET | /v1/ingredients/{slug}/ | Ingredient detail |
| GET | /v1/regions/ | Cuisine regions |
| GET | /v1/schema/ | OpenAPI schema |

---

## [0.0.0] — 2026-10-23

Initial repository setup (E1–E2): repo structure, Docker environment, CI/CD scaffolding.
