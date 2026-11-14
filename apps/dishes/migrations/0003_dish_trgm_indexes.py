"""
Add pg_trgm GIN indexes on dish.name_en and dish.name_sw.

pg_trgm is already installed by ingredients/migrations/0002_e40_trgm_indexes.py,
so we do not CREATE EXTENSION here.

A GIN trgm index turns every ILIKE '%term%' on name_en / name_sw from an O(n)
sequential scan into an O(log n) bitmap-index scan, which matters once the dish
table grows beyond a few hundred rows.

atomic=False is required because CREATE INDEX CONCURRENTLY cannot run inside
a transaction block.
"""

from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("dishes", "0002_remove_dishalias_unique_dish_alias_and_more"),
        ("ingredients", "0002_e40_trgm_indexes"),  # ensures pg_trgm is already installed
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                dish_name_en_trgm_idx
                ON dish
                USING gin (name_en gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS dish_name_en_trgm_idx;",
        ),
        migrations.RunSQL(
            sql="""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS
                dish_name_sw_trgm_idx
                ON dish
                USING gin (name_sw gin_trgm_ops);
            """,
            reverse_sql="DROP INDEX IF EXISTS dish_name_sw_trgm_idx;",
        ),
    ]
