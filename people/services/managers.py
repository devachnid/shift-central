"""Manager access per team (PEOPLE-04): granted and revoked by all-teams
managers; every change audited on the person as `manager_of`."""

from people.models import TeamManager
from people.services import audit


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
