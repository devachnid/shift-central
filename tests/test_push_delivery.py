"""Push delivery: the queue and the one-minute sender (spec 5, section 4)."""

from datetime import date
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command

from messaging import services
from messaging.models import Outbox, PushDevice
from messaging.services import push
from tests.factories import client_for, make_person, make_push_device, make_team, make_team_manager

pytestmark = pytest.mark.django_db


@pytest.fixture
def sender(monkeypatch):
    """Replaces the library call; records (device id, payload) and answers as told."""
    box = SimpleNamespace(calls=[], answer="ok")

    def fake(device, payload):
        box.calls.append((device.pk, payload))
        return box.answer
    monkeypatch.setattr(push, "deliver", fake)
    return box


def pushes():
    return Outbox.objects.filter(channel="push")


# --- queueing --------------------------------------------------------------------

def test_send_writes_the_email_and_queues_a_push_for_a_person_with_a_device(push_on):
    p = make_person()
    make_push_device(p)
    services.send(p, "Your shift", "The long body text", url="/rota/open/")
    email = Outbox.objects.get(channel="email")
    queued = pushes().get()
    assert email.body == "The long body text" and email.sent_at
    assert queued.subject == "Your shift" and queued.body == "" and queued.url == "/rota/open/"
    assert queued.sent_at is None and queued.to_person == p and queued.attempts == 0


def test_the_default_link_is_the_rota(push_on):
    p = make_person()
    make_push_device(p)
    services.send(p, "S", "B")
    assert pushes().get().url == "/rota/"


def test_nothing_is_queued_without_keys_or_without_a_device(push_on, settings):
    quiet = make_person(first_name="Quiet")
    services.send(quiet, "S", "B")                              # no device
    loud = make_person(first_name="Loud")
    make_push_device(loud)
    settings.VAPID_PUBLIC_KEY = ""                              # push switched off
    services.send(loud, "S", "B")
    assert pushes().count() == 0 and Outbox.objects.count() == 2


def test_a_push_is_queued_even_when_the_email_cannot_be_sent(push_on):
    p = make_person(email="")
    make_push_device(p)
    services.send(p, "S", "B")
    assert Outbox.objects.get(channel="email").error == "no email address"
    assert pushes().count() == 1


