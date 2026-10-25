"""
E26 — Search caching helpers.

Provides dataset-version-aware caching for the search endpoint.
Cache keys incorporate the dataset version and all request parameters
that affect the output, so a new dataset release naturally produces
cache misses.  clear_search_cache() actively evicts stale entries.

Architecture section 7: "Redis for hot searches, keyed by input and dataset version."
Blueprint E26: "Caching by dataset version — Faster repeat searches."
"""

from __future__ import annotations

import hashlib
import json
import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CACHE_PREFIX = "ffengine:search:v1:"
CACHE_TTL = 300  # seconds — matches CACHES["default"]["TIMEOUT"]


def get_dataset_version() -> str:
    """
    Return the current dataset version.

    Checks the latest DatasetRelease in the DB; falls back to
    settings.DATASET_VERSION if no releases exist or the DB is unavailable.
    """
    try:
        from apps.curation.models import DatasetRelease

        latest = DatasetRelease.objects.order_by("-created_at").first()
        if latest:
            return latest.version
    except Exception:
        logger.debug("get_dataset_version: DB lookup failed, using settings fallback")
    return getattr(settings, "DATASET_VERSION", "0.0.0")


def build_cache_key(
    dataset_version: str,
    ingredients: list[str],
    exclude: list[str],
    mode: str,
    meal_type: str | None,
    course: str | None,
    lang: str,
    limit: int,
    diet: list[str] | None = None,
) -> str:
    """
    Build a deterministic cache key from all request parameters that affect
    the search output.

    Ingredients and excludes are sorted so that request parameter order
    does not change the key.
    """
    parts = [
        f"v={dataset_version}",
        f"ing={','.join(sorted(ingredients))}",
        f"exc={','.join(sorted(exclude))}",
        f"mode={mode}",
        f"mt={meal_type}",
        f"course={course}",
        f"lang={lang}",
        f"limit={limit}",
        f"diet={','.join(sorted(diet or []))}",
    ]
    key_body = "|".join(parts)
    key_hash = hashlib.sha256(key_body.encode()).hexdigest()[:32]
    return f"{CACHE_PREFIX}{dataset_version}:{key_hash}"


def get_cached_result(key: str) -> dict | None:
    """Return cached search result (payload + etag), or None on miss."""
    return cache.get(key)


def set_cached_result(key: str, payload: dict, etag: str, dataset_version: str) -> None:
    """Store search result payload and ETag in cache, tracking the key for invalidation."""
    cache.set(key, {"payload": payload, "etag": etag}, CACHE_TTL)
    _track_key(key, dataset_version)


def clear_search_cache(dataset_version: str | None = None) -> None:
    """
    Invalidate cached search results.

    If *dataset_version* is given, only clear caches for that version.
    Otherwise, clear all search caches across all versions.
    """
    if dataset_version:
        _clear_version(dataset_version)
    else:
        versions_key = f"{CACHE_PREFIX}_versions"
        versions = cache.get(versions_key, set())
        for version in list(versions):
            _clear_version(version)
        cache.delete(versions_key)
        logger.info("clear_search_cache: cleared all versions")


def compute_etag(payload: dict) -> str:
    """Compute an ETag from the search response payload."""
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()[:32]


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers — key tracking for targeted invalidation
# ──────────────────────────────────────────────────────────────────────────────


def _track_key(key: str, dataset_version: str) -> None:
    """Track a cache key so it can be invalidated later."""
    index_key = f"{CACHE_PREFIX}_keys:{dataset_version}"
    keys = cache.get(index_key, set())
    keys.add(key)
    cache.set(index_key, keys, CACHE_TTL + 60)

    versions_key = f"{CACHE_PREFIX}_versions"
    versions = cache.get(versions_key, set())
    versions.add(dataset_version)
    cache.set(versions_key, versions, None)  # no expiry


def _clear_version(dataset_version: str) -> None:
    """Delete all cached search keys for a specific dataset version."""
    index_key = f"{CACHE_PREFIX}_keys:{dataset_version}"
    keys = cache.get(index_key, set())
    for key in keys:
        cache.delete(key)
    cache.delete(index_key)
    logger.info(
        "clear_search_cache: cleared %d keys for version %s",
        len(keys),
        dataset_version,
    )
