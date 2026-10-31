"""What a day of leave costs (LEAVE-05 to 09, 16, 23) and which account it
draws on (LEAVE-17, 18). A GP's day is their sessions at 4 h 10 min; a GP has
no placeholder because their sessions come from the rota app."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.db.models import Q

from leave.models import BankHoliday, Booking, BookingDay
from leave.services import hours, prorata
from shifts.models import Entry, GpSession
from shifts.services.window import monday

ACTIVE = Booking.ACTIVE


@dataclass(frozen=True)
class DayCost:
    seconds: int
    source: str
    account: str
    placeholder: bool = False
    hours_known: bool = True


def _shifts(person, day, include=None):
    rows = Entry.objects.filter(person=person, day=day, kind=Entry.Kind.SHIFT, overtime="")
    cover = Q(covered_by__isnull=True)
    if include is not None:
        cover |= Q(covered_by=include)
    return rows.filter(cover)


def rota_seconds(person, day, include=None):
    worked = sum((e.hours for e in _shifts(person, day, include)), timedelta(0))
    sessions = GpSession.objects.filter(person=person, day=day).count()
    return int(worked.total_seconds()) + sessions * hours.GP_SESSION


def is_placeholder(person, day):
    """LEAVE-06: the rota "has not been set" for a day when the person's
    Monday-to-Sunday week holds no entry and no session. A GP never has one."""
    if person.is_gp:
        return False
    first = monday(day)
    week = (first, first + timedelta(days=6))
    return not (Entry.objects.filter(person=person, day__range=week).exists()
                or GpSession.objects.filter(person=person, day__range=week).exists())


def placeholder_seconds(person, day):
    """Weekly hours ÷ days per week from the Allowance row in force that day
    when it carries hours, else the person's figures; (0, False) when
    neither is set, so the caller can say so."""
    row = prorata.row_in_force(person, day)
    weekly, days = (row.weekly_hours, row.days_per_week) if row and row.weekly_hours is not None else (person.weekly_hours, person.days_per_week)
    if weekly is None or not days:
        return 0, False
    return hours.from_hours(weekly) // days, True


def account_for(leave_type, day):
    if leave_type.draws_from == "annual" and BankHoliday.objects.filter(day=day).exists():
        return "bank_holiday"
    return leave_type.draws_from


def cost(person, leave_type, day, part, start=None, finish=None, include=None):
    account = account_for(leave_type, day)
    if part == "times":
        anchor = datetime(2000, 1, 1)
        seconds = int((datetime.combine(anchor, finish) - datetime.combine(anchor, start)).total_seconds())
        return DayCost(seconds, "times", account)
    whole = rota_seconds(person, day, include)
    placeholder, known = False, True
    if whole == 0 and is_placeholder(person, day):
        whole, known = placeholder_seconds(person, day)
        placeholder = True
    if part in ("am", "pm"):
        return DayCost(whole // 2, "half", account, placeholder, known)
    if placeholder:
        return DayCost(whole, "placeholder", account, True, known)
    return DayCost(whole, "rota" if whole else "none", account)


def suggestion(person, day):
    """LEAVE-16: the most common rota cost on that weekday over the four
    weeks before the holiday; ties go to the larger figure; 0 when none."""
    figures = Counter(rota_seconds(person, day - timedelta(weeks=w)) for w in range(1, 5))
    best = max(figures.items(), key=lambda kv: (kv[1], kv[0]))
    return best[0]


def active_day(person, day):
    return (BookingDay.objects.filter(booking__person=person, day=day, booking__status__in=ACTIVE)
            .select_related("booking__type").first())
