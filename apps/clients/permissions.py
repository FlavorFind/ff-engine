"""
E36 — Scope-based permission class for API key authentication.

Usage on a view::

    from apps.clients.permissions import HasScope
    from apps.clients.models import ApiKey

    @permission_classes([HasScope(ApiKey.SCOPE_READ_SEARCH)])
    def my_view(request):
        ...

Or on a class-based view::

    class MyView(APIView):
        permission_classes = [HasScope(ApiKey.SCOPE_READ_SEARCH)]
"""

from rest_framework.permissions import BasePermission

from apps.clients.authentication import ApiKeyUser


def HasScope(required_scope: str):  # noqa: N802 — factory styled as a class
    """
    Return a DRF permission class that requires the authenticated API key
    to carry *required_scope*.

    Returns 403 if the key is authenticated but lacks the scope.
    Returns 401 (via IsAuthenticated fallback) if not authenticated at all.
    """

    class _HasScope(BasePermission):
        message = f"API key does not have the required scope: {required_scope!r}."

        def has_permission(self, request, view):
            if not isinstance(request.user, ApiKeyUser):
                # Not authenticated via API key — let IsAuthenticated handle the 401.
                return False
            return request.user.api_key.has_scope(required_scope)

    _HasScope.__name__ = f"HasScope({required_scope!r})"
    return _HasScope
