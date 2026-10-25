# Flavor Find Engine — Build Progress

Tracking all 51 build steps against the two governing documents:

- **Blueprint** — `Flavor_Find_Engine_Blueprint.pdf` (51 steps, 6 iterations)
- **Architecture** — `Flavor_Find_Sprint1_Engine_Architecture.pdf` (full technical spec)

Last updated: 2026-10-25 — E43 complete (Iteration 5 batch 1 done; E40, E41 in progress)

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
| E5 | Dish models: dishes, ingredient links with roles, aliases, steps, regions | Complete core data structure | Integrity rules tested (no duplicate ingredient on one dish) | ✅ |
| E6 | Admin v0 for data entry | Screens to add ingredients and dishes with inline rows | A curator enters a dish unaided | ✅ |
| E7 | Staging server and automatic deployment | A public staging address | Merge to main deploys; one rollback practised | ✅ |
| E8 | Two-factor login and roles for the admin | Curator, reviewer, admin roles with mandatory 2FA | Login without a second factor is impossible | ✅ |
| E9 | Seed the first 100 ingredients and 20 dishes | First real data | Visible in the admin and exportable | ✅ |

---

## Iteration 2: The Data Pipeline (Weeks 3–4)

**Goal:** Fast, safe data entry and the first understanding of words.

| Step | What | Result after | Pass criterion | Status |
|------|------|-------------|---------------|--------|
| E10 | CSV importers for ingredients, aliases, dishes, links | Import tool with dry-run | A bad file reports every problem and saves nothing | ✅ |
| E11 | Exporters and dataset snapshots | Full export of the library | Export then import reproduces identical data | ✅ |
| E12 | Validators (integrity rules) | 20+ automatic checks on save and import | Each rule has a test that breaks it on purpose | ✅ |
| E13 | Duplicate detector | Warnings for similar names | Catches deliberately planted duplicates | ✅ |
| E14 | QA report and dashboard | Counts and gap lists | Shows missing Swahili names, aliases, orphans | ✅ |
| E15 | The cleaner (normaliser) | Text clean-up step | 100 sample inputs give the expected clean words | ✅ |
| E16 | The resolver with fuzzy match and ambiguity | Words become ingredient IDs or options | Correct on 100 test words, including Swahili and misspellings | ✅ |
| E17 | Seed to 400 ingredients and 80 dishes | Bigger library | QA report has no critical issues | ✅ |
| E18 | Golden set v0 (20 cases) and runner | First regression guard | Runs on every pull request | ✅ |

---

## Iteration 3: Matching v1 (Weeks 5–6)

**Goal:** The brain — search that is exact, ranked and explainable.

| Step | What | Result after | Pass criterion | Status |
|------|------|-------------|---------------|--------|
| E19 | Search arrays and indexes on dishes | Fast shortlist capability | Arrays rebuild automatically on every dish change (tested) | ✅ |
| E20 | Staples handling | Configurable staples | Water, salt and oil never block a match | ✅ |
| E21 | The Finder (candidate retrieval) | Shortlist step | Returns only overlapping dishes; benchmarked | ✅ |
| E22 | The Judge (tiers) | Exact, can make, almost | Property tests: adding an ingredient never removes a can-make dish | ✅ |
| E23 | The Ranker (scoring) | Weighted scoring from configuration | Deterministic; ties broken by name | ✅ |
| E24 | The Explainer | Matched, missing, unused, breakdown on every result | Each result carries all reasons | ✅ |
| E25 | Search endpoint with strict, explore, filters and exclusions | First real API | Contract tests pass | ✅ |
| E26 | Caching by dataset version | Faster repeat searches | Cache hit measured; clears on release | ✅ |
| E27 | Seed to 500 ingredients, 150 dishes; golden set to 60 | Growing data and tests | Golden set at 90% or better | ✅ |

---

## Iteration 4: Advisor and Safety (Weeks 7–8)

**Goal:** Pairings, substitutions, diets and allergens.

| Step | What | Result after | Pass criterion | Status |
|------|------|-------------|---------------|--------|
| E28 | Pairing and substitution models, admin and importers | Advisor data structures | Entry and import work with checks | ✅ |
| E29 | Pairing and substitution endpoints | Advisor API | Contract tests pass | ✅ |
| E30 | Missing-ingredients endpoint | 'What do I still need?' | Correct on 20 sample dishes | ✅ |
| E31 | Allergen links and dietary derivation rules | Safety Filter | Each rule tested; allergen exclusion beats everything | ✅ |
| E32 | Manual overrides with reason and audit | Controlled exceptions | Every override appears in the audit log | ✅ |
| E33 | Seed 80 pairings, 100 substitutions; 650 ingredients, 220 dishes | Richer library | QA report clean | ✅ |
| E34 | Golden set to 100 cases | Broader regression guard | At least 93% passing | ✅ |
| E35 | Regions and filters in the catalogue API | Browse by region, meal type, tag | Filter tests pass | ✅ |

