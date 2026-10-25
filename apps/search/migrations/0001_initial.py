import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ZeroResultQuery",
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
                    "raw_input",
                    models.TextField(
                        help_text="Original query string as sent by the client.",
                    ),
                ),
                (
                    "normalised_input",
                    models.TextField(
                        db_index=True,
                        help_text="Lowercased, sorted tokens — used for deduplication.",
                    ),
                ),
                (
                    "count",
                    models.PositiveIntegerField(
                        default=1,
                        help_text="Number of times this query returned zero results.",
                    ),
                ),
                (
                    "last_seen",
                    models.DateTimeField(
                        db_index=True,
                        default=django.utils.timezone.now,
                        help_text="Timestamp of the most recent zero-result hit.",
                    ),
                ),
            ],
            options={
                "db_table": "zero_result_query",
                "ordering": ["-count", "-last_seen"],
            },
        ),
    ]
