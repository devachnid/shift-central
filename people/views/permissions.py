from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from people.models import Person, Team
from people.services import access, managers


@login_required
@access.all_teams_required
def permissions(request, pk):
    person = get_object_or_404(Person, pk=pk)
    saved = False
    if request.method == "POST":
        teams = Team.objects.filter(pk__in=request.POST.getlist("teams"))
        managers.set_teams(request.user, person, teams)
        saved = True
    return render(request, "people/permissions_dialog.html", {
        "person": person, "teams": Team.objects.filter(active=True),
        "granted": set(person.manager_of.values_list("team_id", flat=True)),
        "is_all_teams_person": bool(person.user and person.user.is_all_teams_manager),
        "saved": saved})
