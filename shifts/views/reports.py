"""The hours report page and its CSV (spec, section 7)."""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from shifts.services import csv_safe, hours
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
    blocks, start, end = hours.report(request.user, start, end)
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
                                                 "multi_week": monday(start) != monday(end)})
