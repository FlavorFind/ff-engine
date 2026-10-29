"""Production settings."""

from .base import *  # noqa: F401, F403

DEBUG = False

# Render terminates TLS at the load balancer — don't redirect inside the app.
# SECURE_PROXY_SSL_HEADER tells Django to trust the X-Forwarded-Proto header
# that Render sets so request.is_secure() works correctly.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = False  # Render handles this at the edge

# Security headers
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = ["https://ff-engine-kuar.onrender.com"]

# CORS — only the internal test console origin is allowed in production.
# Add more origins via the CORS_ALLOWED_ORIGINS environment variable.
CORS_ALLOWED_ORIGINS = env.list(  # type: ignore[misc]  # noqa: F405
    "CORS_ALLOWED_ORIGINS",
    default=["https://ff-engine-kuar.onrender.com"],
)
CORS_ALLOW_ALL_ORIGINS = False

# Structured JSON logging in production
LOGGING["handlers"]["console"]["formatter"] = "json"  # noqa: F405

# Static files — served by Whitenoise with compression and long-lived cache headers
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


# Cache — use LocMemCache when Redis is not available (e.g. Render free tier).
# LocMemCache is per-process and resets on restart, but it is sufficient for
# rate-limiting and short-lived search caching on the free tier.
# Set REDIS_URL to a real Redis instance to upgrade automatically.
def _make_cache_config():  # noqa: E302
    _redis_url = env("REDIS_URL", default="")  # noqa: F405
    if not _redis_url or _redis_url.startswith("redis://localhost"):
        return {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "ffengine-locmem",
            }
        }
    return {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _redis_url,
            "KEY_PREFIX": "ffengine",
            "TIMEOUT": 300,
        }
    }


CACHES = _make_cache_config()
