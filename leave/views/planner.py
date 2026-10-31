"""The year planner (REP-03, FMS "Time off planner"): months as rows,
days across aligned by weekday, a coloured cell with initials per booking.
Everyone sees it, by type only (ACC-05)."""

import calendar
from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from leave.models import BankHoliday, Booking, LeaveType
from people.models import Team
from shifts.services.window import visible_people

COLUMNS = 37          # a month starts in column 0 to 6 and runs up to 31 days


def _year(request):
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
    except ValueError:
        return today.year
    return year if 2000 <= year <= 2100 else today.year


@login_required
def planner(request):
    year = _year(request)
    type_name, team_name = request.GET.get("type", ""), request.GET.get("team", "")
    first, last = date(year, 1, 1), date(year, 12, 31)
    people = visible_people(request.user, first, last)
    if team_name:
        people = people.filter(team__name=team_name)
    rows = (Booking.objects.filter(person__in=people, status__in=Booking.LIVE, first_day__lte=last, last_day__gte=first)
            .select_related("person", "type").order_by("person__last_name", "person__first_name", "pk"))
    if type_name:
        rows = rows.filter(type__name=type_name)
    by_day = {}
    for b in rows:
        chip = {"initials": b.person.initials, "colour": b.type.colour, "pending": b.status == Booking.Status.PENDING,
                "title": f"{b.person.name} · {b.type.name}"}
        for d in b.days():
            if first <= d <= last:
                by_day.setdefault(d, []).append(chip)
    holidays = dict(BankHoliday.objects.filter(day__range=(first, last)).values_list("day", "name"))
    months = []
    for m in range(1, 13):
        offset = date(year, m, 1).weekday()           # Monday = 0: the month's first day sits in column `offset`
        days = []
        for n in range(1, calendar.monthrange(year, m)[1] + 1):
            day = date(year, m, n)
            days.append({"day": day, "cells": by_day.get(day, []), "holiday": holidays.get(day), "weekend": day.weekday() >= 5})
        months.append({"name": calendar.month_name[m], "lead": range(offset), "days": days, "trail": range(COLUMNS - offset - len(days))})
    return render(request, "leave/planner.html", {
        "page_title": "Year planner", "year": year, "months": months, "type": type_name, "team": team_name,
        "types": LeaveType.objects.all(), "teams": Team.objects.filter(active=True),
        "columns": [("MTWTFSS"[i % 7], i % 7 >= 5) for i in range(COLUMNS)],
        "previous": year - 1, "next": year + 1})
