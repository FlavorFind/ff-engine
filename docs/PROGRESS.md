# Flavor Find Engine — Build Progress

Tracking all 51 build steps against the two governing documents:

- **Blueprint** — `Flavor_Find_Engine_Blueprint.pdf` (51 steps, 6 iterations)
- **Architecture** — `Flavor_Find_Sprint1_Engine_Architecture.pdf` (full technical spec)

Last updated: 2026-10-23 — E4 complete

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Done — merged to main, CI green |
| 🔄 | In progress |
| ⬜ | Not started |

---

## Iteration 1: Foundations (Weeks 1–2)

**Goal:** A deployed skeleton, the first models, protected admin, and the first real data.

| Step | What | Result after | Pass criterion | Status |
|------|------|-------------|---------------|--------|
| E1 | Create the repository from template and protect main | ff-engine repo with CI skeleton, rules and templates | A first pull request must pass checks to merge | ✅ |
| E2 | Build the local environment with containers | One-command start (app, database, cache, worker) | A new developer is running in under 15 minutes | ✅ |
| E3 | Create the Django project with split settings | Running service with health and version pages | Health check green in CI | ✅ |
| E4 | Core models: categories, ingredients, aliases, units, sources, status | Database tables via migrations | Migrations apply and reverse cleanly | ✅ |
| E5 | Dish models: dishes, ingredient links with roles, aliases, steps, regions | Complete core data structure | Integrity rules tested (no duplicate ingredient on one dish) | ⬜ |
| E6 | Admin v0 for data entry | Screens to add ingredients and dishes with inline rows | A curator enters a dish unaided | ⬜ |
| E7 | Staging server and automatic deployment | A public staging address | Merge to main deploys; one rollback practised | ⬜ |
| E8 | Two-factor login and roles for the admin | Curator, reviewer, admin roles with mandatory 2FA | Login without a second factor is impossible | ⬜ |
| E9 | Seed the first 100 ingredients and 20 dishes | First real data | Visible in the admin and exportable | ⬜ |

---

## Iteration 2: The Data Pipeline (Weeks 3–4)

**Goal:** Fast, safe data entry and the first understanding of words.

| Step | What | Result after | Pass criterion | Status |
|------|------|-------------|---------------|--------|
| E10 | CSV importers for ingredients, aliases, dishes, links | Import tool with dry-run | A bad file reports every problem and saves nothing | ⬜ |
| E11 | Exporters and dataset snapshots | Full export of the library | Export then import reproduces identical data | ⬜ |
| E12 | Validators (integrity rules) | 20+ automatic checks on save and import | Each rule has a test that breaks it on purpose | ⬜ |
| E13 | Duplicate detector | Warnings for similar names | Catches deliberately planted duplicates | ⬜ |
| E14 | QA report and dashboard | Counts and gap lists | Shows missing Swahili names, aliases, orphans | ⬜ |
| E15 | The cleaner (normaliser) | Text clean-up step | 100 sample inputs give the expected clean words | ⬜ |
| E16 | The resolver with fuzzy match and ambiguity | Words become ingredient IDs or options | Correct on 100 test words, including Swahili and misspellings | ⬜ |
| E17 | Seed to 400 ingredients and 80 dishes | Bigger library | QA report has no critical issues | ⬜ |
| E18 | Golden set v0 (20 cases) and runner | First regression guard | Runs on every pull request | ⬜ |

---

## Iteration 3: Matching v1 (Weeks 5–6)

**Goal:** The brain — search that is exact, ranked and explainable.

| Step | What | Result after | Pass criterion | Status |
|------|------|-------------|---------------|--------|
| E19 | Search arrays and indexes on dishes | Fast shortlist capability | Arrays rebuild automatically on every dish change (tested) | ⬜ |
| E20 | Staples handling | Configurable staples | Water, salt and oil never block a match | ⬜ |
| E21 | The Finder (candidate retrieval) | Shortlist step | Returns only overlapping dishes; benchmarked | ⬜ |
| E22 | The Judge (tiers) | Exact, can make, almost | Property tests: adding an ingredient never removes a can-make dish | ⬜ |
| E23 | The Ranker (scoring) | Weighted scoring from configuration | Deterministic; ties broken by name | ⬜ |
| E24 | The Explainer | Matched, missing, unused, breakdown on every result | Each result carries all reasons | ⬜ |
| E25 | Search endpoint with strict, explore, filters and exclusions | First real API | Contract tests pass | ⬜ |
| E26 | Caching by dataset version | Faster repeat searches | Cache hit measured; clears on release | ⬜ |
| E27 | Seed to 500 ingredients, 150 dishes; golden set to 60 | Growing data and tests | Golden set at 90% or better | ⬜ |

---

## Iteration 4: Advisor and Safety (Weeks 7–8)

**Goal:** Pairings, substitutions, diets and allergens.

