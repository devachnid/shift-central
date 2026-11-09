"""The hours report (REP-01, FMS 54): per person, per week, rota hours
minus breaks, overtime in its own column, a GP session at 4 h 10 min."""

from datetime import time, timedelta

from people.models import Person
from people.services import access
from shifts.models import Entry, GpSession
from shifts.services.window import monday

MAX_RANGE = timedelta(days=366)


def people_for(user):
    me = getattr(user, "person", None)
    if access.is_manager(user):
        people = access.managed_people(user)
        if me is not None:
            people = people | Person.objects.filter(pk=me.pk)
        return people.distinct().order_by("team__display_order", "team__name", "display_order", "last_name")
    return Person.objects.filter(pk=me.pk) if me is not None else Person.objects.none()


def _rows(person, start, end):
    rows = []
    for e in Entry.objects.filter(person=person, day__range=(start, end), kind=Entry.Kind.SHIFT, covered_by__isnull=True).select_related("department").order_by("day", "position"):
        worked = e.hours
        rows.append({"day": e.day, "start": e.start, "finish": e.finish, "break_minutes": e.break_minutes,
                     "hours": timedelta(0) if e.overtime else worked, "overtime": worked if e.overtime else timedelta(0),
                     "label": e.department.name if e.department else e.text})
    for s in GpSession.objects.filter(person=person, day__range=(start, end)).order_by("day", "part"):
        rows.append({"day": s.day, "start": None, "finish": None, "break_minutes": 0, "hours": GpSession.HOURS,
                     "overtime": timedelta(0), "label": " ".join(x for x in (s.part, s.label, s.site) if x)})
    rows.sort(key=lambda r: (r["day"], r["start"] or time(0)))
    return rows


def report(user, start, end, person=None):
    """(blocks, start, end): the range actually reported, swapped if
    backwards and clamped to MAX_RANGE, so callers can show what was used.
    A person is listed when they were current on a day of the range or have
    hours in it. `person`, one of people_for(user), narrows it to them."""
    if end < start:
        start, end = end, start
    if end - start > MAX_RANGE:
        start = end - MAX_RANGE
    blocks = []
    people = people_for(user)
    if person is not None:
        people = people.filter(pk=person.pk)
    for person in people:
        rows = _rows(person, start, end)
        if not rows and not (person.start_date <= end and (person.end_date is None or person.end_date >= start)):
            continue   # not here in the range and nothing to show: a leaver, or someone not yet started
        weeks = []
        for r in rows:
            week_start = monday(r["day"])
            if not weeks or weeks[-1]["start"] != week_start:
                weeks.append({"start": week_start, "rows": [], "subtotal": timedelta(0), "overtime": timedelta(0)})
            weeks[-1]["rows"].append(r)
            weeks[-1]["subtotal"] += r["hours"]
            weeks[-1]["overtime"] += r["overtime"]
        blocks.append({"person": person, "shifts": len(rows), "weeks": weeks,
                       "total": sum((r["hours"] for r in rows), timedelta(0)),
                       "overtime": sum((r["overtime"] for r in rows), timedelta(0))})
    return blocks, start, end
