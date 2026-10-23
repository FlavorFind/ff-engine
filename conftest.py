"""
Root conftest.py — pytest-django configuration.

DJANGO_SETTINGS_MODULE is also declared in pyproject.toml [tool.pytest.ini_options]
so pytest picks it up automatically. This file exists to ensure the setting is
available for any tool that discovers conftest.py directly (e.g. VS Code Test Explorer).
"""

import os


def pytest_configure(config):
    """Called by pytest before collection begins."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
    os.environ.setdefault(
        "DATABASE_URL", "postgres://ff_engine:ff_engine_pass@localhost:5432/ff_engine_test"
    )
