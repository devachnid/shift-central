"""The GP leave feed the rota app reads: bearer token, GPs only, approved
only, parts, never a description."""

import logging
from datetime import date, time
from types import SimpleNamespace

import pytest
from django.core.cache import cache

from leave.services import bookings, feed
from tests.factories import make_allowance, make_booking, make_entry, make_gp_session, make_person, make_type, make_user_for

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _fresh_rate_counts(monkeypatch):
    cache.clear()
    monkeypatch.setattr("leave.api_auth.time", SimpleNamespace(time=lambda: 1_800_000_030.0))
    yield
    cache.clear()


@pytest.fixture
def api(client, settings):
    settings.LEAVE_API_TOKENS = frozenset({"t0k"})
    return lambda url: client.get(url, HTTP_AUTHORIZATION="Bearer t0k")


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss")
    make_user_for(boss, is_all_teams_manager=True)
    return boss


def test_token_required_and_no_store(client, settings):
    settings.LEAVE_API_TOKENS = frozenset({"t0k"})
    r = client.get("/api/v1/leave?from=2027-03-01&to=2027-03-07")
    assert r.status_code == 401 and r.headers["WWW-Authenticate"] == "Bearer" and "no-store" in r.headers["Cache-Control"]
    assert client.get("/api/v1/leave?from=2027-03-01&to=2027-03-07", HTTP_AUTHORIZATION="Bearer nope").status_code == 401
    settings.LEAVE_API_TOKENS = frozenset()
    assert client.get("/api/v1/leave?from=2027-03-01&to=2027-03-07", HTTP_AUTHORIZATION="Bearer t0k").status_code == 401


def test_bad_ranges(api):
    assert api("/api/v1/leave?from=x&to=2027-03-07").status_code == 400
    assert api("/api/v1/leave?from=2027-03-07&to=2027-03-01").status_code == 400
    assert api("/api/v1/leave?from=2027-01-01&to=2030-12-31").status_code == 400


def test_range_cap_is_1100_days_inclusive_of_the_limit(api):
    assert api("/api/v1/leave?from=2027-01-01&to=2030-01-05").status_code == 200   # 1100 days after
    assert api("/api/v1/leave?from=2027-01-01&to=2030-01-06").status_code == 400   # 1101
    assert api("/api/v1/leave?to=2027-03-07").status_code == 400
    assert api("/api/v1/leave").status_code == 400


def test_gps_approved_leave_with_parts_and_nothing_else(api, boss):
    doc = make_person(first_name="Doc", email="Doc@Example.org", is_gp=True, start_date=date(2020, 1, 6))
    make_allowance(doc, date(2027, 1, 1), 150, 0)
    make_gp_session(doc, date(2027, 3, 1), "AM")
    make_gp_session(doc, date(2027, 3, 1), "PM")
    make_gp_session(doc, date(2027, 3, 2), "AM")
    bookings.book(boss.user, doc, make_type("Holiday"), date(2027, 3, 1), date(2027, 3, 1), "whole", description="private")
    bookings.book(boss.user, doc, make_type("Training"), date(2027, 3, 2), date(2027, 3, 2), "am")
    bookings.book(boss.user, doc, make_type("Holiday"), date(2027, 3, 3), date(2027, 3, 3), "times", start=time(14), finish=time(16))
    bookings.book(boss.user, doc, make_type("Holiday"), date(2027, 3, 4), date(2027, 3, 4), "times", start=time(9), finish=time(12))
    doc.user = None
    make_user_for(doc)
    bookings.request(doc.user, doc, make_type("Holiday"), date(2027, 3, 5), date(2027, 3, 5), "whole")      # pending: not served
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6))
    make_allowance(sam, date(2027, 1, 1), 100, 0)
    make_entry(sam, date(2027, 3, 1), start=time(9), finish=time(17))
    bookings.book(boss.user, sam, make_type("Holiday"), date(2027, 3, 1), date(2027, 3, 1), "whole")      # not a GP
    body = api("/api/v1/leave?from=2027-03-01&to=2027-03-07").json()
    assert body["from"] == "2027-03-01" and "generated_at" in body
    assert body["leave"] == [
        {"email": "Doc@Example.org", "first_day": "2027-03-01", "last_day": "2027-03-01", "part": "whole", "type": "Holiday"},
        {"email": "Doc@Example.org", "first_day": "2027-03-02", "last_day": "2027-03-02", "part": "am", "type": "Training"},
        {"email": "Doc@Example.org", "first_day": "2027-03-03", "last_day": "2027-03-03", "part": "pm", "type": "Holiday"},
        {"email": "Doc@Example.org", "first_day": "2027-03-04", "last_day": "2027-03-04", "part": "am", "type": "Holiday"},
    ]
    assert "private" not in api("/api/v1/leave?from=2027-03-01&to=2027-03-07").content.decode()


