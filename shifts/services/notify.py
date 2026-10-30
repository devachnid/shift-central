"""Notify staff (ROTA-09, NOTIF-02): one plain-text summary per person of
every day changed since they were last told, from the DayChange rows. A
day whose text is back to what it was sends nothing. A failed send keeps
the rows for next time."""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from messaging.services import send as send_mail
from people.services import access, audit
from shifts.models import DayChange
from shifts.services import render
from shifts.services.window import monday

OLD = timedelta(days=7)
SUBJECT = "Your rota has changed"


def _day_label(day):
    return f"{day:%a} {day.day} {day:%b %Y}"


def lines(person):
    out = []
    for change in DayChange.objects.filter(person=person).order_by("day"):
        now = render.day_text(person, change.day)
        if now == change.before:
            continue
        out.append(f"{_day_label(change.day)}: {now} (was {change.before})")
    return out


def _first_changed(person):
    for change in DayChange.objects.filter(person=person).order_by("day"):
        if render.day_text(person, change.day) != change.before:
            return change.day
    return None


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


def _body(person, first):
    host = settings.CSRF_TRUSTED_ORIGINS[0] if settings.CSRF_TRUSTED_ORIGINS else ""
    link = f"{host}/rota/?from={monday(first).isoformat()}"
    return "\n".join(["Your rota has changed. Here is what is different:", "", *lines(person), "",
                      f"See your rota: {link}", ""])


def send(user, person_ids):
    person_ids = list(dict.fromkeys(person_ids))
    allowed = {p.pk: p for p in access.managed_people(user).filter(pk__in=person_ids)}
    if set(person_ids) - set(allowed):
        raise PermissionDenied("not your team")
    out = {"sent": [], "failed": [], "skipped": []}
    for pk in person_ids:
        person = allowed[pk]
        first = _first_changed(person)
        if first is None:
            DayChange.objects.filter(person=person).delete()
            out["skipped"].append(person)
            continue
        if not person.email:
            out["skipped"].append(person)
            continue
        count = len(lines(person))
        row = send_mail(person, SUBJECT, _body(person, first))
        if row.sent_at is None:
            out["failed"].append(person)
            continue
        with transaction.atomic():
            DayChange.objects.filter(person=person).delete()
            audit.record_as(user, "shifts.entry", person.pk, {"notified": ("", str(count))},
                            note=f"rota changes sent · {person.name}")
        out["sent"].append(person)
    return out


def old_count(user):
    return (DayChange.objects.filter(person__in=access.managed_people(user), at__lt=timezone.now() - OLD)
            .values("person").distinct().count())
