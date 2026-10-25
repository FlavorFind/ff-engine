"""
E36 — API key authentication.

Clients send their key in the X-API-Key header:
    X-API-Key: ffk_<40 hex chars>

Authentication flow:
    1. Extract the raw key from the header.
    2. Derive the 8-char prefix for a fast indexed lookup.
    3. Hash the raw key and compare against the stored hash.
    4. Reject if key not found, hash mismatch, client inactive, or revoked.
    5. Update last_used_at and attach the key to request.auth.

The authenticated "user" is a synthetic AnonymousUser subclass that
carries the ApiKey. This keeps DRF's permission system working without
requiring a Django user account for every API caller.
"""

import logging

from django.contrib.auth.models import AnonymousUser
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from apps.clients.keys import extract_prefix, hash_key

logger = logging.getLogger(__name__)

API_KEY_HEADER = "HTTP_X_API_KEY"


class ApiKeyUser(AnonymousUser):
    """
    Synthetic user object attached to authenticated API requests.

    DRF checks request.user.is_authenticated to decide whether to
    run IsAuthenticated permission checks — we return True here so
    that views protected by IsAuthenticated work correctly.
    """

    def __init__(self, api_key):
        self.api_key = api_key

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def __str__(self):
        return f"ApiKeyUser({self.api_key.client.name})"


class APIKeyAuthentication(BaseAuthentication):
    """
    DRF authentication class for X-API-Key header.

    Returns (ApiKeyUser, api_key) on success, None if no header present
    (letting other authenticators run or the request fall through to
    IsAuthenticated which will then deny it).
    """

    def authenticate(self, request):
        raw_key = request.META.get(API_KEY_HEADER)
        if not raw_key:
            # No key provided — let DRF fall through to permission checks.
            return None

        return self._validate_key(raw_key)

    def _validate_key(self, raw_key: str):
        from apps.clients.models import ApiKey

        prefix = extract_prefix(raw_key)
        key_hash = hash_key(raw_key)

        try:
            api_key = (
                ApiKey.objects.select_related("client")
                .filter(prefix=prefix, hashed_key=key_hash)
                .get()
            )
        except ApiKey.DoesNotExist:
            raise AuthenticationFailed("Invalid API key.") from None
        except ApiKey.MultipleObjectsReturned:
            # Should never happen due to the unique constraint, but be safe.
            logger.error("Multiple API keys found for prefix %s — investigate immediately", prefix)
            raise AuthenticationFailed("Invalid API key.") from None

        if not api_key.client.active:
            raise AuthenticationFailed("API client is inactive.")

        if api_key.is_revoked:
            raise AuthenticationFailed("API key has been revoked.")

        # Update last_used_at without a full model save
        api_key.touch()

        return ApiKeyUser(api_key), api_key

    def authenticate_header(self, request):
        return "X-API-Key"
