import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from people.models import Person, Team
from people.services import access, health, hr_sync


def _csv(people):
    """The rows the manager is looking at, as a download."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="staff.csv"'
    writer = csv.writer(response)
    writer.writerow(["Name", "Job title", "Team", "Email", "Start date", "Finish date"])
    for p in people:
        writer.writerow([
            p.name, p.job_title, p.team.name if p.team else "", p.email,
            p.start_date.isoformat(), p.end_date.isoformat() if p.end_date else "",
        ])
    return response


@login_required
def staff(request):
    """Staff see names, job titles and teams of those who share themselves;
    managers also see emails and dates, the Left and Starting views, the
    Health card and the download."""
    today = timezone.localdate()
    show = request.GET.get("show", "current")
    people = Person.objects.select_related("team")
    manager = access.is_manager(request.user)
    if show == "left" and manager:
        people = people.filter(end_date__lt=today)
    elif show == "starting" and manager:
        people = people.filter(start_date__gt=today)
    else:
        show = "current"
        people = people.current(on=today)
    me = getattr(request.user, "person", None)
    if not manager:
        people = people.filter(show_to_other_staff=True)
        if me is not None:
            people = people | people.model.objects.filter(pk=me.pk)
    team = request.GET.get("team", "")
    if team:
        people = people.filter(team__name=team)
    people = people.distinct()
    if manager and request.GET.get("download"):
        return _csv(people)
    return render(request, "people/staff.html", {
        "page_title": "Staff", "people": people, "show": show, "team": team,
        "teams": Team.objects.filter(active=True),
        "health": health.figures(request.user) if manager else None,
        "managed": {p.pk for p in access.managed_people(request.user)} if manager else set(),
        "me_pk": me.pk if me is not None else None,
    })


@login_required
@access.manager_required
@require_POST
def sync_now(request):
    run = hr_sync.sync()
    if run.ok:
        messages.success(request, f"{run.people_seen} people read from Practice HR.")
    else:
        messages.error(request, f"Practice HR could not be read: {run.message}")
    return redirect("staff")


@login_required
@access.manager_required
def add_staff(request):
    return render(request, "people/add_staff_dialog.html")
