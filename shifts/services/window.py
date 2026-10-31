"""One payload for the grid's window (spec, sections 3 and 6): who is a
row for this viewer, what is in each cell, and the viewer's options."""

from datetime import date, timedelta

from django.db.models import Q
from django.utils import timezone

from leave.services import serialize as leave_serialize
from people.models import Department, Person
from people.services import access
from shifts.models import DayChange, Entry, GpSession
from shifts.services import common, options, serialize

MAX_WEEKS = 20
DAY_LABEL = "%a. %b. {d}"
# The days a request may name. Wide enough for any rota, narrow enough that
# a window or a week either side of it never runs off the calendar.
FIRST_DAY, LAST_DAY = date(2000, 1, 1), date(2100, 12, 31)


def parse_day(value):
    """An ISO date from request input, within FIRST_DAY..LAST_DAY; else
    ValueError with a sentence the island or a page can show."""
    try:
        day = date.fromisoformat(str(value))
    except ValueError:
        raise ValueError("that is not a date") from None
    if not FIRST_DAY <= day <= LAST_DAY:
        raise ValueError("that date is out of range")
    return day


def is_pk(value):
    """A request value that int() reads as a row id: isdigit() alone admits
    superscripts and other digits int() refuses."""
    value = str(value)
    return value.isascii() and value.isdigit()


def monday(day):
    return day - timedelta(days=day.weekday())


def clamp_weeks(value):
    try:
        return min(max(int(value), 1), MAX_WEEKS)
    except (TypeError, ValueError):
        return 1


def visible_people(user, first, last, manager=None):
    """People current on at least one day of the window with display_on_rota
    (section 6); for staff, also shown to other staff; a viewer who may not
    see others sees themselves only. The viewer is always their own row.
    Pass manager when the caller already knows it (it is a query)."""
    me = getattr(user, "person", None)
    if manager is None:
        manager = access.is_manager(user)
    people = Person.objects.filter(display_on_rota=True, start_date__lte=last).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=first)).select_related("team")
    if manager:
        return people
    if me is None:
        return people.filter(show_to_other_staff=True)
    if not me.can_see_other_staff:
        return Person.objects.filter(pk=me.pk).select_related("team")
    return (people.filter(show_to_other_staff=True) | Person.objects.filter(pk=me.pk)).distinct()


def _ids(values):
    return [int(v) for v in values if is_pk(v)]


def _filtered(people, filters, first, last):
    name = (filters.get("name") or "").strip()
    if name:
        people = people.filter(name__icontains=name)
    teams = _ids(filters.getlist("team") if hasattr(filters, "getlist") else filters.get("team", []))
    if teams:
        people = people.filter(team_id__in=teams)
    depts = _ids(filters.getlist("dept") if hasattr(filters, "getlist") else filters.get("dept", []))
    if depts:
        tagged = Entry.objects.filter(day__range=(first, last), department_id__in=depts).values("person_id")
        people = people.filter(pk__in=tagged)
    return people


def payload_unnotified(user, manager=None):
    if manager is None:
        manager = access.is_manager(user)
    if not manager:
        return 0
    return DayChange.objects.filter(person__in=access.managed_people(user)).values("person").distinct().count()


def payload(user, start, weeks, filters):
    first = monday(start)
    last = first + timedelta(days=7 * weeks - 1)
    today = timezone.localdate()
    days = [first + timedelta(days=i) for i in range(7 * weeks)]
    opts = options.for_user(user)
    me = getattr(user, "person", None)
    manager = access.is_manager(user)
    all_teams = access.is_all_teams(user)
    # Who is editable is decided once here, not per row through
    # access.can_manage (a query each); the two must agree, a test checks it.
    managed_team_ids = (set(access.managed_teams(user).values_list("pk", flat=True))
                        if manager and not all_teams else set())
    people = _filtered(visible_people(user, first, last, manager), filters, first, last)
    if opts["only_my_shifts"] and me is not None:
        people = people.filter(pk=me.pk)
    people = list(people.order_by("team__display_order", "team__name", "display_order", "last_name", "first_name"))
    if opts["my_shifts_on_top"] and me is not None:
        people.sort(key=lambda p: p.pk != me.pk)

    by_cell = {}
    for e in Entry.objects.filter(person__in=people, day__range=(first, last), covered_by__isnull=True).select_related("department"):
        by_cell.setdefault(e.person_id, {}).setdefault(e.day.isoformat(), []).append(e)
    sessions = {}
    for s in GpSession.objects.filter(person__in=people, day__range=(first, last)):
        sessions.setdefault(s.person_id, {}).setdefault(s.day.isoformat(), []).append(
            {"part": s.part, "label": s.label, "site": s.site})   # not the note: the grid never draws it
    leave = leave_serialize.leave_for(people, first, last, user)
    if opts["hide_no_shifts"]:
        people = [p for p in people if p.pk in by_cell or p.pk in sessions or p.pk in leave]

    rows = []
    for p in people:
        rows.append({
            "person": p.pk, "name": p.name, "colour": p.name_colour, "job_title": p.job_title,
            "team": p.team.name if p.team else "", "is_gp": p.is_gp,
            "editable": manager and (me is None or p.pk != me.pk) and (all_teams or p.team_id in managed_team_ids),
            "cells": {day: [serialize.entry(e) for e in sorted(es, key=lambda e: e.position)]
                      for day, es in by_cell.get(p.pk, {}).items()},
            "sessions": sessions.get(p.pk, {}),
            "leave": leave.get(p.pk, {}),
        })
    return {
        "from": first.isoformat(), "weeks": weeks,
        "days": [{"date": d.isoformat(), "label": d.strftime(DAY_LABEL).format(d=d.day),
                  "today": d == today, "weekend": d.weekday() >= 5} for d in days],
        "rows": rows,
        "departments": [{"id": d.pk, "name": d.name, "colour": d.colour}
                        for d in Department.objects.filter(archived=False)],
        "common": common.common(user) if manager else [],
        "recent": common.recent(user) if manager else [],
        "options": opts,
        "unnotified": payload_unnotified(user, manager),
        "can_edit": manager,
    }
