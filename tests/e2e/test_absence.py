"""A manager records sickness that joins on to an earlier entry, chooses
Extend, and sees one entry; then downloads the payroll Excel. Signs in
with a password as test_grid does."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from playwright.sync_api import expect

from tests import clock
from tests.factories import make_allowance, make_entry, make_person, make_sick, make_team, make_team_manager, make_type, make_user_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.today(clock.LATE_2026)]


@pytest.fixture
def manager(live_server):
    make_type("Holiday")
    make_type("Sick leave", requestable=False, sickness=True)           # a transactional test empties the seeds
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    user = make_user_for(lead, password="pw", is_all_teams_manager=True)
    nina = make_person(first_name="Nina", team=team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(nina, date(2026, 1, 1), Decimal("172.5"), 60)
    day = date(2026, 10, 5)
    while day <= date(2026, 11, 30):
        if day.weekday() < 5:
            make_entry(nina, day, start=time(9), finish=time(17), break_minutes=30)
        day += timedelta(days=1)
    make_sick(nina, date(2026, 10, 19), date(2026, 10, 23))              # Mon–Fri
    return user


def _sign_in(page, live_server, user, path):
    page.goto(f"{live_server.url}/accounts/login/?next={path}")
    page.fill("input[name=username]", user.email)
    page.fill("input[name=password]", "pw")
    page.click("button[type=submit]")


def test_extend_a_joined_on_entry_then_download_the_payroll(page, live_server, manager):
    _sign_in(page, live_server, manager, "/time-off/")
    page.click("text=Add time off +")
    page.wait_for_selector("#dialog form")
    page.select_option("#dialog select[name=person]", label="Nina Patel")
    page.select_option("#dialog select[name=type]", label="Sick leave")
    page.fill("#dialog input[name=first_day]", "2026-10-26")
    page.fill("#dialog input[name=last_day]", "2026-10-27")
    page.wait_for_selector("#dialog input[name=join]")
    expect(page.locator("#dialog")).to_contain_text("joins on to Sick leave 19 Oct–23 Oct 2026")
    page.click("#dialog button.btn-dark")
    page.wait_for_selector("#dialog", state="hidden")
    rows = page.locator("table.table tbody tr:has-text('Sick leave')")
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("27 Oct 2026")
    page.goto(f"{live_server.url}/reports/payroll/?month=2026-10")
    with page.expect_download() as download:
        page.click("text=Download Excel")
    assert download.value.suggested_filename == "payroll-2026-10.xlsx"
