import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("clients", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="RequestLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("endpoint", models.CharField(db_index=True, max_length=200)),
                ("status_code", models.PositiveSmallIntegerField()),
                (
                    "response_ms",
                    models.PositiveIntegerField(help_text="Response time in milliseconds."),
                ),
                ("logged_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="request_logs",
                        to="clients.apiclient",
                    ),
                ),
            ],
            options={
                "db_table": "request_log",
            },
        ),
        migrations.AddIndex(
            model_name="requestlog",
            index=models.Index(
                fields=["client", "endpoint", "logged_at"],
                name="req_log_client_endpoint_idx",
            ),
        ),
        migrations.CreateModel(
            name="UsageRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("endpoint", models.CharField(db_index=True, max_length=200)),
                ("date", models.DateField(db_index=True)),
                ("calls", models.PositiveIntegerField(default=0)),
                (
                    "errors",
                    models.PositiveIntegerField(default=0, help_text="4xx + 5xx responses."),
                ),
                (
                    "p95_ms",
                    models.PositiveIntegerField(
                        blank=True, help_text="95th percentile response time in ms.", null=True
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="usage_records",
                        to="clients.apiclient",
                    ),
                ),
            ],
            options={
                "db_table": "usage_record",
                "ordering": ["-date", "client", "endpoint"],
            },
        ),
        migrations.AddConstraint(
            model_name="usagerecord",
            constraint=models.UniqueConstraint(
                fields=["client", "endpoint", "date"], name="unique_usage_per_day"
            ),
        ),
    ]