| Step | What | Result after | Pass criterion | Status |
|------|------|-------------|---------------|--------|
| E28 | Pairing and substitution models, admin and importers | Advisor data structures | Entry and import work with checks | ⬜ |
| E29 | Pairing and substitution endpoints | Advisor API | Contract tests pass | ⬜ |
| E30 | Missing-ingredients endpoint | 'What do I still need?' | Correct on 20 sample dishes | ⬜ |
| E31 | Allergen links and dietary derivation rules | Safety Filter | Each rule tested; allergen exclusion beats everything | ⬜ |
| E32 | Manual overrides with reason and audit | Controlled exceptions | Every override appears in the audit log | ⬜ |
| E33 | Seed 80 pairings, 100 substitutions; 650 ingredients, 220 dishes | Richer library | QA report clean | ⬜ |
| E34 | Golden set to 100 cases | Broader regression guard | At least 93% passing | ⬜ |
| E35 | Regions and filters in the catalogue API | Browse by region, meal type, tag | Filter tests pass | ⬜ |

---

## Iteration 5: Platform Features (Weeks 9–10)

**Goal:** Everything needed to let other products depend on the engine safely.

| Step | What | Result after | Pass criterion | Status |
|------|------|-------------|---------------|--------|
| E36 | API clients, keys and scopes | The gatekeeper | Keys shown once; a revoked key stops within a minute | ⬜ |
| E37 | Rate limits and quotas | Per-key protection | Load test shows correct 'slow down' answers | ⬜ |
| E38 | Usage metering and daily summaries | Usage records per client | Dashboard lists calls per client | ⬜ |
| E39 | Nutrition and cost estimates | The Estimator | Flagged as estimates; reviewer spot checks | ⬜ |
| E40 | Performance tuning | Faster queries and cache warming | Search p95 target met on staging | ⬜ |
| E41 | The internal test console | A tool to try queries and weights | The team compares two weight settings side by side | ⬜ |
| E42 | OpenAPI docs and generated clients | Published API documentation | A TypeScript client compiles against it | ⬜ |
| E43 | The Observatory: dashboards, alerts, zero-result log | Operational visibility | An alert fires correctly in a drill | ⬜ |
| E44 | Seed to 800 ingredients and 280 dishes; golden set to 150 | Near-complete library | Golden set at 94% or better | ⬜ |

---

## Iteration 6: Hardening and Release (Weeks 11–12)

**Goal:** The final data, proof under pressure, and a safe launch.

| Step | What | Result after | Pass criterion | Status |
|------|------|-------------|---------------|--------|
| E45 | Finish seeding: 300 dishes, 800+ ingredients, 150 pairings, 200 substitutions | Complete v1 dataset | Reviewer sign-off on every entry | ⬜ |
| E46 | Golden set to 200 and final tuning | Final quality bar | At least 95% passing; all strict-mode rules pass | ⬜ |
| E47 | Load, soak and failure tests | Proof of resilience | Targets met; failures recover automatically | ⬜ |
| E48 | Security review and external penetration test fixes | Hardened engine | No open high or critical findings | ⬜ |
| E49 | Backup restore drill and rollback drill | Disaster readiness | Restore and rollback completed within target times | ⬜ |
| E50 | Final docs, runbooks and data style guide | Handover pack | Another developer completes a task using docs only | ⬜ |
| E51 | Release dataset 1.0.0 and engine v1.0.0 to production | The engine is live | Consumers integrate with their own keys; Stage 2 begins | ⬜ |

---

## Current State (E4 complete)

### What is on `main` right now

**E1 — Repository setup** (Architecture section 10.2)
- `README.md`, `LICENSE`, `SECURITY.md`, `CONTRIBUTING.md`
- `.github/CODEOWNERS`, `.github/pull_request_template.md`
- `.github/ISSUE_TEMPLATE/` — bug_report, feature_request, data_issue
- `.github/workflows/` — ci.yml, main.yml, release.yml, nightly.yml, weekly.yml, data.yml, deploy-staging.yml, deploy-prod.yml
- `.github/dependabot.yml`, `.pre-commit-config.yaml`
- `.gitignore`, `.editorconfig`, `.well-known/security.txt`
- `docs/adr/0001-record-architecture-decisions.md`
- `pyproject.toml` — ruff, mypy, pytest, coverage config
- `Makefile` — make up, make test, make lint, make migrate, make seed

**E2 — Docker environment** (Architecture section 9)
- `docker/Dockerfile` — python:3.12-slim, non-root user, dev deps
- `docker/docker-compose.yml` — web, db (postgres:16), redis:7, worker, beat
- `docker/entrypoint.sh`
- `requirements/base.txt`, `requirements/dev.txt`, `requirements/prod.txt`
- `.env.example`

