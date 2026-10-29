"""
E37 — Per-key rate limiting.

Reads the rate_limit field from the authenticated ApiKey and enforces
a sliding-window limit using DRF's cache-backed throttle infrastructure.

rate_limit is stored as requests per minute (rpm).
  0  → unlimited
  60 → 60 req/min (default)

The throttle key is the API key's UUID so limits are per-key, not per-IP.
"""

from __future__ import annotations

from rest_framework.throttling import SimpleRateThrottle


class ApiKeyRateThrottle(SimpleRateThrottle):
    """
    DRF throttle that enforces the per-key rate_limit stored on ApiKey.

    Works with DRF's cache backend (Redis in production).
    Rate is expressed as requests-per-minute.
    """

    scope = "api_key"

    def get_cache_key(self, request, view):
        # Only throttle authenticated API key requests
        api_key = getattr(request, "auth", None)
        if api_key is None:
            return None

        # rate_limit == 0 means unlimited — skip throttling
        if getattr(api_key, "rate_limit", 0) == 0:
            return None

        return f"throttle_apikey_{api_key.pk}"

    def get_rate(self):
        # Rate is determined per-request from the key, not from settings.
        # Return a sentinel — the actual rate is set in allow_request.
        return None

    def allow_request(self, request, view):
        api_key = getattr(request, "auth", None)
        if api_key is None:
            return True

        rpm = getattr(api_key, "rate_limit", 0)
        if rpm == 0:
            return True

        # Override the rate dynamically from the key's rate_limit field.
        self.rate = f"{rpm}/min"
        self.num_requests, self.duration = self.parse_rate(self.rate)
        try:
            return super().allow_request(request, view)
        except Exception:
            # Redis unavailable (e.g. no Redis on free-tier hosting).
            # Fail open: allow the request rather than returning a 500.
            import logging
            logging.getLogger(__name__).warning(
                "Rate-limit cache unavailable — allowing request without throttling"
            )
            return True
