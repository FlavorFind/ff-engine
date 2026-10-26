"""
E40 — Performance tuning: trigram GIN indexes on ingredient name and alias fields.

The resolver uses pg_trgm similarity queries on:
  - ingredient_alias.normalized_alias
  - ingredient.name_en
  - ingredient.name_sw

Without a GIN index these are sequential scans. At 638+ ingredients
and 1,500+ aliases a GIN trgm index brings fuzzy lookups from O(n)
to O(log n).

This migration installs the pg_trgm extension itself (CREATE EXTENSION IF NOT EXISTS),
so it is self-contained and works on any fresh PostgreSQL database — including the
test DB created by pytest-django — without requiring a separate setup step.

atomic=False is required because CREATE INDEX CONCURRENTLY cannot run inside
a transaction block.
"""

from django.db import migrations


class Migration(migrations.Migration):
    # CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    atomic = False

    dependencies = [
        ("ingredients", "0001_initial"),
    ]

    operations = [
        # Install pg_trgm first — safe to run on any DB, idempotent.
        migrations.RunSQL(
            sql="CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ingredient_alias_normalized_trgm_idx
                ON ingredient_alias
                USING gin (normalized_alias gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS ingredient_alias_normalized_trgm_idx;",
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ingredient_name_en_trgm_idx
                ON ingredient
                USING gin (name_en gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS ingredient_name_en_trgm_idx;",
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                ingredient_name_sw_trgm_idx
                ON ingredient
                USING gin (name_sw gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS ingredient_name_sw_trgm_idx;",
        ),
    ]
