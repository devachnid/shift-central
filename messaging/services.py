"""The one sender. Writes the Outbox row first, so a message is on record
whether or not the relay takes it; never raises; never puts a body or an
address in a log line or in `error`. `error` is the exception's class name
only; the relay's own log has the rest."""

import logging

from django.core.mail import send_mail
from django.utils import timezone

from .models import Outbox

log = logging.getLogger("messaging")


def send(person, subject, body):
    row = Outbox.objects.create(to_person=person, to_email=person.email or "", subject=subject, body=body)
    if not person.email:
        row.error = "no email address"
        row.save(update_fields=["error"])
        return row
    try:
        send_mail(subject, body, None, [person.email], fail_silently=False)
    except Exception as e:  # anything the backend raises is a failed send, not a crash
        row.error = e.__class__.__name__
        log.warning("send failed to person %s: %s", person.pk, e.__class__.__name__)
    else:
        row.sent_at = timezone.now()
    row.save(update_fields=["sent_at", "error"])
    return row
