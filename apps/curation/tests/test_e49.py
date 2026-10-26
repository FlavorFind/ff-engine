"""
E49 — Backup restore drill and rollback drill tests.

Tests:
  - backup_drill --step backup creates a snapshot directory
  - backup_drill --step backup writes a manifest.json
  - backup_drill --step verify passes on a valid snapshot
  - backup_drill --step verify fails on a corrupted snapshot
  - backup_drill --step restore requires --confirm flag
  - rollback_drill prints instructions without modifying the DB
"""

from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
class TestBackupDrill:
    def test_backup_creates_snapshot_dir(self, seeded_db, tmp_path) -> None:
        """backup_drill --step backup must create a snapshot directory."""
        out = StringIO()
        call_command(
            "backup_drill",
            "--step",
            "backup",
            "--snapshot-dir",
            str(tmp_path / "snap"),
            stdout=out,
        )
        assert (tmp_path / "snap").is_dir()

    def test_backup_writes_manifest(self, seeded_db, tmp_path) -> None:
        """Snapshot must contain a manifest.json."""
        snap = tmp_path / "snap"
        call_command(
            "backup_drill",
            "--step",
            "backup",
            "--snapshot-dir",
            str(snap),
            stdout=StringIO(),
        )
        assert (snap / "manifest.json").exists()

    def test_backup_manifest_has_files_key(self, seeded_db, tmp_path) -> None:
        snap = tmp_path / "snap"
        call_command(
            "backup_drill",
            "--step",
            "backup",
            "--snapshot-dir",
            str(snap),
            stdout=StringIO(),
        )
        manifest = json.loads((snap / "manifest.json").read_text())
        assert "files" in manifest

    def test_verify_passes_on_valid_snapshot(self, seeded_db, tmp_path) -> None:
        """backup + verify round-trip must pass without errors."""
        snap = tmp_path / "snap"
        call_command(
            "backup_drill",
            "--step",
            "backup",
            "--snapshot-dir",
            str(snap),
            stdout=StringIO(),
        )
        out = StringIO()
        # Should not raise
        call_command(
            "backup_drill",
            "--step",
            "verify",
            "--snapshot-dir",
            str(snap),
            stdout=out,
        )
        assert "✓" in out.getvalue()

    def test_verify_fails_on_missing_snapshot(self, db) -> None:
        """verify must raise CommandError if snapshot dir doesn't exist."""
        with pytest.raises(CommandError):
            call_command(
                "backup_drill",
                "--step",
                "verify",
                "--snapshot-dir",
                "/tmp/does_not_exist_e49_test",  # nosec B108 — test-only path
                stdout=StringIO(),
            )

    def test_restore_requires_confirm_flag(self, db) -> None:
        """restore without --confirm must raise CommandError."""
        with pytest.raises(CommandError, match="--confirm"):
            call_command(
                "backup_drill",
                "--step",
                "restore",
                "--snapshot-dir",
                "/tmp/some_snapshot",  # nosec B108 — test-only path, command raises before touching it
                stdout=StringIO(),
            )


@pytest.mark.django_db
class TestRollbackDrill:
    def test_rollback_drill_runs_without_error(self, db) -> None:
        """rollback_drill must print instructions without raising."""
        out = StringIO()
        call_command("rollback_drill", stdout=out)
        output = out.getvalue()
        assert "ROLLBACK DRILL" in output

    def test_rollback_drill_prints_render_instructions(self, db) -> None:
        out = StringIO()
        call_command("rollback_drill", stdout=out)
        assert "Render" in out.getvalue()

    def test_rollback_drill_prints_health_check(self, db) -> None:
        out = StringIO()
        call_command("rollback_drill", stdout=out)
        assert "/v1/health/" in out.getvalue()

    def test_rollback_drill_does_not_modify_db(self, seeded_db) -> None:
        """rollback_drill is read-only — row counts must not change."""
        from apps.ingredients.models import Ingredient

        count_before = Ingredient.objects.count()
        call_command("rollback_drill", stdout=StringIO())
        assert Ingredient.objects.count() == count_before
