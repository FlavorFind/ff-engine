"""
E36 — API clients, keys and scopes.

Architecture (Sprint 1 doc, section 5):
  api_client / api_key
    client(id, name, type, active)
    key(id, client_id, prefix, hashed_key, scopes[], rate_limit,
        created, revoked_at, last_used)

Design rules:
  - Keys are shown ONCE at creation, then stored only as SHA-256 hashes.
  - Each key carries a list of scopes that limit what it can call.
  - A revoked key (revoked_at is not null) is rejected immediately.
  - prefix (first 8 chars) is stored in plain text for fast DB lookup
    without scanning every row.
"""

import uuid

from django.db import models
from django.utils import timezone


class ApiClient(models.Model):
    """
    A registered API consumer — the Flavor Find backend, hotel platform,
    AI service, or an external partner.
    """

    class ClientType(models.TextChoices):
        INTERNAL = "internal", "Internal (Flavor Find product)"
        PARTNER = "partner", "External partner"
        AI = "ai", "AI service"
        TEST = "test", "Test / development"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    type = models.CharField(max_length=20, choices=ClientType.choices, default=ClientType.INTERNAL)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "api_client"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.get_type_display()})"


class ApiKey(models.Model):
    """
    An API key belonging to one ApiClient.

    The raw key is NEVER stored. Only the SHA-256 hash is persisted.
    The prefix (first 8 characters of the raw key) is stored in plain
    text so that incoming requests can be looked up without a full-table
    hash scan.

    Scopes follow the pattern  action:resource, e.g.:
        read:search
        read:catalog
        internal:curation
    """

    SCOPE_READ_SEARCH = "read:search"
    SCOPE_READ_CATALOG = "read:catalog"
    SCOPE_INTERNAL_CURATION = "internal:curation"

    ALL_SCOPES = [SCOPE_READ_SEARCH, SCOPE_READ_CATALOG, SCOPE_INTERNAL_CURATION]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(ApiClient, on_delete=models.CASCADE, related_name="keys")
    # First 8 characters of the raw key — stored for fast prefix lookup
    prefix = models.CharField(max_length=8, db_index=True)
    # SHA-256 of the full raw key
    hashed_key = models.CharField(max_length=64)
    # List of allowed scopes
    scopes = models.JSONField(default=list)
    # Requests per minute (0 = unlimited)
    rate_limit = models.PositiveIntegerField(default=60)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "api_key"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["prefix", "hashed_key"], name="unique_prefix_hash"),
        ]

    def __str__(self) -> str:
        status = "revoked" if self.is_revoked else "active"
        return f"{self.prefix}****** ({self.client.name}, {status})"

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at is not None

    def revoke(self) -> None:
        """Revoke this key immediately."""
        self.revoked_at = timezone.now()
        self.save(update_fields=["revoked_at"])

    def has_scope(self, scope: str) -> bool:
        """Return True if this key grants the given scope."""
        return scope in self.scopes

    def touch(self) -> None:
        """Update last_used_at without triggering full model save overhead."""
        ApiKey.objects.filter(pk=self.pk).update(last_used_at=timezone.now())


class RequestLog(models.Model):
    """
    Per-request log entry written after every API call.
    Rolled up into UsageRecord daily by the Celery beat task.
    """

    client = models.ForeignKey(
        ApiClient,
        on_delete=models.CASCADE,
        related_name="request_logs",
    )
    endpoint = models.CharField(max_length=200, db_index=True)
    status_code = models.PositiveSmallIntegerField()
    response_ms = models.PositiveIntegerField(help_text="Response time in milliseconds.")
    logged_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "request_log"
        indexes = [
            models.Index(
                fields=["client", "endpoint", "logged_at"],
                name="request_log_client_endpoint_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.client.name} → {self.endpoint} [{self.status_code}]"


class UsageRecord(models.Model):
    """
    Daily rollup of API usage per client and endpoint.
    Populated by the rollup_daily_usage Celery task.
    """

    client = models.ForeignKey(
        ApiClient,
        on_delete=models.CASCADE,
        related_name="usage_records",
    )
    endpoint = models.CharField(max_length=200, db_index=True)
    date = models.DateField(db_index=True)
    calls = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0, help_text="4xx + 5xx responses.")
    p95_ms = models.PositiveIntegerField(
        null=True, blank=True, help_text="95th percentile response time in ms."
    )

    class Meta:
        db_table = "usage_record"
        ordering = ["-date", "client", "endpoint"]
        constraints = [
            models.UniqueConstraint(
                fields=["client", "endpoint", "date"],
                name="unique_usage_per_day",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.client.name} | {self.endpoint} | {self.date} | {self.calls} calls"
