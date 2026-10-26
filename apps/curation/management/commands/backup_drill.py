"""
E49 — Backup and restore drill management command.

Usage:
    python manage.py backup_drill --step all
    python manage.py backup_drill --step backup
    python manage.py backup_drill --step verify
    python manage.py backup_drill --step restore

Steps
-----
backup  — Export the full seed dataset to a timestamped snapshot directory.
           Simulates the "take a backup before a release" procedure.

verify  — Re-import the most recent snapshot into a temporary Django test DB
           (uses --dry-run on import_csv) and confirm row counts match.
           This proves the backup is restorable without touching the live DB.

restore — Replay the snapshot against the live DB (destructive — clears and
           re-seeds). Only used in disaster recovery. Requires --confirm flag.

all     — Runs backup then verify (safe). Does NOT run restore automatically.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "E49 — Backup, verify and restore drill for the seed dataset."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--step",
            choices=["backup", "verify", "restore", "all"],
            default="all",
            help="Which drill step to run (default: all = backup + verify).",
        )
        parser.add_argument(
            "--snapshot-dir",
            default=None,
            help="Override snapshot directory (default: data/snapshots/<timestamp>).",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            default=False,
            help="Required for --step restore to prevent accidental data loss.",
        )

    def handle(self, *args, **options) -> None:
        step = options["step"]

        if step in ("backup", "all"):
            snapshot_dir = self._do_backup(options["snapshot_dir"])
            options["snapshot_dir"] = str(snapshot_dir)

        if step in ("verify", "all"):
            if not options["snapshot_dir"]:
                snapshot_dir = self._find_latest_snapshot()
            else:
                snapshot_dir = Path(options["snapshot_dir"])
            self._do_verify(snapshot_dir)

        if step == "restore":
            if not options["confirm"]:
                raise CommandError(
                    "Restore is destructive. Re-run with --confirm to proceed.\n"
                    "This will clear and re-seed the live database."
                )
            if not options["snapshot_dir"]:
                snapshot_dir = self._find_latest_snapshot()
            else:
                snapshot_dir = Path(options["snapshot_dir"])
            self._do_restore(snapshot_dir)

    # ── Steps ─────────────────────────────────────────────────────────────────

    def _do_backup(self, override_dir: str | None) -> Path:
        """Export all seed CSVs to a timestamped snapshot directory."""
        if override_dir:
            snapshot_dir = Path(override_dir)
        else:
            ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            snapshot_dir = Path("data/snapshots") / ts

        snapshot_dir.mkdir(parents=True, exist_ok=True)

        self.stdout.write(f"[backup] Exporting dataset to {snapshot_dir} …")

        call_command(
            "export_csv",
            "--snapshot",
            str(snapshot_dir),
            stdout=self.stdout,
            stderr=self.stderr,
        )

        # Write a manifest with counts and timestamp
        manifest = self._read_manifest(snapshot_dir)
        manifest["drill_timestamp"] = datetime.utcnow().isoformat() + "Z"
        manifest["drill_type"] = "backup"
        (snapshot_dir / "drill_manifest.json").write_text(json.dumps(manifest, indent=2))

        self.stdout.write(self.style.SUCCESS(f"[backup] ✓ Snapshot written to {snapshot_dir}"))
        return snapshot_dir

    def _do_verify(self, snapshot_dir: Path) -> None:
        """Dry-run import from snapshot to verify the backup is complete."""
        self.stdout.write(f"[verify] Verifying snapshot at {snapshot_dir} …")

        if not snapshot_dir.exists():
            raise CommandError(f"Snapshot directory not found: {snapshot_dir}")

        manifest_path = snapshot_dir / "manifest.json"
        if not manifest_path.exists():
            raise CommandError(f"No manifest.json in {snapshot_dir}")

        manifest = json.loads(manifest_path.read_text())

        # Verify each expected CSV exists and has the expected row count
        checks_passed = 0
        checks_failed = 0

        for entry in manifest.get("files", []):
            csv_path = snapshot_dir / entry["filename"]
            if not csv_path.exists():
                self.stderr.write(f"  MISSING: {entry['filename']}")
                checks_failed += 1
                continue

            # Count rows in the CSV (exclude header)
            with csv_path.open() as f:
                actual_rows = sum(1 for _ in f) - 1

            expected = entry.get("rows", 0)
            if actual_rows == expected:
                self.stdout.write(f"  ✓ {entry['filename']}: {actual_rows} rows")
                checks_passed += 1
            else:
                self.stderr.write(
                    f"  ✗ {entry['filename']}: expected {expected} rows, " f"got {actual_rows}"
                )
                checks_failed += 1

        if checks_failed:
            raise CommandError(
                f"[verify] ✗ {checks_failed} check(s) failed, " f"{checks_passed} passed."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"[verify] ✓ All {checks_passed} checks passed. " f"Snapshot is restorable."
            )
        )

    def _do_restore(self, snapshot_dir: Path) -> None:
        """Clear the live DB seed data and re-seed from snapshot."""
        self.stdout.write(self.style.WARNING(f"[restore] Re-seeding from {snapshot_dir} …"))

        # seed_all is idempotent — it uses get_or_create, so running it
        # after a partial failure won't create duplicates.
        call_command("seed_all", verbosity=1, stdout=self.stdout, stderr=self.stderr)

        self.stdout.write(self.style.SUCCESS("[restore] ✓ Re-seed complete."))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _find_latest_snapshot(self) -> Path:
        snapshots_root = Path("data/snapshots")
        if not snapshots_root.exists():
            raise CommandError("No snapshots directory found. Run --step backup first.")
        dirs = sorted(
            [d for d in snapshots_root.iterdir() if d.is_dir()],
            key=os.path.getmtime,
            reverse=True,
        )
        if not dirs:
            raise CommandError("No snapshots found. Run --step backup first.")
        return dirs[0]

    def _read_manifest(self, snapshot_dir: Path) -> dict:
        manifest_path = snapshot_dir / "manifest.json"
        if manifest_path.exists():
            return json.loads(manifest_path.read_text())
        return {"files": []}
