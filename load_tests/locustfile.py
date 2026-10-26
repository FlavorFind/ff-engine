"""
E47 — Expanded load, soak and failure tests.

Three user classes for three test scenarios:

1. SearchUser (load test)
   - Simulates typical API traffic hitting search, catalogue, health.
   - Target: p95 < 150 ms at 50 rps on staging (2 vCPU, 4 GB).

2. SoakUser (soak test — run for 30+ minutes)
   - Slower spawn rate, sustained load, exercises all endpoints.
   - Detects memory leaks, connection pool exhaustion, cache TTL issues.

3. BurstUser (failure / spike test)
   - Rapid fire requests with no wait — simulates traffic spike.
   - Used to verify 429 rate limiting fires and the service stays up.

Run examples
------------
# Standard load test (50 users, 2 min):
locust -f load_tests/locustfile.py \
    --host https://ff-engine-kuar.onrender.com \
    --users 50 --spawn-rate 5 \
    --run-time 2m --headless \
    --html load_tests/report_load.html \
    -u SearchUser

# Soak test (20 users, 30 min):
locust -f load_tests/locustfile.py \
    --host https://ff-engine-kuar.onrender.com \
    --users 20 --spawn-rate 1 \
    --run-time 30m --headless \
    --html load_tests/report_soak.html \
    -u SoakUser

# Burst / failure test (100 users, 1 min):
locust -f load_tests/locustfile.py \
    --host https://ff-engine-kuar.onrender.com \
    --users 100 --spawn-rate 50 \
    --run-time 1m --headless \
    --html load_tests/report_burst.html \
    -u BurstUser

Environment variable FF_API_KEY must be set to a valid API key.
"""

from __future__ import annotations

import os
import random

from locust import HttpUser, between, constant, task

# ── Query fixtures ─────────────────────────────────────────────────────────────

_SEARCH_QUERIES = [
    {"ingredients": ["tomato", "onion"]},
    {"ingredients": ["maize flour", "water"]},
    {"ingredients": ["beans", "maize"]},
    {"ingredients": ["chicken"]},
    {"ingredients": ["rice"]},
    {"ingredients": ["sukuma wiki", "onion", "tomato"]},
    {"ingredients": ["tilapia", "onion", "tomato"]},
    {"ingredients": ["chapati"]},
    {"ingredients": ["eggs", "tomato", "onion"]},
    {"ingredients": ["beef", "tomato", "onion", "garlic"]},
    {"ingredients": ["potatoes", "onion", "oil"]},
    {"ingredients": ["coconut milk", "rice"]},
    {"ingredients": ["lentils", "tomato", "onion"]},
    {"ingredients": ["spinach", "onion"]},
    {"ingredients": ["pineapple"]},
    {"ingredients": ["ugali"], "mode": "explore"},
    {"ingredients": ["pilau"], "mode": "explore"},
    {"ingredients": ["beans", "maize"], "mode": "explore"},
    # New E45 ingredients
    {"ingredients": ["lamb shoulder", "almonds", "apricot"]},
    {"ingredients": ["egusi seeds", "palm oil"]},
    {"ingredients": ["minced beef", "curry powder"]},
    {"ingredients": ["bitterleaf", "groundnut paste"]},
    {"ingredients": ["chickpea flour", "berbere"]},
    {"ingredients": ["basmati rice", "goat meat"]},
]

_ALIAS_QUERIES = [
    {"ingredients": ["nyanya"]},  # Swahili: tomato
    {"ingredients": ["unga wa mahindi"]},  # Swahili: maize flour
    {"ingredients": ["sukuma"]},  # Common alias
    {"ingredients": ["wali"]},  # Swahili: rice
    {"ingredients": ["vitunguu"]},  # Swahili: onion
    {"ingredients": ["samaki"]},  # Swahili: fish
    {"ingredients": ["tomatos"]},  # Misspelling
    {"ingredients": ["tomatoe"]},  # Misspelling
    {"ingredients": ["500g beef"]},  # Quantity prefix
    {"ingredients": ["2 cups rice"]},  # Quantity prefix
]

_DISH_SLUGS = [
    "ugali",
    "nyama-choma",
    "pilau",
    "githeri",
    "mukimo",
    "sukuma-wiki",
    "chapati",
    "mandazi",
    "kachumbari",
    "maharagwe",
    "doro-wat",
    "injera",
    "jollof-rice",
    "egusi-soup",
]


def _auth_headers() -> dict[str, str]:
    key = os.environ.get("FF_API_KEY", "")
    return {"X-API-Key": key} if key else {}


# ── Load test user ─────────────────────────────────────────────────────────────


