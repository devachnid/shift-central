"""The Rota page (spec, section 3) and its CSV download (section 10). The
page is the island's mount point plus the phone list; the island fetches
its own data from the API."""

import csv
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from people.services import access
from shifts.services import window


def _start(request):
    try:
        return window.monday(date.fromisoformat(request.GET.get("from", "")))
    except ValueError:
        return window.monday(timezone.localdate())


def _query(request, first, weeks):
    q = request.GET.copy()
    q["from"], q["weeks"] = first.isoformat(), str(weeks)
    q.pop("reorder", None)   # reorder mode is the page's own state (data-reorder), never carried on links
    return q.urlencode()


@login_required
def grid(request):
    first = _start(request)
    weeks = window.clamp_weeks(request.GET.get("weeks", 1))
    data = window.payload(request.user, first, 1, request.GET)   # the phone list's week; the island fetches its own
    me = getattr(request.user, "person", None)
    mine = [r for r in data["rows"] if me is not None and r["person"] == me.pk]
    return render(request, "shifts/grid.html", {
        "page_title": "Rota", "first": first, "weeks": weeks, "weeks_range": range(1, window.MAX_WEEKS + 1),
        "query": _query(request, first, weeks),
        "prev": _query(request, first - timedelta(weeks=weeks), weeks),
        "next": _query(request, first + timedelta(weeks=weeks), weeks),
        "today": _query(request, window.monday(timezone.localdate()), weeks),
        "filters": {k: request.GET.getlist(k) for k in ("name", "team", "dept")},
        "reorder": request.GET.get("reorder") == "1" and access.is_manager(request.user),
        "unnotified": data["unnotified"], "days": data["days"],
        "mine": mine, "others": [r for r in data["rows"] if r not in mine],
        "me_pk": me.pk if me else "",
    })


@login_required
def download(request):
    first = _start(request)
    weeks = window.clamp_weeks(request.GET.get("weeks", 1))
    data = window.payload(request.user, first, weeks, request.GET)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="rota-{first.isoformat()}.csv"'
    writer = csv.writer(response)
    days = data["days"]
    writer.writerow(["Name", "Team"] + [date.fromisoformat(d["date"]).strftime("%a %-d %b") for d in days])
    for row in data["rows"]:
        cells = []
        for d in days:
            items = [e["line"] for e in row["cells"].get(d["date"], [])]
            items = [f"{s['part']} {s['label']} {s['site']}".strip() for s in row["sessions"].get(d["date"], [])] + items
            cells.append(" / ".join(items))
        writer.writerow([row["name"], row["team"]] + cells)
    return response
