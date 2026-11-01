"""Sickness as LEAVE-40 to 44 define it, over the bookings of leave types
that count as sickness: one booking is one instance of absence; instances
are counted over a rolling six months; three, four and five make the
triggers; twenty-nine days make long sickness; an entry that joins on to
another is warned about. Nothing here is stored."""

import calendar
from datetime import date, timedelta

from django.utils import timezone

from leave.models import Booking
from shifts.models import Entry, GpSession

LONG_DAYS = 29          # LEAVE-44: longer than four calendar weeks, first and last day counted
MAX_GAP_DAYS = 7        # a gap longer than a week never "joins on", whatever the rota says
LEVELS = ((5, 3), (4, 2), (3, 1))
LABELS = {0: "", 1: "Trigger 1", 2: "Trigger 2", 3: "Trigger 3+"}


def _months_back(day, months):
    month, year = day.month - months, day.year
    while month <= 0:
        month, year = month + 12, year - 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def window(today):
    """LEAVE-42's rolling six months: the same day of the month six months
    back (the month's last day when it has no such day), plus a day, to
    today. 1 July gives 2 January to 1 July (SICK-01)."""
    return _months_back(today, 6) + timedelta(days=1), today


def overlaps_window(first, last, today=None):
    start, end = window(today or timezone.localdate())
    return first <= end and last >= start


def _rows(person):
    return Booking.objects.filter(person=person, status__in=Booking.ACTIVE, type__sickness=True).select_related("type")


def instances(person, today=None):
    """The person's instances in the window, oldest first: an entry counts
    when any of its days falls inside (LEAVE-42); dates-only entries count."""
    start, end = window(today or timezone.localdate())
    return list(_rows(person).filter(first_day__lte=end, last_day__gte=start).order_by("first_day", "pk"))


def level(count):
    for at_least, lvl in LEVELS:
        if count >= at_least:
            return lvl
    return 0


def level_for(person, today=None):
    return level(len(instances(person, today)))


def level_label(lvl):
    return LABELS[lvl]


def is_long(booking):
    return (booking.last_day - booking.first_day).days + 1 >= LONG_DAYS


def _worked(person, day):
    """A day the person works: a shift on the rota (covered or not: a day
    they were due in) or a GP session."""
    return (Entry.objects.filter(person=person, day=day, kind=Entry.Kind.SHIFT).exists()
            or GpSession.objects.filter(person=person, day=day).exists())


def _bridges(person, a, b):
    """Whether the days strictly between a and b are all days the person
    does not work, and there are at most MAX_GAP_DAYS of them."""
    between = (b - a).days - 1
    if between > MAX_GAP_DAYS:
        return False
    return all(not _worked(person, a + timedelta(days=n)) for n in range(1, between + 1))


def joins_on(person, first, last, exclude=None):
    """LEAVE-41: the existing sickness booking this entry joins on to, or
    None. Adjacent dates join; so does a gap made only of days the person
    does not work (a weekend, a part-timer's day off, a week with no rota)."""
    rows = _rows(person)
    if exclude is not None:
        rows = rows.exclude(pk=exclude.pk)
    before = rows.filter(last_day__lt=first).order_by("-last_day", "-pk").first()
    if before is not None and _bridges(person, before.last_day, first):
        return before
    after = rows.filter(first_day__gt=last).order_by("first_day", "pk").first()
    if after is not None and _bridges(person, last, after.first_day):
        return after
    return None