def test_a_timed_booking_across_one_oclock_is_whole_and_the_edges_are_halves():
    doc = make_person(is_gp=True)
    straddle = make_booking(doc, date(2027, 3, 1), part="times", start=time(11), finish=time(15))
    ends_at_one = make_booking(doc, date(2027, 3, 2), part="times", start=time(9), finish=time(13))
    starts_at_one = make_booking(doc, date(2027, 3, 3), part="times", start=time(13), finish=time(17))
    assert [feed.part_of(b) for b in (straddle, ends_at_one, starts_at_one)] == ["whole", "am", "pm"]


def test_records_carry_only_the_five_fields_and_never_a_note_pk_or_name():
    doc = make_person(first_name="Zebedee", last_name="Quillfeather", email="zeb@example.org", is_gp=True)
    make_booking(doc, date(2027, 3, 1), date(2027, 3, 3), description="chemo-appointment", staff_note="confidential-note")
    records = feed.records(date(2027, 3, 1), date(2027, 3, 7))
    assert records == [{"email": "zeb@example.org", "first_day": "2027-03-01", "last_day": "2027-03-03", "part": "whole", "type": "Holiday"}]
    text = repr(records)
    for secret in ("chemo-appointment", "confidential-note", "Zebedee", "Quillfeather"):
        assert secret not in text


def test_only_approved_and_cancel_requested_are_served(api):
    doc = make_person(is_gp=True, email="gp@example.org")
    for status, day in (("approved", 1), ("cancel_requested", 2), ("pending", 3), ("cancelled", 4), ("declined", 5)):
        make_booking(doc, date(2027, 3, day), status=status)
    days = [r["first_day"] for r in api("/api/v1/leave?from=2027-03-01&to=2027-03-07").json()["leave"]]
    assert days == ["2027-03-01", "2027-03-02"]


def test_only_bookings_overlapping_the_window_and_gps_with_an_email(api):
    doc = make_person(is_gp=True, email="gp@example.org")
    make_booking(doc, date(2027, 2, 26), date(2027, 3, 1))          # overlaps the start
    make_booking(doc, date(2027, 3, 7), date(2027, 3, 9))           # overlaps the end
    make_booking(doc, date(2027, 2, 20), date(2027, 2, 28))        # before
    make_booking(doc, date(2027, 3, 8), date(2027, 3, 9))           # after
    nameless = make_person(is_gp=True, email="")
    make_booking(nameless, date(2027, 3, 3))
    nurse = make_person(is_gp=False, email="nurse@example.org")
    make_booking(nurse, date(2027, 3, 3))
    leave = api("/api/v1/leave?from=2027-03-01&to=2027-03-07").json()["leave"]
    assert [(r["first_day"], r["last_day"]) for r in leave] == [("2027-02-26", "2027-03-01"), ("2027-03-07", "2027-03-09")]
    assert {r["email"] for r in leave} == {"gp@example.org"}


def test_a_response_has_no_store_and_json(api):
    r = api("/api/v1/leave?from=2027-03-01&to=2027-03-07")
    assert r.status_code == 200 and "no-store" in r.headers["Cache-Control"] and r.headers["Content-Type"].startswith("application/json")


