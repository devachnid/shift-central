"""The Notifications page and Log out against a phone's push subscription.
Chromium's push service is not reachable from a test, so the page's view of
it (the service worker registration, its pushManager, the permission) is
replaced by a stand-in that keeps its subscription in localStorage.

Staging found the bug these cover: a phone subscribed while signed in as an
account the server refused, then showed "on" for the next account while the
server held no device for anyone."""

import pytest
from playwright.sync_api import expect

from messaging.models import PushDevice
from tests.factories import make_person, make_user_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

STAND_IN = """
(() => {
  let store;
  try { store = window.localStorage; } catch (e) { return; }   // about:blank has none
  const endpoint = () => store.getItem("e2e.endpoint") || "https://fcm.googleapis.com/fcm/send/e2e-device";
  const sub = () => store.getItem("e2e.sub") ? {
    endpoint: endpoint(),
    toJSON() { return {endpoint: endpoint(), keys: {p256dh: "BNc-key_1=", auth: "au-th_2"}}; },
    unsubscribe() { store.removeItem("e2e.sub"); return Promise.resolve(true); },
  } : null;
  const reg = {pushManager: {
    getSubscription() { return Promise.resolve(sub()); },
    subscribe() { store.setItem("e2e.sub", "1"); return Promise.resolve(sub()); },
  }};
  if (navigator.serviceWorker) {
    Object.defineProperty(navigator.serviceWorker, "register", {value: () => Promise.resolve(reg)});
    Object.defineProperty(navigator.serviceWorker, "ready", {value: Promise.resolve(reg)});
    Object.defineProperty(navigator.serviceWorker, "getRegistration", {value: () => Promise.resolve(reg)});
  }
  if (window.Notification) {
    Object.defineProperty(Notification, "permission", {get: () => "granted"});
    Notification.requestPermission = () => Promise.resolve("granted");
  }
})();
"""


@pytest.fixture
def phone(page):
    page.add_init_script(STAND_IN)
    return page


@pytest.fixture
def morgan(live_server, push_on):
    person = make_person(first_name="Morgan", last_name="Ellis")
    make_user_for(person, password="pw")
    return person


def _sign_in(page, live_server, person):
    page.goto(f"{live_server.url}/accounts/login/?next=/notifications/")
    page.fill("input[name=username]", person.user.email)
    page.fill("input[name=password]", "pw")
    page.click("button[type=submit]")
    page.wait_for_url("**/notifications/")


def test_a_subscription_the_server_never_got_is_registered_on_the_next_visit(phone, live_server, morgan):
    _sign_in(phone, live_server, morgan)
    phone.evaluate("localStorage.setItem('e2e.sub', '1')")     # subscribed earlier; the server refused it
    phone.goto(f"{live_server.url}/notifications/")
    expect(phone.locator("[data-push-status]")).to_have_text("Notifications are on for this device.")
    expect(phone.locator("table")).to_contain_text("Chrome")
    (device,) = PushDevice.objects.all()
    assert device.person == morgan


def test_turning_on_registers_the_phone(phone, live_server, morgan):
    _sign_in(phone, live_server, morgan)
    phone.click("text=Turn on notifications on this phone")
    expect(phone.locator("[data-push-status]")).to_have_text("Notifications are on for this device.")
    assert PushDevice.objects.get().person == morgan


def test_the_servers_reason_is_shown_when_it_refuses(phone, live_server, morgan):
    _sign_in(phone, live_server, morgan)
    phone.evaluate("localStorage.setItem('e2e.endpoint', 'https://push.example.net/x');"
                   "localStorage.setItem('e2e.sub', '1')")
    phone.goto(f"{live_server.url}/notifications/")
    expect(phone.locator("[data-push-status]")).to_have_text("That is not a push address.")
    assert PushDevice.objects.count() == 0


def test_log_out_forgets_the_phone_and_drops_its_subscription(phone, live_server, morgan):
    _sign_in(phone, live_server, morgan)
    phone.click("text=Turn on notifications on this phone")
    expect(phone.locator("[data-push-status]")).to_have_text("Notifications are on for this device.")
    assert PushDevice.objects.count() == 1
    phone.click("button[aria-label='Log out']")
    phone.wait_for_url(lambda url: "/notifications/" not in url)
    assert PushDevice.objects.count() == 0
    assert phone.evaluate("localStorage.getItem('e2e.sub')") is None
