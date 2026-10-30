"""GP sessions from the rota app (spec, section 9): one window fetched,
matched to GPs by email, the window's rows replaced in one transaction.
Never raises; a failure is the run's message and the previous rows stand.
Emails are record values: they go in the run's `detail` for the Health
card, never in `message` or a log line."""

import logging
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from people.models import Person, SyncRun
from shifts.models import GpSession
from shifts.services.gp_client import GpClient, GpError

log = logging.getLogger("shifts.gp_sync")
SOURCE = "gp-rota"
BACK = timedelta(weeks=8)
AHEAD = timedelta(weeks=52)


class BadRecord(Exception):
    pass


def configured():
    return bool(settings.ROTA_URL and settings.ROTA_API_TOKEN)


def _parse(record, position):
    try:
        email = str(record["email"]).strip().lower()
        day = date.fromisoformat(record["day"])
        part = str(record["part"])
        if part not in ("AM", "PM"):
            raise ValueError
        return email, {"day": day, "part": part, "label": str(record.get("type") or "")[:60],
                       "site": str(record.get("site") or "")[:60], "note": str(record.get("note") or "")[:200]}
    except (KeyError, TypeError, ValueError, AttributeError):
        raise BadRecord(f"session {position} in the feed: missing or bad email, day or part") from None


def _gps(today):
    """GPs by lowercased email: those current on the sync day or starting
    after it, never a leaver. A work email can be reused (a GP who left and
    came back has two records); when two share one, the one current today
    wins, else the earlier record."""
    gps = {}
    people = (Person.objects.filter(is_gp=True).exclude(email="")
              .filter(Q(end_date__isnull=True) | Q(end_date__gte=today)).order_by("pk"))
    for person in people:
        key = person.email.lower()
        held = gps.get(key)
        if held is None or (person.current(today) and not held.current(today)):
            gps[key] = person
    return gps


def _apply(payload, start, end, now, today):
    """Rows outside start..end are skipped (the window delete would never
    clear them) and a repeated (person, day, part) keeps its first record
    (the table is unique on it); both are counted, not stored."""
    gps = _gps(today)
    rows, slots = [], set()
    unmatched, matched = set(), set()
    duplicates = outside = 0
    for position, record in enumerate(payload["sessions"], start=1):
        email, fields = _parse(record, position)
        if not start <= fields["day"] <= end:
            outside += 1
            continue
        person = gps.get(email)
        if person is None:
            unmatched.add(email)
            continue
        slot = (person.pk, fields["day"], fields["part"])
        if slot in slots:
            duplicates += 1
            continue
        slots.add(slot)
        matched.add(person.pk)
        rows.append(GpSession(person=person, synced_at=now, **fields))
    with transaction.atomic():
        GpSession.objects.filter(day__range=(start, end)).delete()
        GpSession.objects.bulk_create(rows)
    detail = {"unmatched": sorted(unmatched), "without_email": int(payload.get("without_email") or 0)}
    if duplicates:
        detail["duplicates"] = duplicates
    if outside:
        detail["outside_window"] = outside
    return len(matched), detail


def _plural(n, noun):
    return f"{n} {noun}{'' if n == 1 else 's'}"


def _message(detail):
    notes = []
    if detail["unmatched"]:
        notes.append(f"{_plural(len(detail['unmatched']), 'email')} unmatched")
    if detail["without_email"]:
        notes.append(f"{_plural(detail['without_email'], 'clinician')} without an email")
    if detail.get("duplicates"):
        notes.append(_plural(detail["duplicates"], "duplicate session"))
    if detail.get("outside_window"):
        notes.append(f"{_plural(detail['outside_window'], 'session')} outside the window")
    return "; ".join(notes)


def sync(client=None, now=None):
    client = client or GpClient.from_settings()
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    start, end = today - BACK, today + AHEAD
    run = SyncRun.objects.create(source=SOURCE)
    try:
        payload = client.sessions(start, end)
        seen, detail = _apply(payload, start, end, now, today)
        run.ok, run.people_seen = True, seen
        run.detail = detail
        run.message = _message(detail)
    except (GpError, BadRecord) as e:
        run.message = str(e)[:300]
        log.warning("gp_sync failed: %s", run.message)
    except Exception:
        run.message = "unexpected error; see the journal"
        log.exception("gp_sync failed")
    finally:
        run.finished_at = timezone.now()
        run.save()
    return run


def last_run():
    return SyncRun.objects.filter(source=SOURCE).first()


def unmatched():
    run = SyncRun.objects.filter(source=SOURCE, ok=True).first()
    return list(run.detail.get("unmatched", [])) if run else []
