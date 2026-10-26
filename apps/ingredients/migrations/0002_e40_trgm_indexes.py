"""
E40 — Performance tuning: trigram GIN indexes on ingredient name and alias fields.

The resolver uses pg_trgm similarity queries on:
  - ingredient_alias.normalized_alias
  - ingredient.name_en
  - ingredient.name_sw

Without a GIN index these are sequential scans. At 638+ ingredients
and 1,500+ aliases a GIN trgm index brings fuzzy lookups from O(n)
to O(log n).

pg_trgm extension is enabled in the initial migration and in CI setup.
"""

from django.db import migrations


class Migration(migrations.Migration):
    # CREATE INDEX CONCURRENTLY cannot run inside a transaction block.
    # Setting atomic=False tells Django to run this migration outside
    # the default transaction wrapper.
    atomic = False

    dependencies = [
        ("ingredients", "0001_initial"),
    ]

    operations = [
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