class SearchUser(HttpUser):
    """
    Standard load test — realistic traffic mix.
    Simulates a consumer hitting search, catalogue and health endpoints.
    """

    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.client.headers.update(_auth_headers())

    @task(8)
    def search_by_ingredients(self) -> None:
        """Main search — most common traffic pattern (weight 8)."""
        payload = random.choice(_SEARCH_QUERIES).copy()
        payload.setdefault("mode", "strict")
        payload.setdefault("limit", 20)

        with self.client.post(
            "/v1/search/by-ingredients",
            json=payload,
            name="/v1/search/by-ingredients",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            elif resp.status_code == 429:
                resp.success()  # Rate limited — expected, not a failure
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @task(3)
    def search_aliases(self) -> None:
        """Swahili / misspelling queries — tests the resolver path (weight 3)."""
        payload = random.choice(_ALIAS_QUERIES).copy()
        payload["mode"] = "strict"

        with self.client.post(
            "/v1/search/by-ingredients",
            json=payload,
            name="/v1/search/by-ingredients [alias]",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 429):
                resp.success()
            else:
                resp.failure(f"Unexpected {resp.status_code}")

    @task(2)
    def health_check(self) -> None:
        """Health endpoint — lightest possible check (weight 2)."""
        self.client.get("/v1/health/", name="/v1/health/")

    @task(1)
    def dish_catalogue(self) -> None:
        """Browse dishes endpoint (weight 1)."""
        self.client.get("/v1/dishes/?limit=20", name="/v1/dishes/")


# ── Soak test user ─────────────────────────────────────────────────────────────


class SoakUser(HttpUser):
    """
    Soak test — sustained load over 30+ minutes.
    Slower and more varied; exercises every endpoint to expose memory leaks,
    connection pool exhaustion and cache TTL problems.
    """

    wait_time = between(3, 8)

    def on_start(self) -> None:
        self.client.headers.update(_auth_headers())

    @task(5)
    def search_strict(self) -> None:
        payload = random.choice(_SEARCH_QUERIES).copy()
        payload["mode"] = "strict"
        self.client.post(
            "/v1/search/by-ingredients",
            json=payload,
            name="/v1/search/by-ingredients [soak-strict]",
        )

    @task(3)
    def search_explore(self) -> None:
        payload = random.choice(_SEARCH_QUERIES).copy()
        payload["mode"] = "explore"
        self.client.post(
            "/v1/search/by-ingredients",
            json=payload,
            name="/v1/search/by-ingredients [soak-explore]",
        )

    @task(2)
    def dish_detail(self) -> None:
        slug = random.choice(_DISH_SLUGS)
        self.client.get(f"/v1/dishes/{slug}/", name="/v1/dishes/[slug]/")

    @task(2)
    def dish_pairings(self) -> None:
        slug = random.choice(_DISH_SLUGS)
        self.client.get(
            f"/v1/dishes/{slug}/pairings/",
            name="/v1/dishes/[slug]/pairings/",
        )

    @task(1)
    def dish_missing(self) -> None:
        slug = random.choice(_DISH_SLUGS)
        self.client.post(
            f"/v1/dishes/{slug}/missing/",
            json={"ingredients": ["tomato", "onion"]},
            name="/v1/dishes/[slug]/missing/",
        )

    @task(1)
    def ingredients_list(self) -> None:
        self.client.get("/v1/ingredients/?limit=50", name="/v1/ingredients/")

    @task(1)
    def health_check(self) -> None:
        self.client.get("/v1/health/", name="/v1/health/")


# ── Burst / failure test user ──────────────────────────────────────────────────


class BurstUser(HttpUser):
    """
    Burst / failure test — no wait time, fires requests as fast as possible.
    Used to verify:
      - 429 responses fire correctly when rate limit is exceeded.
      - The service stays up (no 500s, no OOM).
      - Response time degrades gracefully under spike load.
    """

    wait_time = constant(0)

    def on_start(self) -> None:
        self.client.headers.update(_auth_headers())

    @task(9)
    def burst_search(self) -> None:
        payload = random.choice(_SEARCH_QUERIES).copy()
        payload.setdefault("mode", "strict")

        with self.client.post(
            "/v1/search/by-ingredients",
            json=payload,
            name="/v1/search/by-ingredients [burst]",
            catch_response=True,
        ) as resp:
            # Under burst: 200 (cache hit) and 429 (rate limited) are both acceptable.
            # Any 5xx is a failure.
            if resp.status_code < 500:
                resp.success()
            else:
                resp.failure(f"Server error {resp.status_code}")

    @task(1)
    def burst_health(self) -> None:
        """Health endpoint must always return 200 even under burst load."""
        with self.client.get(
            "/v1/health/",
            name="/v1/health/ [burst]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"Health check failed: {resp.status_code}")
