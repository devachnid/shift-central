"""The payroll page by role, the Excel's three sheets, Mark as sent, the
Health card's line, the Reports menu."""

import io
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.test import Client
from openpyxl import load_workbook

from leave.services import bookings
from payroll.models import PayrollRun
from shifts.models import Entry
from tests.factories import make_allowance, make_entry, make_person, make_team, make_team_manager, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 1, 25))]
JAN = date(2027, 1, 1)


def _client(person, **kw):
    c = Client()
    c.force_login(person.user or make_user_for(person, **kw))
    return c


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss", team=make_team("Management"))
    make_user_for(boss, is_all_teams_manager=True)
    return boss


@pytest.fixture
def staff(boss):
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_user_for(lead)
    make_team_manager(lead, reception)
    ann = make_person(first_name="Ann", last_name="=HYPERLINK(1)", team=reception, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    nick = make_person(first_name="Nick", team=nursing, start_date=date(2020, 1, 6), weekly_hours=Decimal("30"), days_per_week=4)
    for p in (ann, nick):
        make_allowance(p, JAN, Decimal("150"), 0)
        d = JAN
        while d <= date(2027, 1, 31):
            if d.weekday() < 5:
                make_entry(p, d, start=time(9), finish=time(17), break_minutes=30)
            d += timedelta(days=1)
    make_entry(ann, date(2027, 1, 6), start=time(9), finish=time(15), break_minutes=0, kind="shift", overtime="")   # a second shift the same day: 6 h more
    Entry.objects.filter(person=ann, day=date(2027, 1, 13)).delete()                                                # no shift: a KIT day during maternity
    bookings.book(boss.user, ann, make_type("KIT day"), date(2027, 1, 13), date(2027, 1, 13), "times", time(9), time(15))
    return {"lead": lead, "ann": ann, "nick": nick}


def test_the_page_by_role(boss, staff):
    assert _client(staff["ann"]).get("/reports/payroll/").status_code == 403
    body = _client(staff["lead"]).get("/reports/payroll/?month=2027-01").content.decode()
    assert "Ann" in body and "Nick" not in body and "Mark as sent" not in body and "Not yet sent" in body
    body = _client(boss).get("/reports/payroll/?month=2027-01").content.decode()
    assert "Ann" in body and "Nick" in body and "Mark as sent to the bureau" in body and "KIT day" in body
    assert "<th>Total to pay</th>" in body and "Reception total" in body and "Practice total" in body
    assert 'href="/reports/payroll/"' in body


def test_a_bad_month_falls_back_and_an_out_of_range_one_is_a_400(boss):
    c = _client(boss)
    assert c.get("/reports/payroll/?month=junk").status_code == 200 and "January 2027" in c.get("/reports/payroll/?month=junk").content.decode()
    assert c.get("/reports/payroll/?month=2029-01").status_code == 400


def test_the_excel_has_three_sheets_text_cells_and_the_type_columns(boss, staff):
    r = _client(boss).get("/reports/payroll/?month=2027-01&download=1")
    assert r.status_code == 200 and r["Content-Disposition"] == 'attachment; filename="payroll-2027-01.xlsx"'
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Payroll", "Corrections", "Starters and leavers"]
    ws = wb["Payroll"]
    header = [c.value for c in ws[1]]
    assert header[:12] == ["Name", "Team", "Worked", "Paid leave", "Total to pay", "Paid overtime", "Unpaid leave", "Sickness", "Sickness instances",
                           "TOIL taken", "Leave days", "KIT day (days)"]
    assert header[12] == "KIT day (hours)" and header[-3:] == ["Started", "Leaves", "Leaver's leave remaining"]
    ann = next(row for row in ws.iter_rows(min_row=2) if row[0].value.startswith("Ann"))
    assert ann[0].data_type == "s" and ann[0].value == "Ann =HYPERLINK(1)"
    assert ann[2].value == 156.0 and ann[12].value == 6.0 and ann[11].value == 1       # 157.5 − 7.5 + 6 worked; 6 h KIT
    assert ws["A1"].font.bold
    assert wb["Corrections"]["A1"].value == "Month" and wb["Starters and leavers"]["A1"].value == "Name"
    lead = _client(staff["lead"]).get("/reports/payroll/?month=2027-01&download=1")
    names = [row[0].value for row in load_workbook(io.BytesIO(lead.content))["Payroll"].iter_rows(min_row=2)]
    assert any(n.startswith("Ann") for n in names) and not any(n.startswith("Nick") for n in names)


def test_mark_as_sent_is_a_confirm_dialog_for_all_teams_managers(boss, staff):
    c = _client(boss)
    body = c.get("/reports/payroll/sent/?month=2027-01").content.decode()
    assert "January 2027" in body and "people" in body
    r = c.post("/reports/payroll/sent/?month=2027-01")
    assert r.json() == {"refresh": True}
    run = PayrollRun.objects.get()
    assert run.month == JAN and run.sent_by == boss.user
    body = c.get("/reports/payroll/?month=2027-01").content.decode()
    assert "Sent to the bureau on 25 Jan 2027 by Boss" in body and "Draft" not in body
    assert _client(staff["lead"]).post("/reports/payroll/sent/?month=2027-01").status_code == 403
    assert c.post("/reports/payroll/sent/?month=junk").status_code == 400 and c.post("/reports/payroll/sent/").status_code == 400
    assert PayrollRun.objects.count() == 1                                                  # nothing was marked by the bad requests
    page = c.get("/activity/").content.decode()
    assert "Payroll" in page and "January 2027" in page


def test_the_health_line_until_sent(boss, staff):
    c = _client(boss)
    assert "Payroll for January 2027 not yet sent" in c.get("/staff/").content.decode()
    c.post("/reports/payroll/sent/?month=2027-01")
    assert "Payroll for January 2027 not yet sent" not in c.get("/staff/").content.decode()
    assert "Payroll for" not in _client(staff["lead"]).get("/staff/").content.decode()


def test_the_reports_menu(boss, staff):
    body = _client(boss).get("/reports/hours/").content.decode()
    assert 'href="/reports/payroll/"' in body
    assert 'href="/reports/payroll/"' not in _client(staff["ann"]).get("/reports/hours/").content.decode()
