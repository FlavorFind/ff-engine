"""
Custom user model for the Flavor Find engine.

Extends AbstractUser to add a role field (curator / reviewer / admin).
All admin access requires two-factor authentication (enforced by django-two-factor-auth).

Roles
------
curator   — can create and edit draft data; cannot publish.
reviewer  — can approve curator submissions; cannot delete.
admin     — full access; maps to Django staff/superuser conventions.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        CURATOR = "curator", "Curator"
        REVIEWER = "reviewer", "Reviewer"
        ADMIN = "admin", "Admin"

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CURATOR,
        help_text="Access level within the curation workflow.",
    )

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        ordering = ["username"]

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_curator(self) -> bool:
        return self.role == self.Role.CURATOR

    @property
    def is_reviewer(self) -> bool:
        return self.role == self.Role.REVIEWER

    @property
    def is_admin_role(self) -> bool:
        """True when the role field is 'admin' (distinct from is_staff/is_superuser)."""
        return self.role == self.Role.ADMIN
