"""A manager posts an open shift, a staff member claims it, the manager
approves, and the shift is on the rota. Two browser contexts, each signed in
with a password as test_grid does."""

from datetime import date

import pytest
from playwright.sync_api import expect

from tests import clock
from tests.factories import make_person, make_team, make_team_manager, make_user_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.today(clock.LATE_2026)]
DAY = "2026-11-09"       # the Monday after the pinned Monday


@pytest.fixture
def cast(live_server):
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team, start_date=date(2020, 1, 6))
    make_team_manager(lead, team)
    sam = make_person(first_name="Sam", team=team, start_date=date(2020, 1, 6))
    return make_user_for(lead, password="pw"), make_user_for(sam, password="pw")


def _sign_in(page, live_server, user, next_path):
    page.goto(f"{live_server.url}/accounts/login/?next={next_path}")
    page.fill("input[name=username]", user.email)
    page.fill("input[name=password]", "pw")
    page.click("button[type=submit]")


def test_post_claim_approve_and_see_it_on_the_rota(browser, page, live_server, cast):
    lead, sam = cast
    _sign_in(page, live_server, lead, "/rota/open/")
    page.click("text=Post an open shift")
    page.wait_for_selector("#dialog form")
    page.select_option("#dialog select[name=team]", label="Reception")
    page.fill("#dialog input[name=day]", DAY)
    page.fill("#dialog input[name=start]", "09:00")
    page.fill("#dialog input[name=finish]", "13:00")
    page.check("#dialog input[name=everyone]")
    page.click("#dialog button.btn-dark")
    expect(page.locator(".open-card")).to_have_count(1)

    other = browser.new_context().new_page()
    _sign_in(other, live_server, sam, "/rota/open/")
    other.click(".open-card >> text=Claim")
    other.wait_for_selector("#dialog form")
    other.click("#dialog button.btn-dark")
    expect(other.locator(".open-card")).to_contain_text("You've claimed this")

    page.reload()
    page.click(".open-card >> text=Decide")
    page.wait_for_selector("#dialog form")
    page.click("#dialog button[name=action][value=approve]")
    page.wait_for_selector("#dialog form", state="detached")
    page.goto(f"{live_server.url}/rota/?from={DAY}")
    page.wait_for_selector("table.rota-grid")
    sam_monday = page.locator("tr:has(th.rota-name:has-text('Sam')) td").first
    expect(sam_monday.locator(".tile-shift")).to_have_count(1)
    expect(sam_monday).to_contain_text("09:00")


def test_the_notifications_page_opens_from_the_menu(page, live_server, cast):
    _sign_in(page, live_server, cast[1], "/rota/")
    page.click("a[aria-label=Notifications]")
    expect(page.locator("h2")).to_contain_text("Notifications on this phone")
