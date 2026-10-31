"""The booking lifecycle (spec section 4). Every function audits under
leave.booking against the person; every write is one transaction; emails
go after the commit through leave.services.notify, which never raises."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from leave.models import Booking, BookingDay
from leave.services import balances, blackouts, costing, hours, notify, years
from leave.services.common import LeaveError, describe
from people.services import access, audit
from shifts.models import Entry
from shifts.services import render
from shifts.services.entries import _touch

ACCOUNT_LABEL = {"annual": "annual leave", "bank_holiday": "bank holiday allowance", "toil": "TOIL"}


# --- who may --------------------------------------------------------------

def may_request(user, person):
    return access.is_self(user, person)


def may_book(user, person):
    return access.can_manage(user, person) or (access.is_self(user, person) and person.own_leave_without_approval)


def may_decide(user, booking):
    return access.can_manage(user, booking.person)


def may_view_detail(user, booking):
    return access.is_self(user, booking.person) or access.can_manage(user, booking.person)


# --- checks ---------------------------------------------------------------

def _check_dates(person, first, last, part, start, finish):
    if first > last:
        raise LeaveError("dates", "The last day is before the first")
    if part != "whole" and first != last:
        raise LeaveError("dates", "A half day or times is one day")
    if part == "times" and (start is None or finish is None or start >= finish):
        raise LeaveError("dates", "Give a start before a finish")
    if part != "times" and (start or finish):
        raise LeaveError("dates", "Times are for a timed booking only")
    allowed = years.years_for(person)
    if years.year_of(person, first) not in allowed or years.year_of(person, last) not in allowed:
        raise LeaveError("dates", "Leave can be booked in this leave year and the next")


def _check_overlap(person, first, last, exclude=None):
    rows = Booking.objects.filter(person=person, status__in=Booking.LIVE, first_day__lte=last, last_day__gte=first)
    if exclude is not None:
        rows = rows.exclude(pk=exclude.pk)
    clash = rows.first()
    if clash is not None:
        raise LeaveError("overlap", f"{clash.label} is already booked for {clash.first_day:%-d %b}")


def preview(person, leave_type, first, last, part, start=None, finish=None):
    probe = Booking(person=person, type=leave_type, first_day=first, last_day=last, part=part, start=start, finish=finish)
    return [costing.cost(person, leave_type, d, part, start, finish) for d in probe.days()]


def _total(costs):
    out = {}
    for c in costs:
        out[c.account] = out.get(c.account, 0) + c.seconds
    return out


def _check_balance(person, first, costs):
    year = years.year_of(person, first)
    for account, seconds in _total(costs).items():
        if account == "none" or seconds == 0:
            continue
        available = balances.available(person, year, account)
        if available is not None and seconds > available:
            raise LeaveError("balance", f"This would take {hours.fmt(seconds)} of {ACCOUNT_LABEL[account]} and {hours.fmt(max(available, 0))} is available")


def suggestion_for(person, day):
    return costing.suggestion(person, day)


# --- request and book -----------------------------------------------------

def _new(user, person, leave_type, first, last, part, start, finish, description, paid, note, status):
    if leave_type.archived:
        raise LeaveError("type", "That leave type is no longer in use")
    if leave_type.paid_choice:
        paid = leave_type.default_paid if paid is None else bool(paid)
    else:
        paid = None if leave_type.name != "Unpaid leave" else False
    return Booking(person=person, type=leave_type, first_day=first, last_day=last, part=part, start=start, finish=finish,
                   description=(description or "").strip()[:80], paid=paid, status=status, requested_by=user,
                   staff_note=(note or "")[:300] if status == Booking.Status.PENDING else "",
                   manager_note=(note or "")[:300] if status != Booking.Status.PENDING else "")


def request(user, person, leave_type, first, last, part, start=None, finish=None, description="", paid=None, note="", base_url=""):
    if not may_request(user, person):
        raise PermissionDenied("you can only request your own leave")
    if not leave_type.requestable:
        raise LeaveError("type", f"{leave_type.name} is recorded by a manager, not requested")
    _check_dates(person, first, last, part, start, finish)
    _check_overlap(person, first, last)
    for day in Booking(first_day=first, last_day=last).days():
        if blackouts.blocks(person, day):
            raise LeaveError("blackout", f"Leave cannot be requested for {day:%a %-d %b}")
    costs = preview(person, leave_type, first, last, part, start, finish)
    _check_balance(person, first, costs)
    booking = _new(user, person, leave_type, first, last, part, start, finish, description, paid, note, Booking.Status.PENDING)
    with transaction.atomic():
        booking.save()
        audit.record_as(user, "leave.booking", person.pk, {"booking": ("", describe(booking, sum(c.seconds for c in costs)))}, note="requested")
    notify.request_made(booking, base_url)
    return booking


def book(user, person, leave_type, first, last, part, start=None, finish=None, description="", paid=None, note="", costs=None, base_url=""):
    """A manager's booking, approved as it is made. `costs` is {day: seconds}
    typed on the Advanced tab; each becomes an override."""
    if not may_book(user, person):
        raise PermissionDenied("you don't manage this person")
    _check_dates(person, first, last, part, start, finish)
    _check_overlap(person, first, last)
    booking = _new(user, person, leave_type, first, last, part, start, finish, description, paid, note, Booking.Status.APPROVED)
    booking.decided_by, booking.decided_at = user, timezone.now()
    with transaction.atomic():
        booking.save()
        days = _apply(booking)
        for bd in days:
            typed = (costs or {}).get(bd.day)
            if typed is not None:          # a typed figure is always an override, so a bank holiday day reads "bank holiday" even at the rota's cost
                bd.cost_seconds, bd.source, bd.placeholder = int(typed), BookingDay.Source.OVERRIDE, False
                bd.override_by, bd.override_note = user, (note or "set when booked")[:300]
                bd.save()
        audit.record_as(user, "leave.booking", person.pk, {"booking": ("", describe(booking))}, note="booked by a manager")
    _after_apply(booking, days, base_url)
    return booking


def approve(user, booking, note="", base_url=""):
    if not may_decide(user, booking):
        raise PermissionDenied("you don't manage this person")
    if booking.status != Booking.Status.PENDING:
        raise LeaveError("status", "This request has already been decided")
    _check_overlap(booking.person, booking.first_day, booking.last_day, exclude=booking)
    before = describe(booking)
    with transaction.atomic():
        booking.status, booking.decided_by, booking.decided_at, booking.manager_note = Booking.Status.APPROVED, user, timezone.now(), (note or "")[:300]
        booking.save()
        days = _apply(booking)
        audit.record_as(user, "leave.booking", booking.person_id, {"booking": (before, describe(booking))}, note="approved")
    notify.decided(booking, base_url)
    _after_apply(booking, days, base_url)


def decline(user, booking, note="", base_url=""):
    if not may_decide(user, booking):
        raise PermissionDenied("you don't manage this person")
    if booking.status != Booking.Status.PENDING:
        raise LeaveError("status", "This request has already been decided")
    before = describe(booking)
    with transaction.atomic():
        booking.status, booking.decided_by, booking.decided_at, booking.manager_note = Booking.Status.DECLINED, user, timezone.now(), (note or "")[:300]
        booking.save()
        audit.record_as(user, "leave.booking", booking.person_id, {"booking": (before, describe(booking))}, note="declined")
    notify.decided(booking, base_url)


# --- apply and undo -------------------------------------------------------

def _shorten(booking, day):
    """The one uncovered shift whose span contains the leave; returns the
    entry and its original times, or (None, None, None)."""
    for e in Entry.objects.filter(person=booking.person, day=day, kind=Entry.Kind.SHIFT, covered_by__isnull=True).order_by("position"):
        if e.start <= booking.start and e.finish >= booking.finish:
            original = (e.start, e.finish)
            if booking.start == e.start:
                e.start = booking.finish
            elif booking.finish == e.finish:
                e.finish = booking.start
            else:
                e.finish = booking.start
            if e.start >= e.finish:
                # the leave is the whole shift: keep the row, cover it instead
                e.start, e.finish = original
                return e, None, None
            e.save(update_fields=["start", "finish", "updated_at"])
            return e, original[0], original[1]
    return None, None, None


def _apply(booking):
    """Cost each day, write its BookingDay, cover or shorten the entries,
    record a DayChange where the day's text changes. Inside the caller's
    transaction."""
    days = []
    for day in booking.days():
        before = render.day_text(booking.person, day)
        c = costing.cost(booking.person, booking.type, day, booking.part, booking.start, booking.finish)
        bd = BookingDay.objects.create(booking=booking, day=day, cost_seconds=c.seconds, source=c.source, account=c.account, placeholder=c.placeholder)
        if booking.part == Booking.Part.TIMES:
            entry, s, f = _shorten(booking, day)
            if entry is not None and s is None:
                Entry.objects.filter(pk=entry.pk).update(covered_by=bd)
            elif entry is not None:
                bd.shortened_entry, bd.original_start, bd.original_finish = entry, s, f
                bd.save(update_fields=["shortened_entry", "original_start", "original_finish"])
        else:
            Entry.objects.filter(person=booking.person, day=day, covered_by__isnull=True).update(covered_by=bd)
        if render.day_text(booking.person, day) != before:
            _touch(booking.person, day, before=before)
        days.append(bd)
    return days


def _undo(booking):
    for bd in BookingDay.objects.filter(booking=booking).select_related("shortened_entry"):
        before = render.day_text(booking.person, bd.day)
        Entry.objects.filter(covered_by=bd).update(covered_by=None)
        e = bd.shortened_entry
        if e is not None and bd.original_start is not None:
            e.start, e.finish = bd.original_start, bd.original_finish
            e.save(update_fields=["start", "finish", "updated_at"])
        bd.delete()
        if render.day_text(booking.person, bd.day) != before:
            _touch(booking.person, bd.day, before=before)


def _after_apply(booking, days, base_url):
    flagged = [bd for bd in days if bd.placeholder]
    if flagged:
        notify.cost_to_check(booking.person, flagged, base_url)


# --- cancel ---------------------------------------------------------------

def request_cancel(user, booking, note="", base_url=""):
    if not access.is_self(user, booking.person):
        raise PermissionDenied("you can only cancel your own leave")
    if booking.status != Booking.Status.APPROVED:
        raise LeaveError("status", "Only approved leave can be cancelled")
    if booking.last_day < timezone.localdate():
        raise LeaveError("dates", "Leave in the past is cancelled by a manager")
    before = describe(booking)
    with transaction.atomic():
        booking.status, booking.cancel_requested_at, booking.staff_note = Booking.Status.CANCEL_REQUESTED, timezone.now(), (note or "")[:300]
        booking.save()
        audit.record_as(user, "leave.booking", booking.person_id, {"booking": (before, describe(booking))}, note="cancellation requested")
    notify.cancel_requested(booking, base_url)


def decide_cancel(user, booking, approve, note="", base_url=""):
    if not may_decide(user, booking):
        raise PermissionDenied("you don't manage this person")
    if booking.status != Booking.Status.CANCEL_REQUESTED:
        raise LeaveError("status", "No cancellation is waiting on this booking")
    before = describe(booking)
    with transaction.atomic():
        if approve:
            _undo(booking)
            booking.status = Booking.Status.CANCELLED
        else:
            booking.status = Booking.Status.APPROVED
        booking.cancel_decided_by, booking.cancel_decided_at, booking.manager_note = user, timezone.now(), (note or "")[:300]
        booking.save()
        audit.record_as(user, "leave.booking", booking.person_id, {"booking": (before, describe(booking))},
                        note="cancellation approved" if approve else "cancellation refused")
    notify.cancel_decided(booking, approve, base_url)


def cancel(user, booking, note="", base_url=""):
    """A manager cancels outright, past days included."""
    if not may_decide(user, booking):
        raise PermissionDenied("you don't manage this person")
    if booking.status not in Booking.LIVE:
        raise LeaveError("status", "This booking is not live")
    before = describe(booking)
    with transaction.atomic():
        _undo(booking)
        booking.status, booking.cancel_decided_by, booking.cancel_decided_at, booking.manager_note = Booking.Status.CANCELLED, user, timezone.now(), (note or "")[:300]
        booking.save()
        audit.record_as(user, "leave.booking", booking.person_id, {"booking": (before, describe(booking))}, note="cancelled by a manager")
    notify.cancel_decided(booking, True, base_url)


# --- edit, override, recost -----------------------------------------------

EDITABLE = ("type", "first", "last", "part", "start", "finish", "description", "paid")


def edit(user, booking, base_url="", **fields):
    if not may_decide(user, booking):
        raise PermissionDenied("you don't manage this person")
    if booking.status not in (Booking.Status.APPROVED, Booking.Status.PENDING):
        raise LeaveError("status", "Only approved or pending leave can be edited")
    unknown = set(fields) - set(EDITABLE)
    if unknown:
        raise ValueError(f"not editable: {sorted(unknown)}")
    first = fields.get("first", booking.first_day)
    last = fields.get("last", booking.last_day)
    part = fields.get("part", booking.part)
    start = fields.get("start", booking.start) if part == "times" else None
    finish = fields.get("finish", booking.finish) if part == "times" else None
    _check_dates(booking.person, first, last, part, start, finish)
    _check_overlap(booking.person, first, last, exclude=booking)
    before = describe(booking)
    with transaction.atomic():
        was_active = booking.is_active
        if was_active:
            _undo(booking)
        booking.first_day, booking.last_day, booking.part, booking.start, booking.finish = first, last, part, start, finish
        if "type" in fields:
            booking.type = fields["type"]
        if "description" in fields:
            booking.description = (fields["description"] or "").strip()[:80]
        if "paid" in fields and booking.type.paid_choice:
            booking.paid = bool(fields["paid"])
        booking.save()
        days = _apply(booking) if was_active else []
        audit.record_as(user, "leave.booking", booking.person_id, {"booking": (before, describe(booking))}, note="edited by a manager")
    _after_apply(booking, days, base_url)


def override_day(user, booking_day, seconds, note):
    if not may_decide(user, booking_day.booking):
        raise PermissionDenied("you don't manage this person")
    if not (note or "").strip():
        raise ValueError("A reason is needed to override a day's cost")
    before = booking_day.cost_seconds
    with transaction.atomic():
        booking_day.cost_seconds, booking_day.source, booking_day.placeholder = int(seconds), BookingDay.Source.OVERRIDE, False
        booking_day.override_by, booking_day.override_note = user, note.strip()[:300]
        booking_day.save()
        audit.record_as(user, "leave.booking", booking_day.booking.person_id,
                        {f"cost {booking_day.day.isoformat()}": (hours.fmt(before), hours.fmt(booking_day.cost_seconds))}, note=note.strip()[:300])


def recost(booking_day):
    """Re-cost a whole day from the rota; half-day, timed and overridden days
    keep their cost. Covers the day's entries either way. Returns whether
    the figure changed."""
    booking = booking_day.booking
    if booking.part == Booking.Part.TIMES or booking_day.source == BookingDay.Source.OVERRIDE:
        return False
    Entry.objects.filter(person=booking.person, day=booking_day.day, covered_by__isnull=True).update(covered_by=booking_day)
    if booking.part != Booking.Part.WHOLE:
        return False
    c = costing.cost(booking.person, booking.type, booking_day.day, "whole", include=booking_day)
    changed = c.seconds != booking_day.cost_seconds or booking_day.placeholder
    booking_day.cost_seconds, booking_day.source, booking_day.placeholder = c.seconds, c.source, c.placeholder
    booking_day.save(update_fields=["cost_seconds", "source", "placeholder"])
    return changed


def after_rota_write(person, day, base_url=""):
    """Called by entries._write after writing a day that has an active
    BookingDay. Covers the new entries, re-costs, flags managers when the
    cost changed, and returns the pks of the entries still visible."""
    bd = costing.active_day(person, day)
    if bd is None:
        return list(Entry.objects.filter(person=person, day=day).values_list("pk", flat=True))
    if recost(bd):
        notify.cost_to_check(person, [bd], base_url)
    return list(Entry.objects.filter(person=person, day=day, covered_by__isnull=True).values_list("pk", flat=True))
