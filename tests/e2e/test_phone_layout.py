"""The app at phone size, signed in as an all-teams manager (the longest
menu). Staging, on Android: the rota's top-bar controls widened the page
past the screen, so the whole page panned under a finger; the bottom bar
held every section and ran off the right edge; and no page linked to the
pages under a section (Open shifts, My leave, the reports), which the
desktop shows as pop-out menus a phone does not have."""

import pytest
from playwright.sync_api import expect

from tests.factories import make_person, make_team, make_user_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]
PHONE = {"viewport": {"width": 412, "height": 915}, "device_scale_factor": 2.6, "is_mobile": True, "has_touch": True}


@pytest.fixture
def boss(live_server):
    team = make_team("Reception")
    make_person(first_name="Nina", team=team)
    return make_user_for(make_person(first_name="Morgan", last_name="Ellis", team=team), password="pw",
                         is_all_teams_manager=True)


def _signed_in(browser, live_server, boss, **context):
    page = browser.new_context(**context).new_page()
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill("input[name=username]", boss.email)
    page.fill("input[name=password]", "pw")
    page.click("button[type=submit]")
    page.wait_for_url(lambda url: "/accounts/login/" not in url)
    return page


@pytest.fixture
def phone(browser, live_server, boss):
    return _signed_in(browser, live_server, boss, **PHONE)


@pytest.mark.parametrize("path", ["/rota/", "/staff/", "/time-off/", "/uploads/", "/reports/hours/", "/messages/"])
def test_no_page_is_wider_than_the_phone(phone, live_server, path):
    phone.goto(live_server.url + path)
    width = phone.evaluate("() => ({inner: innerWidth, scroll: document.documentElement.scrollWidth})")
    assert width == {"inner": 412, "scroll": 412}


def test_the_bottom_bar_fits_the_screen(phone, live_server):
    phone.goto(live_server.url + "/staff/")
    rights = phone.evaluate("""() => [...document.querySelectorAll('.sidebar *')]
        .filter(e => e.checkVisibility()).map(e => e.getBoundingClientRect().right)""")
    assert rights and max(rights) <= 412
    assert phone.locator(".sidebar .nav-label:visible").all_inner_texts() == ["Rota", "Time off", "Messages", "Menu"]


def test_the_menu_reaches_every_section_and_the_pages_under_them(phone, live_server):
    phone.goto(live_server.url + "/staff/")
    phone.locator(".sidebar").get_by_text("Menu", exact=True).click()
    menu = phone.locator(".phone-menu-panel")
    for label in ("Staff", "Uploads", "Reports", "Settings", "Notifications", "Open shifts", "My leave",
                  "Year planner", "Payroll", "Log out"):
        expect(menu.get_by_text(label, exact=True)).to_be_visible()
    menu.get_by_text("Open shifts", exact=True).click()
    phone.wait_for_url("**/rota/open/")


def test_a_desktop_keeps_its_side_panel_and_shows_no_menu(browser, live_server, boss):
    desk = _signed_in(browser, live_server, boss, viewport={"width": 1280, "height": 900})
    expect(desk.locator(".phone-menu")).to_be_hidden()
    expect(desk.locator(".sidebar [data-nav='uploads']")).to_be_visible()
    expect(desk.locator(".sidebar-foot button")).to_be_visible()
