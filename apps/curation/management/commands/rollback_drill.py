"""
E49 — Rollback drill management command.

Simulates the rollback procedure documented in the runbook:
  1. Check the current deployed commit / version.
  2. Print the previous release tag to roll back to.
  3. Verify the database migrations can be reversed to the previous state.
  4. Print the exact commands to execute on Render for a real rollback.

This command is read-only — it prints instructions, it does NOT execute
any destructive git or migration operations. Actual rollback is done by
a human following the printed instructions.

Usage:
    python manage.py rollback_drill
    python manage.py rollback_drill --target-version 0.9.0
"""

from __future__ import annotations

import subprocess

from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "E49 — Print rollback instructions for the current release."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--target-version",
            default=None,
            help="The version tag to roll back to (e.g. v0.9.0). "
            "Defaults to the previous git tag.",
        )

    def handle(self, *args, **options) -> None:
        self.stdout.write(self.style.WARNING("\n=== ROLLBACK DRILL ===\n"))

        # 1. Current state
        current_commit = self._get_current_commit()
        current_version = self._get_current_version()
        self.stdout.write(f"Current commit:  {current_commit}")
        self.stdout.write(f"Current version: {current_version}")

        # 2. Target version
        target = options["target_version"] or self._get_previous_tag()
        self.stdout.write(f"Rollback target: {target or '(no previous tag found)'}")

        # 3. Migration state
        self.stdout.write("\n--- Migration state ---")
        self._check_migration_state()

        # 4. Print rollback instructions
        self.stdout.write("\n--- Rollback instructions ---")
        self._print_rollback_instructions(target, current_commit)

        self.stdout.write(
            self.style.SUCCESS(
                "\n[rollback_drill] ✓ Instructions printed. "
                "No changes made to the database or git state."
            )
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_current_commit(self) -> str:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            return result.stdout.strip() or "unknown"
        except FileNotFoundError:
            return "unknown (git not available)"

    def _get_current_version(self) -> str:
        import django.conf

        return getattr(django.conf.settings, "ENGINE_VERSION", "dev")

    def _get_previous_tag(self) -> str | None:
        try:
            result = subprocess.run(
                ["git", "tag", "--sort=-version:refname"],
                capture_output=True,
                text=True,
                check=False,
            )
            tags = [t.strip() for t in result.stdout.splitlines() if t.strip()]
            # Return the second tag (previous release) if available
            return tags[1] if len(tags) > 1 else (tags[0] if tags else None)
        except FileNotFoundError:
            return None

    def _check_migration_state(self) -> None:
        """List all applied migrations for the local apps."""
        local_apps = [
            "accounts",
            "ingredients",
            "dishes",
            "regions",
            "dietary",
            "pairings",
            "substitutions",
            "nutrition",
            "search",
            "curation",
            "clients",
        ]
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT app, name FROM django_migrations "
                "WHERE app = ANY(%s) ORDER BY app, name;",
                [local_apps],
            )
            rows = cursor.fetchall()

        if rows:
            for app, name in rows:
                self.stdout.write(f"  [applied] {app}.{name}")
        else:
            self.stdout.write("  (no local app migrations found)")

    def _print_rollback_instructions(self, target: str | None, current_commit: str) -> None:
        target_str = target or "<previous-tag>"

        self.stdout.write(
            f"""
Step 1 — On Render dashboard:
  a. Go to ff-engine service → Deploys
  b. Find the deploy for {target_str} (or the commit before {current_commit})
  c. Click "Rollback to this deploy"
  d. Wait for deploy to complete (≈ 2 min)

Step 2 — If the rollback involves a migration reversal:
  a. Open a Render shell: Dashboard → Shell
  b. Run: python manage.py showmigrations
  c. Identify which migrations are in the new (rolled-back) release
  d. For each migration to reverse (newest first):
       python manage.py migrate <app> <previous-migration-name>
  e. Example:
       python manage.py migrate clients 0001_initial

Step 3 — Verify the service is healthy:
  curl https://ff-engine-kuar.onrender.com/v1/health/
  # Expected: {{"status": "ok", "database": "ok"}}

Step 4 — Verify the golden set still passes at ≥ 95%:
  python manage.py run_golden_set --fail-fast

Step 5 — If rollback was due to a data issue, restore from snapshot:
  python manage.py backup_drill --step restore --confirm \\
    --snapshot-dir data/snapshots/<timestamp>

Step 6 — Post-mortem:
  - Document what went wrong in docs/runbooks/incident-log.md
  - File a GitHub issue labelled 'incident'
  - Review and update the release checklist before next deploy
"""
        )
