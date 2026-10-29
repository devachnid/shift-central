"""Who may manage whom. Roles are decided at request time, never stored on
the person: all-teams manager is the user's flag from HR's admin claim;
team manager is a TeamManager row for the user's person."""

from functools import wraps

from django.core.exceptions import PermissionDenied

from people.models import Person, Team, TeamManager


def _person(user):
    return getattr(user, "person", None) if user.is_authenticated else None


def is_all_teams(user):
    return bool(user.is_authenticated and user.is_all_teams_manager)


def managed_teams(user):
    if is_all_teams(user):
        return Team.objects.all()
    person = _person(user)
    if person is None:
        return Team.objects.none()
    return Team.objects.filter(managers__person=person).distinct()


def role(user):
    if is_all_teams(user):
        return "all"
    person = _person(user)
    if person is not None and TeamManager.objects.filter(person=person).exists():
        return "team"
    return "staff"


def is_manager(user):
    return role(user) != "staff"


def is_self(user, person):
    me = _person(user)
    return me is not None and me.pk == person.pk


def can_manage_team(user, team):
    if is_all_teams(user):
        return True
    return team is not None and managed_teams(user).filter(pk=team.pk).exists()


def can_manage(user, person):
    """Managing a person: their team is one the user manages, and the
    person is not the user themselves (spec 3 relies on this for leave)."""
    if is_self(user, person):
        return False
    if is_all_teams(user):
        return True
    return person.team_id is not None and can_manage_team(user, person.team)


def managed_people(user):
    """Everyone the user has manager access over, themselves included where
    they manage their own team (the lead nurse sees Nursing's list in full);
    can_manage() is the per-person rule and excludes self."""
    if is_all_teams(user):
        return Person.objects.all()
    teams = managed_teams(user)
    if not teams.exists():
        return Person.objects.none()
    return Person.objects.filter(team__in=teams)


def manager_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_manager(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def all_teams_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_all_teams(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped
