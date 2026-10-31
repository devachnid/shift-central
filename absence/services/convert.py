"""LEAVE-28: sick during annual leave. A manager picks the sick days inside
a booked holiday; the holiday is cut around them (its hours come back
through the booking services' own edit path) and a sickness booking is
recorded for them, costed from the rota like any sickness."""

from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction

from leave.models import Booking, BookingDay
from leave.services import bookings, notify
from leave.services.common import LeaveError, span

CONVERTIBLE = ("annual", "bank_holiday")
NOTE = "converted to sickness"


def eligible(booking):
    return (booking.status in Booking.ACTIVE and not booking.dates_only and booking.part == Booking.Part.WHOLE
            and booking.type.draws_from in CONVERTIBLE)


def check(booking, leave_type, first, last):
    if booking.status not in Booking.ACTIVE:
        raise LeaveError("status", "Only approved leave can be converted")
    if booking.dates_only or booking.part != Booking.Part.WHOLE:
        raise LeaveError("part", "Only whole days of leave can be converted")
    if booking.type.draws_from not in CONVERTIBLE:
        raise LeaveError("type", f"{booking.type.name} is not annual leave")
    if not (booking.first_day <= first <= last <= booking.last_day):
        raise LeaveError("days", "Choose days inside the booking")
    if not leave_type.sickness:
        raise LeaveError("type", f"{leave_type.name} does not count as sickness")


def hours_back(booking, first, last):
    """The seconds the booking's days in first..last were charged."""
    return sum(BookingDay.objects.filter(booking=booking, day__range=(first, last)).values_list("cost_seconds", flat=True))


def convert(user, booking, leave_type, first, last, note="", base_url=""):
    if not bookings.may_decide(user, booking):
        raise PermissionDenied("you don't manage this person")
    with transaction.atomic():
        fresh = bookings._reread(booking)
        check(fresh, leave_type, first, last)
        label, dates = fresh.label, span(fresh)
        person = fresh.person
        if first == fresh.first_day and last == fresh.last_day:
            bookings.cancel(user, fresh, note=NOTE, base_url=base_url)
        elif first == fresh.first_day:
            bookings.edit(user, fresh, base_url=base_url, note=NOTE, first=last + timedelta(days=1))
        else:
            tail_last = fresh.last_day
            # A manager's typed figure on a tail day stands: the tail is re-booked with those costs as overrides.
            typed = {bd.day: bd.cost_seconds for bd in BookingDay.objects.filter(booking=fresh, source=BookingDay.Source.OVERRIDE, day__gt=last)}
            bookings.edit(user, fresh, base_url=base_url, note=NOTE, last=first - timedelta(days=1))
            if last < tail_last:
                bookings.book(user, person, fresh.type, last + timedelta(days=1), tail_last, Booking.Part.WHOLE,
                              description=fresh.description, paid=fresh.paid, note=fresh.manager_note, costs=typed or None, base_url=base_url)
        manager_note = f"converted from {label} {dates}" + (f"; {note.strip()}" if note and note.strip() else "")
        sick = bookings.book(user, person, leave_type, first, last, Booking.Part.WHOLE, note=manager_note[:300], base_url=base_url)
    bookings._mail(notify.converted, label, dates, sick, base_url)
    return sick
