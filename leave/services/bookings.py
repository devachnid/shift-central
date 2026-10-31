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


def _reread(booking):
    """The booking as it stands now. The caller's instance may be stale (a
    second worker decided it meanwhile); call inside the transaction, where
    SQLite's IMMEDIATE mode has already serialised writers."""
    return Booking.objects.select_related("person", "type").get(pk=booking.pk)


def _mail(send, *args):
    """Send after the outermost commit, never inside a write lock or before
    a rollback; at once when no transaction is open."""
    transaction.on_commit(lambda: send(*args))


def request(user, person, leave_type, first, last, part, start=None, finish=None, description="", paid=None, note="", base_url=""):
    if not may_request(user, person):
        raise PermissionDenied("you can only request your own leave")
    if not leave_type.requestable:
        raise LeaveError("type", f"{leave_type.name} is recorded by a manager, not requested")
    _check_dates(person, first, last, part, start, finish)
    for day in Booking(first_day=first, last_day=last).days():
        if blackouts.blocks(person, day):
            raise LeaveError("blackout", f"Leave cannot be requested for {day:%a %-d %b}")
    costs = preview(person, leave_type, first, last, part, start, finish)
    _check_balance(person, first, costs)
    booking = _new(user, person, leave_type, first, last, part, start, finish, description, paid, note, Booking.Status.PENDING)
    with transaction.atomic():
        _check_overlap(person, first, last)
        booking.save()
        audit.record_as(user, "leave.booking", person.pk, {"booking": ("", describe(booking, sum(c.seconds for c in costs)))}, note="requested")
    _mail(notify.request_made, booking, base_url)
    return booking


def _type_costs(user, rows, costs, note):
    """A manager's typed figures become overrides on the booking's days (a
    typed figure is always an override, so a bank holiday day reads "bank
    holiday" even at the rota's cost). Returns the audit lines."""
    changes = {}
    for bd in rows:
        typed = (costs or {}).get(bd.day)
        if typed is not None and not (bd.source == BookingDay.Source.OVERRIDE and bd.cost_seconds == int(typed)):   # an unchanged figure keeps its note
            before = bd.cost_seconds
            bd.cost_seconds, bd.source, bd.placeholder = int(typed), BookingDay.Source.OVERRIDE, False
            bd.override_by, bd.override_note = user, note[:300]
            bd.save()
            if before != bd.cost_seconds:
                changes[f"cost {bd.day.isoformat()}"] = (hours.fmt(before), hours.fmt(bd.cost_seconds))
    return changes


def book(user, person, leave_type, first, last, part, start=None, finish=None, description="", paid=None, note="", costs=None, base_url=""):
    """A manager's booking, approved as it is made. `costs` is {day: seconds}
    typed on the Advanced tab; each becomes an override. Only a manager's
    typed figures count: a person booking their own leave is costed from
    the rota."""
    if not may_book(user, person):
        raise PermissionDenied("you don't manage this person")
    if not access.can_manage(user, person):
        costs = None
    _check_dates(person, first, last, part, start, finish)
    booking = _new(user, person, leave_type, first, last, part, start, finish, description, paid, note, Booking.Status.APPROVED)
    booking.decided_by, booking.decided_at = user, timezone.now()
    with transaction.atomic():
        _check_overlap(person, first, last)
        booking.save()
        days = _apply(booking)
        _type_costs(user, days, costs, note or "set when booked")
        audit.record_as(user, "leave.booking", person.pk, {"booking": ("", describe(booking))}, note="booked by a manager")
    _after_apply(booking, days, base_url)
    return booking


def approve(user, booking, note="", base_url=""):
    if not may_decide(user, booking):
        raise PermissionDenied("you don't manage this person")
    with transaction.atomic():
        fresh = _reread(booking)
        if fresh.status != Booking.Status.PENDING:
            raise LeaveError("status", "This request has already been decided")
        _check_overlap(fresh.person, fresh.first_day, fresh.last_day, exclude=fresh)
        before = describe(fresh)
        fresh.status, fresh.decided_by, fresh.decided_at, fresh.manager_note = Booking.Status.APPROVED, user, timezone.now(), (note or "")[:300]
        fresh.save()
        days = _apply(fresh)
        audit.record_as(user, "leave.booking", fresh.person_id, {"booking": (before, describe(fresh))}, note="approved")
    booking.refresh_from_db()
    _mail(notify.decided, fresh, base_url)
    _after_apply(fresh, days, base_url)


def decline(user, booking, note="", base_url=""):
    if not may_decide(user, booking):
        raise PermissionDenied("you don't manage this person")
    with transaction.atomic():
        fresh = _reread(booking)
        if fresh.status != Booking.Status.PENDING:
            raise LeaveError("status", "This request has already been decided")
        before = describe(fresh)
        fresh.status, fresh.decided_by, fresh.decided_at, fresh.manager_note = Booking.Status.DECLINED, user, timezone.now(), (note or "")[:300]
        fresh.save()
        audit.record_as(user, "leave.booking", fresh.person_id, {"booking": (before, describe(fresh))}, note="declined")
    booking.refresh_from_db()
    _mail(notify.decided, fresh, base_url)


# --- apply and undo -------------------------------------------------------

def _remaining(original_start, original_finish, start, finish):
    """What is left of a shift once the leave start-finish is taken from it:
    the leave at the start leaves the end, otherwise the shift stops where
    the leave begins."""
    if start == original_start:
        return finish, original_finish
    return original_start, start


def _shorten(booking, day):
    """The one uncovered shift whose span contains the leave; returns the
    entry and its original times, or (None, None, None)."""
    for e in Entry.objects.filter(person=booking.person, day=day, kind=Entry.Kind.SHIFT, covered_by__isnull=True).order_by("position"):
        if e.start <= booking.start and e.finish >= booking.finish:
            original = (e.start, e.finish)
            e.start, e.finish = _remaining(*original, booking.start, booking.finish)
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
        _mail(notify.cost_to_check, booking.person, flagged, base_url)


# --- cancel ---------------------------------------------------------------

def request_cancel(user, booking, note="", base_url=""):
    if not access.is_self(user, booking.person):
        raise PermissionDenied("you can only cancel your own leave")
    with transaction.atomic():
        fresh = _reread(booking)
        if fresh.status != Booking.Status.APPROVED:
            raise LeaveError("status", "Only approved leave can be cancelled")
        if fresh.last_day < timezone.localdate():
            raise LeaveError("dates", "Leave in the past is cancelled by a manager")
        before = describe(fresh)
        fresh.status, fresh.cancel_requested_at, fresh.staff_note = Booking.Status.CANCEL_REQUESTED, timezone.now(), (note or "")[:300]
        fresh.save()
        audit.record_as(user, "leave.booking", fresh.person_id, {"booking": (before, describe(fresh))}, note="cancellation requested")
    booking.refresh_from_db()
    _mail(notify.cancel_requested, fresh, base_url)


def decide_cancel(user, booking, approve, note="", base_url=""):
    if not may_decide(user, booking):
        raise PermissionDenied("you don't manage this person")
    with transaction.atomic():
        fresh = _reread(booking)
        if fresh.status != Booking.Status.CANCEL_REQUESTED:
            raise LeaveError("status", "No cancellation is waiting on this booking")
        before = describe(fresh)
        if approve:
            _undo(fresh)
            fresh.status = Booking.Status.CANCELLED
        else:
            fresh.status = Booking.Status.APPROVED
        fresh.cancel_decided_by, fresh.cancel_decided_at, fresh.manager_note = user, timezone.now(), (note or "")[:300]
        fresh.save()
        audit.record_as(user, "leave.booking", fresh.person_id, {"booking": (before, describe(fresh))},
                        note="cancellation approved" if approve else "cancellation refused")
    booking.refresh_from_db()
    _mail(notify.cancel_decided, fresh, approve, base_url)


def cancel(user, booking, note="", base_url=""):
    """A manager cancels outright, past days included."""
    if not may_decide(user, booking):
        raise PermissionDenied("you don't manage this person")
    with transaction.atomic():
        fresh = _reread(booking)
        if fresh.status not in Booking.LIVE:
            raise LeaveError("status", "This booking is not live")
        before = describe(fresh)
        _undo(fresh)
        fresh.status, fresh.cancel_decided_by, fresh.cancel_decided_at, fresh.manager_note = Booking.Status.CANCELLED, user, timezone.now(), (note or "")[:300]
        fresh.save()
        audit.record_as(user, "leave.booking", fresh.person_id, {"booking": (before, describe(fresh))}, note="cancelled by a manager")
    booking.refresh_from_db()
    _mail(notify.cancel_decided, fresh, True, base_url)


# --- edit, override, recost -----------------------------------------------

EDITABLE = ("type", "first", "last", "part", "start", "finish", "description", "paid")


def edit(user, booking, base_url="", costs=None, **fields):
    if not may_decide(user, booking):
        raise PermissionDenied("you don't manage this person")
    unknown = set(fields) - set(EDITABLE)
    if unknown:
        raise ValueError(f"not editable: {sorted(unknown)}")
    with transaction.atomic():
        fresh = _reread(booking)
        if fresh.status not in (Booking.Status.APPROVED, Booking.Status.PENDING):
            raise LeaveError("status", "Only approved or pending leave can be edited")
        new_type = fields.get("type", fresh.type)
        first = fields.get("first", fresh.first_day)
        last = fields.get("last", fresh.last_day)
        part = fields.get("part", fresh.part)
        start = fields.get("start", fresh.start) if part == "times" else None
        finish = fields.get("finish", fresh.finish) if part == "times" else None
        relabel = (new_type.pk, first, last, part, start, finish) == (fresh.type_id, fresh.first_day, fresh.last_day, fresh.part, fresh.start, fresh.finish)
        if not relabel:
            _check_dates(fresh.person, first, last, part, start, finish)
            _check_overlap(fresh.person, first, last, exclude=fresh)
        before = describe(fresh)
        days = []
        if relabel:                    # only the label or the paid flag: nothing is re-costed, nothing is uncovered
            _set_labels(fresh, fields)
            fresh.save()
        else:
            was_active = fresh.is_active
            kept = {}
            if was_active:
                kept = {bd.day: (bd.cost_seconds, bd.override_note, bd.override_by_id)
                        for bd in BookingDay.objects.filter(booking=fresh, source=BookingDay.Source.OVERRIDE)}
                _undo(fresh)
            fresh.type, fresh.first_day, fresh.last_day, fresh.part, fresh.start, fresh.finish = new_type, first, last, part, start, finish
            _set_labels(fresh, fields)
            fresh.save()
            days = _apply(fresh) if was_active else []
            for bd in days:            # a manager's typed figure stands when the booking moves or grows
                if bd.day in kept:
                    bd.cost_seconds, bd.override_note, bd.override_by_id = kept[bd.day]
                    bd.source, bd.placeholder = BookingDay.Source.OVERRIDE, False
                    bd.save()
        typed = _type_costs(user, days or list(BookingDay.objects.filter(booking=fresh)), costs, "set when edited")
        audit.record_as(user, "leave.booking", fresh.person_id, {"booking": (before, describe(fresh)), **typed}, note="edited by a manager")
    booking.refresh_from_db()
    _after_apply(fresh, days, base_url)


