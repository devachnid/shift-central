"""ROTA-12: everyone, by site, with WFH apart and "off" meaning on
approved leave today."""

from datetime import date

import pytest
from django.test import Client

from shifts.services import today
from tests.factories import make_booking, make_department, make_entry, make_gp_session, make_person, make_team, make_user_for

pytestmark = pytest.mark.django_db
DAY = date(2027, 3, 1)


def test_sites_come_from_the_department_name(db):
    ag, pmc, other = make_department("Reception AG"), make_department("Cleaning PMC"), make_department("Workflow")
    p = make_person()
    assert today.site_of(make_entry(p, DAY, department=ag)) == "AG"
    assert today.site_of(make_entry(p, DAY, department=pmc)) == "PMC"
    assert today.site_of(make_entry(p, DAY, department=other)) == "Either"
    assert today.site_of(make_entry(p, DAY)) == "Either"


def test_the_board_groups_working_wfh_and_off():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    ag = make_department("Reception AG")
    a = make_person(first_name="Ann", team=reception)
    make_entry(a, DAY, department=ag)
    w = make_person(first_name="Wes", team=reception)
    make_entry(w, DAY, wfh=True)
    o = make_person(first_name="Off", team=nursing)
    doc = make_person(first_name="Doc", team=make_team("GPs"), is_gp=True)
    make_gp_session(doc, DAY, "AM", site="PMC")
    make_person(first_name="Gone", start_date=date(2020, 1, 1), end_date=date(2027, 2, 1))
    board = today.board(DAY)
    sites = {s["name"]: s for s in board["sites"]}
    assert [p["person"] for p in sites["AG"]["teams"][0]["people"]] == [a]
    assert sites["PMC"]["teams"][0]["people"][0]["lines"] == ["AM Surgery PMC"]
    assert [x["person"] for x in board["wfh"]] == [w]
    assert board["off"] == []   # no shift is not leave
    make_booking(o, DAY, status="approved")
    from leave.models import BookingDay
    BookingDay.objects.create(booking=o.bookings.get(), day=DAY, cost_seconds=0)
    assert today.board(DAY)["off"] == [{"person": o, "label": "Holiday"}]


def test_the_page_is_for_managers_and_takes_a_day():
    boss = make_user_for(make_person(first_name="Boss"), is_all_teams_manager=True)
    c = Client()
    c.force_login(boss)
    body = c.get("/rota/today/?day=2027-03-01").content.decode()
    assert "Monday 1 March 2027" in body and "Working from home" in body and "Off" in body
    assert "?day=2027-03-02" in body and "?day=2027-02-28" in body
    staff = Client()
    staff.force_login(make_user_for(make_person(first_name="Staff")))
    assert staff.get("/rota/today/").status_code == 403
