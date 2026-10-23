"""Test settings — fast, isolated, no external services."""

from .base import *  # noqa: F401, F403

DEBUG = False

# Use a fast password hasher in tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Disable Sentry in tests
SENTRY_DSN = ""

# Use in-memory cache in tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Celery runs tasks synchronously in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

LOGGING["root"]["level"] = "WARNING"  # noqa: F405
