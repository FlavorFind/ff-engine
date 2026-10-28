"""
E52 — Community submission intake tests.

POST /v1/internal/submissions/ accepts dish/ingredient/pairing drafts from
partner apps. Requires the internal:curation API key scope.

Coverage:
  - Valid payload creates a CommunitySubmission with status=pending
  - All three submission types (dish/ingredient/pairing) accepted
  - Submitting client is recorded
  - Without internal:curation scope → 403
  - Without any API key → 401
  - Invalid submission_type / empty payload / missing field → 400
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.clients.keys import create_key
from apps.clients.models import ApiClient, ApiKey
from apps.curation.models import CommunitySubmission


def _make_key(scopes: list[str], name: str) -> tuple[APIClient, ApiClient]:
    """Create an ApiClient + key with the given scopes; return an authed APIClient."""
    client_rec = ApiClient.objects.create(name=name)
    _, raw_key = create_key(client_rec, scopes=scopes)
    api = APIClient()
    api.credentials(HTTP_X_API_KEY=raw_key)
    return api, client_rec


VALID_PAYLOAD = {"name": "Test Dish", "ingredients": ["tomato", "onion"]}


@pytest.mark.django_db
class TestSubmissionIntake:
    def test_valid_submission_creates_pending_submission(self):
        api, client_rec = _make_key([ApiKey.SCOPE_INTERNAL_CURATION], "_e52-valid")
        resp = api.post(
            "/v1/internal/submissions/",
            data={"submission_type": "dish", "payload": VALID_PAYLOAD},
            format="json",
        )
        assert resp.status_code == 201, resp.content
        data = resp.json()
        assert data["submission_type"] == "dish"
        assert data["status"] == "pending"

        sub = CommunitySubmission.objects.get()
        assert sub.status == CommunitySubmission.SubmissionStatus.PENDING
        assert sub.submission_type == "dish"
        assert sub.payload == VALID_PAYLOAD
        assert sub.submitter_client_id == client_rec.id
        assert str(sub.id) == data["id"]

    @pytest.mark.parametrize("stype", ["dish", "ingredient", "pairing"])
    def test_all_submission_types_accepted(self, stype):
        api, _ = _make_key([ApiKey.SCOPE_INTERNAL_CURATION], f"_e52-type-{stype}")
        resp = api.post(
            "/v1/internal/submissions/",
            data={"submission_type": stype, "payload": {"x": 1}},
            format="json",
        )
        assert resp.status_code == 201
        assert CommunitySubmission.objects.filter(submission_type=stype).exists()

    def test_submitter_note_optional(self):
        api, _ = _make_key([ApiKey.SCOPE_INTERNAL_CURATION], "_e52-note")
        resp = api.post(
            "/v1/internal/submissions/",
            data={
                "submission_type": "dish",
                "payload": {"x": 1},
                "submitter_note": "From hotel partner",
            },
            format="json",
        )
        assert resp.status_code == 201
        assert CommunitySubmission.objects.get().submitter_note == "From hotel partner"


@pytest.mark.django_db
class TestSubmissionAuth:
    def test_wrong_scope_returns_403(self):
        api, _ = _make_key([ApiKey.SCOPE_READ_SEARCH], "_e52-search")
        resp = api.post(
            "/v1/internal/submissions/",
            data={"submission_type": "dish", "payload": {"x": 1}},
            format="json",
        )
        assert resp.status_code == 403
        assert CommunitySubmission.objects.count() == 0

    def test_no_key_returns_401(self):
        api = APIClient()
        resp = api.post(
            "/v1/internal/submissions/",
            data={"submission_type": "dish", "payload": {"x": 1}},
            format="json",
        )
        assert resp.status_code == 401
        assert CommunitySubmission.objects.count() == 0


@pytest.mark.django_db
class TestSubmissionValidation:
    def test_invalid_submission_type_returns_400(self):
        api, _ = _make_key([ApiKey.SCOPE_INTERNAL_CURATION], "_e52-badtype")
        resp = api.post(
            "/v1/internal/submissions/",
            data={"submission_type": "invalid", "payload": {"x": 1}},
            format="json",
        )
        assert resp.status_code == 400
        assert CommunitySubmission.objects.count() == 0

    def test_empty_payload_returns_400(self):
        api, _ = _make_key([ApiKey.SCOPE_INTERNAL_CURATION], "_e52-empty")
        resp = api.post(
            "/v1/internal/submissions/",
            data={"submission_type": "dish", "payload": {}},
            format="json",
        )
        assert resp.status_code == 400
        assert CommunitySubmission.objects.count() == 0

    def test_missing_submission_type_returns_400(self):
        api, _ = _make_key([ApiKey.SCOPE_INTERNAL_CURATION], "_e52-missing")
        resp = api.post(
            "/v1/internal/submissions/",
            data={"payload": {"x": 1}},
            format="json",
        )
        assert resp.status_code == 400
        assert CommunitySubmission.objects.count() == 0

    def test_missing_payload_returns_400(self):
        api, _ = _make_key([ApiKey.SCOPE_INTERNAL_CURATION], "_e52-nopayload")
        resp = api.post(
            "/v1/internal/submissions/",
            data={"submission_type": "dish"},
            format="json",
        )
        assert resp.status_code == 400
        assert CommunitySubmission.objects.count() == 0
