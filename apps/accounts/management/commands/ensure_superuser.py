"""
Creates a superuser from environment variables if one does not exist,
and attaches a StaticDevice so the mandatory 2FA check passes on staging.

Required env vars:
  DJANGO_SUPERUSER_USERNAME
  DJANGO_SUPERUSER_EMAIL
  DJANGO_SUPERUSER_PASSWORD

Optional env var:
  DJANGO_SUPERUSER_OTP_TOKEN  (default: "000000")
    The static token used for 2FA login on staging.
    After first login, go to /admin/ and enroll a real TOTP device,
    then remove this env var.

Safe to run multiple times — skips if the user already exists.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create superuser + static OTP device from env vars (staging setup)"

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get("DJANGO_SUPERUSER_USERNAME")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        otp_token = os.environ.get("DJANGO_SUPERUSER_OTP_TOKEN", "000000")

        if not username or not password:
            self.stdout.write(
                self.style.WARNING(
                    "DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD "
                    "not set — skipping superuser creation"
                )
            )
            return

        # ------------------------------------------------------------------
        # Create the user if missing
        # ------------------------------------------------------------------
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "role": "admin",
            },
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' created"))
        else:
            self.stdout.write(
                self.style.WARNING(f"Superuser '{username}' already exists — skipping creation")
            )

        # ------------------------------------------------------------------
        # Ensure a StaticDevice exists so 2FA login works on staging.
        # StaticDevice tokens are one-time use. We add it only if the user
        # has NO verified device at all (fresh staging setup).
        # ------------------------------------------------------------------
        try:
            from django_otp.plugins.otp_static.models import StaticDevice, StaticToken

            if not StaticDevice.objects.filter(user=user, confirmed=True).exists():
                device = StaticDevice.objects.create(
                    user=user,
                    name="Staging bootstrap device",
                    confirmed=True,
                )
                StaticToken.objects.create(device=device, token=otp_token)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Static OTP device created — login token: {otp_token}\n"
                        "  After logging in, go to /admin/ → Users → your account\n"
                        "  and enroll a real TOTP device (Google Authenticator).\n"
                        "  Then delete the DJANGO_SUPERUSER_OTP_TOKEN env var."
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"User '{username}' already has a verified OTP device — skipping"
                    )
                )
        except ImportError:
            self.stdout.write(self.style.ERROR("django_otp not installed — OTP device not created"))
