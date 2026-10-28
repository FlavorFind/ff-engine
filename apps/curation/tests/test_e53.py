"""
E53 — publish_release management command tests.

publish_release creates a DatasetRelease, invalidates the search cache for
the previous version, and logs to ChangeLog. It is gated behind step-up 2FA
via --confirm-stepup.

Coverage:
  - Valid version + --confirm-stepup creates a DatasetRelease with counts
  - The release is logged to ChangeLog (action=create)
  - Without --confirm-stepup the command refuses (SystemExit code 1)
  - --dry-run creates nothing (and bypasses the step-up gate)
  - Invalid version format raises CommandError
  - Duplicate version raises CommandError
  - Version not newer than the latest raises CommandError
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.curation.models import ChangeLog, DatasetRelease


def _publish(version: str, **opts) -> None:
    """Run publish_release with quiet IO defaults."""
    opts.setdefault("verbosity", 0)
    call_command(
        "publish_release",
        version,
        stdout=StringIO(),
        stderr=StringIO(),
        **opts,
    )


@pytest.mark.django_db
class TestPublishRelease:
    def test_valid_release_creates_datasetrelease(self):
        assert DatasetRelease.objects.count() == 0
        _publish("2099.01.0", confirm_stepup=True, notes="test release")
        rel = DatasetRelease.objects.get(version="2099.01.0")
        assert rel.notes == "test release"
        # Counts must be present for every tracked entity
        for key in ("dishes", "ingredients", "pairings", "substitutions"):
            assert key in rel.counts

    def test_release_logs_to_changelog(self):
        _publish("2099.02.0", confirm_stepup=True)
        assert ChangeLog.objects.filter(object_type="DatasetRelease", action="create").exists()

    def test_refuses_without_confirm_stepup(self):
        with pytest.raises(SystemExit) as exc_info:
            _publish("2099.03.0", notes="x")
        assert exc_info.value.code == 1
        assert not DatasetRelease.objects.filter(version="2099.03.0").exists()

    def test_dry_run_creates_nothing(self):
        before = DatasetRelease.objects.count()
        _publish("2099.04.0", dry_run=True, confirm_stepup=True)
        assert DatasetRelease.objects.count() == before

    def test_dry_run_bypasses_stepup_gate(self):
        """--dry-run does not require --confirm-stepup (it creates nothing)."""
        before = DatasetRelease.objects.count()
        _publish("2099.05.0", dry_run=True)
        assert DatasetRelease.objects.count() == before


@pytest.mark.django_db
class TestPublishReleaseValidation:
    @pytest.mark.parametrize("bad", ["v1.0.0", "2026.11", "2026.11.0.1", "abc", "2026.13", ""])
    def test_invalid_version_raises_commanderror(self, bad):
        with pytest.raises(CommandError):
            _publish(bad, confirm_stepup=True)

    def test_duplicate_version_raises_commanderror(self):
        _publish("2099.06.0", confirm_stepup=True)
        with pytest.raises(CommandError):
            _publish("2099.06.0", confirm_stepup=True)

    def test_version_not_newer_than_latest_raises_commanderror(self):
        _publish("2099.10.0", confirm_stepup=True)
        with pytest.raises(CommandError):
            _publish("2099.01.0", confirm_stepup=True)