**E3 — Django project skeleton** (Blueprint E3 + Architecture sections 4, 7, 15)
- `manage.py`
- `config/settings/base.py` — all settings, Sentry, structured logging, DRF, CORS, Celery, Redis
- `config/settings/dev.py` — DEBUG=True, debug_toolbar
- `config/settings/test.py` — in-memory cache, eager Celery, fast hasher
- `config/settings/prod.py` — security hardening, HSTS, JSON logging
- `config/urls.py`, `config/wsgi.py`, `config/asgi.py`, `config/celery.py`
- All 12 apps: `core`, `ingredients`, `dishes`, `regions`, `dietary`, `pairings`, `substitutions`, `nutrition`, `search`, `curation`, `clients`, `api`
- `apps/core/models.py` — `TimeStampedModel` (UUID pk, timestamps), `StatusChoices`, `StatusMixin`
- `apps/core/middleware.py` — `RequestIDMiddleware` (X-Request-ID header)
- `apps/core/logging.py` — `JSONFormatter` (structured JSON logs)
- `apps/core/pagination.py` — `CursorPagination`
- `apps/core/exceptions.py` — `custom_exception_handler` (consistent error shape)
- `apps/api/views.py` — `GET /v1/health` + `GET /v1/meta/version` (both public)
- `apps/api/tests/test_health.py` — 3 tests: health 200, version fields, no auth required
- `apps/clients/authentication.py` — `APIKeyAuthentication` placeholder
- `conftest.py` — pytest-django root config
- CI: lint (ruff check + format) + tests (pytest with postgres:16 + redis:7) — **both green**

**E4 — Core ingredient models** (Blueprint E4 + Architecture section 5)
- `apps/ingredients/models.py` — `IngredientCategory`, `Unit`, `Allergen`, `Ingredient`, `IngredientAllergen`, `IngredientAlias`
- `apps/curation/models.py` — `Source`, `ChangeLog` (append-only), `DatasetRelease`
- `apps/ingredients/migrations/0001_initial.py` + `apps/curation/migrations/0001_initial.py`
- `apps/ingredients/admin.py` + `apps/curation/admin.py`
- 18 model tests + migration column-spec tests — **CI green**

### What is NOT yet built (next steps)

- **E5** — `dishes` app models: `Dish`, `DishIngredient` (with roles), `DishStep`, `Region`, `DishRegion` + migrations
- **E6** — Django admin v0: inline ingredient rows, bulk status actions, search by alias
- **E7** — Staging server + automatic deployment pipeline
- **E8** — 2FA login + curator/reviewer/admin roles in the admin
- **E9** — Seed first 100 ingredients + 20 dishes

---

## Architecture Compliance Checklist

### Four-layer architecture (Architecture section 4)

| Layer | Status |
|-------|--------|
| API layer (DRF views/routers) | ✅ Skeleton in `apps/api/` |
| Service layer | ⬜ Not yet — added per step (E15 normaliser, E21 finder, etc.) |
| Domain/Data access layer | ⬜ Not yet — models land in E4/E5 |
| Storage (PostgreSQL + Redis) | ✅ Configured in settings + docker-compose |

### Security baseline (Architecture section 14)

| Item | Status |
|------|--------|
| Branch protection (PR required, CI required, no force push) | ✅ |
| CODEOWNERS on sensitive paths | ✅ |
| Secret scanning + push protection | ✅ (GitHub org setting) |
| Signed commits required | ✅ (branch ruleset) |
| Pre-commit hooks (ruff, gitleaks) | ✅ `.pre-commit-config.yaml` |
| 2FA on every human account | ✅ (GitHub org enforcement) |
| 2FA on admin application | ⬜ E8 |
| API key lifecycle (hashed, scoped, revocable) | ⬜ E36 |

### CI pipelines (Architecture section 12)

| Pipeline | Status |
|----------|--------|
| PR pipeline — lint + tests | ✅ `.github/workflows/ci.yml` |
| Main pipeline — build + deploy staging | ✅ `.github/workflows/main.yml` (skeleton) |
| Release pipeline | ✅ `.github/workflows/release.yml` (skeleton) |
| Nightly — golden set, DAST, scans | ✅ `.github/workflows/nightly.yml` (skeleton) |
| Weekly — load test, restore drill | ✅ `.github/workflows/weekly.yml` (skeleton) |
| Data pipeline | ✅ `.github/workflows/data.yml` (skeleton) |

> Note: main/release/nightly/weekly/data pipelines are skeletons. Full jobs are added per iteration as the spec describes.

---

## Data targets at v1.0 (Architecture section 2)

| Item | Target | Current |
|------|--------|---------|
| Dishes | 300 reviewed, 100 verified | 0 |
| Ingredients | 800+ with EN + SW names | 0 |
| Aliases | 1,500+ | 0 |
| Pairings | 150+ | 0 |
| Substitutions | 200+ | 0 |
| Golden set | 200 cases at 95%+ | 0 |
