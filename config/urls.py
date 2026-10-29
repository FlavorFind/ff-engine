"""Root URL configuration."""

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from two_factor.urls import urlpatterns as tf_urls


def home(request):
    """Simple landing page for the engine root."""
    html = (
        "<!DOCTYPE html>"
        "<html lang='en'><head>"
        "<meta charset='UTF-8'/>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'/>"
        "<title>FlavorFind Engine</title>"
        "<style>"
        "*{box-sizing:border-box;margin:0;padding:0}"
        "body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
        "background:#0f172a;color:#f1f5f9;min-height:100vh;"
        "display:flex;align-items:center;justify-content:center}"
        ".card{text-align:center;padding:3rem 2.5rem;background:#1e293b;"
        "border-radius:1rem;border:1px solid #334155;max-width:480px;width:90%}"
        ".dot{display:inline-block;width:12px;height:12px;background:#22c55e;"
        "border-radius:50%;animation:pulse 2s infinite;margin-right:8px}"
        "@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}"
        ".status{display:flex;align-items:center;justify-content:center;"
        "font-size:.9rem;color:#22c55e;font-weight:600;margin-bottom:1.5rem}"
        "h1{font-size:1.8rem;font-weight:700;margin-bottom:.5rem;color:#f97316}"
        "p{color:#94a3b8;margin-bottom:2rem;line-height:1.6}"
        ".links{display:flex;gap:.75rem;justify-content:center;flex-wrap:wrap}"
        "a{padding:.5rem 1.25rem;border-radius:.5rem;text-decoration:none;"
        "font-size:.875rem;font-weight:500;transition:opacity .2s}"
        "a:hover{opacity:.8}"
        ".primary{background:#f97316;color:#fff}"
        ".secondary{background:#1e40af;color:#fff}"
        ".ghost{border:1px solid #475569;color:#94a3b8}"
        ".version{margin-top:2rem;font-size:.75rem;color:#475569}"
        "</style></head><body>"
        "<div class='card'>"
        "<div class='status'><span class='dot'></span> Server is running</div>"
        "<h1>FlavorFind Engine</h1>"
        "<p>East African recipe matching API.<br>"
        "Find dishes you can make from ingredients you have.</p>"
        "<div class='links'>"
        "<a href='/docs/' class='primary'>API Docs</a>"
        "<a href='/v1/health/' class='secondary'>Health Check</a>"
        "<a href='/v1/schema/?format=json' class='ghost'>OpenAPI Schema</a>"
        "</div>"
        "<div class='version'>v1.0.0 &middot; staging</div>"
        "</div>"
        "</body></html>"
    )
    return HttpResponse(html)


urlpatterns = [
    # Root landing page
    path("", home, name="home"),
    # Two-factor auth login (replaces the standard Django login).
    # Mounted at "" so login URL stays /account/login/ as per tf_urls default.
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