def test_only_get_and_the_scheme_is_case_insensitive(client, settings):
    settings.LEAVE_API_TOKENS = frozenset({"t0k"})
    url = "/api/v1/leave?from=2027-03-01&to=2027-03-07"
    r = client.post(url, HTTP_AUTHORIZATION="Bearer t0k")
    assert r.status_code == 405 and r.headers["Allow"] == "GET"
    assert client.post(url).status_code == 401
    assert client.get(url, HTTP_AUTHORIZATION="bearer t0k").status_code == 200
    assert client.get(url, HTTP_AUTHORIZATION="Basic t0k").status_code == 401
    assert client.get(url, HTTP_AUTHORIZATION="Bearer ").status_code == 401


def test_a_non_ascii_token_is_refused_not_a_server_error(client, settings):
    settings.LEAVE_API_TOKENS = frozenset({"t0k"})
    assert client.get("/api/v1/leave?from=2027-03-01&to=2027-03-07", HTTP_AUTHORIZATION="Bearer tök").status_code == 401


def test_no_session_and_no_csrf_are_needed(settings):
    from django.test import Client

    settings.LEAVE_API_TOKENS = frozenset({"t0k"})
    strict = Client(enforce_csrf_checks=True)
    r = strict.post("/api/v1/leave", HTTP_AUTHORIZATION="Bearer t0k")
    assert r.status_code == 405
    assert strict.get("/api/v1/leave?from=2027-03-01&to=2027-03-07", HTTP_AUTHORIZATION="Bearer t0k").status_code == 200


def test_rate_limit_counts_every_request_and_zero_switches_it_off(client, settings):
    settings.LEAVE_API_TOKENS = frozenset({"t0k"})
    settings.API_RATE_LIMIT_PER_MINUTE = 2
    url = "/api/v1/leave?from=2027-03-01&to=2027-03-07"
    assert client.get(url, HTTP_AUTHORIZATION="Bearer wrong").status_code == 401
    assert client.get(url, HTTP_AUTHORIZATION="Bearer t0k").status_code == 200
    r = client.get(url, HTTP_AUTHORIZATION="Bearer t0k")
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1 and "no-store" in r.headers["Cache-Control"]
    settings.API_RATE_LIMIT_PER_MINUTE = 0
    assert client.get(url, HTTP_AUTHORIZATION="Bearer t0k").status_code == 200


def test_logs_never_carry_a_token_an_email_or_a_note(client, settings, caplog):
    settings.LEAVE_API_TOKENS = frozenset({"t0k-real"})
    doc = make_person(is_gp=True, email="logged.gp@example.org")
    make_booking(doc, date(2027, 3, 1), description="log-me-not", staff_note="nor-me")
    caplog.set_level(logging.DEBUG)
    url = "/api/v1/leave?from=2027-03-01&to=2027-03-07"
    client.get(url, HTTP_AUTHORIZATION="Bearer guess-token")
    client.get(url, HTTP_AUTHORIZATION="Bearer t0k-real")
    settings.API_RATE_LIMIT_PER_MINUTE = 1
    client.get(url, HTTP_AUTHORIZATION="Bearer t0k-real")
    text = caplog.text
    for secret in ("guess-token", "t0k-real", "logged.gp@example.org", "log-me-not", "nor-me"):
        assert secret not in text
    assert "API request refused" in text


def test_settings_parse_a_comma_separated_env_into_a_frozenset(monkeypatch):
    import importlib

    import config.settings as s

    monkeypatch.setenv("LEAVE_API_TOKENS", " a ,b,, ,c ")
    monkeypatch.setenv("DEBUG", "1")
    try:
        reloaded = importlib.reload(s)
        assert reloaded.LEAVE_API_TOKENS == frozenset({"a", "b", "c"})
    finally:
        monkeypatch.undo()
        importlib.reload(s)
