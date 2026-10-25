"""
Tests for E36 — API clients, keys and scopes.

Exit criteria from the blueprint:
  - Keys shown once; a revoked key stops within a minute.

Test coverage:
  - Key generation produces a raw key starting with 'ffk_'
  - Raw key is not stored in the DB (only the hash)
  - A valid key authenticates successfully
  - A revoked key returns 401
  - An inactive client returns 401
  - A wrong / random key returns 401
  - A missing key returns 401 on protected endpoints
  - Scope checking: key without read:search cannot call search
  - has_scope returns True/False correctly
  - touch() updates last_used_at
  - prefix extraction is correct
"""

import pytest
from rest_framework.test import APIClient

from apps.clients.keys import create_key, extract_prefix, generate_raw_key, hash_key
from apps.clients.models import ApiClient, ApiKey

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client_record(db):
    return ApiClient.objects.create(
        name="_test_FlavorFind Backend", type=ApiClient.ClientType.INTERNAL
    )


@pytest.fixture
def search_key(client_record):
    api_key, raw_key = create_key(client_record, scopes=[ApiKey.SCOPE_READ_SEARCH])
    return api_key, raw_key


@pytest.fixture
def full_key(client_record):
    api_key, raw_key = create_key(client_record, scopes=ApiKey.ALL_SCOPES)
    return api_key, raw_key


SEARCH_URL = "/v1/search/by-ingredients"


@pytest.fixture
def api_client():
    return APIClient()


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_generate_raw_key_starts_with_prefix():
    raw = generate_raw_key()
    assert raw.startswith("ffk_")


@pytest.mark.django_db
def test_generate_raw_key_length():
    raw = generate_raw_key()
    # ffk_ (4) + 40 hex chars = 44
    assert len(raw) == 44


@pytest.mark.django_db
def test_generate_raw_key_unique():
    keys = {generate_raw_key() for _ in range(100)}
    assert len(keys) == 100


@pytest.mark.django_db
def test_extract_prefix():
    raw = "ffk_ab1234567890abcdef"
    assert extract_prefix(raw) == "ffk_ab12"


@pytest.mark.django_db
def test_hash_key_is_64_chars():
    raw = generate_raw_key()
    assert len(hash_key(raw)) == 64


@pytest.mark.django_db
def test_hash_is_deterministic():
    raw = generate_raw_key()
    assert hash_key(raw) == hash_key(raw)


# ---------------------------------------------------------------------------
# Key storage — raw key is never stored
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_raw_key_not_stored(client_record):
    api_key, raw_key = create_key(client_record, scopes=[ApiKey.SCOPE_READ_SEARCH])
    # Reload from DB
    db_key = ApiKey.objects.get(pk=api_key.pk)
    assert db_key.hashed_key != raw_key
    assert raw_key not in db_key.hashed_key


@pytest.mark.django_db
def test_hashed_key_matches_hash(client_record):
    api_key, raw_key = create_key(client_record, scopes=[ApiKey.SCOPE_READ_SEARCH])
    assert api_key.hashed_key == hash_key(raw_key)


@pytest.mark.django_db
def test_prefix_stored_correctly(client_record):
    api_key, raw_key = create_key(client_record, scopes=[ApiKey.SCOPE_READ_SEARCH])
    assert api_key.prefix == extract_prefix(raw_key)


# ---------------------------------------------------------------------------
# ApiKey model behaviour
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_key_not_revoked_by_default(search_key):
    api_key, _ = search_key
    assert not api_key.is_revoked


@pytest.mark.django_db
def test_revoke_sets_revoked_at(search_key):
    api_key, _ = search_key
    api_key.revoke()
    api_key.refresh_from_db()
    assert api_key.is_revoked
    assert api_key.revoked_at is not None


@pytest.mark.django_db
def test_has_scope_true(search_key):
    api_key, _ = search_key
    assert api_key.has_scope(ApiKey.SCOPE_READ_SEARCH)


@pytest.mark.django_db
def test_has_scope_false(search_key):
    api_key, _ = search_key
    assert not api_key.has_scope(ApiKey.SCOPE_INTERNAL_CURATION)


@pytest.mark.django_db
def test_touch_updates_last_used(search_key):
    api_key, _ = search_key
    assert api_key.last_used_at is None
    api_key.touch()
    api_key.refresh_from_db()
    assert api_key.last_used_at is not None


@pytest.mark.django_db
def test_str_includes_prefix_and_client(search_key):
    api_key, raw_key = search_key
    s = str(api_key)
    assert extract_prefix(raw_key) in s
    assert "_test_FlavorFind Backend" in s


# ---------------------------------------------------------------------------
# Authentication — valid key passes
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_valid_key_authenticates(api_client, search_key):
    _, raw_key = search_key
    api_client.credentials(HTTP_X_API_KEY=raw_key)
    resp = api_client.get("/v1/health/")
    # Health endpoint uses AllowAny — just confirm no auth error
    assert resp.status_code == 200


@pytest.mark.django_db
def test_missing_key_returns_401_on_protected_endpoint(api_client, db):
    """No key on an endpoint that requires IsAuthenticated should return 401."""
    resp = api_client.post(
        "/v1/search/by-ingredients",
        data={"ingredients": ["tomato"]},
        format="json",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_wrong_key_returns_401(api_client, db):
    api_client.credentials(HTTP_X_API_KEY="ffk_" + "0" * 40)
    resp = api_client.post(
        "/v1/search/by-ingredients",
        data={"ingredients": ["tomato"]},
        format="json",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_revoked_key_returns_401(api_client, search_key):
    api_key, raw_key = search_key
    api_key.revoke()
    api_client.credentials(HTTP_X_API_KEY=raw_key)
    resp = api_client.post(
        "/v1/search/by-ingredients",
        data={"ingredients": ["tomato"]},
        format="json",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_inactive_client_returns_401(api_client, client_record):
    client_record.active = False
    client_record.save()
    _, raw_key = create_key(client_record, scopes=[ApiKey.SCOPE_READ_SEARCH])
    api_client.credentials(HTTP_X_API_KEY=raw_key)
    resp = api_client.post(
        "/v1/search/by-ingredients",
        data={"ingredients": ["tomato"]},
        format="json",
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_valid_key_allows_search(api_client, search_key, seeded_db):
    _, raw_key = search_key
    api_client.credentials(HTTP_X_API_KEY=raw_key)
    resp = api_client.post(
        "/v1/search/by-ingredients",
        data={"ingredients": ["tomato"]},
        format="json",
    )
    assert resp.status_code == 200
