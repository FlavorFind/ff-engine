"""
E36 — API key generation and hashing utilities.

Keys are formatted as:  ffk_<40 random hex chars>
  - "ffk_" prefix makes keys easy to identify in logs and code.
  - First 8 characters after "ffk_" are stored as the lookup prefix.
  - The full key is hashed with SHA-256 before storage.

The raw key is returned ONCE at creation time and never retrievable again.
"""

import hashlib
import secrets

KEY_PREFIX = "ffk_"
KEY_RANDOM_BYTES = 20  # 40 hex chars


def generate_raw_key() -> str:
    """
    Generate a new random API key.

    Returns the raw key string — caller must show this to the user
    immediately, as it will not be retrievable after hashing.
    """
    return KEY_PREFIX + secrets.token_hex(KEY_RANDOM_BYTES)


def hash_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of *raw_key*."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def extract_prefix(raw_key: str) -> str:
    """
    Return the 8-character prefix used for fast DB lookup.

    The prefix is the first 8 characters of the key INCLUDING the
    'ffk_' leader, e.g. 'ffk_ab12'.
    """
    return raw_key[:8]


def create_key(client, scopes: list[str], rate_limit: int = 60):
    """
    Create a new ApiKey for *client*, return (api_key_instance, raw_key).

    The raw_key must be shown to the user immediately — it is not stored.
    """
    from apps.clients.models import ApiKey

    raw_key = generate_raw_key()
    api_key = ApiKey.objects.create(
        client=client,
        prefix=extract_prefix(raw_key),
        hashed_key=hash_key(raw_key),
        scopes=scopes,
        rate_limit=rate_limit,
    )
    return api_key, raw_key
