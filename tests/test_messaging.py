"""One sender for every email the app will ever send: an Outbox row per
message, sent or not, and nothing raised."""

import pytest
from django.core import mail

from messaging.models import Outbox
from messaging.services import send
from tests.factories import make_person

pytestmark = pytest.mark.django_db


def test_a_message_is_sent_and_recorded():
    p = make_person()
    row = send(p, "Your rota has changed", "Tue 3 Mar: 08:00-16:15")
    assert len(mail.outbox) == 1 and mail.outbox[0].to == [p.email]
    assert row.sent_at and row.error == "" and row.to_person == p and row.to_email == p.email
    assert Outbox.objects.count() == 1


def test_a_failure_is_recorded_without_the_body_and_nothing_raises(settings, monkeypatch):
    def boom(*a, **kw):
        raise OSError("relay down: secret-body")
    monkeypatch.setattr("messaging.services.send_mail", boom)
    row = send(make_person(), "Subject", "the body")
    assert row.sent_at is None and row.error.startswith("OSError") and "body" not in row.error


def test_a_person_without_an_email_gets_a_row_that_says_so():
    p = make_person(email="")
    row = send(p, "Subject", "the body")
    assert row.sent_at is None and row.error == "no email address"
