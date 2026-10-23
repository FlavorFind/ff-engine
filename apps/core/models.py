"""Base models shared across all apps."""
import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base with UUID pk, created_at and updated_at."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StatusChoices(models.TextChoices):
    DRAFT = "draft", "Draft"
    REVIEWED = "reviewed", "Reviewed"
    VERIFIED = "verified", "Verified"
    ARCHIVED = "archived", "Archived"


class StatusMixin(models.Model):
    """Mixin that adds the curation status workflow to a model."""

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.DRAFT,
        db_index=True,
    )

    class Meta:
        abstract = True
