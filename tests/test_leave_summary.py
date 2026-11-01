"""REP-05: the leave one-pager for a leave year: taken and remaining per
person with team and practice totals; PDF or Excel."""

import io
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client
from openpyxl import load_workbook

from leave.services import hours, summary
from tests.factories import make_allowance, make_person, make_team, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 6, 1))]
Y27 = date(2027, 1, 1)


def h(text):
    return hours.from_hours(Decimal(text))


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss", team=make_team("Management"))
    make_user_for(boss, is_all_teams_manager=True)
    return boss


def test_the_figures_and_the_footnote_for_another_leave_year_start(boss):
    reception = make_team("Reception")
    ann = make_person(first_name="Ann", team=reception, start_date=date(2020, 1, 6))
    make_allowance(ann, Y27, Decimal("172.5"), 60)
    april = make_person(first_name="Apr", team=reception, start_date=date(2020, 1, 6), leave_year_start="04-01")
    make_allowance(april, date(2026, 4, 1), Decimal("100"), 0)
    make_person(first_name="New", team=reception, start_date=date(2027, 3, 1))     # no allowance: "not set"
    s = summary.summary(boss.user, Y27)
    rows = {r.person.first_name: r for r in s["people"]}
    assert rows["Ann"].allowance == h("232.5") and rows["Ann"].remaining == h("232.5") and not rows["Ann"].missing
    assert rows["Apr"].year == date(2026, 4, 1) and rows["Apr"].allowance == h("100")
    assert rows["New"].missing
    team = next(t for t in s["teams"] if t.name == "Reception")
    assert team.allowance == h("332.5") and team.people == 3
    assert s["practice"].allowance >= h("332.5")
    assert any("2026/27" in f for f in s["footnotes"])


def test_the_page_pdf_and_excel(boss):
    c = Client()
    c.force_login(boss.user)
    ann = make_person(first_name="Ann", team=make_team("Reception"), start_date=date(2020, 1, 6))
    make_allowance(ann, Y27, Decimal("172.5"), 60)
    body = c.get("/reports/leave-summary/?year=2027").content.decode()
    assert "Leave summary" in body and "Ann" in body and "232 h 30 min" in body and "Practice total" in body
    r = c.get("/reports/leave-summary/?year=2027&format=pdf")
    assert r.content.startswith(b"%PDF") and 'filename="leave-summary-2027.pdf"' in r["Content-Disposition"]
    wb = load_workbook(io.BytesIO(c.get("/reports/leave-summary/?year=2027&format=xlsx").content))
    assert wb.sheetnames == ["Practice", "Teams", "People"]
    staff = Client()
    staff.force_login(make_user_for(ann))
    assert staff.get("/reports/leave-summary/").status_code == 403
    assert 'href="/reports/leave-summary/"' in c.get("/reports/hours/").content.decode()
