"""The leave report (REP-02): per person for a range, allowance combined,
adjustments, days booked, deducted, remaining, TOIL; team subtotals; CSV.
Managers see their people (and themselves), staff their own row.
Instances and Trigger are the six months to the range's end, or to today when
the range runs on past it (LEAVE-42)."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from leave.models import Booking, BookingDay
from leave.services import balances, hours, sickness, years
from people.models import Person
from people.services import access
from shifts.services import csv_safe
from shifts.services.window import parse_day

DEDUCTS = ("annual", "bank_holiday")


def _dates(request):
    """The default range is the viewer's current leave year."""
    today = timezone.localdate()
    me = getattr(request.user, "person", None)
    default = years.year_of(me, today) if me is not None else date(today.year, 1, 1)
    try:
        start = parse_day(request.GET.get("from", ""))
    except ValueError:
        start = default
    try:
        end = parse_day(request.GET.get("to", ""))
    except ValueError:
        end = years.year_end(start)
    if end < start:
        start, end = end, start
    return start, end


def _people(user, start, end):
    me = getattr(user, "person", None)
    if access.is_manager(user):
        people = access.managed_people(user)
        if me is not None:
            people = people | Person.objects.filter(pk=me.pk)
    elif me is not None:
        people = Person.objects.filter(pk=me.pk)
    else:
        return []
    return list(people.distinct().filter(start_date__lte=end).exclude(end_date__lt=start)
                .select_related("team").order_by("team__display_order", "team__name", "last_name", "first_name"))


def rows(user, start, end):
    out = []
    today = timezone.localdate()
    for p in _people(user, start, end):
        s = balances.statement(p, years.year_of(p, start))
        days = BookingDay.objects.filter(booking__person=p, booking__status__in=Booking.ACTIVE, day__range=(start, end))
        deducted = days.filter(account__in=DEDUCTS).aggregate(total=Sum("cost_seconds"))["total"] or 0
        instances = len(sickness.instances(p, min(end, today)))
        out.append({"person": p, "team": p.team.name if p.team else "—", "missing": s.missing,
                    "allowance": s.annual_allowance + s.bank_holiday_allowance,
                    "adjustments": s.adjustments["annual"] + s.adjustments["bank_holiday"], "days": days.count(),
                    "deducted": deducted, "remaining": s.annual_remaining, "toil": s.toil_remaining,
                    "instances": instances, "trigger": sickness.level_label(sickness.level(instances))})
    return out


@login_required
def leave_report(request):
    start, end = _dates(request)
    data = rows(request.user, start, end)
    if request.GET.get("download"):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="leave-{start.isoformat()}-{end.isoformat()}.csv"'
        w = csv_safe.Writer(response)
        w.writerow(["Name", "Team", "Allowance", "Adjustments", "Days", "Deducted", "Remaining", "TOIL", "Instances", "Trigger"])
        for r in data:
            w.writerow([r["person"].name, r["team"], "" if r["missing"] else hours.fmt(r["allowance"]), hours.fmt(r["adjustments"]), r["days"],
                        hours.fmt(r["deducted"]), "" if r["missing"] else hours.fmt(r["remaining"]), hours.fmt(r["toil"]), r["instances"], r["trigger"]])
        return response
    teams = []
    for r in data:
        if not teams or teams[-1]["team"] != r["team"]:
            teams.append({"team": r["team"], "rows": [], "allowance": 0, "adjustments": 0, "days": 0, "deducted": 0, "remaining": 0, "toil": 0, "instances": 0})
        group = teams[-1]
        group["rows"].append(r)
        for key in ("adjustments", "days", "deducted", "toil", "instances"):
            group[key] += r[key]
        if not r["missing"]:
            group["allowance"] += r["allowance"]
            group["remaining"] += r["remaining"]
    return render(request, "leave/report.html", {"page_title": "Leave", "teams": teams, "start": start, "end": end})
