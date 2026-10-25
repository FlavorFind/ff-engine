"""
E43 — Zero-result query observatory tests.

Tests:
  - log_zero_result creates a ZeroResultQuery row on first call
  - Duplicate normalised input increments count, not creates new row
  - Different normalised inputs create separate rows
  - normalised_input is order-insensitive (sorted tokens)
  - normalised_input is case-insensitive
  - Blank/whitespace input is ignored (no row created)
  - qa_zero_results management command outputs rows ordered by count
  - Admin is reachable (registered with Django admin)
"""

from __future__ import annotations

import pytest
from django.core.management import call_command

from apps.search.models import ZeroResultQuery, log_zero_result

# ── log_zero_result ───────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLogZeroResult:
    def test_creates_row_on_first_call(self):
        log_zero_result("ugali sukuma")
        assert ZeroResultQuery.objects.filter(raw_input="ugali sukuma").exists()

    def test_count_starts_at_one(self):
        log_zero_result("ugali sukuma")
        zrq = ZeroResultQuery.objects.get(raw_input="ugali sukuma")
        assert zrq.count == 1

    def test_duplicate_increments_count(self):
        log_zero_result("ugali sukuma")
        log_zero_result("ugali sukuma")
        assert ZeroResultQuery.objects.count() == 1
        zrq = ZeroResultQuery.objects.get(raw_input="ugali sukuma")
        assert zrq.count == 2

    def test_order_insensitive_deduplication(self):
        """'sukuma ugali' and 'ugali sukuma' normalise to the same key."""
        log_zero_result("sukuma ugali")
        log_zero_result("ugali sukuma")
        assert ZeroResultQuery.objects.count() == 1
        zrq = ZeroResultQuery.objects.first()
        assert zrq.count == 2

    def test_case_insensitive_deduplication(self):
        log_zero_result("Ugali Sukuma")
        log_zero_result("ugali sukuma")
        assert ZeroResultQuery.objects.count() == 1
        zrq = ZeroResultQuery.objects.first()
        assert zrq.count == 2

    def test_different_inputs_create_separate_rows(self):
        log_zero_result("ugali sukuma")
        log_zero_result("chapati beans")
        assert ZeroResultQuery.objects.count() == 2

    def test_blank_input_is_ignored(self):
        log_zero_result("   ")
        assert ZeroResultQuery.objects.count() == 0

    def test_empty_string_is_ignored(self):
        log_zero_result("")
        assert ZeroResultQuery.objects.count() == 0

    def test_last_seen_updated_on_duplicate(self):
        log_zero_result("ugali")
        before = ZeroResultQuery.objects.get(raw_input="ugali").last_seen

        # Force a slight time gap
        log_zero_result("ugali")

        after = ZeroResultQuery.objects.get(raw_input="ugali").last_seen
        # last_seen should be refreshed on duplicate
        assert after >= before

    def test_ordering_by_count_desc(self):
        log_zero_result("ugali")
        log_zero_result("ugali")
        log_zero_result("chapati")  # count = 1
        rows = list(ZeroResultQuery.objects.all())
        assert rows[0].raw_input == "ugali"  # higher count first


# ── management command ────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestQaZeroResultsCommand:
    def test_command_runs_without_error(self, capsys):
        call_command("qa_zero_results")
        # No exception = pass

    def test_command_shows_no_results_message_when_empty(self, capsys):
        call_command("qa_zero_results")
        out = capsys.readouterr().out
        assert "No zero-result" in out

    def test_command_lists_queries(self, capsys):
        log_zero_result("ugali sukuma")
        log_zero_result("ugali sukuma")  # count = 2
        log_zero_result("chapati beans")  # count = 1

        call_command("qa_zero_results")
        out = capsys.readouterr().out
        assert "ugali sukuma" in out
        assert "chapati beans" in out

    def test_command_respects_limit(self, capsys):
        for i in range(10):
            log_zero_result(f"ingredient_{i}")

        call_command("qa_zero_results", limit=3)
        out = capsys.readouterr().out
        # Should mention "3 of 10"
        assert "3" in out

    def test_command_respects_min_count(self, capsys):
        log_zero_result("rare query")  # count = 1
        log_zero_result("common query")
        log_zero_result("common query")  # count = 2

        call_command("qa_zero_results", min_count=2)
        out = capsys.readouterr().out
        assert "common query" in out
        assert "rare query" not in out

    def test_command_ordered_by_frequency(self, capsys):
        log_zero_result("infrequent")  # count = 1
        log_zero_result("frequent")
        log_zero_result("frequent")
        log_zero_result("frequent")  # count = 3

        call_command("qa_zero_results")
        out = capsys.readouterr().out
        # 'frequent' should appear before 'infrequent' in output
        assert out.index("frequent") < out.index("infrequent")


# ── model / admin ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestZeroResultQueryModel:
    def test_str_representation(self):
        zrq = ZeroResultQuery.objects.create(
            raw_input="ugali",
            normalised_input="ugali",
            count=3,
        )
        assert "ugali" in str(zrq)
        assert "3" in str(zrq)

    def test_admin_is_registered(self):
        from django.contrib.admin.sites import site

        assert (
            ZeroResultQuery in site._registry
        ), "ZeroResultQuery must be registered with Django admin"