def test_a_failure_while_queueing_never_breaks_send(push_on, monkeypatch):
    p = make_person()
    make_push_device(p)
    monkeypatch.setattr(push, "queue", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert services.send(p, "S", "B").sent_at


# --- sending ---------------------------------------------------------------------

def test_the_payload_is_the_title_the_subject_and_the_link_only(push_on, sender):
    p = make_person()
    make_push_device(p)
    services.send(p, "Your open shift claim is approved", "SECRET BODY", url="/rota/")
    push.send_pending()
    ((_, payload),) = sender.calls
    assert payload == {"title": "AMG Shift Central", "body": "Your open shift claim is approved", "url": "/rota/"}


def test_a_delivered_push_is_marked_sent_and_the_device_stamped(push_on, sender):
    p = make_person()
    d = make_push_device(p, failures=2)
    services.send(p, "S", "B")
    counts = push.send_pending()
    row, d = pushes().get(), PushDevice.objects.get(pk=d.pk)
    assert row.sent_at and row.error == "" and counts["sent"] == 1
    assert d.last_ok_at and d.failures == 0


def test_one_success_among_several_devices_marks_the_row_sent(push_on, monkeypatch):
    p = make_person()
    good, bad = make_push_device(p), make_push_device(p)
    monkeypatch.setattr(push, "deliver", lambda device, payload: "ok" if device.pk == good.pk else "failed")
    services.send(p, "S", "B")
    push.send_pending()
    assert pushes().get().sent_at and PushDevice.objects.get(pk=bad.pk).failures == 1


def test_a_gone_device_is_deleted_and_a_person_left_with_none_gets_no_retries(push_on, sender):
    sender.answer = "gone"
    p = make_person()
    make_push_device(p)
    services.send(p, "S", "B")
    counts = push.send_pending()
    row = pushes().get()
    assert PushDevice.objects.count() == 0 and row.error == "no device" and row.sent_at is None and counts["gone"] == 1
    assert push.send_pending()["sent"] == 0                    # not tried again


def test_failures_are_retried_each_run_and_given_up_after_the_fifth(push_on, sender):
    sender.answer = "failed"
    p = make_person()
    make_push_device(p)
    services.send(p, "S", "B")
    for attempt in range(1, push.MAX_ATTEMPTS):
        push.send_pending()
        row = pushes().get()
        assert row.attempts == attempt and row.error == "" and row.sent_at is None
    push.send_pending()
    row = pushes().get()
    assert row.attempts == push.MAX_ATTEMPTS and row.error == "push failed"
    calls = len(sender.calls)
    push.send_pending()
    assert len(sender.calls) == calls                           # finished: not tried again


def test_a_push_older_than_a_day_is_dropped_not_sent(push_on, sender, today):
    p = make_person()
    make_push_device(p)
    services.send(p, "Your shift is tomorrow", "B")
    today(date(2026, 11, 4))                                    # the pinned clock was 2 Nov 09:00
    counts = push.send_pending()
    assert pushes().get().error == "expired" and sender.calls == [] and counts["expired"] == 1


def test_a_run_sends_at_most_one_batch_oldest_first(push_on, sender, monkeypatch):
    monkeypatch.setattr(push, "BATCH", 2)
    people = [make_person(first_name=f"P{n}") for n in range(3)]
    for p in people:
        make_push_device(p)
        services.send(p, f"For {p.first_name}", "B")
    push.send_pending()
    assert [r.subject for r in pushes().order_by("queued_at") if r.sent_at] == ["For P0", "For P1"]
    push.send_pending()
    assert pushes().filter(sent_at__isnull=False).count() == 3


# --- deliver (the library call) ----------------------------------------------------

def test_deliver_maps_the_library_outcomes(push_on, monkeypatch):
    import pywebpush
    device = make_push_device(make_person())
    sent = []
    monkeypatch.setattr(pywebpush, "webpush", lambda **kw: sent.append(kw))
    assert push.deliver(device, {"title": "T", "body": "B", "url": "/rota/"}) == "ok"
    kw = sent[0]
    assert kw["subscription_info"] == {"endpoint": device.endpoint, "keys": {"p256dh": device.p256dh, "auth": device.auth}}
    assert kw["timeout"] == 5 and kw["ttl"] == 24 * 3600 and kw["vapid_claims"]["sub"] == "mailto:test@example.org"

    def boom(status):
        def raiser(**kw):
            raise pywebpush.WebPushException("x", response=SimpleNamespace(status_code=status))
        return raiser

    for status, outcome in ((410, "gone"), (404, "gone"), (500, "failed"), (429, "failed")):
        monkeypatch.setattr(pywebpush, "webpush", boom(status))
        assert push.deliver(device, {}) == outcome
    monkeypatch.setattr(pywebpush, "webpush", lambda **kw: (_ for _ in ()).throw(OSError("net")))
    assert push.deliver(device, {}) == "failed"


# --- the command, status and Health -------------------------------------------------

def test_the_command_reports_and_exits_cleanly(push_on, sender):
    p = make_person()
    make_push_device(p)
    services.send(p, "S", "B")
    out = StringIO()
    call_command("send_push", stdout=out)
    assert "1 sent" in out.getvalue()


def test_the_command_says_so_when_push_is_not_configured():
    out = StringIO()
    call_command("send_push", stdout=out)
    assert "not configured" in out.getvalue()


def test_status_counts_devices_the_queue_and_the_last_success(push_on, sender):
    p = make_person()
    make_push_device(p)
    services.send(p, "S", "B")
    assert push.status()["queued"] == 1 and push.status()["devices"] == 1 and push.status()["last_ok"] is None
    push.send_pending()
    st = push.status()
    assert st["queued"] == 0 and st["last_ok"] and st["configured"]


def test_only_all_teams_managers_see_the_push_line_on_the_health_card(push_on):
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    boss = make_person(first_name="Boss", team=team)
    assert b"Phone notifications" not in client_for(lead).get("/staff/").content
    assert b"Phone notifications" in client_for(boss, is_all_teams_manager=True).get("/staff/").content


def test_a_leave_decision_opens_my_leave(push_on):
    from leave.services import notify as leave_notify
    from tests.factories import make_booking
    p = make_person()
    make_push_device(p)
    leave_notify.decided(make_booking(p, date(2026, 11, 9)))
    assert pushes().get().url == "/time-off/mine/"
