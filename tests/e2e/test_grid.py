"""The island, end to end: type a shift, see it, drag it, copy a block,
mark overtime, undo. Signs in with a password: HR is not configured under
pytest, so the password form is open."""

import pytest
from playwright.sync_api import expect

from tests.factories import make_department, make_person, make_team, make_team_manager, make_user_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]
MON = "2027-03-01"


@pytest.fixture
def manager(live_server):
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    user = make_user_for(lead, password="pw")
    make_person(first_name="Nina", team=team)
    make_person(first_name="Omar", team=team)
    make_department("Reception PMC")
    return user


def _sign_in(page, live_server, user):
    page.goto(f"{live_server.url}/accounts/login/?next=/rota/?from={MON}")
    page.fill("input[name=username]", user.email)
    page.fill("input[name=password]", "pw")
    page.click("button[type=submit]")
    page.wait_for_selector("table.rota-grid")


def test_type_drag_copy_overtime_undo(page, live_server, manager):
    _sign_in(page, live_server, manager)
    nina_mon = page.locator("tr:has(th.rota-name:has-text('Nina')) td").first
    nina_mon.click()
    page.keyboard.type("08:00-16:15 1 hour break Reception PMC")
    page.keyboard.press("Enter")
    tile = nina_mon.locator(".tile-shift")
    tile.wait_for()
    assert "08:00–16:15" in tile.inner_text() and "1 hour break" in tile.inner_text()

    # Drag Monday's tile to Tuesday.
    nina_tue = page.locator("tr:has(th.rota-name:has-text('Nina')) td").nth(1)
    nina_mon.click()
    nina_mon.hover()
    page.mouse.down()
    nina_tue.hover()
    nina_tue.hover()
    page.mouse.up()
    nina_tue.locator(".tile-shift").wait_for()
    assert nina_mon.locator(".tile-shift").count() == 0

    # Copy Tuesday onto Omar's Wednesday.
    nina_tue.click()
    page.keyboard.press("Control+C")
    omar_wed = page.locator("tr:has(th.rota-name:has-text('Omar')) td").nth(2)
    omar_wed.click()
    page.keyboard.press("Control+V")
    omar_wed.locator(".tile-shift").wait_for()

    # Mark it TOIL from the menu.
    omar_wed.click(button="right")
    page.click(".rota-menu button:has-text('Add')")
    page.click(".rota-menu-sub button:has-text('Overtime')")
    page.click(".rota-menu-sub .rota-menu-sub button:has-text('TOIL')")
    omar_wed.locator(".tile.is-overtime").wait_for()

    # Undo twice: the TOIL mark, then the paste.
    omar_wed.click()
    page.keyboard.press("Control+Z")
    expect(page.locator(".tile.is-overtime")).to_have_count(0)
    page.keyboard.press("Control+Z")
    expect(omar_wed.locator(".tile-shift")).to_have_count(0)
