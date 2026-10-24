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

# Structured JSON logging in production
LOGGING["handlers"]["console"]["formatter"] = "json"  # noqa: F405
