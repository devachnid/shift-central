"""REP-01: rota hours minus breaks per person per week, overtime apart,
GP sessions at 4 h 10 min; managers see their people, staff themselves."""

from datetime import date, time, timedelta

import pytest
from django.test import Client

from shifts.services import hours
from tests.factories import make_entry, make_gp_session, make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db
MON = date(2027, 3, 1)


@pytest.fixture
def world():
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    nina = make_person(first_name="Nina", team=team)
    make_entry(nina, MON, start=time(8), finish=time(16, 15), break_minutes=60)
    make_entry(nina, MON, start=time(17), finish=time(19), overtime="paid")
    make_entry(nina, MON + timedelta(days=1), kind="comment", text="training")
    make_entry(nina, MON + timedelta(days=8), start=time(9), finish=time(13))
    doc = make_person(first_name="Doc", team=make_team("GPs"), is_gp=True)
    make_gp_session(doc, MON, "AM")
    make_gp_session(doc, MON, "PM")
    return {"lead": lead, "user": make_user_for(lead), "nina": nina, "doc": doc}


def test_breaks_come_off_overtime_is_apart_and_weeks_subtotal(world):
    blocks = {b["person"]: b for b in hours.report(world["user"], MON, MON + timedelta(days=13))}
    nina = blocks[world["nina"]]
    assert nina["shifts"] == 3 and nina["total"] == timedelta(hours=11, minutes=15)
    assert nina["overtime"] == timedelta(hours=2)
    week1, week2 = nina["weeks"]
    assert week1["subtotal"] == timedelta(hours=7, minutes=15) and week1["overtime"] == timedelta(hours=2)
    assert [r["day"] for r in week1["rows"]] == [MON, MON]
    assert week2["subtotal"] == timedelta(hours=4)


def test_gp_sessions_count_four_hours_ten_each(world):
    boss = make_user_for(make_person(first_name="Boss"), is_all_teams_manager=True)
    blocks = {b["person"]: b for b in hours.report(boss, MON, MON + timedelta(days=6))}
    doc = blocks[world["doc"]]
    assert doc["total"] == timedelta(hours=8, minutes=20) and doc["shifts"] == 2
    assert doc["weeks"][0]["rows"][0]["label"] == "AM Surgery AG" and doc["weeks"][0]["rows"][0]["start"] is None


def test_who_sees_whom(world):
    assert set(hours.people_for(world["user"])) == {world["lead"], world["nina"]}
    me = world["nina"]
    assert list(hours.people_for(make_user_for(me))) == [me]


def test_the_page_and_the_csv(world):
    c = Client()
    c.force_login(world["user"])
    body = c.get("/reports/hours/?from=2027-03-01&to=2027-03-07").content.decode()
    assert "Nina Patel — 2 shifts / 7 h 15 min" in body and "Overtime" in body and "2 h" in body
    assert '<h1 class="topbar-title">Hours</h1>' in body
    r = c.get("/reports/hours/?from=2027-03-01&to=2027-03-07&download=1")
    assert r["Content-Type"] == "text/csv"
    assert "Nina Patel,Mon,2027-03-01,08:00,16:15,60,7 h 15 min," in r.content.decode()


def test_a_range_over_a_year_or_backwards_is_clamped(world):
    c = Client()
    c.force_login(world["user"])
    assert c.get("/reports/hours/?from=2027-03-07&to=2027-03-01").status_code == 200
    assert c.get("/reports/hours/?from=2020-01-01&to=2027-03-01").status_code == 200
