"""Web push (spec 5, section 4): which phones are registered and whether
push is switched on, then delivery (queue, deliver, send_pending, status)."""

import os
import re
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from messaging.models import Outbox, PushDevice

_B64URL = re.compile(r"^[A-Za-z0-9_\-=]+$")
# The one shape of address accepted: https, a plain host name, the default port
# at most, then a path of visible characters. Nothing that two URL parsers could
# read differently (a backslash, userinfo, a space) gets through.
_ENDPOINT = re.compile(r"https://([a-z0-9.-]+)(?::443)?(/[!-~]*)?", re.I)


def endpoint_allowed(endpoint):
    """An https address on a known push service, in one strict shape. The server
    will POST to it, so it is never a free choice of host, and it must mean the
    same host to every URL parser (urlsplit and urllib3 differ on a backslash)."""
    if not isinstance(endpoint, str) or "\\" in endpoint:
        return False
    m = _ENDPOINT.fullmatch(endpoint)
    if not m:
        return False
    host = m.group(1).lower()
    return any(host == h or host.endswith("." + h) for h in settings.PUSH_ENDPOINT_HOSTS)


def configured():
    """All three settings present and the private key file there."""
    return bool(settings.VAPID_PRIVATE_KEY_FILE and settings.VAPID_PUBLIC_KEY and settings.VAPID_SUBJECT
                and os.path.isfile(settings.VAPID_PRIVATE_KEY_FILE))


def label_for(user_agent):
    ua = user_agent or ""
    system = next((name for key, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"),
                                          ("Windows", "Windows"), ("Mac OS X", "Mac"), ("Linux", "Linux")) if key in ua), "Device")
    browser = next((name for key, name in (("Edg/", "Edge"), ("Firefox", "Firefox"), ("Chrome", "Chrome"),
                                           ("Safari", "Safari")) if key in ua), "browser")
    return f"{system} {browser}"[:80]


def register(person, endpoint, p256dh, auth, user_agent=""):
    """Add (or take over) the device behind this subscription. ValueError
    with a sentence when the subscription is not one a push service made."""
    if not (isinstance(endpoint, str) and len(endpoint) <= 1000 and endpoint_allowed(endpoint)):
        raise ValueError("That is not a push address.")
    for value, limit in ((p256dh, 200), (auth, 100)):
        if not (isinstance(value, str) and 0 < len(value) <= limit and _B64URL.match(value)):
            raise ValueError("That is not a valid push key.")
    device, _ = PushDevice.objects.update_or_create(
        endpoint=endpoint,
        defaults={"person": person, "p256dh": p256dh, "auth": auth, "label": label_for(user_agent), "failures": 0})
    return device


def unregister(person, endpoint):
    """Remove this person's device with the endpoint; False when they have none."""
    deleted, _ = PushDevice.objects.filter(person=person, endpoint=endpoint).delete()
    return bool(deleted)


def remove_device(person, pk):
    """Remove this person's device with this id; False when they have none."""
    deleted, _ = PushDevice.objects.filter(person=person, pk=pk).delete()
    return bool(deleted)


EXPIRY = timedelta(hours=24)     # a late "your shift is tomorrow" is worse than none
MAX_ATTEMPTS = 5
BATCH = 200
TIMEOUT = 5


def queue(person, subject, url):
    """Write the push row for a notification, or nothing: push must be
    switched on and the person must have a device. The row carries the
    subject and the page to open, never the message."""
    if not configured() or not person.push_devices.exists():
        return None
    return Outbox.objects.create(to_person=person, channel=Outbox.Channel.PUSH, subject=subject[:200],
                                 body="", url=url or "/rota/")


def deliver(device, payload):
    """One push to one device: "ok", "gone" (the push service says the
    device is no more: delete it) or "failed" (try again later). The only
    function that talks to the network; tests replace it."""
    import json

    from pywebpush import WebPushException, webpush
    try:
        webpush(subscription_info={"endpoint": device.endpoint, "keys": {"p256dh": device.p256dh, "auth": device.auth}},
                data=json.dumps(payload), vapid_private_key=settings.VAPID_PRIVATE_KEY_FILE,
                vapid_claims={"sub": settings.VAPID_SUBJECT}, timeout=TIMEOUT)
    except WebPushException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        return "gone" if status in (404, 410) else "failed"
    except Exception:  # a network error is a failed push, not a crash
        return "failed"
    return "ok"


def send_pending():
    """Send the queued pushes, oldest first, at most BATCH. Returns counts."""
    counts = Counter()
    now = timezone.now()
    rows = (Outbox.objects.filter(channel=Outbox.Channel.PUSH, sent_at__isnull=True, error="")
            .select_related("to_person").order_by("queued_at", "pk")[:BATCH])
    for row in rows:
        if now - row.queued_at > EXPIRY:
            row.error = "expired"
            row.save(update_fields=["error"])
            counts["expired"] += 1
            continue
        devices = list(row.to_person.push_devices.all()) if row.to_person_id else []
        payload = {"title": "AMG Shift Central", "body": row.subject, "url": row.url}
        delivered = False
        for device in devices:
            outcome = deliver(device, payload)
            if outcome == "ok":
                delivered = True
                device.last_ok_at, device.failures = timezone.now(), 0
                device.save(update_fields=["last_ok_at", "failures"])
            elif outcome == "gone":
                device.delete()
                counts["gone"] += 1
            else:
                device.failures += 1
                device.save(update_fields=["failures"])
        if delivered:
            row.sent_at = timezone.now()
            row.save(update_fields=["sent_at"])
            counts["sent"] += 1
            continue
        row.attempts += 1
        if not row.to_person_id or not row.to_person.push_devices.exists():
            row.error = "no device"
            counts["no_device"] += 1
        elif row.attempts >= MAX_ATTEMPTS:
            row.error = "push failed"
            counts["failed"] += 1
        row.save(update_fields=["attempts", "error"])
    return counts


def status():
    """For the Health card and the dashboard."""
    last = (Outbox.objects.filter(channel=Outbox.Channel.PUSH, sent_at__isnull=False)
            .order_by("-sent_at").values_list("sent_at", flat=True).first())
    return {"configured": configured(), "devices": PushDevice.objects.count(), "last_ok": last,
            "queued": Outbox.objects.filter(channel=Outbox.Channel.PUSH, sent_at__isnull=True, error="").count()}
