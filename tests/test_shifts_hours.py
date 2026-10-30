"""REP-01: rota hours minus breaks per person per week, overtime apart,
GP sessions at 4 h 10 min; managers see their people, staff themselves."""

import re
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
    blocks = {b["person"]: b for b in hours.report(world["user"], MON, MON + timedelta(days=13))[0]}
    nina = blocks[world["nina"]]
    assert nina["shifts"] == 3 and nina["total"] == timedelta(hours=11, minutes=15)
    assert nina["overtime"] == timedelta(hours=2)
    week1, week2 = nina["weeks"]
    assert week1["subtotal"] == timedelta(hours=7, minutes=15) and week1["overtime"] == timedelta(hours=2)
    assert [r["day"] for r in week1["rows"]] == [MON, MON]
    assert week2["subtotal"] == timedelta(hours=4)


def test_gp_sessions_count_four_hours_ten_each(world):
    boss = make_user_for(make_person(first_name="Boss"), is_all_teams_manager=True)
    blocks = {b["person"]: b for b in hours.report(boss, MON, MON + timedelta(days=6))[0]}
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
    assert "Nina Patel — 2 shifts / 7 h 15 min + 2 h overtime" in body
    assert "<td>60 min</td><td>7 h 15 min</td><td></td>" in body
    assert "<td></td><td></td><td>2 h</td>" in body
    assert '<h1 class="topbar-title">Hours</h1>' in body
    assert 'class="subtotal"' not in body
    assert "Lead Patel — 0 shifts / 0 min" in body and "No shifts in this range." in body
    r = c.get("/reports/hours/?from=2027-03-01&to=2027-03-07&download=1")
    assert r["Content-Type"] == "text/csv"
    assert "Nina Patel,Mon,2027-03-01,08:00,16:15,60,7 h 15 min," in r.content.decode()
    assert "Nina Patel,Mon,2027-03-01,17:00,19:00,0,0 min,2 h," in r.content.decode()


def test_a_range_over_two_weeks_shows_weekly_subtotals(world):
    c = Client()
    c.force_login(world["user"])
    body = c.get("/reports/hours/?from=2027-03-01&to=2027-03-14").content.decode()
    assert body.count('class="subtotal"') == 2
    assert "Week of 1 Mar</td><td>7 h 15 min</td><td>2 h</td>" in body
    assert "Week of 8 Mar</td><td>4 h</td><td>0 min</td>" in body


def test_a_mid_week_range_that_crosses_a_monday_still_subtotals(world):
    c = Client()
    c.force_login(world["user"])
    body = c.get("/reports/hours/?from=2027-03-03&to=2027-03-09").content.decode()
    assert "Week of 8 Mar</td><td>4 h</td>" in body


def test_a_gp_session_is_a_row_on_the_page_and_in_the_csv(world):
    boss = make_user_for(make_person(first_name="Boss"), is_all_teams_manager=True)
    c = Client()
    c.force_login(boss)
    page = c.get("/reports/hours/?from=2027-03-01&to=2027-03-07").content.decode()
    assert re.search(r"<td>1 Mar 2027</td><td></td><td></td>\s*<td></td><td>4 h 10 min</td><td></td><td>AM Surgery AG</td></tr>", page)
    csv_body = c.get("/reports/hours/?from=2027-03-01&to=2027-03-07&download=1").content.decode()
    assert "Doc Patel,Mon,2027-03-01,,,0,4 h 10 min,,AM Surgery AG" in csv_body


def test_a_backwards_range_is_swapped(world):
    c = Client()
    c.force_login(world["user"])
    forward = c.get("/reports/hours/?from=2027-03-01&to=2027-03-07&download=1").content
    backward = c.get("/reports/hours/?from=2027-03-07&to=2027-03-01&download=1").content
    assert backward == forward and b"Nina Patel,Mon,2027-03-01" in backward
    blocks, start, end = hours.report(world["user"], MON + timedelta(days=6), MON)
    assert (start, end) == (MON, MON + timedelta(days=6))
    nina = {b["person"]: b for b in blocks}[world["nina"]]
    assert nina["shifts"] == 2
    page = c.get("/reports/hours/?from=2027-03-07&to=2027-03-01").content.decode()
    assert 'name="from" value="2027-03-01"' in page and 'name="to" value="2027-03-07"' in page
    assert "?from=2027-03-01&amp;to=2027-03-07&amp;download=1" in page


def test_a_range_over_a_year_is_clamped_and_the_form_shows_it(world):
    make_entry(world["nina"], date(2020, 1, 6), start=time(9), finish=time(12))
    c = Client()
    c.force_login(world["user"])
    body = c.get("/reports/hours/?from=2020-01-01&to=2027-03-01").content.decode()
    clamped = date(2027, 3, 1) - timedelta(days=366)
    assert f'name="from" value="{clamped.isoformat()}"' in body
    assert "6 Jan 2020" not in body and "1 Mar 2027" in body
    _, start, end = hours.report(world["user"], date(2020, 1, 1), date(2027, 3, 1))
    assert (start, end) == (clamped, date(2027, 3, 1))
