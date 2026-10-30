"""
E36 + E38 — Admin for ApiClient, ApiKey, UsageRecord, RequestLog.

Key workflow:
  - Create a client, then use the "Generate new key" action on the
    client change page to produce a key.
  - The raw key is shown ONCE in a message banner — it cannot be
    retrieved later.
  - Keys can be revoked via the "Revoke selected keys" bulk action.
"""

from django.contrib import admin, messages
from django.utils.html import format_html

from apps.clients.keys import create_key
from apps.clients.models import ApiClient, ApiKey, RequestLog, UsageRecord


class ApiKeyInline(admin.TabularInline):
    model = ApiKey
    extra = 0
    readonly_fields = (
        "prefix",
        "scopes",
        "rate_limit",
        "created_at",
        "last_used_at",
        "revoked_at",
        "status_badge",
    )
    fields = readonly_fields
    can_delete = False
    show_change_link = True

    def status_badge(self, obj):
        if obj.is_revoked:
            return format_html('<span style="color:red;">Revoked</span>')
        return format_html('<span style="color:green;">Active</span>')

    status_badge.short_description = "Status"


@admin.register(ApiClient)
class ApiClientAdmin(admin.ModelAdmin):
    list_display = ["name", "type", "active", "key_count", "created_at"]
    list_filter = ["type", "active"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [ApiKeyInline]
    actions = ["generate_read_search_key", "generate_full_key"]

    def key_count(self, obj):
        return obj.keys.filter(revoked_at__isnull=True).count()

    key_count.short_description = "Active keys"

    @admin.action(description="Generate read:search key for selected clients")
    def generate_read_search_key(self, request, queryset):
        self._generate_keys(request, queryset, scopes=[ApiKey.SCOPE_READ_SEARCH])

    @admin.action(description="Generate full access key for selected clients")
    def generate_full_key(self, request, queryset):
        self._generate_keys(request, queryset, scopes=ApiKey.ALL_SCOPES)

    def _generate_keys(self, request, queryset, scopes):
        for client in queryset:
            _, raw_key = create_key(client, scopes=scopes)
            self.message_user(
                request,
                format_html(
                    "<strong>{}</strong> — new key (shown once, copy it now):<br>"
                    "<code style='font-size:1.1em;'>{}</code>",
                    client.name,
                    raw_key,
                ),
                level=messages.WARNING,
            )


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = [
        "prefix",
        "client",
        "scopes_display",
        "rate_limit",
        "is_revoked",
        "last_used_at",
        "created_at",
    ]
    list_filter = ["client", "revoked_at"]
    search_fields = ["prefix", "client__name"]
    readonly_fields = [
        "id",
        "prefix",
        "hashed_key",
        "created_at",
        "last_used_at",
        "revoked_at",
    ]
    fieldsets = (
        ("Key Info", {"fields": ("id", "prefix", "hashed_key")}),
        ("Configuration", {"fields": ("client", "scopes", "rate_limit")}),
        ("Status", {"fields": ("created_at", "last_used_at", "revoked_at")}),
    )
    actions = ["revoke_keys"]

    def scopes_display(self, obj):
        return ", ".join(obj.scopes) if obj.scopes else "—"

    scopes_display.short_description = "Scopes"

    def is_revoked(self, obj):
        return obj.is_revoked

    is_revoked.boolean = True
    is_revoked.short_description = "Revoked"

    @admin.action(description="Revoke selected keys")
    def revoke_keys(self, request, queryset):
        count = 0
        for key in queryset.filter(revoked_at__isnull=True):
            key.revoke()
            count += 1
        self.message_user(request, f"{count} key(s) revoked.")


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ["client", "endpoint", "date", "calls", "errors", "p95_ms"]
    list_filter = ["client", "endpoint", "date"]
    search_fields = ["client__name", "endpoint"]
    ordering = ["-date", "client__name"]
    readonly_fields = ["client", "endpoint", "date", "calls", "errors", "p95_ms"]
    date_hierarchy = "date"


@admin.register(RequestLog)
class RequestLogAdmin(admin.ModelAdmin):
    list_display = ["client", "endpoint", "status_code", "response_ms", "logged_at"]
    list_filter = ["client", "endpoint", "status_code"]
    search_fields = ["client__name", "endpoint"]
    ordering = ["-logged_at"]
    readonly_fields = ["client", "endpoint", "status_code", "response_ms", "logged_at"]
    date_hierarchy = "logged_at"