---

## Iteration 5: Platform Features (Weeks 9–10)

**Goal:** Everything needed to let other products depend on the engine safely.

| Step | What | Result after | Pass criterion | Status |
|------|------|-------------|---------------|--------|
| E36 | API clients, keys and scopes | The gatekeeper | Keys shown once; a revoked key stops within a minute | ✅ |
| E37 | Rate limits and quotas | Per-key protection | Load test shows correct 'slow down' answers | ✅ |
| E38 | Usage metering and daily summaries | Usage records per client | Dashboard lists calls per client | ✅ |
| E39 | Nutrition and cost estimates | The Estimator | Flagged as estimates; reviewer spot checks | ✅ |
| E40 | Performance tuning | Faster queries and cache warming | Search p95 target met on staging | 🔄 |
| E41 | The internal test console | A tool to try queries and weights | The team compares two weight settings side by side | 🔄 |
| E42 | OpenAPI docs and generated clients | Published API documentation | A TypeScript client compiles against it | ✅ |
| E43 | The Observatory: dashboards, alerts, zero-result log | Operational visibility | An alert fires correctly in a drill | ✅ |
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


## Current State (E43 complete — Iteration 5 batch 1 done)

### What is on `main` right now

**E1–E9** — Foundations ✅
**E10–E18** — Data pipeline ✅
**E19–E27** — Matching v1 ✅
**E28–E35** — Advisor and safety ✅
**E36** — API clients, keys and scopes ✅
**E37** — Per-key rate limiting (`ApiKeyRateThrottle`, Redis-backed, per-key UUID bucket) ✅
**E38** — Usage metering (`RequestLog`, `UsageRecord`, `MeteringMiddleware`, `rollup_daily_usage`) ✅
**E39** — Nutrition facts endpoint (`NutritionFact` model, `GET /v1/dishes/{slug}/nutrition/`, seed CSV with 50 ingredients) ✅
**E42** — OpenAPI `@extend_schema` on all 7 views + `schema-validation` CI job + `APIKeyAuthentication` extension ✅
**E43** — Zero-result observatory (`ZeroResultQuery`, `log_zero_result`, `qa_zero_results` management command) ✅

### In progress (batch 2)
- **E40** — Performance tuning (GIN indexes, p95 load test, cache warming)
- **E41** — Internal test console (React app)

### Skipped by decision
- **E44** — Data expansion (800 ingredients, 280 dishes) — deferred, no code impact

---

## Architecture Compliance Checklist

### Four-layer architecture (Architecture section 4)

| Layer | Status |
|-------|--------|
| API layer (DRF views/routers) | ✅ |
| Service layer | ✅ search, pairings, substitutions, dietary, metering |
| Domain/Data access layer | ✅ all models built |
| Storage (PostgreSQL + Redis) | ✅ |

### Security baseline (Architecture section 14)

| Item | Status |
|------|--------|
| Branch protection (PR required, CI required, no force push) | ✅ |
| CODEOWNERS on sensitive paths | ✅ |
| Secret scanning + push protection | ✅ |
| Signed commits required | ✅ |
| Pre-commit hooks (ruff, gitleaks) | ✅ |
| 2FA on every human account | ✅ |
| 2FA on admin application | ✅ E8 |
| API key lifecycle (hashed, scoped, revocable) | ✅ E36 |
| Rate limits + metering | ✅ E37, E38 |

### CI pipelines (Architecture section 12)

| Pipeline | Status |
|----------|--------|
| PR pipeline — lint + tests + migration check | ✅ |
| Schema validation (spectacular --validate) | ✅ E42 |
| Main pipeline — build + deploy staging | ✅ |
| Release pipeline | ✅ |
| Nightly / weekly / data pipelines | ✅ skeletons |

---

## Data targets at v1.0 (Architecture section 2)

| Item | Target | Current |
|------|--------|---------|
| Dishes | 300 reviewed, 100 verified | ~219 seeded |
| Ingredients | 800+ with EN + SW names | ~638 seeded |
| Aliases | 1,500+ | present |
| Pairings | 150+ | ~80 seeded |
| Substitutions | 200+ | ~100 seeded |
| Golden set | 200 cases at 95%+ | 100 cases |
