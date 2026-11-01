"""Registering a phone for push (spec 5, section 4)."""

import json
from io import StringIO

import pytest
from django.core.management import call_command

from messaging.models import PushDevice
from messaging.services import push
from tests.factories import client_for, make_person, make_push_device

pytestmark = pytest.mark.django_db
GOOD = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc123", "keys": {"p256dh": "BNc-key_1=", "auth": "au-th_2"}}


def post_json(client, url, data):
    return client.post(url, json.dumps(data), content_type="application/json")


def test_push_is_off_until_all_three_settings_and_the_key_file_exist(settings, tmp_path):
    assert not push.configured()
    settings.VAPID_PUBLIC_KEY, settings.VAPID_SUBJECT = "BKey", "mailto:a@example.org"
    settings.VAPID_PRIVATE_KEY_FILE = str(tmp_path / "missing.pem")
    assert not push.configured()                       # the file is not there
    (tmp_path / "missing.pem").write_text("pem")
    assert push.configured()
    settings.VAPID_SUBJECT = ""
    assert not push.configured()


def test_the_page_says_push_is_off_when_it_is_not_configured():
    body = client_for(make_person()).get("/notifications/").content.decode()
    assert "not switched on" in body and 'id="push-card"' not in body


def test_the_page_carries_the_public_key_and_the_urls_when_configured(push_on):
    body = client_for(make_person()).get("/notifications/").content.decode()
    assert 'id="push-card"' in body and 'data-key="BPublicKeyForTests"' in body
    assert 'data-subscribe-url="/push/subscribe/"' in body and "/static/js/push.js" in body


def test_subscribing_registers_the_device_for_the_signed_in_person(push_on):
    me = make_person()
    r = post_json(client_for(me), "/push/subscribe/", GOOD)
    assert r.status_code == 200 and r.json()["ok"] is True
    (d,) = PushDevice.objects.all()
    assert d.person == me and d.endpoint == GOOD["endpoint"] and d.p256dh == "BNc-key_1=" and d.auth == "au-th_2"


def test_subscribing_again_updates_rather_than_duplicates_and_moves_to_the_new_owner(push_on):
    a, b = make_person(first_name="A"), make_person(first_name="B")
    post_json(client_for(a), "/push/subscribe/", GOOD)
    post_json(client_for(b), "/push/subscribe/", GOOD)         # the same browser, a different person
    (d,) = PushDevice.objects.all()
    assert d.person == b


FCM = "https://fcm.googleapis.com/fcm/send/"


@pytest.mark.parametrize("bad", [
    {}, {"endpoint": "http://fcm.googleapis.com/x", "keys": {"p256dh": "a", "auth": "b"}},          # not https
    {"endpoint": FCM + "a" * 1100, "keys": {"p256dh": "a", "auth": "b"}},                            # too long
    {"endpoint": FCM + "a", "keys": {"p256dh": "not valid!", "auth": "b"}},                          # bad key
    {"endpoint": FCM + "a", "keys": {}},
    {"endpoint": "https://hr.devachnid.co.uk/oidc/token/", "keys": {"p256dh": "a", "auth": "b"}},   # not a push service
    {"endpoint": "https://fcm.googleapis.com.evil.example/x", "keys": {"p256dh": "a", "auth": "b"}},  # look-alike host
    {"endpoint": "https://user:pw@fcm.googleapis.com/x", "keys": {"p256dh": "a", "auth": "b"}},      # credentials
    {"endpoint": "https://fcm.googleapis.com:8443/x", "keys": {"p256dh": "a", "auth": "b"}},         # odd port
    {"endpoint": "https://127.0.0.1/x", "keys": {"p256dh": "a", "auth": "b"}},                        # an address
    {"endpoint": "https://127.0.0.1\\.fcm.googleapis.com/x", "keys": {"p256dh": "a", "auth": "b"}},  # backslash ends the host elsewhere
])
def test_a_bad_subscription_is_refused(push_on, bad):
    r = post_json(client_for(make_person()), "/push/subscribe/", bad)
    assert r.status_code == 400 and PushDevice.objects.count() == 0


def test_subscribing_needs_a_person_keys_and_a_sign_in(push_on, settings):
    from django.test import Client
    assert post_json(Client(), "/push/subscribe/", GOOD).status_code == 302          # to the sign-in
    settings.VAPID_PUBLIC_KEY = ""
    assert post_json(client_for(make_person()), "/push/subscribe/", GOOD).status_code == 400


def test_the_known_push_services_and_added_hosts_are_accepted(push_on, settings):
    for host in ("fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com", "db5p.notify.windows.com"):
        assert push.endpoint_allowed(f"https://{host}/send/x"), host
    assert not push.endpoint_allowed("https://push.example.net/send/x")
    settings.PUSH_ENDPOINT_HOSTS = (*settings.PUSH_ENDPOINT_HOSTS, "push.example.net")
    assert push.endpoint_allowed("https://push.example.net/send/x")


