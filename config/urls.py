"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from two_factor.urls import urlpatterns as tf_urls

urlpatterns = [
    # Two-factor auth login (replaces the standard Django login).
    # Must come before admin/ so the admin login redirect lands here.
    path("", include(tf_urls, namespace="two_factor")),
    # Django admin — protected by AdminSiteOTPRequired (see accounts/admin.py)
    path("admin/", admin.site.urls),
    # API v1
    path("v1/", include("apps.api.urls")),
    # OpenAPI schema and docs
    path("v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("schema/", SpectacularAPIView.as_view(), name="schema-root"),  # legacy
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

# Debug toolbar in dev
from django.conf import settings  # noqa: E402

if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass
