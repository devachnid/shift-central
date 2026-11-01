"""The Shifts report (spec 5, section 9)."""

import io
from datetime import date, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from leave.services import bookings
from shifts.services import shift_report
from tests.factories import (client_for, make_department, make_entry, make_person, make_team, make_team_manager, make_type,
                             make_user_for)

pytestmark = pytest.mark.django_db
MON = date(2026, 11, 9)


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_team_manager(lead, reception)
    c = SimpleNamespace(reception=reception, nursing=nursing, lead=lead, boss=make_person(first_name="Boss", team=reception),
                        sam=make_person(first_name="Sam", team=reception, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5),
                        nina=make_person(first_name="Nina", team=nursing))
    for p in (lead, c.sam, c.nina):
        make_user_for(p)
    make_user_for(c.boss, is_all_teams_manager=True)
    return c


def shift(person, day, **kw):
    kw.setdefault("start", time(8))
    kw.setdefault("finish", time(16, 15))
    kw.setdefault("break_minutes", 45)
    return make_entry(person, day, **kw)


def test_net_hours_are_finish_less_start_less_break_with_overtime_shown_apart(cast):
    shift(cast.sam, MON)
    shift(cast.sam, MON + timedelta(days=1), start=time(9), finish=time(12), break_minutes=0, overtime="paid")
    (block,) = shift_report.report(cast.boss.user, MON, MON + timedelta(days=6))["blocks"]
    assert block["person"] == cast.sam and len(block["rows"]) == 2
    assert block["total"] == timedelta(hours=10, minutes=30) and block["overtime"] == timedelta(hours=3)


def test_the_grand_total_adds_every_person(cast):
    shift(cast.sam, MON)
    shift(cast.nina, MON)
    r = shift_report.report(cast.boss.user, MON, MON)
    assert r["grand_total"] == timedelta(hours=15) and len(r["blocks"]) == 2


def test_shifts_replaced_by_leave_are_left_out(cast):
    shift(cast.sam, MON)
    bookings.book(cast.boss.user, cast.sam, make_type("Training"), MON, MON, "whole")
    assert shift_report.report(cast.boss.user, MON, MON)["blocks"] == []


def test_a_team_manager_sees_only_their_own_teams(cast):
    shift(cast.sam, MON)
    shift(cast.nina, MON)
    assert [b["person"] for b in shift_report.report(cast.lead.user, MON, MON)["blocks"]] == [cast.sam]


def test_filters(cast):
    dept = make_department("Reception AG")
    shift(cast.sam, MON, department=dept)
    shift(cast.sam, MON + timedelta(days=1))
    shift(cast.nina, MON)
    boss = cast.boss.user
    assert len(shift_report.report(boss, MON, MON + timedelta(days=6), team=cast.nursing)["blocks"]) == 1
    (block,) = shift_report.report(boss, MON, MON + timedelta(days=6), department=dept)["blocks"]
    assert len(block["rows"]) == 1
    (block,) = shift_report.report(boss, MON, MON + timedelta(days=6), person=cast.sam)["blocks"]
    assert len(block["rows"]) == 2


def test_the_range_is_swapped_when_backwards_and_capped_at_a_year(cast):
    r = shift_report.report(cast.boss.user, MON + timedelta(days=6), MON)
    assert (r["start"], r["end"]) == (MON, MON + timedelta(days=6))
    r = shift_report.report(cast.boss.user, MON - timedelta(days=900), MON)
    assert (r["end"] - r["start"]).days == 366


def test_the_page_and_the_download(cast):
    shift(cast.sam, MON, text="Cover")
    assert client_for(cast.sam).get("/reports/shifts/").status_code == 403
    c = client_for(cast.lead)
    page = c.get(f"/reports/shifts/?from={MON}&to={MON}").content.decode()
    assert "Sam Patel" in page and "08:00" in page and "16:15" in page and "7 h 30 min" in page and "Cover" in page
    r = c.get(f"/reports/shifts/?from={MON}&to={MON}&download=1")
    assert r["Content-Type"].endswith("spreadsheetml.sheet") and f"shifts-{MON}-{MON}.xlsx" in r["Content-Disposition"]
    ws = load_workbook(io.BytesIO(r.content)).active
    assert [c.value for c in ws[1]][:3] == ["Date", "Day", "Name"]
    assert ws["C2"].value == "Sam Patel" and ws["F2"].value == "08:00" and ws["I2"].value == 7.5
    assert ws["A3"].value == "Total" and ws["I3"].value == 7.5


def test_a_name_that_looks_like_a_formula_is_written_as_text(cast):
    evil = make_person(first_name="=HYPERLINK", team=cast.reception)
    shift(evil, MON)
    ws = load_workbook(io.BytesIO(client_for(cast.boss).get(f"/reports/shifts/?from={MON}&to={MON}&download=1").content)).active
    assert ws["C2"].data_type == "s" and ws["C2"].value.startswith("=HYPERLINK")


def test_the_nav_has_the_report_for_managers_only(cast):
    assert 'href="/reports/shifts/"' in client_for(cast.lead).get("/rota/").content.decode()
    assert 'href="/reports/shifts/"' not in client_for(cast.sam).get("/rota/").content.decode()


def test_a_junk_filter_value_is_ignored_not_a_server_error(cast):
    shift(cast.sam, MON)
    c = client_for(cast.boss)
    for junk in ("%C2%B2", "abc", "99999", "-1"):
        r = c.get(f"/reports/shifts/?from={MON}&to={MON}&person={junk}&team={junk}&department={junk}")
        assert r.status_code == 200