def test_a_device_label_is_taken_from_the_user_agent(push_on):
    c = client_for(make_person())
    c.post("/push/subscribe/", json.dumps(GOOD), content_type="application/json",
           HTTP_USER_AGENT="Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36")
    assert PushDevice.objects.get().label == "Android Chrome"
    assert push.label_for("Mozilla/5.0 (iPhone; CPU iPhone OS 17 like Mac OS X) Version/17 Safari/604") == "iPhone Safari"
    assert push.label_for("") == "Device browser"


def test_unsubscribing_removes_only_your_own_device(push_on):
    a, b = make_person(first_name="A"), make_person(first_name="B")
    make_push_device(a, endpoint="https://x.example/a")
    ca, cb = client_for(a), client_for(b)
    assert post_json(cb, "/push/unsubscribe/", {"endpoint": "https://x.example/a"}).status_code == 404
    assert PushDevice.objects.count() == 1
    assert post_json(ca, "/push/unsubscribe/", {"endpoint": "https://x.example/a"}).status_code == 200
    assert PushDevice.objects.count() == 0


def test_the_page_lists_your_devices_and_removes_one(push_on):
    me = make_person()
    d = make_push_device(me, label="Android Chrome")
    other = make_push_device(make_person(first_name="Z"), label="Someone else's")
    c = client_for(me)
    body = c.get("/notifications/").content.decode()
    assert "Android Chrome" in body and "Someone else's" not in body
    assert c.post(f"/push/devices/{other.pk}/remove/").status_code == 404
    assert c.post(f"/push/devices/{d.pk}/remove/").status_code == 302
    assert not PushDevice.objects.filter(pk=d.pk).exists()


def test_subscribe_is_post_only_and_csrf_protected(push_on):
    from django.test import Client
    me = make_person()
    c = client_for(me)
    assert c.get("/push/subscribe/").status_code == 405
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(me.user)
    assert post_json(strict, "/push/subscribe/", GOOD).status_code == 403


def test_vapid_keys_writes_a_private_key_file_and_prints_the_public_key(tmp_path):
    out = StringIO()
    target = tmp_path / "vapid.pem"
    call_command("vapid_keys", "--out", str(target), stdout=out)
    assert target.read_text().startswith("-----BEGIN PRIVATE KEY-----")
    assert oct(target.stat().st_mode & 0o777) == "0o640"
    text = out.getvalue()
    assert f"VAPID_PRIVATE_KEY_FILE={target}" in text and "VAPID_PUBLIC_KEY=B" in text and "VAPID_SUBJECT=mailto:" in text


def test_vapid_keys_will_not_overwrite_a_key(tmp_path):
    from django.core.management import CommandError
    target = tmp_path / "vapid.pem"
    target.write_text("keep me")
    with pytest.raises(CommandError):
        call_command("vapid_keys", "--out", str(target), stdout=StringIO())
    assert target.read_text() == "keep me"


def test_the_nav_has_notifications_for_everyone():
    assert 'data-nav="notifications"' in client_for(make_person()).get("/rota/").content.decode()


@pytest.mark.parametrize("bad", [
    "https://127.0.0.1\\.fcm.googleapis.com/x", "https://evil.example\\.fcm.googleapis.com/x",
    "https://evil.example;.fcm.googleapis.com/x", "https://evil.example%2f.fcm.googleapis.com/x",
    "https://fcm.googleapis.com/a\tb", "https://fcm.googleapis.com/a b", "https://fcm.googleapis.com/a\\b",
    "https://fcm.googleapis.com\n/x", "https://fcm.googleapis.com:8443/x", "https://fcm.googleapis.com@evil.example/x",
    "http://fcm.googleapis.com/x", "https://fcm.googleapis.com.evil.example/x", "", None,
])
def test_endpoint_allowed_refuses_anything_a_second_parser_could_read_differently(bad):
    assert not push.endpoint_allowed(bad)


def test_endpoint_allowed_accepts_the_plain_forms():
    assert push.endpoint_allowed("https://fcm.googleapis.com:443/fcm/send/abc?x=1")
    assert push.endpoint_allowed("https://FCM.googleapis.com")
    assert push.endpoint_allowed("https://updates.push.services.mozilla.com/wpush/v2/gAAAA")


def test_remove_device_service_only_removes_the_owners(push_on):
    a, b = make_person(first_name="A"), make_person(first_name="B")
    d = make_push_device(a)
    assert push.remove_device(b, d.pk) is False and PushDevice.objects.count() == 1
    assert push.remove_device(a, d.pk) is True and PushDevice.objects.count() == 0
    assert push.remove_device(a, d.pk) is False


def test_endpoint_allowed_refuses_the_kelvin_sign():
    """re.I alone folds U+212A to k; the host must be plain ASCII."""
    assert not push.endpoint_allowed("https://\u212aexample.fcm.googleapis.com/x")
    assert not push.endpoint_allowed("https://example.fcm.googleapis.com/\u212a")
    assert push.endpoint_allowed("https://Kexample.fcm.googleapis.com/x")      # ASCII capitals are still fine
