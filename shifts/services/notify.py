"""Notify staff (ROTA-09, NOTIF-02): one plain-text summary per person of
every day changed since they were last told, from the DayChange rows. A
day whose text is back to what it was sends nothing. A failed send keeps
the rows for next time. A batch goes over one SMTP connection, and once
the relay has failed the rest of the batch is not tried: each would wait
out the same timeout, and their rows are kept either way."""

import smtplib
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.core.mail import get_connection
from django.db import transaction
from django.utils import timezone

from messaging import services as messaging
from messaging.services import send as send_mail
from people.services import access, audit
from shifts.models import DayChange
from shifts.services import render
from shifts.services.window import monday

OLD = timedelta(days=7)
SUBJECT = "Your rota has changed"


def _day_label(day):
    return f"{day:%a} {day.day} {day:%b %Y}"


def _changed(person, changes):
    """[(day, now, was)] for the rows whose day is not back to what it was."""
    out = []
    for change in changes:
        now = render.day_text(person, change.day)
        if now != change.before:
            out.append((change.day, now, change.before))
    return out


def _lines(rows):
    return [f"{_day_label(day)}: {now} (was {was})" for day, now, was in rows]


def lines(person):
    return _lines(_changed(person, DayChange.objects.filter(person=person).order_by("day")))


def pending(user):
    """Everyone the user manages with unnotified rows, each with a reason
    when nothing can be sent."""
    people = access.managed_people(user).filter(day_changes__isnull=False).distinct().order_by("name")
    out = []
    for person in people:
        days = list(DayChange.objects.filter(person=person).order_by("day").values_list("day", flat=True))
        reason = ""
        if not lines(person):
            reason = "changes cancel out"
        elif not person.email:
            reason = "no email"
        out.append({"person": person, "days": days, "reason": reason})
    return out


def _body(rows, base_url):
    link = f"{base_url.rstrip('/')}/rota/?from={monday(rows[0][0]).isoformat()}"
    return "\n".join(["Your rota has changed. Here is what is different:", "", *_lines(rows), "",
                      f"See your rota: {link}", ""])


def _broken(exc):
    """A failure of the relay itself rather than of one message: the rest of
    the batch would fail the same way. A refused recipient is about that
    one address."""
    return isinstance(exc, (OSError, smtplib.SMTPException)) and not isinstance(exc, smtplib.SMTPRecipientsRefused)


def _settle(person, changes, mailed):
    """After a send: delete each row that is done with. A mailed day whose
    text has changed again since the mail was built keeps its row, now
    against the text that was mailed; an unmailed day (it had cancelled out)
    goes only if it still has."""
    for change in changes:
        now = render.day_text(person, change.day)
        if change.day in mailed:
            if now == mailed[change.day]:
                change.delete()
            else:
                change.before = mailed[change.day]
                change.save(update_fields=["before"])
        elif now == change.before:
            change.delete()


def send(user, person_ids, base_url):
    """Mail each ticked person their summary; `base_url` is the site's root
    (the view's build_absolute_uri("/")) for the link in the email. Only the
    rows read before the mail was built are settled, so a change saved in
    the meantime is kept for next time."""
    person_ids = list(dict.fromkeys(person_ids))
    allowed = {p.pk: p for p in access.managed_people(user).filter(pk__in=person_ids)}
    if set(person_ids) - set(allowed):
        raise PermissionDenied("not your team")
    out = {"sent": [], "failed": [], "skipped": []}
    connection, broken = None, False
    if messaging.configured():
        connection = get_connection()
        try:
            connection.open()
        except Exception:  # whatever open() raises, the relay cannot be reached
            broken = True
    try:
        for pk in person_ids:
            person = allowed[pk]
            changes = list(DayChange.objects.filter(person=person).order_by("day"))
            rows = _changed(person, changes)
            if not rows:
                with transaction.atomic():
                    _settle(person, changes, {})
                out["skipped"].append(person)
                continue
            if not person.email:
                out["skipped"].append(person)
                continue
            if broken:
                out["failed"].append(person)   # not tried: the relay is down
                continue
            row = send_mail(person, SUBJECT, _body(rows, base_url), connection=connection)
            if row.sent_at is None:
                out["failed"].append(person)
                broken = _broken(getattr(row, "failure", None))
                continue
            with transaction.atomic():
                _settle(person, changes, {day: now for day, now, _ in rows})
                audit.record_as(user, "shifts.entry", person.pk, {"notified": ("", str(len(rows)))},
                                note=f"rota changes sent · {person.name}")
            out["sent"].append(person)
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:  # closing a dead connection is not news
                pass
    return out


def old_count(user):
    """People with a real change (not one that cancelled out) left unsent
    for over a week."""
    old = (DayChange.objects.filter(person__in=access.managed_people(user), at__lt=timezone.now() - OLD)
           .values_list("person", flat=True).distinct())
    return sum(1 for person in access.managed_people(user).filter(pk__in=old) if lines(person))
