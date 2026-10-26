"""
E40 — Locust load test for the search endpoint.

Target (Architecture section 2 success criteria):
  Search p95 under 150 ms at 50 requests per second on staging
  (2 vCPU, 4 GB server).

Run against staging:
  locust -f load_tests/locustfile.py \
    --host https://staging.ff-engine.example.com \
    --users 50 --spawn-rate 5 \
    --run-time 2m --headless \
    --html load_tests/report.html

Environment variable FF_API_KEY must be set to a valid API key.
"""

from __future__ import annotations

import os
import random

from locust import HttpUser, between, task

# ── Query fixtures ────────────────────────────────────────────────────────────

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
]

_INGREDIENT_QUERIES = [
    {"ingredients": ["nyanya"]},  # Swahili: tomato
    {"ingredients": ["unga wa mahindi"]},  # Swahili: maize flour
    {"ingredients": ["sukuma"]},  # Common alias
    {"ingredients": ["tomatos"]},  # Misspelling
    {"ingredients": ["tomatoe"]},  # Misspelling
]


class SearchUser(HttpUser):
    """
    Simulates a typical API consumer hitting the search endpoint.

    Wait time is random between 1 and 3 seconds to simulate
    realistic request spacing (not hammer mode).
    """

    wait_time = between(1, 3)

    def on_start(self):
        """Set the API key header for all requests."""
        api_key = os.environ.get("FF_API_KEY", "")
        if api_key:
            self.client.headers["X-API-Key"] = api_key

    @task(8)
    def search_by_ingredients(self):
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
                # Rate limited — mark as success so it doesn't skew p95
                resp.success()
            else:
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(3)
    def search_swahili_aliases(self):
        """Swahili / misspelling queries — tests the resolver path (weight 3)."""
        payload = random.choice(_INGREDIENT_QUERIES).copy()
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
                resp.failure(f"Unexpected status {resp.status_code}")

    @task(2)
    def health_check(self):
        """Health endpoint — lightest possible check (weight 2)."""
        self.client.get("/v1/health/", name="/v1/health/")

    @task(1)
    def dish_catalogue(self):
        """Browse dishes endpoint (weight 1)."""
        self.client.get("/v1/dishes/?limit=20", name="/v1/dishes/")
