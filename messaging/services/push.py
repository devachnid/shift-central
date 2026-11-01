"""Web push (spec 5, section 4): which phones are registered and whether
push is switched on. Delivery is further down this file (queue, deliver,
send_pending)."""

import os
import re
from urllib.parse import urlsplit

from django.conf import settings

from messaging.models import PushDevice

_B64URL = re.compile(r"^[A-Za-z0-9_\-=]+$")


def endpoint_allowed(endpoint):
    """An https address on a known push service: no credentials, the default
    port. The server will POST to it, so it is never a free choice of host."""
    try:
        parts = urlsplit(endpoint)
        host, port = (parts.hostname or "").lower(), parts.port
    except ValueError:
        return False
    return (parts.scheme == "https" and parts.username is None and port in (None, 443)
            and any(host == h or host.endswith("." + h) for h in settings.PUSH_ENDPOINT_HOSTS))


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
