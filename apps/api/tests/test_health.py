"""Tests for health and version endpoints — E3 exit criteria."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def client():
    return APIClient()


@pytest.mark.django_db
def test_health_returns_200(client):
    """Health endpoint must return 200 when DB is reachable."""
    response = client.get(reverse("health"))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "ok"
    assert response.data["database"] == "ok"


@pytest.mark.django_db
def test_version_returns_engine_and_dataset_version(client):
    """Version endpoint returns engine version, dataset version and API version."""
    response = client.get(reverse("version"))
    assert response.status_code == status.HTTP_200_OK
    assert "engine_version" in response.data
    assert "dataset_version" in response.data
    assert response.data["api_version"] == "v1"


@pytest.mark.django_db
def test_health_no_auth_required(client):
    """Health and version endpoints must be public — no API key needed."""
    response = client.get(reverse("health"))
    assert response.status_code != status.HTTP_401_UNAUTHORIZED
    assert response.status_code != status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_version_reads_from_db_dataset_release(client):
    """Version endpoint must return the version from the latest DatasetRelease, not settings."""
    from apps.curation.models import DatasetRelease

    DatasetRelease.objects.create(version="2026.10.test", notes="test release")
    response = client.get(reverse("version"))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["dataset_version"] == "2026.10.test"
