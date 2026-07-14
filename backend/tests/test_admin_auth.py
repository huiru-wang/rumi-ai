from datetime import datetime, timedelta, timezone

import pytest

from src.admin_auth import AdminAuth, AdminAuthError


def test_admin_auth_issues_and_verifies_session_token():
    auth = AdminAuth("operator", "secret-password", "signing-secret")

    token = auth.login("operator", "secret-password")

    assert auth.verify(token) == "operator"


def test_admin_auth_rejects_wrong_password():
    auth = AdminAuth("operator", "secret-password", "signing-secret")

    with pytest.raises(AdminAuthError):
        auth.login("operator", "wrong-password")


def test_admin_auth_rejects_expired_token():
    now = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
    auth = AdminAuth(
        "operator",
        "secret-password",
        "signing-secret",
        ttl=timedelta(minutes=30),
        now=lambda: now,
    )
    token = auth.login("operator", "secret-password")
    auth.now = lambda: now + timedelta(minutes=31)

    with pytest.raises(AdminAuthError):
        auth.verify(token)


def test_admin_auth_requires_configuration():
    auth = AdminAuth("", "", "")

    with pytest.raises(AdminAuthError):
        auth.login("operator", "secret-password")
