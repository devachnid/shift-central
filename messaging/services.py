"""The one sender. Writes the Outbox row first, so a message is on record
whether or not the relay takes it; never raises; never puts a body or an
address in a log line or in `error`. `error` is the exception's class name
only; the relay's own log has the rest.

There is no console fallback: with no EMAIL_HOST nothing is tried and the
row says "mail not configured", so a box without a relay keeps every change
for Notify staff rather than printing mail nobody reads. A caller sending a
batch passes one open connection (`notify.send` does), so the relay sees
one login, not one per person."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Outbox

log = logging.getLogger("messaging")
NOT_CONFIGURED = "mail not configured"


def configured():
    return bool(settings.EMAIL_HOST)


def send(person, subject, body, connection=None):
    """Send one message, on `connection` when given. Returns the Outbox row;
    its `sent_at` is None when nothing was sent."""
    row = Outbox.objects.create(to_person=person, to_email=person.email or "", subject=subject, body=body)
    if not person.email:
        row.error = "no email address"
        row.save(update_fields=["error"])
        return row
    if not configured():
        row.error = NOT_CONFIGURED
        row.save(update_fields=["error"])
        return row
    try:
        send_mail(subject, body, None, [person.email], fail_silently=False, connection=connection)
    except Exception as e:  # anything the backend raises is a failed send, not a crash
        row.error = e.__class__.__name__
        row.failure = e   # for the caller in this request only; never stored
        log.warning("send failed to person %s: %s", person.pk, e.__class__.__name__)
    else:
        row.sent_at = timezone.now()
    row.save(update_fields=["sent_at", "error"])
    return row
