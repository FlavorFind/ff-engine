"""
Creates a superuser from environment variables if one does not exist.

Required env vars:
  DJANGO_SUPERUSER_USERNAME
  DJANGO_SUPERUSER_EMAIL
  DJANGO_SUPERUSER_PASSWORD

Safe to run multiple times — skips if the user already exists.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create superuser from env vars if one does not exist"

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD "
                    "not set — skipping superuser creation"
                )
            )
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f"Superuser '{username}' already exists — skipping")
            )
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created"))
