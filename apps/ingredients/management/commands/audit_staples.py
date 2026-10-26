"""
E59b — audit_staples management command.

Prints every ingredient flagged is_staple=True and warns about any that
also appear as a *primary* role in DishIngredient rows.

A true staple should never be the primary ingredient of a dish — if it
is, it likely means the is_staple flag is wrong (the ingredient is a
recipe component, not a universal background ingredient).

Usage:
    python manage.py audit_staples
    python manage.py audit_staples --fail-on-warn   # exit 1 if any warnings
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

EXPECTED_STAPLES = frozenset(
    [
        "water",
        "salt",
        "iodized-salt",
        "cooking-oil",
        "vegetable-oil",
        "black-pepper",
    ]
)


class Command(BaseCommand):
    help = "E59b — Audit the is_staple flags and warn about misclassified ingredients."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--fail-on-warn",
            action="store_true",
            default=False,
            help="Exit with status 1 if any warnings are found.",
        )

    def handle(self, *args, **options) -> None:
        from apps.dishes.models import DishIngredient
        from apps.ingredients.models import Ingredient

        staples = list(Ingredient.objects.filter(is_staple=True).order_by("slug"))
        staple_slugs = {i.slug for i in staples}

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\nStaple audit — {len(staples)} ingredient(s) flagged is_staple=True\n"
            )
        )

        warnings: list[str] = []

        for ing in staples:
            # Check: is this ingredient the primary role in any dish?
            primary_count = DishIngredient.objects.filter(ingredient=ing, role="primary").count()
            if primary_count > 0:
                dish_names = list(
                    DishIngredient.objects.filter(ingredient=ing, role="primary")
                    .select_related("dish")
                    .values_list("dish__name_en", flat=True)[:3]
                )
                sample = ", ".join(dish_names)
                if primary_count > 3:
                    sample += f" … (+{primary_count - 3} more)"
                msg = (
                    f"  ⚠  {ing.slug!r} is a staple but is PRIMARY in "
                    f"{primary_count} dish(es): {sample}"
                )
                warnings.append(msg)
                self.stdout.write(self.style.WARNING(msg))
            else:
                self.stdout.write(f"  ✓  {ing.slug}")

        # Check for unexpected staples (not in the expected set)
        unexpected = staple_slugs - EXPECTED_STAPLES
        if unexpected:
            for slug in sorted(unexpected):
                msg = f"  ⚠  {slug!r} is flagged as a staple but is NOT in the expected set"
                warnings.append(msg)
                self.stdout.write(self.style.WARNING(msg))

        # Check for missing expected staples
        missing = EXPECTED_STAPLES - staple_slugs
        if missing:
            for slug in sorted(missing):
                msg = f"  ✗  {slug!r} is expected to be a staple but is NOT flagged"
                warnings.append(msg)
                self.stdout.write(self.style.ERROR(msg))

        self.stdout.write("")
        if warnings:
            self.stdout.write(self.style.WARNING(f"{len(warnings)} warning(s) found."))
            if options["fail_on_warn"]:
                raise SystemExit(1)
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Staple audit passed. "
                    f"{len(staples)} staple(s), all expected, none misclassified."
                )
            )
