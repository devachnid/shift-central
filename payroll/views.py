"""The payroll report (PAY-01 to 03): the month on screen for the viewer's
people, the Excel, Mark as sent to the bureau (all-teams managers)."""

from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.text import slugify

from exports import xlsx as exports_xlsx
from payroll.services import report, runs, xlsx
from people.services import access, filters

def _month(request):
    try:
        return report.month_of(request.GET.get("month", ""))
    except ValueError as e:
        return HttpResponseBadRequest(str(e))


def _teams(rows):
    groups = []
    for r in rows:
        if not groups or groups[-1]["team"] != r.team:
            groups.append({"team": r.team, "rows": [], **{f: 0 for f in report.FIELDS}})
        groups[-1]["rows"].append(r)
        for f in report.FIELDS:
            groups[-1][f] += getattr(r, f)
    return groups


@login_required
@access.manager_required
def payroll(request):
    month = _month(request)
    if not hasattr(month, "year"):
        return month
    people = report.people_for(request.user, month)
    choices = sorted(people, key=lambda p: p.name)
    person = filters.chosen(request, choices, "person")
    rows = report.rows(people.filter(pk=person.pk) if person else people, month)
    names = report.type_names(rows)
    corrections = report.corrections(request.user, month)
    if person is not None:
        corrections = [c for c in corrections if c.person.pk == person.pk]
    run = runs.latest(month)
    if request.GET.get("download"):
        stem = f"payroll-{month:%Y-%m}" + (f"-{slugify(person.name)}" if person else "")
        return exports_xlsx.response(xlsx.build(month, rows, names, corrections, run, only=person), f"{stem}.xlsx")
    teams = _teams(rows)
    totals = {f: sum(g[f] for g in teams) for f in report.FIELDS}
    previous = (month - timedelta(days=1)).replace(day=1)
    following = report.month_end(month) + timedelta(days=1)
    today = timezone.localdate()
    has_next = following <= date(today.year + 1, today.month, 1)
    has_previous = previous >= report.EARLIEST
    return render(request, "payroll/report.html", {
        "page_title": "Payroll", "month": month, "teams": teams, "totals": totals, "type_names": names,
        "corrections": corrections, "movers": [r for r in rows if r.started or r.leaves], "run": run,
        "previous": previous, "following": following, "has_next": has_next, "has_previous": has_previous, "all_teams": access.is_all_teams(request.user),
        "person_choices": choices, "person": person, "filter_query": filters.query(person=person)})


@login_required
@access.all_teams_required
def mark_sent(request):
    # Never a fallback here: marking "this month" sent because the parameter was unreadable is a wrong record.
    try:
        month = report.month_strict(request.GET.get("month", ""))
    except ValueError as e:
        return HttpResponseBadRequest(str(e))
    if request.method == "POST":
        runs.mark_sent(request.user, month)
        return JsonResponse({"refresh": True})
    count = report.people_for(request.user, month).count()
    return render(request, "payroll/sent_dialog.html", {"month": month, "count": count, "run": runs.latest(month)})
