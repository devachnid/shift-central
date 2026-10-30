"""GP sessions from the rota app: replaced in full for the fetched window,
matched by email to GPs, never raising, never logging an address."""

import json
import logging
from datetime import date, datetime, timedelta, timezone as tz
from pathlib import Path

import pytest
from django.test import Client

from people.models import SyncRun
from shifts.models import GpSession
from shifts.services import gp_sync
from shifts.services.gp_client import GpClient, GpError
from tests.factories import make_gp_session, make_person, make_user_for

pytestmark = pytest.mark.django_db
FIXTURE = Path(__file__).parent / "fixtures" / "gp_sessions.json"
NOW = datetime(2027, 1, 5, 12, tzinfo=tz.utc)


class FakeClient:
    def __init__(self, payload=None, error=None):
        self.payload = payload if payload is not None else json.loads(FIXTURE.read_text())
        self.error = error
        self.calls = []

    def sessions(self, start, end):
        self.calls.append((start, end))
        if self.error:
            raise self.error
        return self.payload


@pytest.fixture
def doc():
    return make_person(first_name="Doc", email="doc@example.org", is_gp=True)


def test_sessions_are_matched_by_email_case_insensitively_and_gps_only(doc):
    make_person(first_name="Sam", email="sam.1@example.org", is_gp=False)
    run = gp_sync.sync(FakeClient(), now=NOW)
    assert run.ok and run.source == "gp-rota" and run.people_seen == 1
    rows = list(GpSession.objects.filter(person=doc).order_by("day", "part"))
    assert [(r.day, r.part, r.label, r.site, r.note) for r in rows] == [
        (date(2027, 1, 4), "AM", "Surgery", "AG", ""), (date(2027, 1, 4), "PM", "Admin", "", "paperwork"),
        (date(2027, 1, 5), "AM", "Surgery", "PMC", "")]
    assert run.detail == {"unmatched": ["nobody@example.org", "sam.1@example.org"], "without_email": 1}
    assert run.message == "2 emails unmatched; 1 clinician without an email"


def test_the_window_is_eight_weeks_back_to_fifty_two_ahead(doc):
    client = FakeClient()
    gp_sync.sync(client, now=NOW)
    assert client.calls == [(date(2027, 1, 5) - timedelta(weeks=8), date(2027, 1, 5) + timedelta(weeks=52))]


def test_the_window_is_replaced_in_full_and_nothing_outside_it_is_touched(doc):
    inside = make_gp_session(doc, date(2027, 1, 7), "AM")
    outside = make_gp_session(doc, date(2020, 1, 1), "AM")
    gp_sync.sync(FakeClient(), now=NOW)
    assert not GpSession.objects.filter(pk=inside.pk).exists()
    assert GpSession.objects.filter(pk=outside.pk).exists()
    assert GpSession.objects.filter(person=doc).count() == 4


def _feed_with(*extra):
    payload = json.loads(FIXTURE.read_text())
    payload["sessions"] = payload["sessions"] + list(extra)
    return payload


def test_duplicate_entries_for_one_slot_keep_the_first_and_are_counted(doc):
    again = {"email": "Doc@example.org", "day": "2027-01-04", "part": "AM", "type": "Other", "site": "X", "note": ""}
    run = gp_sync.sync(FakeClient(_feed_with(again, again)), now=NOW)
    assert run.ok and run.people_seen == 1
    assert GpSession.objects.filter(person=doc).count() == 3
    first = GpSession.objects.get(person=doc, day=date(2027, 1, 4), part="AM")
    assert (first.label, first.site) == ("Surgery", "AG")
    assert run.detail["duplicates"] == 2
    assert run.message == "2 emails unmatched; 1 clinician without an email; 2 duplicate sessions"
    assert gp_sync.sync(FakeClient(_feed_with(again)), now=NOW).ok


def test_a_record_outside_the_window_is_skipped_and_the_next_run_still_succeeds(doc):
    past_end = date(2027, 1, 5) + timedelta(weeks=52, days=1)
    late = {"email": "doc@example.org", "day": past_end.isoformat(), "part": "AM", "type": "Surgery", "site": "", "note": ""}
    run = gp_sync.sync(FakeClient(_feed_with(late)), now=NOW)
    assert run.ok and run.detail["outside_window"] == 1
    assert run.message == "2 emails unmatched; 1 clinician without an email; 1 session outside the window"
    assert not GpSession.objects.filter(day=past_end).exists()
    assert GpSession.objects.filter(person=doc).count() == 3
    again = gp_sync.sync(FakeClient(_feed_with(late)), now=NOW)
    assert again.ok and GpSession.objects.filter(person=doc).count() == 3


def test_a_failed_fetch_keeps_the_data_and_never_logs_an_address(doc, caplog):
    make_gp_session(doc, date(2027, 1, 7), "AM")
    with caplog.at_level(logging.WARNING):
        run = gp_sync.sync(FakeClient(error=GpError("GP rota returned 503")), now=NOW)
    assert not run.ok and run.message == "GP rota returned 503"
    assert GpSession.objects.count() == 1
    assert "example.org" not in caplog.text


def test_a_bad_payload_is_a_failed_run_not_a_crash(doc):
    run = gp_sync.sync(FakeClient(payload={"sessions": [{"email": "doc@example.org", "day": "nope"}]}), now=NOW)
    assert not run.ok and "day" in run.message and "doc@" not in run.message


def test_last_run_and_configured(doc, settings):
    settings.ROTA_URL, settings.ROTA_API_TOKEN = "", ""
    assert not gp_sync.configured() and gp_sync.last_run() is None
    gp_sync.sync(FakeClient(), now=NOW)
    SyncRun.objects.create(source="practice-hr", ok=True)
    assert gp_sync.last_run().source == "gp-rota"
    assert gp_sync.unmatched() == ["nobody@example.org", "sam.1@example.org"]


def test_the_client_refuses_plain_http_and_sends_the_token(settings):
    settings.DEBUG = False
    with pytest.raises(GpError):
        GpClient("http://rota.example", "t").sessions(date(2027, 1, 1), date(2027, 1, 2))
    seen = {}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return b'{"from": "2027-01-01", "to": "2027-01-02", "sessions": [], "without_email": 0}'

    def opener(req):
        seen["url"], seen["auth"] = req.full_url, req.get_header("Authorization")
        return Resp()
    body = GpClient("https://rota.example", "t0k", opener=opener).sessions(date(2027, 1, 1), date(2027, 1, 2))
    assert body["sessions"] == [] and seen["auth"] == "Bearer t0k"
    assert seen["url"] == "https://rota.example/api/v1/sessions?from=2027-01-01&to=2027-01-02"


def test_the_health_card_shows_the_gp_feed(doc):
    gp_sync.sync(FakeClient(), now=NOW)
    c = Client()
    c.force_login(make_user_for(make_person(first_name="Boss"), is_all_teams_manager=True))
    body = c.get("/staff/").content.decode()
    assert "GP rota" in body and "not matched here" in body and "nobody@example.org" in body


def test_the_command_refuses_to_run_unconfigured(settings):
    from django.core.management import CommandError, call_command
    settings.ROTA_URL, settings.ROTA_API_TOKEN = "", ""
    with pytest.raises(CommandError):
        call_command("gp_sync")
