"""
Curation signals.

When a new DatasetRelease is created, clear all cached search results
for previous dataset versions so that subsequent searches recompute
against the freshly released data.

Blueprint E26: "clears on release".
"""

from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.curation.models import DatasetRelease

logger = logging.getLogger(__name__)


@receiver(post_save, sender=DatasetRelease)
def clear_search_cache_on_release(sender, instance, created, **kwargs):
    """Clear the entire search cache whenever a new release is saved."""
    from apps.search.cache import clear_search_cache

    clear_search_cache()
    logger.info(
        "clear_search_cache_on_release: cleared search caches (release=%s, created=%s)",
        instance.version,
        created,
    )
