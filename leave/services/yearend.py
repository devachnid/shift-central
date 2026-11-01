"""LEAVE-21, 22 and 24: the year-end flag. When a person's leave year has
just ended, a YearEnd row records what was left; the managers are emailed;
on the page one chooses carry all, lose all or carry part (and keep or
lose TOIL), and the choice is written as Adjustments in the new year with
the reason the statement then shows."""

import logging
from datetime import date, timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from leave.models import Booking, YearEnd
from leave.services import adjustments, balances, hours, notify, sickness, years
from leave.services.common import recipients
from people.models import Person
from people.services import access, audit

log = logging.getLogger("leave.yearend")

OPEN_WINDOW = timedelta(days=31)
LAUNCH = date(2027, 1, 1)     # go-live: a leave year that ended before it was settled by hand (MIG-04)


def open_due(today=None):
    """Open a row for each current person whose leave year began within the
    last month and whose ended year has no row yet. A year with no allowance
    (everyone's 2026) opens nothing; nothing left closes at once. Returns
    the rows that need a decision."""
    today = today or timezone.localdate()
    opened = []
    for person in Person.objects.current(on=today).order_by("pk"):
        try:
            row = _open_one(person, today)
        except Exception:
            log.exception("year end: person %s", person.pk)
            continue
        if row is not None and not row.decided:
            opened.append(row)
    return opened


def _open_one(person, today):
    """The row opened for this person today, or None when none is due."""
    year = years.year_of(person, today)
    if today - year > OPEN_WINDOW:
        return None
    ended = years.previous_year(year)
    if years.year_end(ended) < LAUNCH:
        return None
    if YearEnd.objects.filter(person=person, year_ended=ended).exists():
        return None
    s = balances.statement(person, ended)
    if s.missing:
        return None
    row = YearEnd(person=person, year_ended=ended, annual_remaining=s.annual_remaining, toil_remaining=s.toil_remaining)
    if s.annual_remaining == 0 and s.toil_remaining <= 0:
        row.decided_at, row.note = timezone.now(), "nothing left"
        row.annual_carried = row.annual_lost = row.toil_lost = 0
    row.save()
    return row


def notify_opened(rows, base_url=""):
    """One email per manager, naming the people they manage among rows."""
    by_manager = {}
    for row in rows:
        for m in recipients(row.person):
            by_manager.setdefault(m.pk, (m, []))[1].append(row)
    for manager, theirs in by_manager.values():
        notify.year_end(manager, theirs, base_url)
    YearEnd.objects.filter(pk__in=[r.pk for r in rows]).update(notified_at=timezone.now())
    return len(by_manager)


def run(today=None, base_url=""):
    rows = open_due(today)
    # Rows saved by an earlier run that never got as far as the email are sent now.
    pending = list(YearEnd.objects.filter(decided_at__isnull=True, notified_at__isnull=True).select_related("person__team"))
    if pending:
        notify_opened(pending, base_url)
    return len(rows)


def long_absence(row):
    """Whether a long sickness or a flagged-return booking touched the year
    (LEAVE-29: marked in the year-end flag)."""
    end = years.year_end(row.year_ended)
    rows = Booking.objects.filter(person=row.person, status__in=Booking.ACTIVE, first_day__lte=end, last_day__gte=row.year_ended).select_related("type")
    return any(b.type.flag_return or (b.type.sickness and sickness.is_long(b)) for b in rows)


def _now(person, year_ended):
    """(annual_remaining, toil_remaining) for the ended year as they stand
    today, or None when its allowance is no longer set."""
    s = balances.statement(person, year_ended)
    return None if s.missing else (s.annual_remaining, s.toil_remaining)


def live(row):
    """An open row with its figures as they stand today, not as the flag
    found them: last year's statement is put right in January, a conversion
    gives hours back and TOIL runs on. Not saved; a decided row is returned
    as it is."""
    if not row.decided:
        figures = _now(row.person, row.year_ended)
        if figures is not None:
            row.annual_remaining, row.toil_remaining = figures
    return row


def open_rows(user):
    return list(YearEnd.objects.filter(person__in=access.managed_people(user), decided_at__isnull=True).select_related("person__team"))


def decide(user, row, annual_carry, toil_keep=None, note=""):
    if not access.can_manage(user, row.person):
        raise PermissionDenied("you don't manage this person")
    with transaction.atomic():
        fresh = YearEnd.objects.select_related("person").get(pk=row.pk)
        if fresh.decided:
            raise ValueError("Already decided")
        figures = _now(fresh.person, fresh.year_ended)      # the figures now, not those the flag found
        if figures is not None:
            fresh.annual_remaining, fresh.toil_remaining = figures
        remaining = fresh.annual_remaining
        low, high = (remaining, 0) if remaining < 0 else (0, remaining)
        if not (low <= int(annual_carry) <= high):
            raise ValueError(f"Carry between {hours.fmt(low)} and {hours.fmt(high)}")
        toil_keep = fresh.toil_remaining if toil_keep is None else int(toil_keep)
        toil_lost = 0
        if fresh.toil_remaining > 0:
            if not (0 <= toil_keep <= fresh.toil_remaining):
                raise ValueError(f"Keep between 0 min and {hours.fmt(fresh.toil_remaining)} of TOIL")
            toil_lost = fresh.toil_remaining - toil_keep
        new_year = years.next_year(fresh.year_ended)
        label = years.label(fresh.year_ended)
        if annual_carry:
            reason = f"{'deficit ' if annual_carry < 0 else ''}carried over from {label}"
            adjustments.add(user, fresh.person, new_year, "annual", annual_carry, reason)
        if toil_lost:
            adjustments.add(user, fresh.person, new_year, "toil", -toil_lost, f"TOIL lost at year end {label}")
        fresh.annual_carried, fresh.annual_lost, fresh.toil_lost = int(annual_carry), remaining - int(annual_carry), toil_lost
        fresh.decided_by, fresh.decided_at, fresh.note = user, timezone.now(), (note or "").strip()[:300]
        fresh.save()
        audit.record_as(user, "leave.yearend", fresh.person_id,
                        {f"year end {label}": ("", f"carried {hours.fmt(fresh.annual_carried)}, lost {hours.fmt(fresh.annual_lost)}, TOIL lost {hours.fmt(toil_lost)}")},
                        note=fresh.note)
    return fresh
