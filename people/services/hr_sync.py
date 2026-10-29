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


def _id(value):
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError
    return value


def _first_team(positions):
    return positions[0]["team"]


def _field(record, key, convert=None, *, required=True, position):
    """One field of a feed record, converted. A failure names the record's
    place in the feed and the field, never a value: HR's records are
    everyone's name, email and dates, and the message reaches the Health card."""
    try:
        value = record[key] if required else record.get(key)
        return convert(value) if convert else value
    except (KeyError, TypeError, ValueError, IndexError, AttributeError):
        raise BadRecord(f"record {position} in the feed: missing or bad {key}") from None


def _parse(record, position):
    """The fields Person takes from one feed record."""
    employee_id = _field(record, "id", _id, position=position)
    fields = {key: _field(record, key, position=position)
              for key in ("first_name", "last_name", "name", "email")}
    employment = _field(record, "employment", position=position)
    fields["start_date"] = _field(employment, "start", _date, position=position)
    if fields["start_date"] is None:
        raise BadRecord(f"record {position} in the feed: missing or bad start")
    fields["end_date"] = _field(employment, "end", _date, required=False, position=position)
    fields["is_gp"] = record.get("unit") == "sessions"
    fields["team_name"] = ""
    if record.get("positions"):
        fields["team_name"] = _field(record, "positions", _first_team, position=position)
    return employee_id, fields


def _team(name, cache):
    if not name:
        return None
    if name not in cache:
        cache[name], _ = Team.objects.get_or_create(name=name)
    return cache[name]


def _apply(records, seen_at):
    teams = {}
    for position, record in enumerate(records, start=1):
        employee_id, fields = _parse(record, position)
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
            audit.record(None, person, changes,
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
    except Exception:
        run.message = "unexpected error; see the journal"
        log.exception("hr_sync failed")
    finally:
        run.finished_at = timezone.now()
        run.save()
    return run


def not_seen_recently(now=None):
    """People the last day's syncs did not include — gone from HR's feed."""
    now = now or timezone.now()
    return Person.objects.filter(last_seen_from_hr__lt=now - NEVER_SEEN_AFTER)


def last_run():
    return SyncRun.objects.first()
