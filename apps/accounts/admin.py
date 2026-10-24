"""Admin configuration for the accounts app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from two_factor.admin import AdminSiteOTPRequired

from .models import CustomUser

# Replace the default admin site with one that enforces OTP on every login.
# Any user who has not verified a second factor is redirected to the 2FA
# login flow — they cannot reach any admin page without completing TOTP.
admin.site.__class__ = AdminSiteOTPRequired


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Admin for CustomUser — adds the role field to the standard user admin."""

    list_display = ("username", "email", "role", "is_staff", "is_active", "date_joined")
    list_filter = ("role", "is_staff", "is_active")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    fieldsets = UserAdmin.fieldsets + (  # type: ignore[operator]
        (
            "Role",
            {
                "fields": ("role",),
                "description": "Controls what this user can do in the curation workflow.",
            },
        ),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (  # type: ignore[operator]
        (
            "Role",
            {
                "fields": ("role",),
            },
        ),
    )
