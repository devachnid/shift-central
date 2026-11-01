"""Task 1 of spec 5: the Outbox grows a channel, send takes a link, and the
Activity log knows the labels later tasks write."""

import pytest
from django.test import Client

from messaging import services
from messaging.models import Outbox
from people.services import audit
from tests.factories import client_for, make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


def test_a_sent_email_row_is_on_the_email_channel_with_no_attempts():
    row = services.send(make_person(), "Subject", "Body")
    assert row.channel == Outbox.Channel.EMAIL and row.attempts == 0 and row.url == ""


def test_send_accepts_a_link_without_changing_the_email():
    from django.core import mail
    row = services.send(make_person(), "Subject", "Body", url="/rota/open/")
    assert row.sent_at and len(mail.outbox) == 1 and mail.outbox[0].body == "Body"


def test_absolute_link_uses_the_given_base_else_the_first_trusted_origin(settings):
    settings.CSRF_TRUSTED_ORIGINS = ["https://shifts.example.org"]
    assert services.absolute_link("", "/rota/") == "https://shifts.example.org/rota/"
    assert services.absolute_link("https://x.example/", "/rota/") == "https://x.example/rota/"
    settings.CSRF_TRUSTED_ORIGINS = []
    assert services.absolute_link("", "/rota/") == "/rota/"


def test_batch_yields_nothing_when_no_relay_is_configured(settings):
    settings.EMAIL_HOST = ""
    with services.batch() as connection:
        assert connection is None


def test_batch_opens_one_connection_and_closes_it(monkeypatch):
    calls = []

    class Fake:
        def open(self):
            calls.append("open")

        def close(self):
            calls.append("close")

    monkeypatch.setattr(services, "get_connection", lambda: Fake())
    with services.batch() as connection:
        assert isinstance(connection, Fake)
    assert calls == ["open", "close"]


def test_batch_yields_nothing_when_the_relay_cannot_be_opened(monkeypatch):
    class Broken:
        def open(self):
            raise OSError("down")

        def close(self):
            raise AssertionError("never opened, so never closed")

    monkeypatch.setattr(services, "get_connection", lambda: Broken())
    with services.batch() as connection:
        assert connection is None


def test_client_for_signs_a_person_in():
    p = make_person()
    assert client_for(p).get("/rota/").status_code == 200


def test_the_activity_log_names_the_engagement_rows():
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    user = make_user_for(lead)
    sam = make_person(first_name="Sam", team=team)
    audit.record_as(user, "uploads.personfile", sam.pk, {"added": ("", "Contract")}, note="x")
    audit.record_as(user, "uploads.sharedfile", 7, {"added": ("", "Handbook")}, note="x")
    audit.record_as(user, "shifts.openshift", 3, {"posted": ("", "2026-11-09")}, note="x")
    audit.record_as(user, "messaging.message", 4, {"sent": ("", "to 2 people")}, note="x")
    audit.record_as(user, "messaging.notice", 5, {"posted": ("", "Fire drill")}, note="x")
    client = Client()
    client.force_login(user)
    records = {e.model: e.record for e in client.get("/activity/").context["entries"]}
    assert records["uploads.personfile"] == sam.name
    assert records["uploads.sharedfile"] == "Shared file"
    assert records["shifts.openshift"] == "Open shift"
    assert records["messaging.message"] == "Message"
    assert records["messaging.notice"] == "Notice"
