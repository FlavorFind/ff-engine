"""Initial migration for dishes app — Dish, DishIngredient, DishAlias, DishStep."""

import uuid
import django.contrib.postgres.fields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("curation", "0001_initial"),
        ("ingredients", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Dish",
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
                ("slug", models.SlugField(max_length=200, unique=True)),
                ("name_en", models.CharField(max_length=200, unique=True)),
                ("name_sw", models.CharField(blank=True, max_length=200)),
                ("description", models.TextField(blank=True)),
                (
                    "meal_type",
                    models.CharField(
                        choices=[
                            ("breakfast", "Breakfast"),
                            ("lunch", "Lunch"),
                            ("dinner", "Dinner"),
                            ("snack", "Snack"),
                            ("drink", "Drink"),
                            ("dessert", "Dessert"),
                            ("any", "Any"),
                        ],
                        db_index=True,
                        default="any",
                        max_length=20,
                    ),
                ),
                (
                    "course",
                    models.CharField(
                        choices=[
                            ("starter", "Starter"),
                            ("main", "Main"),
                            ("side", "Side"),
                            ("dessert", "Dessert"),
                            ("drink", "Drink"),
                            ("snack", "Snack"),
                        ],
                        default="main",
                        max_length=20,
                    ),
                ),
                (
                    "spice_level",
                    models.CharField(
                        choices=[
                            ("none", "None"),
                            ("mild", "Mild"),
                            ("medium", "Medium"),
                            ("hot", "Hot"),
                            ("very_hot", "Very hot"),
                        ],
                        default="none",
                        max_length=20,
                    ),
                ),
                (
                    "difficulty",
                    models.CharField(
                        choices=[
                            ("easy", "Easy"),
                            ("medium", "Medium"),
                            ("hard", "Hard"),
                        ],
                        default="easy",
                        max_length=20,
                    ),
                ),
                ("prep_min", models.PositiveIntegerField(default=0)),
                ("cook_min", models.PositiveIntegerField(default=0)),
                ("servings", models.PositiveIntegerField(default=1)),
                ("popularity", models.FloatField(default=0.0)),
                (
                    "quality_level",
                    models.CharField(
                        choices=[
                            ("seeded", "Seeded"),
                            ("community", "Community"),
                            ("reviewed", "Reviewed"),
                            ("verified", "Verified"),
                        ],
                        db_index=True,
                        default="seeded",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("reviewed", "Reviewed"),
                            ("verified", "Verified"),
                            ("archived", "Archived"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "source",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dishes",
                        to="curation.source",
                    ),
                ),
                # Denormalised search arrays — GIN indexes added below
                (
                    "required_ids",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.IntegerField(),
                        default=list,
                        help_text="PKs of required non-staple ingredients.",
                        size=None,
                    ),
                ),
                (
                    "optional_ids",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.IntegerField(),
                        default=list,
                        help_text="PKs of optional ingredients.",
                        size=None,
                    ),
                ),
                (
                    "primary_ids",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.IntegerField(),
                        default=list,
                        help_text="PKs of primary ingredients.",
                        size=None,
                    ),
                ),
                (
                    "all_ids",
                    django.contrib.postgres.fields.ArrayField(
                        base_field=models.IntegerField(),
                        default=list,
                        help_text="PKs of all ingredients.",
                        size=None,
                    ),
                ),
            ],
            options={
                "db_table": "dish",
                "ordering": ["name_en"],
            },
        ),
        migrations.AddIndex(
            model_name="dish",
            index=models.Index(fields=["status"], name="dish_status_idx"),
        ),
        migrations.AddIndex(
            model_name="dish",
            index=models.Index(fields=["quality_level"], name="dish_quality_idx"),
        ),
        migrations.AddIndex(
            model_name="dish",
            index=models.Index(fields=["meal_type"], name="dish_meal_type_idx"),
        ),
        # GIN indexes on the array fields — used by the search engine in E19
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS dish_required_ids_gin ON dish USING gin (required_ids);",
            reverse_sql="DROP INDEX IF EXISTS dish_required_ids_gin;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS dish_optional_ids_gin ON dish USING gin (optional_ids);",
            reverse_sql="DROP INDEX IF EXISTS dish_optional_ids_gin;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS dish_primary_ids_gin ON dish USING gin (primary_ids);",
            reverse_sql="DROP INDEX IF EXISTS dish_primary_ids_gin;",
        ),
        migrations.RunSQL(
            sql="CREATE INDEX IF NOT EXISTS dish_all_ids_gin ON dish USING gin (all_ids);",
            reverse_sql="DROP INDEX IF EXISTS dish_all_ids_gin;",
        ),
        # DishIngredient
        migrations.CreateModel(
            name="DishIngredient",
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
                (
                    "dish",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dish_ingredients",
                        to="dishes.dish",
                    ),
                ),
                (
                    "ingredient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="dish_ingredients",
                        to="ingredients.ingredient",
                    ),
                ),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("primary", "Primary"),
                            ("required", "Required"),
                            ("optional", "Optional"),
                            ("garnish", "Garnish"),
                        ],
                        db_index=True,
                        default="required",
                        max_length=20,
                    ),
                ),
                (
                    "quantity",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=8,
                        null=True,
                    ),
                ),
                (
                    "unit",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dish_ingredients",
                        to="ingredients.unit",
                    ),
                ),
                ("preparation_note", models.CharField(blank=True, max_length=200)),
                ("position", models.PositiveIntegerField(default=0)),
            ],
            options={
                "db_table": "dish_ingredient",
                "ordering": ["position", "role"],
            },
        ),
        migrations.AddConstraint(
            model_name="dishingredient",
            constraint=models.UniqueConstraint(
                fields=["dish", "ingredient"],
                name="unique_dish_ingredient",
            ),
        ),
        # DishAlias
        migrations.CreateModel(
            name="DishAlias",
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
                        related_name="aliases",
                        to="dishes.dish",
                    ),
                ),
                ("alias", models.CharField(db_index=True, max_length=200)),
                (
                    "language",
                    models.CharField(
                        choices=[
                            ("en", "English"),
                            ("sw", "Swahili"),
                            ("sheng", "Sheng"),
                            ("other", "Other"),
                        ],
                        default="en",
                        max_length=10,
                    ),
                ),
            ],
            options={
                "db_table": "dish_alias",
                "ordering": ["alias"],
            },
        ),
        migrations.AddConstraint(
            model_name="dishalias",
            constraint=models.UniqueConstraint(
                fields=["dish", "alias"],
                name="unique_dish_alias",
            ),
        ),
        # DishStep
        migrations.CreateModel(
            name="DishStep",
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
                        related_name="steps",
                        to="dishes.dish",
                    ),
                ),
                ("position", models.PositiveIntegerField()),
                ("text_en", models.TextField()),
                ("text_sw", models.TextField(blank=True)),
            ],
            options={
                "db_table": "dish_step",
                "ordering": ["position"],
            },
        ),
        migrations.AddConstraint(
            model_name="dishstep",
            constraint=models.UniqueConstraint(
                fields=["dish", "position"],
                name="unique_dish_step_position",
            ),
        ),
    ]
