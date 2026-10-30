"""GP sessions from the rota app (spec, section 9): one window fetched,
matched to GPs by email, the window's rows replaced in one transaction.
Never raises; a failure is the run's message and the previous rows stand.
Emails are record values: they go in the run's `detail` for the Health
card, never in `message` or a log line."""

import logging
from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
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


def _apply(payload, start, end, now):
    gps = {p.email.lower(): p for p in Person.objects.filter(is_gp=True).exclude(email="")}
    rows, unmatched, matched = [], set(), set()
    for position, record in enumerate(payload["sessions"], start=1):
        email, fields = _parse(record, position)
        person = gps.get(email)
        if person is None:
            unmatched.add(email)
            continue
        matched.add(person.pk)
        rows.append(GpSession(person=person, synced_at=now, **fields))
    with transaction.atomic():
        GpSession.objects.filter(day__range=(start, end)).delete()
        GpSession.objects.bulk_create(rows)
    return len(matched), sorted(unmatched), int(payload.get("without_email") or 0)


def sync(client=None, now=None):
    client = client or GpClient.from_settings()
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    start, end = today - BACK, today + AHEAD
    run = SyncRun.objects.create(source=SOURCE)
    try:
        payload = client.sessions(start, end)
        seen, unmatched, without_email = _apply(payload, start, end, now)
        run.ok, run.people_seen = True, seen
        run.detail = {"unmatched": unmatched, "without_email": without_email}
        notes = []
        if unmatched:
            notes.append(f"{len(unmatched)} email{'s' if len(unmatched) != 1 else ''} unmatched")
        if without_email:
            notes.append(f"{without_email} clinician{'s' if without_email != 1 else ''} without an email")
        run.message = "; ".join(notes)
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
