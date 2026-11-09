"""The hours report page and its CSV (spec, section 7)."""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from exports import xlsx
from people.models import Department, Team
from people.services import access, filters
from shifts.services import csv_safe, hours, shift_report, staff_by_hour
from shifts.services import render as fmt
from shifts.services.window import monday, parse_day


def _dates(request):
    today = timezone.localdate()
    try:
        start = parse_day(request.GET.get("from", ""))
    except ValueError:
        start = monday(today)
    try:
        end = parse_day(request.GET.get("to", ""))
    except ValueError:
        end = start + timedelta(days=6)
    return start, end


@login_required
def hours_report(request):
    start, end = _dates(request)
    choices = list(hours.people_for(request.user).order_by("name")) if access.is_manager(request.user) else []
    person = filters.chosen(request, choices, "person")
    blocks, start, end = hours.report(request.user, start, end, person)
    if request.GET.get("download"):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="hours-{start.isoformat()}-{end.isoformat()}.csv"'
        w = csv_safe.Writer(response)
        w.writerow(["Name", "Day", "Date", "Start", "Finish", "Break", "Hours", "Overtime", "Department or note"])
        for b in blocks:
            for week in b["weeks"]:
                for r in week["rows"]:
                    w.writerow([b["person"].name, r["day"].strftime("%a"), r["day"].isoformat(),
                                r["start"].strftime("%H:%M") if r["start"] else "", r["finish"].strftime("%H:%M") if r["finish"] else "",
                                r["break_minutes"], fmt.duration(r["hours"]), fmt.duration(r["overtime"]) if r["overtime"] else "", r["label"]])
        return response
    for b in blocks:
        b["total_text"], b["overtime_text"] = fmt.duration(b["total"]), fmt.duration(b["overtime"])
        for week in b["weeks"]:
            week["subtotal_text"], week["overtime_text"] = fmt.duration(week["subtotal"]), fmt.duration(week["overtime"])
            for r in week["rows"]:
                r["hours_text"] = fmt.duration(r["hours"]) if r["hours"] else ""
                r["overtime_text"] = fmt.duration(r["overtime"]) if r["overtime"] else ""
    return render(request, "shifts/hours.html", {"page_title": "Hours", "blocks": blocks, "start": start, "end": end,
                                                 "multi_week": monday(start) != monday(end), "person_choices": choices,
                                                 "person": person, "filter_query": filters.query(person=person)})


def _pick(model, value):
    """The row with this id from a filter (a model or a queryset), else None."""
    rows = model.objects.all() if hasattr(model, "objects") else model
    return rows.filter(pk=int(value)).first() if value and value.isascii() and value.isdigit() else None


@login_required
@access.manager_required
def shifts_report(request):
    start, end = _dates(request)
    person_choices = access.managed_people(request.user).order_by("name")
    team, department = _pick(Team, request.GET.get("team")), _pick(Department, request.GET.get("department"))
    person = _pick(person_choices, request.GET.get("person"))
    data = shift_report.report(request.user, start, end, team, department, person)
    if request.GET.get("download"):
        rows = [[e.day, e.day.strftime("%a"), e.person.name, e.person.team.name if e.person.team else "",
                 e.department.name if e.department else "", e.start.strftime("%H:%M"), e.finish.strftime("%H:%M"),
                 e.break_minutes, xlsx.Hours(int(e.hours.total_seconds())),
                 e.get_overtime_display() if e.overtime else "", e.text]
                for b in data["blocks"] for e in b["rows"]]
        rows.append(["Total", "", "", "", "", "", "", "", xlsx.Hours(int(data["grand_total"].total_seconds())), "", ""])
        header = ["Date", "Day", "Name", "Team", "Department", "Start", "Finish", "Break (min)", "Net hours", "Overtime", "Comment"]
        return xlsx.response(xlsx.workbook([("Shifts", header, rows)]), f"shifts-{data['start']}-{data['end']}.xlsx")
    for b in data["blocks"]:
        b["total_text"], b["overtime_text"] = fmt.duration(b["total"]), fmt.duration(b["overtime"])
        for e in b["rows"]:
            e.hours_text = fmt.duration(e.hours)
    return render(request, "shifts/shifts_report.html", {
        "page_title": "Shifts", "data": data, "grand_text": fmt.duration(data["grand_total"]), "start": data["start"], "end": data["end"],
        "teams": access.managed_teams(request.user).filter(active=True), "departments": Department.objects.filter(archived=False),
        "people": person_choices, "team": team, "department": department, "person": person})


@login_required
@access.manager_required
def staff_by_hour_report(request):
    start, end = _dates(request)
    site = request.GET.get("site", "")
    site = site if site in ("AG", "PMC") else ""
    team = _pick(Team, request.GET.get("team"))
    data = staff_by_hour.report(request.user, start, end, site, team)
    if request.GET.get("download"):
        rows = []
        for r in data["rows"]:
            rows.append([r["day"], r["day"].strftime("%a"), *r["counts"], r["peak"]])
            rows.append([r["day"], "of which WFH", *r["wfh"], ""])
        return xlsx.response(xlsx.workbook([("Staff by hour", ["Date", "Day", *data["labels"], "Peak"], rows)]),
                             f"staff-by-hour-{data['start']}-{data['end']}.xlsx")
    return render(request, "shifts/staff_by_hour.html", {
        "page_title": "Staff by hour", "data": data, "start": data["start"], "end": data["end"], "site": site, "team": team,
        "teams": access.managed_teams(request.user).filter(active=True)})
