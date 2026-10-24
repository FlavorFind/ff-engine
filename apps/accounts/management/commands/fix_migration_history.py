"""
One-time fix: marks accounts.0001_initial as applied in the migration
history without running it.

Needed because the staging DB had Django's admin migrations applied
before the accounts app existed. Django now sees an inconsistent history
because admin depends on accounts.

This command is safe to run multiple times — it checks first.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Mark accounts.0001_initial as applied (one-time staging fix)"

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM django_migrations WHERE app = %s AND name = %s",
                ["accounts", "0001_initial"],
            )
            row = cursor.fetchone()
            if row:
                self.stdout.write(
                    self.style.WARNING(
                        "accounts.0001_initial already in django_migrations — skipping"
                    )
                )
                return

            cursor.execute(
                "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, NOW())",
                ["accounts", "0001_initial"],
            )
            self.stdout.write(
                self.style.SUCCESS("Marked accounts.0001_initial as applied in django_migrations")
            )
