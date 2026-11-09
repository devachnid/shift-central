"""REP-04: the sickness one-pager. Practice totals, then each team, then
each person: instances in the rolling six months as at the range's end,
time off sick inside the range in days and hours, the longest instance
and whether it was long, the trigger level. Dates-only entries count
their days; they have no hours."""

from dataclasses import dataclass

from django.db.models import Sum
from django.utils import timezone

from leave.models import Booking, BookingDay
from leave.services import hours, sickness
from people.services import access


@dataclass
class Totals:
    name: str
    people: int = 0
    instances: int = 0
    days: int = 0
    seconds: int = 0
    trigger_1: int = 0
    trigger_2: int = 0
    trigger_3: int = 0


@dataclass
class PersonRow:
    person: object
    team: str
    instances: int
    days: int
    seconds: int
    longest: int
    long: bool
    trigger: str
    level: int


def _people(user, start, end, team=None):
    people = access.managed_people(user).filter(start_date__lte=end).exclude(end_date__lt=start)
    if team is not None:
        people = people.filter(team=team)
    return list(people.select_related("team").order_by("team__display_order", "team__name", "last_name", "first_name"))


def _in_range(booking, start, end):
    return (min(booking.last_day, end) - max(booking.first_day, start)).days + 1


def _row(person, start, end):
    in_range = list(Booking.objects.filter(person=person, status__in=Booking.ACTIVE, type__sickness=True, first_day__lte=end, last_day__gte=start))
    days = sum(_in_range(b, start, end) for b in in_range)
    seconds = BookingDay.objects.filter(booking__in=in_range, day__range=(start, end)).aggregate(t=Sum("cost_seconds"))["t"] or 0
    longest = max(((b.last_day - b.first_day).days + 1 for b in in_range), default=0)
    as_at = min(end, timezone.localdate())          # a range that runs into the future is read as at today
    level = sickness.level_for(person, as_at)
    return PersonRow(person, person.team.name if person.team else "—", len(sickness.instances(person, as_at)), days, seconds, longest,
                     longest >= sickness.LONG_DAYS, sickness.level_label(level), level)


def _add(t, r, instances):
    t.people += 1
    t.instances += instances
    t.days += r.days
    t.seconds += r.seconds
    if r.level == 1:
        t.trigger_1 += 1
    elif r.level == 2:
        t.trigger_2 += 1
    elif r.level == 3:
        t.trigger_3 += 1


def summary(user, start, end, team=None):
    """`team`, one of the viewer's: only its people, its totals at the top."""
    practice, teams, people = Totals(team.name if team else "Practice"), {}, []
    for p in _people(user, start, end, team):
        r = _row(p, start, end)
        people.append(r)
        in_range = Booking.objects.filter(person=p, status__in=Booking.ACTIVE, type__sickness=True, first_day__lte=end, last_day__gte=start).count()
        _add(practice, r, in_range)
        _add(teams.setdefault(r.team, Totals(r.team)), r, in_range)
    return {"practice": practice, "teams": list(teams.values()), "people": people}


def _totals_row(t):
    return [t.name, t.people, t.instances, t.days, hours.fmt(t.seconds), t.trigger_1, t.trigger_2, t.trigger_3]


def sections(data):
    """The three tables as text, for the PDF and the Excel alike."""
    head = ["", "People", "Instances in range", "Days off sick", "Hours off sick", "Trigger 1", "Trigger 2", "Trigger 3+"]
    return [(data["practice"].name, head, [_totals_row(data["practice"])]),
            ("Teams", head, [_totals_row(t) for t in data["teams"]]),
            ("People", ["Name", "Team", "Instances (rolling six months)", "Days off sick", "Hours off sick", "Longest instance (days)", "Trigger"],
             [[r.person.name, r.team, r.instances, r.days, hours.fmt(r.seconds), f"{r.longest}{' (long)' if r.long else ''}", r.trigger] for r in data["people"]])]
