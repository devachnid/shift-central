import datetime as dt

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from tests import clock

User = get_user_model()


def _ticking_from(instant):
    real = timezone.now
    started = real()

    def now():
        return instant.astimezone(dt.timezone.utc) + (real() - started)
    return now


def _at_nine(day):
    return dt.datetime.combine(day, dt.time(9, 0), tzinfo=clock.LONDON)


@pytest.fixture(autouse=True)
def pinned_clock(request, monkeypatch):
    """django.utils.timezone.now (and so localdate, localtime and every
    auto_now field) reads tests.clock.PIN, ticking on from it, or 09:00 on
    the day a test's @pytest.mark.today(day) names."""
    marker = request.node.get_closest_marker("today")
    instant = _at_nine(marker.args[0]) if marker else clock.PIN
    monkeypatch.setattr(timezone, "now", _ticking_from(instant))


@pytest.fixture
def today(monkeypatch):
    """Move the clock in the middle of a test: today(date(2027, 2, 1))."""
    def pin(day):
        monkeypatch.setattr(timezone, "now", _ticking_from(_at_nine(day)))
    return pin


@pytest.fixture(autouse=True)
def mail_relay(settings):
    """A relay is configured, as on the practice's box; the test runner's
    locmem backend still catches every message. A test of the unconfigured
    case sets EMAIL_HOST back to empty."""
    settings.EMAIL_HOST = "smtp.example.org"


@pytest.fixture(autouse=True)
def on_commit_runs_when_no_savepoint(monkeypatch):
    """The test's own transaction stands in for "no transaction open": an
    on_commit callback registered with no atomic block of the code's own
    open runs at once, as it does in production; one registered inside a
    nested atomic block waits (use django_capture_on_commit_callbacks)."""
    from django.db import transaction
    real = transaction.on_commit

    def on_commit(func, using=None, robust=False):
        if transaction.get_connection(using).savepoint_ids:
            return real(func, using, robust)
        return func()

    monkeypatch.setattr(transaction, "on_commit", on_commit)


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(email="root@example.org", password="pw")


@pytest.fixture
def root_client(superuser):
    client = Client()
    client.force_login(superuser)
    return client


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(email="sam@example.org")


@pytest.fixture
def staff_client(staff_user):
    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture
def all_teams_user(db):
    return User.objects.create_user(email="boss@example.org", is_all_teams_manager=True)


@pytest.fixture
def all_teams_client(all_teams_user):
    client = Client()
    client.force_login(all_teams_user)
    return client


@pytest.fixture
def oidc_on(settings):
    settings.PRACTICE_HR_URL = "https://hr.example"
    settings.OIDC_RP_CLIENT_ID = "abc"


@pytest.fixture
def push_on(settings, tmp_path):
    """Web push configured, as on the practice's box (no real key needed:
    the sender is always faked in tests)."""
    key = tmp_path / "vapid.pem"
    key.write_text("test key")
    settings.VAPID_PRIVATE_KEY_FILE = str(key)
    settings.VAPID_PUBLIC_KEY = "BPublicKeyForTests"
    settings.VAPID_SUBJECT = "mailto:test@example.org"
