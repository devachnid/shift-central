"""The sickness summary (REP-04): screen, PDF or Excel for a range."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.utils.text import slugify

from absence.services import onepager
from exports import pdf, xlsx
from leave.services import sickness
from people.services import access, filters
from shifts.services.window import parse_day


def _range(request):
    today = timezone.localdate()
    default_start, default_end = sickness.window(today)
    try:
        start = parse_day(request.GET.get("from", ""))
    except ValueError:
        start = default_start
    try:
        end = parse_day(request.GET.get("to", ""))
    except ValueError:
        end = default_end
    if end < start:
        start, end = end, start
    return start, end


@login_required
@access.manager_required
def sickness_summary(request):
    start, end = _range(request)
    choices = list(access.managed_teams(request.user).filter(active=True))
    team = filters.chosen(request, choices, "team")
    data = onepager.summary(request.user, start, end, team)
    stem = f"sickness-{start.isoformat()}-{end.isoformat()}" + (f"-{slugify(team.name)}" if team else "")
    fmt = request.GET.get("format")
    me = getattr(request.user, "person", None)
    footer = f"Generated {timezone.localdate():%-d %b %Y} by {me.name if me else request.user.email} · AMG Shift Central"
    if fmt == "pdf":
        return pdf.response(pdf.document("Sickness summary", f"{start:%-d %b %Y} to {end:%-d %b %Y}" + (f" · {team.name} only" if team else ""), onepager.sections(data), footer), f"{stem}.pdf")
    if fmt == "xlsx":
        return xlsx.response(xlsx.workbook([(name, head, rows) for name, head, rows in onepager.sections(data)]), f"{stem}.xlsx")
    return render(request, "absence/sickness_summary.html", {"page_title": "Sickness summary", "start": start, "end": end, **data,
                                                                "team_choices": choices, "team": team, "filter_query": filters.query(team=team)})