def _set_labels(booking, fields):
    if "description" in fields:
        booking.description = (fields["description"] or "").strip()[:80]
    if "paid" in fields and booking.type.paid_choice:
        booking.paid = bool(fields["paid"])


def override_day(user, booking_day, seconds, note):
    with transaction.atomic():
        # Re-read inside the transaction: a stale instance must never
        # resurrect a day of a booking that has since been cancelled.
        booking_day = BookingDay.objects.select_related("booking__person").filter(pk=booking_day.pk).first()
        if booking_day is None or booking_day.booking.status not in Booking.ACTIVE:
            raise LeaveError("status", "This booking is no longer live")
        if not may_decide(user, booking_day.booking):
            raise PermissionDenied("you don't manage this person")
        if not (note or "").strip():
            raise ValueError("A reason is needed to override a day's cost")
        before = booking_day.cost_seconds
        booking_day.cost_seconds, booking_day.source, booking_day.placeholder = int(seconds), BookingDay.Source.OVERRIDE, False
        booking_day.override_by, booking_day.override_note = user, note.strip()[:300]
        booking_day.save()
        audit.record_as(user, "leave.booking", booking_day.booking.person_id,
                        {f"cost {booking_day.day.isoformat()}": (hours.fmt(before), hours.fmt(booking_day.cost_seconds))}, note=note.strip()[:300])


def _relink(bd):
    """A grid rewrite deletes and recreates the day's rows, so a timed day
    loses its shortened entry (SET_NULL) or its covered one. Find the new row
    again: the shortened span, or the shift the leave filled."""
    booking = bd.booking
    shifts = Entry.objects.filter(person=booking.person, day=bd.day, kind=Entry.Kind.SHIFT, covered_by__isnull=True).order_by("position")
    if bd.original_start is None:
        for e in shifts:
            if e.start <= booking.start and e.finish >= booking.finish:
                Entry.objects.filter(pk=e.pk).update(covered_by=bd)
                return
    elif bd.shortened_entry_id is None:
        left = _remaining(bd.original_start, bd.original_finish, booking.start, booking.finish)
        for e in shifts:
            if (e.start, e.finish) == left:
                bd.shortened_entry = e
                bd.save(update_fields=["shortened_entry"])
                return


def recost(booking_day):
    """Re-cost a whole day from the rota; half-day, timed and overridden days
    keep their cost. Covers the day's entries either way (a timed day finds
    its shortened or covered shift again). Returns whether the figure
    changed."""
    booking = booking_day.booking
    if booking.part == Booking.Part.TIMES:
        _relink(booking_day)
        return False
    Entry.objects.filter(person=booking.person, day=booking_day.day, covered_by__isnull=True).update(covered_by=booking_day)
    if booking.part != Booking.Part.WHOLE or booking_day.source == BookingDay.Source.OVERRIDE:
        return False
    c = costing.cost(booking.person, booking.type, booking_day.day, "whole", include=booking_day)
    changed = c.seconds != booking_day.cost_seconds or booking_day.placeholder
    booking_day.cost_seconds, booking_day.source, booking_day.placeholder = c.seconds, c.source, c.placeholder
    booking_day.save(update_fields=["cost_seconds", "source", "placeholder"])
    return changed


def after_rota_write(person, day, base_url=""):
    """Called by entries._write after writing a day that has an active
    BookingDay. Covers the new entries, re-costs, flags managers when the
    cost changed (after the outermost commit), and returns the pks of the
    entries still visible."""
    bd = costing.active_day(person, day)
    if bd is None:
        return list(Entry.objects.filter(person=person, day=day).values_list("pk", flat=True))
    if recost(bd):
        _mail(notify.cost_to_check, person, [bd], base_url)
    return list(Entry.objects.filter(person=person, day=day, covered_by__isnull=True).values_list("pk", flat=True))
