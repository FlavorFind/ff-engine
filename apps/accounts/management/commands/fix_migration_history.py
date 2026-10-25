"""
Staging DB fix: resolves the accounts/admin migration dependency issue.

The staging DB has admin.0001_initial applied but accounts.0001_initial
is missing. Django refuses to migrate until this is resolved.

This command creates the accounts_customuser table exactly as
accounts.0001_initial would, then records the migration as applied.
The subsequent migrate --no-input finds a consistent history and continues.

Safe to run multiple times — checks if table already exists first.
"""

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Create accounts tables and record migration to fix staging DB"

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Check if already done
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'accounts_customuser'
                )
                """
            )
            if cursor.fetchone()[0]:
                self.stdout.write(
                    self.style.WARNING("accounts_customuser already exists — nothing to do")
                )
                return

            self.stdout.write("Creating accounts_customuser table...")

            cursor.execute(
                """
                CREATE TABLE accounts_customuser (
                    id bigserial NOT NULL PRIMARY KEY,
                    password varchar(128) NOT NULL,
                    last_login timestamptz NULL,
                    is_superuser boolean NOT NULL,
                    username varchar(150) NOT NULL UNIQUE,
                    first_name varchar(150) NOT NULL,
                    last_name varchar(150) NOT NULL,
                    email varchar(254) NOT NULL,
                    is_staff boolean NOT NULL,
                    is_active boolean NOT NULL,
                    date_joined timestamptz NOT NULL,
                    role varchar(20) NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE accounts_customuser_groups (
                    id bigserial NOT NULL PRIMARY KEY,
                    customuser_id bigint NOT NULL
                        REFERENCES accounts_customuser(id) DEFERRABLE INITIALLY DEFERRED,
                    group_id integer NOT NULL
                        REFERENCES auth_group(id) DEFERRABLE INITIALLY DEFERRED,
                    UNIQUE (customuser_id, group_id)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE accounts_customuser_user_permissions (
                    id bigserial NOT NULL PRIMARY KEY,
                    customuser_id bigint NOT NULL
                        REFERENCES accounts_customuser(id) DEFERRABLE INITIALLY DEFERRED,
                    permission_id integer NOT NULL
                        REFERENCES auth_permission(id) DEFERRABLE INITIALLY DEFERRED,
                    UNIQUE (customuser_id, permission_id)
                )
                """
            )

            # Record migration as applied (clean any stale record first)
            cursor.execute(
                "DELETE FROM django_migrations WHERE app = %s AND name = %s",
                ["accounts", "0001_initial"],
            )
            cursor.execute(
                "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, NOW())",
                ["accounts", "0001_initial"],
            )

        self.stdout.write(
            self.style.SUCCESS(
                "accounts tables created and migration recorded — migrate can now proceed"
            )
        )
