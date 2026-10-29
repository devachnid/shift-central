import pytest
from django.test import Client

from people.models import AuditEntry, TeamManager
from people.services import access, managers
from tests.factories import make_person, make_team, make_user_for

pytestmark = pytest.mark.django_db


def test_grant_and_revoke_are_audited(all_teams_user):
    nursing, pharmacy = make_team("Nursing"), make_team("Pharmacy")
    lead = make_person(team=nursing)
    managers.set_teams(all_teams_user, lead, [nursing, pharmacy])
    assert set(TeamManager.objects.filter(person=lead).values_list("team__name", flat=True)) == {"Nursing", "Pharmacy"}
    managers.set_teams(all_teams_user, lead, [nursing])
    assert list(TeamManager.objects.filter(person=lead).values_list("team__name", flat=True)) == ["Nursing"]
    rows = AuditEntry.objects.filter(model="people.person", object_id=lead.pk,
                                     field="manager_of").order_by("pk")
    assert [(r.before, r.after) for r in rows] == [("", "Nursing"), ("", "Pharmacy"), ("Pharmacy", "")]


def test_the_dialog_is_all_teams_only():
    nursing = make_team("Nursing")
    lead = make_person(team=nursing)
    boss = Client()
    boss.force_login(make_user_for(make_person(), is_all_teams_manager=True))
    body = boss.get(f"/staff/{lead.pk}/permissions/").content.decode()
    assert 'name="teams"' in body and "Nursing" in body
    r = boss.post(f"/staff/{lead.pk}/permissions/", {"teams": [nursing.pk]})
    assert r.status_code == 200 and access.can_manage_team(make_user_for(lead), nursing)
    team_lead = Client()
    team_lead.force_login(lead.user)
    assert team_lead.get(f"/staff/{lead.pk}/permissions/").status_code == 403


def test_an_all_teams_managers_own_dialog_says_it_is_set_in_hr():
    boss_person = make_person()
    boss = Client()
    boss.force_login(make_user_for(boss_person, is_all_teams_manager=True))
    other = make_person(first_name="Other")
    make_user_for(other, is_all_teams_manager=True)
    body = boss.get(f"/staff/{other.pk}/permissions/").content.decode()
    assert "all teams, set in Practice HR" in body
