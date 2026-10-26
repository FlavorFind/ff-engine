"""
E48 — Security headers middleware.

Adds security response headers to every response:
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - Referrer-Policy: strict-origin-when-cross-origin
  - Permissions-Policy: camera=(), microphone=(), geolocation=()
  - Cache-Control: no-store (for API endpoints only — /v1/* paths)

Django's SecurityMiddleware already handles HSTS and SSL redirect in
production. This middleware adds the headers that are not covered by
Django's built-in security middleware.
"""

from __future__ import annotations


class SecurityHeadersMiddleware:
    """
    Inject security headers on every HTTP response.

    Headers are set conservatively — they do not override headers already
    set by the view (e.g. the search endpoint sets its own Cache-Control).
    """

    _API_PATH_PREFIX = "/v1/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Always set these
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("X-Frame-Options", "DENY")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )

        # API endpoints: default to no-store if the view didn't set Cache-Control
        if request.path.startswith(self._API_PATH_PREFIX):
            response.setdefault("Cache-Control", "no-store")

        return response
