"""
E8 tests — Two-factor authentication and roles.

Pass criterion: login without a second factor is impossible.

Test categories
---------------
1. CustomUser model — role field defaults, helpers, str representation.
2. Admin 2FA enforcement — a user with correct password but no verified OTP
   device cannot access any admin page.
3. Role checks — curator / reviewer / admin helper properties.
4. Migration sanity — CustomUser is the AUTH_USER_MODEL.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


# ---------------------------------------------------------------------------
# 1. CustomUser model
# ---------------------------------------------------------------------------


class TestCustomUserModel(TestCase):
    def test_role_defaults_to_curator(self):
        user = User(username="alice", password="x")
        assert user.role == "curator"

    def test_str_includes_username_and_role(self):
        user = User(username="bob", role="reviewer")
        assert "bob" in str(user)
        assert "Reviewer" in str(user)

    def test_is_curator_property(self):
        user = User(username="c", role="curator")
        assert user.is_curator is True
        assert user.is_reviewer is False
        assert user.is_admin_role is False

    def test_is_reviewer_property(self):
        user = User(username="r", role="reviewer")
        assert user.is_reviewer is True
        assert user.is_curator is False
        assert user.is_admin_role is False

    def test_is_admin_role_property(self):
        user = User(username="a", role="admin")
        assert user.is_admin_role is True
        assert user.is_curator is False
        assert user.is_reviewer is False

    def test_role_choices_are_complete(self):
        choices = {c[0] for c in User.Role.choices}
        assert choices == {"curator", "reviewer", "admin"}

    @pytest.mark.django_db
    def test_create_user_persists_role(self):
        user = User.objects.create_user(username="diana", password="pass1234", role="reviewer")
        refreshed = User.objects.get(pk=user.pk)
        assert refreshed.role == "reviewer"


# ---------------------------------------------------------------------------
# 2. Admin 2FA enforcement
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAdminRequires2FA(TestCase):
    """
    The admin site uses AdminSiteOTPRequired.
    A user who has authenticated with only a password (no OTP device verified)
    must be redirected away from every admin URL — they must not see admin content.
    """

    def setUp(self):
        self.client = Client()
        self.staff_user = User.objects.create_user(
            username="staffer",
            password="correctpassword123",
            is_staff=True,
            role="admin",
        )

    def _admin_url(self, path=""):
        return f"/admin/{path}"

    def test_unauthenticated_user_cannot_reach_admin(self):
        response = self.client.get(self._admin_url())
        # Must redirect (to the 2FA login page, not serve admin)
        assert response.status_code in (301, 302)

    def test_password_only_login_cannot_reach_admin(self):
        """
        A staff user who logs in with only a password (no OTP) should be
        redirected away from /admin/ — not served the admin index.
        """
        # Log in via session (password only — no OTP device set up)
        logged_in = self.client.login(username="staffer", password="correctpassword123")
        assert logged_in, "Client.login() should succeed with correct credentials"

        response = self.client.get(self._admin_url())
        # AdminSiteOTPRequired redirects users without verified OTP
        assert response.status_code in (
            301,
            302,
        ), f"Expected redirect for password-only login, got {response.status_code}"
        # Must not see admin HTML
        assert b"Site administration" not in response.content

    def test_password_only_login_cannot_reach_admin_subpage(self):
        self.client.login(username="staffer", password="correctpassword123")
        response = self.client.get(self._admin_url("accounts/customuser/"))
        assert response.status_code in (301, 302)
        assert b"Select user to change" not in response.content

    def test_2fa_login_page_is_accessible(self):
        """The 2FA login page itself must be reachable (not protected by OTP)."""
        response = self.client.get(reverse("two_factor:login"))
        assert response.status_code == 200

    def test_wrong_password_cannot_reach_admin(self):
        self.client.login(username="staffer", password="wrongpassword")
        response = self.client.get(self._admin_url())
        assert response.status_code in (301, 302)


# ---------------------------------------------------------------------------
# 3. Role checks
# ---------------------------------------------------------------------------


class TestRoleHelpers(TestCase):
    """Role properties are mutually exclusive."""

    def _user(self, role):
        return User(username="x", role=role)

    def test_only_one_role_property_true_at_a_time(self):
        for role in ("curator", "reviewer", "admin"):
            user = self._user(role)
            props = {
                "is_curator": user.is_curator,
                "is_reviewer": user.is_reviewer,
                "is_admin_role": user.is_admin_role,
            }
            true_count = sum(1 for v in props.values() if v)
            assert true_count == 1, (
                f"Role '{role}' should set exactly one property True, got {props}"
            )

    def test_invalid_role_value_all_helpers_false(self):
        """
        If somehow an invalid value ends up in the role field, none of the
        helpers should raise — they should all return False.
        """
        user = User(username="x", role="unknown")
        assert user.is_curator is False
        assert user.is_reviewer is False
        assert user.is_admin_role is False


# ---------------------------------------------------------------------------
# 4. AUTH_USER_MODEL is wired correctly
# ---------------------------------------------------------------------------


class TestAuthUserModelConfig(TestCase):
    def test_get_user_model_returns_custom_user(self):
        from apps.accounts.models import CustomUser

        assert User is CustomUser

    def test_custom_user_has_role_field(self):
        field_names = [f.name for f in User._meta.get_fields()]
        assert "role" in field_names
