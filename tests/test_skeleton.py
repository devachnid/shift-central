"""The project starts, the user model is email-only, and the root redirects."""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_a_user_is_made_from_an_email_alone():
    u = User.objects.create_user(email="Sam@Example.org")
    assert u.email == "Sam@Example.org" and not u.has_usable_password()
    assert not u.is_all_teams_manager and not u.is_staff and not u.is_superuser


def test_emails_are_unique_ignoring_case():
    from django.db import IntegrityError
    User.objects.create_user(email="sam@example.org")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="SAM@example.org")


def test_a_superuser_can_use_the_admin_and_nobody_else_can(client, superuser, staff_user):
    client.force_login(superuser)
    assert client.get("/admin/").status_code == 200
    client.force_login(staff_user)
    assert client.get("/admin/").status_code in (302, 403)


def test_the_root_sends_a_signed_out_visitor_to_login(client):
    r = client.get("/", follow=False)
    assert r.status_code == 302 and r["Location"].startswith("/accounts/login/")


def test_sessions_last_ten_minutes_from_the_last_request(settings):
    assert settings.SESSION_COOKIE_AGE == 600 and settings.SESSION_SAVE_EVERY_REQUEST is True


def test_signed_in_pages_are_never_cached(staff_client):
    r = staff_client.get("/", follow=True)
    assert "no-store" in r["Cache-Control"]
