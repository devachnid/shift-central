from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from people.models import Person, Team
from people.services import access, managers


@login_required
@access.all_teams_required
def permissions(request, pk):
    """The teams a person manages. An inactive team is listed while it is
    still granted, so saving the dialog does not revoke it unseen. An
    all-teams manager's access is HR's admin claim: no teams to write, but
    the own-leave flag is ours for everyone."""
    person = get_object_or_404(Person, pk=pk)
    is_all_teams_person = bool(person.user and person.user.is_all_teams_manager)
    myself = access.is_self(request.user, person)      # the own-leave flag is never set on oneself
    saved = False
    if request.method == "POST":
        if not is_all_teams_person:
            # A tampered value is dropped rather than reaching the pk lookup.
            wanted = [v for v in request.POST.getlist("teams") if v.isascii() and v.isdigit()]
            managers.set_teams(request.user, person, Team.objects.filter(pk__in=wanted))
        if not myself:
            managers.set_own_leave_flag(request.user, person, request.POST.get("own_leave_without_approval") == "on")
        saved = True
    granted = set(person.manager_of.values_list("team_id", flat=True))
    return render(request, "people/permissions_dialog.html", {
        "person": person, "teams": Team.objects.filter(Q(active=True) | Q(pk__in=granted)),
        "granted": granted, "is_all_teams_person": is_all_teams_person, "saved": saved, "myself": myself})
