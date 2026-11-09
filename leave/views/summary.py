"""The leave summary (REP-05): screen, PDF or Excel for a leave year."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.utils.text import slugify

from exports import pdf, xlsx
from leave.services import summary, years
from people.services import access, filters


def _year(request):
    today = timezone.localdate()
    me = getattr(request.user, "person", None)
    default = years.year_of(me, today) if me is not None else date(today.year, 1, 1)
    try:
        y = int(request.GET.get("year", ""))
        return date(y, default.month, default.day) if 2000 <= y <= 2100 else default
    except ValueError:
        return default


@login_required
@access.manager_required
def leave_summary(request):
    year = _year(request)
    choices = list(access.managed_teams(request.user).filter(active=True))
    team = filters.chosen(request, choices, "team")
    data = summary.summary(request.user, year, team)
    label = years.label(year)
    me = getattr(request.user, "person", None)
    footer = f"Generated {timezone.localdate():%-d %b %Y} by {me.name if me else request.user.email} · AMG Shift Central"
    stem = f"leave-summary-{year.year}" + (f"-{slugify(team.name)}" if team else "")
    fmt = request.GET.get("format")
    if fmt == "pdf":
        return pdf.response(pdf.document("Leave summary", f"Leave year {label}" + (f" · {team.name} only" if team else "") + (" · " + " ".join(data["footnotes"]) if data["footnotes"] else ""),
                                         summary.sections(data), footer), f"{stem}.pdf")
    if fmt == "xlsx":
        return xlsx.response(xlsx.workbook(summary.sections(data)), f"{stem}.xlsx")
    return render(request, "leave/summary.html", {"page_title": "Leave summary", "year": year, "label": label,
                                                  "previous": year.year - 1, "following": year.year + 1, **data,
                                                  "team_choices": choices, "team": team, "filter_query": filters.query(team=team)})
