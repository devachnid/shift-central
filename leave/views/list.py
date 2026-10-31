"""The Time off list (FMS "Time off"): everyone's approved and pending
bookings by type; description, pay and cost for the person and their
managers (ACC-05). Filters, and a CSV for managers."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from leave.models import Booking, LeaveType
from leave.services import hours, years
from people.models import Team
from people.services import access
from shifts.services import csv_safe
from shifts.services.window import parse_day


def _range(request, person):
    """The default window is the person's current leave year and the next:
    the two years leave can be booked in."""
    year = years.year_of(person, timezone.localdate()) if person else date(timezone.localdate().year, 1, 1)
    try:
        start = parse_day(request.GET.get("from", ""))
    except ValueError:
        start = year
    try:
        end = parse_day(request.GET.get("to", ""))
    except ValueError:
        end = years.year_end(years.next_year(year)) if start == year else years.year_end(start)
    return start, end


def visible_rows(user, start, end, filters):
    me = getattr(user, "person", None)
    rows = (Booking.objects.filter(first_day__lte=end, last_day__gte=start)
            .select_related("person__team", "type").prefetch_related("booking_days"))
    hidden_unless_detail = filters.get("status") in (Booking.Status.DECLINED, Booking.Status.CANCELLED)
    if not hidden_unless_detail:       # named by status they are listed, for the person and their managers only
        rows = rows.exclude(status__in=(Booking.Status.DECLINED, Booking.Status.CANCELLED))
    if filters.get("type"):
        rows = rows.filter(type__name=filters["type"])
    if filters.get("team"):
        rows = rows.filter(person__team__name=filters["team"])
    if filters.get("status"):
        rows = rows.filter(status=filters["status"])
    if filters.get("person") and filters["person"].isascii() and filters["person"].isdigit():
        rows = rows.filter(person_id=int(filters["person"]))
    everyone = access.is_all_teams(user)
    team_ids = set(access.managed_teams(user).values_list("pk", flat=True))
    out = []
    for b in rows.order_by("-first_day", "person__last_name"):
        mine = me is not None and me.pk == b.person_id
        manage = not mine and (everyone or b.person.team_id in team_ids)
        detail = mine or manage
        if hidden_unless_detail and not detail:
            continue          # colleagues never see declined or cancelled bookings (ACC-06)
        out.append({"booking": b, "detail": detail, "manage": manage, "days": (b.last_day - b.first_day).days + 1,
                    "cost": sum(bd.cost_seconds for bd in b.booking_days.all()) if detail and b.is_active else None})
    return out


@login_required
def time_off(request):
    start, end = _range(request, getattr(request.user, "person", None))
    filters = {k: request.GET.get(k, "") for k in ("type", "team", "status", "person")}
    rows = visible_rows(request.user, start, end, filters)
    manager = access.is_manager(request.user)
    if request.GET.get("download") and manager:
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="time-off-{start.isoformat()}-{end.isoformat()}.csv"'
        w = csv_safe.Writer(response)
        w.writerow(["Staff", "First day off", "Last day off", "Days", "Type", "Display", "Pay", "Allowance used", "Status"])
        for r in rows:
            b = r["booking"]
            w.writerow([b.person.name, b.first_day.isoformat(), b.last_day.isoformat(), r["days"], b.type.name,
                        b.label if r["detail"] else b.type.name, "" if b.paid is None or not r["detail"] else ("Paid" if b.paid else "Unpaid"),
                        hours.fmt(r["cost"]) if r["cost"] is not None else "", b.get_status_display()])
        return response
    return render(request, "leave/list.html", {
        "page_title": "Time off", "rows": rows, "start": start, "end": end, "filters": filters, "is_manager": manager,
        "types": LeaveType.objects.filter(archived=False), "teams": Team.objects.filter(active=True), "statuses": Booking.Status.choices})
