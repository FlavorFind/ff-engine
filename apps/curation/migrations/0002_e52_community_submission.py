"""
E52 — Community submissions intake.

Adds the CommunitySubmission model: a holding queue for dish, ingredient
and pairing submissions from community members and partner apps.
All submissions enter as PENDING and require curator review before
any content reaches the live dataset.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clients", "0002_e38_usage_metering"),
        ("curation", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CommunitySubmission",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "submission_type",
                    models.CharField(
                        choices=[
                            ("dish", "Dish"),
                            ("ingredient", "Ingredient"),
                            ("pairing", "Pairing"),
                        ],
                        db_index=True,
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending review"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("duplicate", "Duplicate"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "payload",
                    models.JSONField(
                        help_text="Raw submission payload. Schema depends on submission_type."
                    ),
                ),
                ("submitter_note", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True)),
                (
                    "submitter_client",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="submissions",
                        to="clients.apiclient",
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="reviewed_submissions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "community_submission",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="communitysubmission",
            index=models.Index(
                fields=["status", "submission_type"],
                name="community_submission_status_type_idx",
            ),
        ),
    ]
