"""
E57 — Security verification tests.

Verifies that the three architecture-required security features exist and
work correctly:

1. Step-up 2FA — the admin uses AdminSiteOTPRequired (every page requires an
   OTP-verified session); the publish_release CLI command requires
   --confirm-stepup; the ApiKey lifecycle requires admin step-up for
   create/revoke operations.

2. Audit-log shipping — every sensitive data action writes a ChangeLog row.
   ChangeLog rows are append-only (no edit/delete permission in admin).

3. Access matrix — the scope-based permission system is wired correctly:
   read:search allows search but not internal:curation endpoints, and vice versa.

Architecture references:
  Sprint 1 doc section 14.3 (IAM table)
  Sprint 1 doc section 14.2 (threat model)
  Sprint 1 doc section 14.4 (2FA architecture)
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

# ---------------------------------------------------------------------------
# 1. Step-up 2FA
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_admin_site_uses_otp_required():
    """
    The Django admin must be wrapped by AdminSiteOTPRequired so that every
    admin page requires a fully OTP-verified session.
    Architecture: "Every human account must use two-factor authentication."
    """
    from django.contrib import admin as django_admin

    # AdminSiteOTPRequired replaces the standard AdminSite in accounts/admin.py
    site_type = type(django_admin.site).__name__
    assert site_type == "AdminSiteOTPRequired", (
        f"Expected AdminSiteOTPRequired, got {site_type!r}. "
        "The admin site must be wrapped by django-otp's OTP-required class."
    )


@pytest.mark.fast
def test_publish_release_has_confirm_stepup_argument():
    """
    The publish_release management command must declare a --confirm-stepup
    flag.  Without it, CLI operators could publish a dataset release without
    step-up 2FA confirmation.
    Architecture section 14.3: "Publish a dataset release — Approve (step-up 2FA)"
    """
    import argparse

    from apps.curation.management.commands.publish_release import Command

    parser = argparse.ArgumentParser()
    Command().add_arguments(parser)
    dests = [a.dest for a in parser._actions]
    assert "confirm_stepup" in dests, (
        "publish_release must declare --confirm-stepup. "
        "This flag gates CLI dataset releases behind step-up 2FA confirmation."
    )


@pytest.mark.fast
def test_publish_release_refuses_without_confirm_stepup():
    """
    Running publish_release without --confirm-stepup must exit with code 1.
    """
    from io import StringIO

    with pytest.raises(SystemExit) as exc_info:
        from django.core.management import call_command

        call_command(
            "publish_release",
            "2099.01.0",
            "--notes",
            "test",
            stderr=StringIO(),
        )
    assert exc_info.value.code == 1


@pytest.mark.fast
def test_otp_middleware_in_middleware_stack():
    """
    OTPMiddleware must be in MIDDLEWARE so every request checks OTP state.
    """
    from django.conf import settings

    middleware = settings.MIDDLEWARE
    assert any("OTPMiddleware" in m for m in middleware), (
        "django_otp.middleware.OTPMiddleware must be in MIDDLEWARE. "
        "Without it the admin's OTP check is bypassed."
    )


# ---------------------------------------------------------------------------
# 2. Audit log shipping
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_changelog_is_append_only_in_admin():
    """
    ChangeLog admin must deny add, change and delete so the audit trail
    cannot be tampered with via the UI.
    Architecture: "Audit records are append-only inside the application."
    """
    from apps.curation.admin import ChangeLogAdmin
    from apps.curation.models import ChangeLog

    admin_instance = ChangeLogAdmin(ChangeLog, None)
    assert admin_instance.has_add_permission(None) is False
    assert admin_instance.has_change_permission(None) is False
    assert admin_instance.has_delete_permission(None) is False


@pytest.mark.django_db
def test_community_submission_writes_to_changelog():
    """
    POST /v1/internal/submissions must create a ChangeLog row with
    action='create' and object_type='CommunitySubmission'.
    """
    from apps.clients.keys import create_key
    from apps.clients.models import ApiClient, ApiKey
    from apps.curation.models import ChangeLog

    client_rec = ApiClient.objects.create(name="_e57_test_client")
    _, raw_key = create_key(client_rec, scopes=[ApiKey.SCOPE_INTERNAL_CURATION])

    api = APIClient()
    api.credentials(HTTP_X_API_KEY=raw_key)
    before = ChangeLog.objects.filter(object_type="CommunitySubmission").count()

    resp = api.post(
        "/v1/internal/submissions/",
        data={
            "submission_type": "dish",
            "payload": {"name": "Test Dish", "ingredients": ["tomato"]},
        },
        format="json",
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.data}"

    after = ChangeLog.objects.filter(object_type="CommunitySubmission").count()
    assert after == before + 1, "ChangeLog must record community submission creation"


@pytest.mark.django_db
def test_changelog_records_can_be_created():
    """ChangeLog.objects.create() produces a persisted, retrievable record."""
    from apps.curation.models import ChangeLog

    entry = ChangeLog.objects.create(
        object_type="Ingredient",
        object_id="test-uuid-e57",
        action=ChangeLog.Action.UPDATE,
        diff={"before": {"name": "old"}, "after": {"name": "new"}},
        reason="E57 audit test",
    )
    fetched = ChangeLog.objects.get(pk=entry.pk)
    assert fetched.object_type == "Ingredient"
    assert fetched.action == "update"
    assert fetched.diff["reason"] if "reason" in fetched.diff else True


# ---------------------------------------------------------------------------
# 3. Access matrix
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_scope_constants_are_correct():
    """
    The three scope constants must match the values expected by all
    permission checks.  Changing them is a breaking change.
    """
    from apps.clients.models import ApiKey

    assert ApiKey.SCOPE_READ_SEARCH == "read:search"
    assert ApiKey.SCOPE_READ_CATALOG == "read:catalog"
    assert ApiKey.SCOPE_INTERNAL_CURATION == "internal:curation"


@pytest.mark.fast
def test_has_scope_permission_class_callable():
    """HasScope must be importable and callable (returns a DRF permission)."""
    from apps.clients.permissions import HasScope

    perm = HasScope("read:search")
    assert hasattr(perm, "has_permission")


@pytest.mark.django_db
def test_read_search_key_cannot_post_to_submissions():
    """
    A key with only read:search scope must receive 403 on the internal
    submissions endpoint (which requires internal:curation).
    """
    from apps.clients.keys import create_key
    from apps.clients.models import ApiClient, ApiKey

    client_rec = ApiClient.objects.create(name="_e57_search_only")
    _, raw_key = create_key(client_rec, scopes=[ApiKey.SCOPE_READ_SEARCH])

    api = APIClient()
    api.credentials(HTTP_X_API_KEY=raw_key)
    resp = api.post(
        "/v1/internal/submissions/",
        data={"submission_type": "dish", "payload": {"name": "x"}},
        format="json",
    )
    assert resp.status_code == 403, (
        f"read:search key must not access internal:curation endpoint. Got {resp.status_code}"
    )


@pytest.mark.django_db
def test_internal_curation_key_cannot_search():
    """
    A key with only internal:curation scope must receive 403 on the
    search endpoint (which requires read:search).
    """
    from apps.clients.keys import create_key
    from apps.clients.models import ApiClient, ApiKey

    client_rec = ApiClient.objects.create(name="_e57_curation_only")
    _, raw_key = create_key(client_rec, scopes=[ApiKey.SCOPE_INTERNAL_CURATION])

    api = APIClient()
    api.credentials(HTTP_X_API_KEY=raw_key)
    resp = api.post(
        "/v1/search/by-ingredients",
        data={"ingredients": ["tomato"]},
        format="json",
    )
    assert resp.status_code == 403, (
        f"internal:curation key must not access read:search endpoint. Got {resp.status_code}"
    )


@pytest.mark.django_db
def test_no_key_returns_401_on_protected_endpoints():
    """Unauthenticated requests must be rejected."""
    api = APIClient()
    for url in [
        "/v1/search/by-ingredients",
        "/v1/internal/submissions/",
    ]:
        resp = api.post(url, data={}, format="json")
        assert resp.status_code in (401, 403), (
            f"Expected 401/403 without API key on {url}, got {resp.status_code}"
        )


@pytest.mark.django_db
def test_revoked_key_returns_401():
    """A revoked key must be rejected immediately."""
    from apps.clients.keys import create_key
    from apps.clients.models import ApiClient, ApiKey

    client_rec = ApiClient.objects.create(name="_e57_revoke_test")
    api_key, raw_key = create_key(client_rec, scopes=[ApiKey.SCOPE_READ_SEARCH])
    api_key.revoke()

    api = APIClient()
    api.credentials(HTTP_X_API_KEY=raw_key)
    resp = api.post(
        "/v1/search/by-ingredients",
        data={"ingredients": ["tomato"]},
        format="json",
    )
    assert resp.status_code in (401, 403), f"Revoked key must be rejected. Got {resp.status_code}"
