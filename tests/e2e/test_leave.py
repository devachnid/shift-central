"""Book leave from the grid's menu, see the tile and the shift gone, cancel
it, see the shift back. Signs in with a password as test_grid does."""

import pytest
from playwright.sync_api import expect

from tests import clock
from tests.factories import make_allowance, make_entry, make_person, make_team, make_team_manager, make_type, make_user_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.today(clock.LATE_2026)]
MON = "2027-03-01"


@pytest.fixture
def manager(live_server):
    from datetime import date, time
    from decimal import Decimal
    # A transactional test empties the tables when it ends, seeded types
    # included, so make sure this one has the type it books.
    make_type("Holiday")
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    user = make_user_for(lead, password="pw")
    nina = make_person(first_name="Nina", team=team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(nina, date(2027, 1, 1), Decimal("172.5"), 60)
    make_entry(nina, date(2027, 3, 1), start=time(9), finish=time(17), break_minutes=30)
    return user


def _sign_in(page, live_server, user):
    page.goto(f"{live_server.url}/accounts/login/?next=/rota/?from={MON}")
    page.fill("input[name=username]", user.email)
    page.fill("input[name=password]", "pw")
    page.click("button[type=submit]")
    page.wait_for_selector("table.rota-grid")


def test_book_from_the_menu_then_cancel(page, live_server, manager):
    _sign_in(page, live_server, manager)
    nina_mon = page.locator("tr:has(th.rota-name:has-text('Nina')) td").first
    expect(nina_mon.locator(".tile-shift")).to_have_count(1)
    nina_mon.click(button="right")
    page.click(".rota-menu >> text=Time off…")
    page.wait_for_selector("#dialog form")
    page.select_option("#dialog select[name=type]", label="Holiday")
    page.click("#dialog button.btn-dark")
    expect(nina_mon.locator(".tile-leave")).to_have_text("Holiday")
    expect(nina_mon.locator(".tile-shift")).to_have_count(0)
    nina_mon.click(button="right")
    page.click(".rota-menu >> text=Cancel time off")
    page.wait_for_selector("#dialog form")
    page.click("#dialog button.btn-dark")
    expect(nina_mon.locator(".tile-shift")).to_have_count(1)
    expect(nina_mon.locator(".tile-leave")).to_have_count(0)
