# ff-engine

The Flavor Find isolated recipe engine.

A standalone Django service that knows Kenyan and East African food. It powers ingredient-based recipe matching, pairings, substitutions, dietary filtering and a public REST API. Every other Flavor Find product (consumer app, hotel platform, AI service) talks to this engine through the API.

---

## Status

Sprint 1 — in active development. See the [build roadmap](../ff-docs) for the full plan.

---

## Quick start

```bash
# 1. Clone and enter the repo
git clone https://github.com/FlavorFind/ff-engine.git
cd ff-engine

# 2. Copy environment file
cp .env.example .env

# 3. Start all services
make up

# 4. Run migrations and seed data
make migrate
make seed

# 5. Run tests
make test
```

> Full setup guide: `docs/architecture.md`

---

## Tech stack

- Python 3.12, Django (latest LTS), Django REST Framework
- PostgreSQL 16 (GIN + trigram indexes)
- Redis 7 (cache, rate limits, queues)
- Celery + Celery Beat (background jobs, dataset releases)
- Docker + docker-compose (local and production)
- Caddy (TLS and routing)
- pytest, factory_boy, Hypothesis, Locust

---

## Repository layout

```
ff-engine/
├── apps/
│   ├── core/          # Base models, pagination, errors, permissions
│   ├── ingredients/   # Ingredient taxonomy, aliases, allergens
│   ├── dishes/        # Dishes, ingredient roles, steps
│   ├── regions/       # Counties, coastal, cuisine groups
│   ├── dietary/       # Dietary and allergen tags
│   ├── pairings/      # Dish pairings with strength
│   ├── substitutions/ # Ingredient substitutions
│   ├── nutrition/     # Nutrition and cost estimates
│   ├── search/        # The matching engine
│   ├── curation/      # Data pipeline, importers, workflow
│   ├── clients/       # API keys, rate limits, metering
│   └── api/           # Versioned routers and OpenAPI schema
├── config/            # Django settings (base, dev, test, prod)
├── data/              # Seed CSVs and golden query set
├── docker/            # Dockerfile, docker-compose, entrypoint
├── docs/              # Architecture, API docs, runbook
├── requirements/      # base.txt, dev.txt, prod.txt
└── scripts/           # Load tests, backup, restore drill
```

---

## Development rules

- **Branch:** short-lived feature branches → PR into `main` → squash merge
- **CI:** every PR must pass lint, type checks and tests before merge
- **Secrets:** never committed; use `.env` locally and a secret manager in production
- **Migrations:** always reversible; reviewed like code
- **Done means:** reviewed, tested, deployed to staging, demoed

---

## Licence

Confidential — Flavor Find. All rights reserved.
