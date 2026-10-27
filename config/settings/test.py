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

# E59c — Per-statement timeout to prevent runaway queries from hanging the suite.
# 5 seconds is generous for any single query in the test suite; a query that
# takes longer is almost certainly a missing index or an accidental full-table scan.
DATABASES["default"].setdefault("OPTIONS", {})  # noqa: F405
DATABASES["default"]["OPTIONS"]["options"] = "-c statement_timeout=5000"  # noqa: F405
