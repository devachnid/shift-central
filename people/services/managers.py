"""Manager access per team (PEOPLE-04): granted and revoked by all-teams
managers; every change audited on the person as `manager_of`."""

from django.core.exceptions import PermissionDenied

from people.models import TeamManager
from people.services import access, audit


def grant(actor, person, team):
    row, made = TeamManager.objects.get_or_create(person=person, team=team,
                                                  defaults={"granted_by": actor})
    if made:
        audit.record(actor, person, {"manager_of": ("", team.name)})
    return row


def revoke(actor, person, team):
    deleted, _ = TeamManager.objects.filter(person=person, team=team).delete()
    if deleted:
        audit.record(actor, person, {"manager_of": (team.name, "")})


def set_teams(actor, person, teams):
    wanted = {t.pk: t for t in teams}
    current = {r.team_id: r.team for r in TeamManager.objects.filter(person=person).select_related("team")}
    for pk, team in sorted(wanted.items(), key=lambda kv: kv[1].name):
        if pk not in current:
            grant(actor, person, team)
    for pk, team in current.items():
        if pk not in wanted:
            revoke(actor, person, team)


def set_own_leave_flag(actor, person, flag):
    """The practice manager's own leave needs no approval (PEOPLE-07). Set
    by another all-teams manager, never on oneself: that would be approving
    one's own leave."""
    if access.is_self(actor, person):
        raise PermissionDenied("you can't set your own leave to need no approval")
    if person.own_leave_without_approval != flag:
        person.own_leave_without_approval = flag
        person.save(update_fields=["own_leave_without_approval"])
        audit.record(actor, person, {"own_leave_without_approval": (not flag, flag)})
