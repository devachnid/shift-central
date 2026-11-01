"""The one sender. Writes the Outbox row first, so a message is on record
whether or not the relay takes it; never raises; never puts a body or an
address in a log line or in `error`. `error` is the exception's class name
only; the relay's own log has the rest.

There is no console fallback: with no EMAIL_HOST nothing is tried and the
row says "mail not configured", so a box without a relay keeps every change
for Notify staff rather than printing mail nobody reads. A caller sending a
batch passes one open connection (`batch()` gives one, `notify.send` makes
its own), so the relay sees one login, not one per person.

Every message also queues a push (`push.queue`) when push is switched on and
the person has a phone registered; the one-minute timer sends it (`manage
send_push`). The push carries the subject and `url`, the page a tap opens
(default: the rota), never the body. Queueing a push never breaks the send."""

import logging
from contextlib import contextmanager

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.utils import timezone

from messaging.models import Outbox

from . import push

log = logging.getLogger("messaging")
NOT_CONFIGURED = "mail not configured"


def configured():
    return bool(settings.EMAIL_HOST)


def absolute_link(base_url, path):
    """An absolute link: the request's own address, or, for mail sent with
    none (a timer, a rota write), the first trusted origin."""
    base_url = base_url or (settings.CSRF_TRUSTED_ORIGINS or [""])[0]
    return (base_url.rstrip("/") + path) if base_url else path


@contextmanager
def batch():
    """One open relay connection for a run of sends; None when no relay is
    configured or it cannot be reached (each send then records its own
    failure)."""
    connection = None
    if configured():
        connection = get_connection()
        try:
            connection.open()
        except Exception:  # whatever open() raises, the relay cannot be reached
            connection = None
    try:
        yield connection
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:  # closing a dead connection is not news
                pass


def _send_email(person, subject, body, connection=None):
    """Send one email, on `connection` when given. Returns the Outbox row;
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


def send(person, subject, body, connection=None, url=None):
    """Send one message by email and, when push is on and the person has a
    phone registered, queue a push for the timer to send. Returns the email's
    Outbox row; its `sent_at` is None when nothing was sent. `url` is the page
    a tap on the push opens (default: the rota)."""
    row = _send_email(person, subject, body, connection)
    try:
        push.queue(person, subject, url)
    except Exception:  # a push must never break the message that caused it
        log.warning("queueing a push failed for person %s", person.pk)
    return row
