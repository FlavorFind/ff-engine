"""Initial migration for regions app — Region and DishRegion."""

import uuid
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("dishes", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Region",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("slug", models.SlugField(max_length=100, unique=True)),
                ("name", models.CharField(max_length=100)),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("county", "County"),
                            ("coast", "Coast"),
                            ("cuisine", "Cuisine group"),
                        ],
                        max_length=20,
                    ),
                ),
                ("description", models.TextField(blank=True)),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="children",
                        to="regions.region",
                    ),
                ),
            ],
            options={
                "db_table": "region",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="DishRegion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "dish",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dish_regions",
                        to="dishes.dish",
                    ),
                ),
                (
                    "region",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dish_regions",
                        to="regions.region",
                    ),
                ),
            ],
            options={
                "db_table": "dish_region",
            },
        ),
        migrations.AddConstraint(
            model_name="dishregion",
            constraint=models.UniqueConstraint(
                fields=["dish", "region"],
                name="unique_dish_region",
            ),
        ),
    ]
