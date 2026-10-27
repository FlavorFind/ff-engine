"""
E53 — publish_release management command.

Creates a new DatasetRelease, invalidates the search cache for the previous
version, and logs the action to ChangeLog.

Usage:
    python manage.py publish_release 2026.11.0 --notes 'Added 50 new dishes'
    python manage.py publish_release 2026.11.0 --dry-run

Step-up 2FA:
    In the admin UI, publishing a dataset release requires the admin to
    re-verify their second factor (step-up 2FA, valid for 5 minutes).
    This CLI command mirrors that gate via --confirm-stepup: the operator
    must explicitly confirm that step-up 2FA has been verified through the
    admin interface before running the command. Without this flag the
    command refuses to proceed.

    Architecture reference (Sprint 1 doc, section 14.3):
      "Publish a dataset release — Approve (step-up 2FA)" for admin role.
"""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

# Version format: YYYY.MM.N (e.g. 2026.11.0)
_VERSION_RE = re.compile(r"^\d{4}\.\d{1,2}\.\d+$")


class Command(BaseCommand):
    help = "E53 — Publish a new dataset release (requires --confirm-stepup)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "version",
            help="Dataset version in YYYY.MM.N format, e.g. 2026.11.0",
        )
        parser.add_argument(
            "--notes",
            default="",
            help="Changelog notes for this release.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be created without saving anything.",
        )
        parser.add_argument(
            "--confirm-stepup",
            action="store_true",
            default=False,
            help=(
                "Confirm that step-up 2FA has been verified through the admin "
                "interface. Required for a real publish (not --dry-run)."
            ),
        )

    def handle(self, *args, **options) -> None:  # noqa: C901
        version: str = options["version"].strip()
        notes: str = options["notes"].strip()
        dry_run: bool = options["dry_run"]
        confirm_stepup: bool = options["confirm_stepup"]
        verbosity: int = options["verbosity"]

        # ── 1. Validate version format ────────────────────────────────────────
        if not _VERSION_RE.match(version):
            raise CommandError(
                f"Invalid version {version!r}. Expected format: YYYY.MM.N (e.g. 2026.11.0)"
            )

        # ── 2. Step-up 2FA gate ───────────────────────────────────────────────
        if not dry_run and not confirm_stepup:
            self.stderr.write(
                self.style.ERROR(
                    "\nPublishing a dataset release requires step-up 2FA.\n\n"
                    "  1. Log in to the admin interface (/admin/).\n"
                    "  2. Re-verify your second factor (authenticator app or security key).\n"
                    "  3. Run this command again with --confirm-stepup.\n\n"
                    "This gate exists because dataset releases are irreversible and "
                    "immediately affect all API consumers.\n"
                )
            )
            raise SystemExit(1)

        # ── 3. Check version uniqueness and ordering ──────────────────────────
        from apps.curation.models import DatasetRelease

        if DatasetRelease.objects.filter(version=version).exists():
            raise CommandError(f"Version {version!r} already exists.")

        latest = DatasetRelease.objects.order_by("-created_at").first()
        if latest and latest.version >= version:
            raise CommandError(
                f"New version {version!r} must be newer than the latest release {latest.version!r}."
            )

        # ── 4. Count current dataset objects ─────────────────────────────────
        counts = _collect_counts()

        # ── 5. Dry-run output ─────────────────────────────────────────────────
        if dry_run:
            self.stdout.write(self.style.MIGRATE_HEADING("\n[DRY RUN] publish_release\n"))
            self.stdout.write(f"  Version  : {version}")
            self.stdout.write(f"  Notes    : {notes or '(none)'}")
            self.stdout.write(f"  Counts   : {counts}")
            self.stdout.write(f"  Previous : {latest.version if latest else '(none)'}")
            self.stdout.write("\nNo changes made. Remove --dry-run to publish.\n")
            return

        # ── 6. Create the release and clear the cache ─────────────────────────
        with transaction.atomic():
            release = DatasetRelease.objects.create(
                version=version,
                notes=notes,
                counts=counts,
            )

            # Log to audit trail
            from apps.curation.models import ChangeLog

            ChangeLog.objects.create(
                object_type="DatasetRelease",
                object_id=str(release.pk),
                action=ChangeLog.Action.CREATE,
                diff={"version": version, "counts": counts},
                reason=f"Dataset release {version} published via CLI",
            )

        # Invalidate the search cache for the previous version (outside the
        # transaction so a cache failure does not roll back the release).
        if latest:
            try:
                from apps.search.cache import clear_search_cache

                clear_search_cache(latest.version)
                if verbosity >= 1:
                    self.stdout.write(
                        f"  Cleared search cache for previous version {latest.version}"
                    )
            except Exception as exc:
                self.stderr.write(self.style.WARNING(f"Cache clear failed (non-fatal): {exc}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Dataset release {version} published.\n"
                f"  Dishes: {counts.get('dishes', 0)}, "
                f"Ingredients: {counts.get('ingredients', 0)}, "
                f"Pairings: {counts.get('pairings', 0)}, "
                f"Substitutions: {counts.get('substitutions', 0)}\n"
            )
        )


def _collect_counts() -> dict:
    """Return current dataset object counts."""
    from apps.core.models import StatusChoices
    from apps.dishes.models import Dish
    from apps.ingredients.models import Ingredient
    from apps.pairings.models import Pairing
    from apps.substitutions.models import Substitution

    live = [StatusChoices.REVIEWED, StatusChoices.VERIFIED]
    return {
        "dishes": Dish.objects.filter(status__in=live).count(),
        "ingredients": Ingredient.objects.filter(status__in=live).count(),
        "pairings": Pairing.objects.count(),
        "substitutions": Substitution.objects.count(),
    }
