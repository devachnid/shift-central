"""Pull people from Practice HR (spec, section 3). One transaction: upsert
by employee id, overwrite the HR-owned fields, never touch the typed ones,
never delete. A person absent from the feed keeps their last_seen_from_hr,
which the Health card reads."""

import logging
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from people.models import Person, SyncRun, Team
from people.services import audit
from people.services.hr_client import HRClient, HRError

log = logging.getLogger("people.hr_sync")

NEVER_SEEN_AFTER = timedelta(days=1)
HR_FIELDS = ("first_name", "last_name", "name", "email", "team", "start_date", "end_date", "is_gp")


class BadRecord(Exception):
    pass


def _date(value):
    return date.fromisoformat(value) if value else None


def _parse(record):
    """The fields Person takes from one feed record. Names only in the
    error, never values."""
    try:
        employee_id = int(record["id"])
        employment = record["employment"]
        positions = record.get("positions") or []
        team_name = positions[0]["team"] if positions else ""
        return employee_id, {
            "first_name": record["first_name"], "last_name": record["last_name"],
            "name": record["name"], "email": record["email"],
            "start_date": _date(employment["start"]), "end_date": _date(employment.get("end")),
            "is_gp": record.get("unit") == "sessions", "team_name": team_name,
        }
    except (KeyError, TypeError, ValueError, IndexError) as e:
        ident = record.get("id", "?") if isinstance(record, dict) else "?"
        raise BadRecord(f"record id {ident}: missing or bad {e.__class__.__name__}: {e}") from None


def _team(name, cache):
    if not name:
        return None
    if name not in cache:
        cache[name], _ = Team.objects.get_or_create(name=name)
    return cache[name]


def _apply(records, seen_at):
    teams = {}
    for record in records:
        employee_id, fields = _parse(record)
        if fields["start_date"] is None:
            raise BadRecord(f"record id {employee_id}: no employment start")
        team = _team(fields.pop("team_name"), teams)
        fields["team"] = team
        person = Person.objects.filter(hr_employee_id=employee_id).first()
        if person is None:
            person = Person.objects.create(hr_employee_id=employee_id, last_seen_from_hr=seen_at,
                                           **fields)
            audit.record(None, person, {"created": ("", f"employee {employee_id}")},
                         note=audit.SYNC_NOTE)
            continue
        changes = {}
        for field in HR_FIELDS:
            before, after = getattr(person, field), fields[field]
            if before != after:
                changes[field] = (before, after)
                setattr(person, field, after)
        person.last_seen_from_hr = seen_at
        person.save()
        if changes:
            audit.record(None, person, {k: (str(b), str(a)) for k, (b, a) in changes.items()},
                         note=audit.SYNC_NOTE)


def sync(client=None):
    """Run one sync and return its SyncRun. Never raises: a failure is the
    run's message, and the previous data stands."""
    client = client or HRClient.from_settings()
    run = SyncRun.objects.create()
    try:
        records = client.people()
        with transaction.atomic():
            _apply(records, timezone.now())
        run.ok, run.people_seen = True, len(records)
    except (HRError, BadRecord) as e:
        run.message = str(e)[:300]
        log.warning("hr_sync failed: %s", run.message)
    run.finished_at = timezone.now()
    run.save()
    return run


def not_seen_recently(now=None):
    """People the last day's syncs did not include — gone from HR's feed."""
    now = now or timezone.now()
    return Person.objects.filter(last_seen_from_hr__lt=now - NEVER_SEEN_AFTER)


def last_run():
    return SyncRun.objects.first()
