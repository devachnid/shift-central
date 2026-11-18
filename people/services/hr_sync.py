"""Pull people from Practice HR (spec, section 3). One transaction: upsert
by employee id, overwrite the HR-owned fields, never touch the typed ones,
never delete. A person absent from the feed keeps their last_seen_from_hr,
which the Health card reads.

Each record's `contracts` (allowance spec, 5.1) are copied to
people.Contract, replacing the person's rows; a record without the key
leaves the copy alone. A person whose hours contracts in force add up to
more than 0 has their weekly hours from them (5.4)."""

import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from people.models import Contract, Person, SyncRun, Team
from people.services import audit, contracts, profiles
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


TWO_PLACES = Decimal("0.01")
CONTRACT_FIELDS = ("hr_id", "type_name", "unit", "from_day", "to_day", "weekly_amount", "full_time_weekly",
                   "leave_base", "leave_steps")


def _amount(value):
    """An amount as Practice HR sends it: a string, "22.50"."""
    if not isinstance(value, str):
        raise ValueError
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError from None
    if not number.is_finite() or not 0 <= number < 1000:
        raise ValueError
    return number.quantize(TWO_PLACES)


def _text(value):
    if not isinstance(value, str) or not value:
        raise ValueError
    return value[:60]


def _contract(raw):
    """One contract of a feed record, as Contract's fields. Anything
    missing or unreadable raises; terms that are readable but cannot be
    worked out (a weekly amount of 0, steps that do not rise) are copied
    as sent, and the entitlement service says so."""
    leave = raw["leave"]
    steps = [] if leave is None else [[_id(step["after_years"]), str(_amount(step["total"]))] for step in leave["steps"]]
    if raw["unit"] not in Contract.Unit.values:
        raise ValueError
    return {"hr_id": _id(raw["id"]), "type_name": _text(raw["contract_type"]), "unit": raw["unit"],
            "from_day": date.fromisoformat(raw["from"]), "to_day": _date(raw["to"]),
            "weekly_amount": _amount(raw["weekly_amount"]), "full_time_weekly": _amount(raw["full_time_weekly"]),
            "leave_base": None if leave is None else _amount(leave["base"]), "leave_steps": steps}


def _contracts(value):
    rows = sorted((_contract(raw) for raw in value), key=lambda c: c["hr_id"])
    if len({c["hr_id"] for c in rows}) != len(rows):
        raise ValueError
    return rows


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
    fields["team_name"] = None          # no position today: see _apply
    if record.get("positions"):
        fields["team_name"] = _field(record, "positions", _first_team, position=position)
    # None when the key is absent (an older Practice HR): the copy is left alone.
    fields["contracts"] = _field(record, "contracts", _contracts, position=position) if "contracts" in record else None
    return employee_id, fields


def _copy_contracts(person, rows):
    """Replace the person's copied contracts with the feed's. Unchanged
    rows are left as they are, so a run that brings nothing new writes
    nothing. A contract id held under anyone else goes too: the id is HR's."""
    have = [{name: getattr(c, name) for name in CONTRACT_FIELDS} for c in person.contracts.order_by("hr_id")]
    if have == rows:
        return
    Contract.objects.filter(Q(person=person) | Q(hr_id__in=[c["hr_id"] for c in rows])).delete()
    Contract.objects.bulk_create([Contract(person=person, **c) for c in rows])


def _own_weekly_hours(person, today):
    """Allowance spec, 5.4: a person whose hours contracts in force today
    (on the start date, for a starter) add up to more than 0 has that sum
    as their weekly hours. A GP has none. Bank staff on a 0-hour contract
    and someone between contracts keep the hours typed here."""
    if person.is_gp:
        return
    weekly = contracts.weekly_hours_on(list(person.contracts.all()), max(today, person.start_date))
    if weekly:
        profiles.set_weekly_hours_from_hr(person, weekly)


def _team(name, cache):
    if not name:
        return None
    if name not in cache:
        cache[name], _ = Team.objects.get_or_create(name=name)
    return cache[name]


def _apply(records, seen_at):
    """HR's feed gives today's positions, so a starter whose post begins next
    month has none yet, and nor does someone between posts. A record with no
    position keeps the person's team; a new person with none starts without
    one, for an all-teams manager to see on the Staff list meanwhile."""
    teams = {}
    leaving = []
    today = timezone.localdate()
    for position, record in enumerate(records, start=1):
        employee_id, fields = _parse(record, position)
        team_name = fields.pop("team_name")
        sent = fields.pop("contracts")
        person = Person.objects.filter(hr_employee_id=employee_id).first()
        if team_name is None and person is not None:
            fields["team"] = person.team
        else:
            fields["team"] = _team(team_name, teams)
        if person is None:
            person = Person.objects.create(hr_employee_id=employee_id, last_seen_from_hr=seen_at,
                                           **fields)
            audit.record(None, person, {"created": ("", f"employee {employee_id}")},
                         note=audit.SYNC_NOTE)
        else:
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
                if "end_date" in changes:
                    leaving.append(person)
        if sent is not None:
            _copy_contracts(person, sent)
        _own_weekly_hours(person, today)
    return leaving


def sync(client=None):
    """Run one sync and return its SyncRun. Never raises: a failure is the
    run's message, and the previous data stands."""
    client = client or HRClient.from_settings()
    run = SyncRun.objects.create()
    leaving = []
    try:
        records = client.people()
        with transaction.atomic():
            leaving = _apply(records, timezone.now())
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
    if run.ok:
        from leave.services import leavers       # people → leave only here, at call time
        flag_failed = False
        for person in leaving:
            try:
                leavers.flag(person)
            except Exception:
                log.exception("leaver flag failed for person %s", person.pk)
                flag_failed = True
        if flag_failed:
            # Shown on the Health card's sync line: the date is not "changed" on the next sync, so nothing retries it.
            run.message = (run.message + "; " if run.message else "") + "leaver flag failed; see the journal"
            run.save(update_fields=["message"])
        try:
            with transaction.atomic():
                profiles.apply_due_hours_changes()
        except Exception:
            log.exception("hours changes failed")
            run.message = (run.message + "; " if run.message else "") + "hours changes failed; see the journal"
            run.save(update_fields=["message"])
    return run


def not_seen_recently(now=None):
    """People gone from HR's feed: the last good run left them out, and they
    have not been in it for over a day.

    Measured against the last successful run, not the clock: a day of
    failed runs advances nobody's last_seen_from_hr, and judged by the
    clock alone that would list everyone. With no good run in the last
    day there is nothing to judge by, so nobody is listed; the Practice HR
    box on the Health card is red instead."""
    now = now or timezone.now()
    good = SyncRun.objects.filter(source="practice-hr", ok=True,
                                  started_at__gte=now - NEVER_SEEN_AFTER).first()
    if good is None:
        return Person.objects.none()
    return Person.objects.filter(last_seen_from_hr__lt=min(good.started_at, now - NEVER_SEEN_AFTER))


def last_run():
    return SyncRun.objects.filter(source="practice-hr").first()
