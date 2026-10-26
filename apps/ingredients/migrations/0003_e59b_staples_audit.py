"""
E59b — Staples audit.

Resets is_staple to False on every ingredient, then marks exactly the
six universally-present East African kitchen staples as True.

Correct staples (6):
  water          — universal
  salt           — universal
  iodized-salt   — standard table salt in Kenya
  cooking-oil    — universal generic oil
  vegetable-oil  — widely used generic
  black-pepper   — universal condiment

Everything else (maize-flour, flour, sugar, butter, yeast, stock, all
specific oil variants, warm-water, etc.) is a recipe ingredient, not a
staple, and must not be assumed present in every kitchen.
"""

from django.db import migrations

CORRECT_STAPLES = frozenset(
    [
        "water",
        "salt",
        "iodized-salt",
        "cooking-oil",
        "vegetable-oil",
        "black-pepper",
    ]
)


def set_staples(apps, schema_editor):
    Ingredient = apps.get_model("ingredients", "Ingredient")
    # 1. Clear all staple flags.
    Ingredient.objects.filter(is_staple=True).update(is_staple=False)
    # 2. Set the correct six.
    updated = Ingredient.objects.filter(slug__in=CORRECT_STAPLES).update(is_staple=True)
    if updated != len(CORRECT_STAPLES):
        found = set(
            Ingredient.objects.filter(slug__in=CORRECT_STAPLES).values_list("slug", flat=True)
        )
        missing = CORRECT_STAPLES - found
        raise ValueError(
            f"E59b migration: expected {len(CORRECT_STAPLES)} staple slugs, "
            f"updated {updated}. Missing from DB: {missing}"
        )


def revert_staples(apps, schema_editor):
    """
    Reverse: restore the pre-audit staple list.

    We restore only the six correct staples — the original 26 are not
    restored because that state was wrong. A full data restore is needed
    if you genuinely need the old list back.
    """
    Ingredient = apps.get_model("ingredients", "Ingredient")
    Ingredient.objects.filter(is_staple=True).update(is_staple=False)
    Ingredient.objects.filter(slug__in=CORRECT_STAPLES).update(is_staple=True)


class Migration(migrations.Migration):
    dependencies = [
        ("ingredients", "0002_e40_trgm_indexes"),
    ]

    operations = [
        migrations.RunPython(set_staples, reverse_code=revert_staples),
    ]
