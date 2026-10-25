"""
E43 — Zero-result query observatory.

ZeroResultQuery tracks every search that returned zero results.
Duplicates increment the count rather than creating a new row.
Used by the QA team to identify gaps in the ingredient dictionary
and dish library.

Architecture references:
  Blueprint section 5 — Dictionary: new aliases come from zero-result log.
  Table: zero_result_query(id, raw_input, normalised_input, count,
         last_seen)
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone


class ZeroResultQuery(models.Model):
    """
    A search query that returned zero results.

    raw_input        — the original query string as typed by the user
    normalised_input — lowercased, stripped, sorted tokens
    count            — how many times this query returned zero results
    last_seen        — timestamp of the most recent zero-result hit

    Duplicates are detected by normalised_input (case/order insensitive).
    """

    raw_input = models.TextField(
        help_text="Original query string as sent by the client.",
    )
    normalised_input = models.TextField(
        db_index=True,
        help_text="Lowercased, sorted tokens — used for deduplication.",
    )
    count = models.PositiveIntegerField(
        default=1,
        help_text="Number of times this query returned zero results.",
    )
    last_seen = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="Timestamp of the most recent zero-result hit.",
    )

    class Meta:
        db_table = "zero_result_query"
        ordering = ["-count", "-last_seen"]

    def __str__(self) -> str:
        return f"{self.raw_input!r} (×{self.count})"


def log_zero_result(raw_input: str) -> None:
    """
    Record a zero-result query.

    If a row with the same normalised_input already exists, increment
    its count and update last_seen.  Otherwise create a new row.

    Safe to call on every search miss — uses get_or_create + F() to
    avoid race conditions.
    """
    from django.db.models import F

    normalised = _normalise(raw_input)
    if not normalised:
        return

    obj, created = ZeroResultQuery.objects.get_or_create(
        normalised_input=normalised,
        defaults={"raw_input": raw_input, "count": 1},
    )
    if not created:
        ZeroResultQuery.objects.filter(pk=obj.pk).update(
            count=F("count") + 1,
            last_seen=timezone.now(),
        )


def _normalise(text: str) -> str:
    """
    Lowercase, strip punctuation, sort tokens, rejoin with spaces.
    Returns empty string if input is blank after normalisation.
    """
    import re

    tokens = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return " ".join(sorted(tokens))
