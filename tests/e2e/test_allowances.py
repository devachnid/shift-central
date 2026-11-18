"""A manager confirms a worked-out allowance on the Allowances page, then
changes one in its pop-up. Signs in with a password as test_grid does."""

from datetime import date
from decimal import Decimal

import pytest
from playwright.sync_api import expect

from people.models import Person
from tests import clock
from tests.factories import make_bank_holiday, make_contract, make_person, make_team, make_team_manager, make_user_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.today(clock.LATE_2026)]


@pytest.fixture
def manager(live_server):
    from leave.services import entitlement
    # A transactional test empties the tables when it ends, the seeded bank
    # holidays included, so this one makes the eight it counts.
    for month, day in ((1, 1), (3, 26), (3, 29), (5, 3), (5, 31), (8, 30), (12, 27), (12, 28)):
        make_bank_holiday(date(2027, month, day))
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    user = make_user_for(lead, password="pw")
    for name, weekly in (("Nina", "37.5"), ("Omar", "30")):
        person = make_person(first_name=name, team=team, start_date=date(2025, 6, 1), weekly_hours=Decimal(weekly), days_per_week=5)
        make_contract(person, weekly, steps=[(1, 23)])
    entitlement.refresh()
    return user


def test_confirm_a_worked_out_figure_and_change_another(page, live_server, manager):
    page.goto(f"{live_server.url}/accounts/login/?next=/staff/allowances/")
    page.fill("input[name=username]", manager.email)
    page.fill("input[name=password]", "pw")
    page.click("button[type=submit]")
    nina = page.locator("tr:has-text('Nina Patel')")
    expect(nina).to_contain_text("172 h 30 min")
    expect(nina).to_contain_text("worked out, not yet checked")
    expect(nina).to_contain_text("23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min")
    nina.get_by_role("button", name="Confirm").click()
    expect(page.locator(".flash")).to_have_text("1 allowance confirmed.")
    expect(page.locator("#to-check ~ table").first.locator("tr:has-text('Nina Patel')")).to_have_count(0)
    nina_pk = Person.objects.get(first_name="Nina").pk
    page.goto(f"{live_server.url}/staff/{nina_pk}/profile/?tab=hours")         # and her profile says who checked it
    expect(page.locator("tr:has-text('1 Jan 2027')").first).to_contain_text("worked out, checked by Lead Patel on")
    page.goto(f"{live_server.url}/staff/allowances/")

    omar = page.locator("tr:has-text('Omar Patel')")
    omar.get_by_role("link", name="Change…").click()
    page.wait_for_selector("#dialog form")
    page.fill("#dialog input[name=annual_hours]", "150")
    page.fill("#dialog input[name=note]", "contract says 25 days")
    page.click("#dialog button.btn-dark")
    differ = page.locator("#differ ~ table").first.locator("tr:has-text('Omar Patel')")
    expect(differ).to_contain_text("150 h and 48 h")
    expect(differ).to_contain_text("138 h and 48 h")
    differ.get_by_role("button", name="Use the worked-out figure").click()
    expect(page.locator(".flash")).to_have_text("Omar Patel: the worked-out figure is in use.")
    expect(page.locator("text=Nothing to check.")).to_be_visible()
    expect(page.locator("text=Every typed figure is what its contract gives.")).to_be_visible()
