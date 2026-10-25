import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("ingredients", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="NutritionFact",
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
                    "kcal",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Kilocalories per 100 g.",
                        max_digits=8,
                    ),
                ),
                (
                    "protein_g",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Protein in grams per 100 g.",
                        max_digits=7,
                    ),
                ),
                (
                    "carbs_g",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Total carbohydrates in grams per 100 g.",
                        max_digits=7,
                    ),
                ),
                (
                    "fat_g",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Total fat in grams per 100 g.",
                        max_digits=7,
                    ),
                ),
                (
                    "fibre_g",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Dietary fibre in grams per 100 g.",
                        max_digits=7,
                    ),
                ),
                (
                    "sodium_mg",
                    models.DecimalField(
                        decimal_places=2,
                        default=0,
                        help_text="Sodium in milligrams per 100 g.",
                        max_digits=8,
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        help_text="Data source (e.g. USDA FoodData Central, KENFRI 2019).",
                        max_length=200,
                    ),
                ),
                (
                    "confidence",
                    models.CharField(
                        choices=[
                            ("high", "High (lab / official)"),
                            ("medium", "Medium (label / trusted source)"),
                            ("low", "Low (estimate)"),
                        ],
                        db_index=True,
                        default="medium",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "ingredient",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="nutrition",
                        to="ingredients.ingredient",
                    ),
                ),
            ],
            options={
                "db_table": "nutrition_fact",
                "ordering": ["ingredient__name_en"],
            },
        ),
    ]
