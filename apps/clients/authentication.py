"""API key authentication — full implementation in E36."""

from rest_framework.authentication import BaseAuthentication


class APIKeyAuthentication(BaseAuthentication):
    """
    Placeholder API key authentication.
    Full implementation (hashed keys, scopes, rate limits) in build step E36.
    """

    def authenticate(self, request):
        # Allow all requests through during development.
        # This will be replaced with real key checking in E36.
        return None
