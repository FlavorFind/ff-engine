"""
Staging DB fix: ensures accounts migrations run correctly.

Problem: staging DB had admin.0001_initial applied before accounts
existed. On first fix attempt we inserted a fake migration record,
but the actual table was never created.

This command:
  1. If accounts_customuser table exists → nothing to do.
  2. If table is missing but fake record exists → delete the fake record
     so Django will run the real migration and create the table.
  3. If neither exists → also nothing to do (fresh DB, migrate handles it).

Safe to run multiple times.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Fix accounts migration state on staging DB"

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Check if the real table exists
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'accounts_customuser'
                )
                """
            )
            table_exists = cursor.fetchone()[0]

            if table_exists:
                self.stdout.write(
                    self.style.WARNING("accounts_customuser table already exists — nothing to fix")
                )
                return

            # Table missing — remove any fake migration record so
            # Django runs the real migration
            cursor.execute(
                "DELETE FROM django_migrations WHERE app = %s AND name = %s",
                ["accounts", "0001_initial"],
            )
            deleted = cursor.rowcount
            if deleted:
                self.stdout.write(
                    self.style.SUCCESS(
                        "Removed stale accounts.0001_initial record — "
                        "migrate will now create the table"
                    )
                )
            else:
                self.stdout.write("No stale record found — proceeding normally")
