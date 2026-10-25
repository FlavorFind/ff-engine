"""
E42 — OpenAPI extension for APIKeyAuthentication.

Registers the X-API-Key header auth scheme with drf-spectacular so
that 'spectacular --validate --fail-on-warn' does not warn about an
unresolvable authenticator.
"""

from __future__ import annotations

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class APIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    """Tell spectacular how to document our X-API-Key header auth."""

    target_class = "apps.clients.authentication.APIKeyAuthentication"
    name = "ApiKeyAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": (
                "API key passed in the X-API-Key header. "
                "Keys are issued per client, scoped (read:search, read:catalog, "
                "internal:curation), and stored hashed. "
                "A revoked key is rejected immediately with 401."
            ),
        }
