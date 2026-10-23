"""
Curation models — Source, ChangeLog, DatasetRelease.

Architecture section 5 (Data Model):
  source       id, kind, title, citation, permission_status, contributor
  change_log   id, object_type, object_id, action, diff (JSON), actor, created_at
  dataset_release  id, version, notes, counts (JSON), created_at
"""

from django.contrib.auth import get_user_model
from django.db import models

from apps.core.models import TimeStampedModel

User = get_user_model()


class Source(TimeStampedModel):
    """Where a piece of knowledge came from and whether we have permission to use it."""

    class Kind(models.TextChoices):
        FAMILY = "family", "Family cook"
        CHEF = "chef", "Chef"
        BOOK = "book", "Book"
        SURVEY = "survey", "Survey"
        WEB = "web", "Web"

    class PermissionStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        GRANTED = "granted", "Granted"
        RESTRICTED = "restricted", "Restricted"
        PUBLIC_DOMAIN = "public_domain", "Public domain"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=255)
    citation = models.TextField(blank=True)
    permission_status = models.CharField(
        max_length=20,
        choices=PermissionStatus.choices,
        default=PermissionStatus.PENDING,
    )
    contributor = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "source"
        ordering = ["title"]

    def __str__(self) -> str:
        return f"{self.title} ({self.get_kind_display()})"


class ChangeLog(models.Model):
    """
    Append-only audit trail for every data change.

    Architecture spec: every edit recorded with who, when and why.
    Records are never updated or deleted — soft immutability enforced at the app layer.
    """

    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        STATUS_CHANGE = "status_change", "Status change"
        IMPORT = "import", "Import"

    object_type = models.CharField(max_length=100, db_index=True)
    object_id = models.CharField(max_length=36, db_index=True)  # UUID as string
    action = models.CharField(max_length=20, choices=Action.choices)
    diff = models.JSONField(default=dict)  # before/after values
    actor = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="change_logs",
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "change_log"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} {self.object_type} {self.object_id}"


class DatasetRelease(TimeStampedModel):
    """
    A numbered snapshot of the whole knowledge library.

    Architecture spec: every release has a version (e.g. 2026.12.0) and a changelog.
    Every API response reports which dataset version produced it.
    """

    version = models.CharField(max_length=20, unique=True)  # e.g. 2026.12.0
    notes = models.TextField(blank=True)
    counts = models.JSONField(default=dict)  # e.g. {"dishes": 150, "ingredients": 400}
    released_by = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_NULL,
        related_name="dataset_releases",
    )

    class Meta:
        db_table = "dataset_release"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Dataset {self.version}"
