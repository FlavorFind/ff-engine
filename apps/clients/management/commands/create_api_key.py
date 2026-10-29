"""
Management command to create an API client and key without shell access.

Usage:
    python manage.py create_api_key --client verify-kit --scopes read:search read:catalog

This is useful on platforms like Render (free tier) where interactive
shell access is not available.

The raw key is printed to stdout ONCE — copy it immediately.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.clients.keys import create_key
from apps.clients.models import ApiClient, ApiKey


class Command(BaseCommand):
    help = "Create an API client and generate a key for it (prints raw key to stdout)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--client",
            required=True,
            help="Name for the API client (e.g. 'verify-kit')",
        )
        parser.add_argument(
            "--type",
            default="test",
            choices=[c[0] for c in ApiClient.ClientType.choices],
            help="Client type (default: test)",
        )
        parser.add_argument(
            "--scopes",
            nargs="+",
            default=["read:search"],
            choices=ApiKey.ALL_SCOPES,
            help="Scopes to grant (default: read:search)",
        )
        parser.add_argument(
            "--rate-limit",
            type=int,
            default=60,
            help="Requests per minute; 0 = unlimited (default: 60)",
        )
        parser.add_argument(
            "--revoke",
            action="store_true",
            default=False,
            help="Immediately revoke the key after creation (for testing revoked-key behaviour)",
        )
        parser.add_argument(
            "--or-existing",
            action="store_true",
            default=False,
            help=(
                "If a client with this name already exists, create a new key for it "
                "rather than failing (default: fail if client already exists)"
            ),
        )

    def handle(self, *args, **options):
        client_name = options["client"]
        client_type = options["type"]
        scopes = options["scopes"]
        rate_limit = options["rate_limit"]
        revoke = options["revoke"]
        or_existing = options["or_existing"]

        if or_existing:
            client, created = ApiClient.objects.get_or_create(
                name=client_name,
                defaults={"type": client_type, "active": True},
            )
        else:
            if ApiClient.objects.filter(name=client_name).exists():
                raise CommandError(
                    f"ApiClient '{client_name}' already exists. "
                    "Use --or-existing to generate a new key for it anyway."
                )
            client = ApiClient.objects.create(
                name=client_name,
                type=client_type,
                active=True,
            )
            created = True

        _, raw_key = create_key(client, scopes=scopes, rate_limit=rate_limit)

        if revoke:
            from django.utils import timezone

            ApiKey.objects.filter(client=client, prefix=raw_key[:8]).update(
                revoked_at=timezone.now()
            )

        action = "Created" if created else "Found existing"
        self.stdout.write(self.style.SUCCESS(f"{action} client: {client_name}"))
        self.stdout.write(self.style.SUCCESS(f"Scopes: {', '.join(scopes)}"))
        self.stdout.write(self.style.SUCCESS(f"Rate limit: {rate_limit} req/min (0=unlimited)"))
        if revoke:
            self.stdout.write(self.style.WARNING("Key was immediately revoked."))
        self.stdout.write("")
        # Print the key on its own line so it's easy to copy/grep
        self.stdout.write(raw_key)
