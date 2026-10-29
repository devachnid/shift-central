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


def _boss_client():
    c = Client()
    c.force_login(make_user_for(make_person(first_name="Boss"), is_all_teams_manager=True))
    return c


def test_a_grant_on_an_inactive_team_is_listed_and_survives_a_save(all_teams_user):
    nursing, old = make_team("Nursing"), make_team("Old Nursing")
    lead = make_person(team=nursing)
    managers.grant(all_teams_user, lead, old)
    old.active = False
    old.save()
    c = _boss_client()
    body = c.get(f"/staff/{lead.pk}/permissions/").content.decode()
    assert "Old Nursing (inactive)" in body and f'value="{old.pk}" id="team-{old.pk}" checked' in body
    c.post(f"/staff/{lead.pk}/permissions/", {"teams": [nursing.pk, old.pk]})
    assert set(TeamManager.objects.filter(person=lead).values_list("team__name", flat=True)) == {
        "Nursing", "Old Nursing"}


def test_an_inactive_team_nobody_holds_is_not_offered():
    make_team("Old Nursing", active=False)
    body = _boss_client().get(f"/staff/{make_person().pk}/permissions/").content.decode()
    assert "Old Nursing" not in body


@pytest.mark.parametrize("bad", ["abc", "²", "-1", "1.5"])
def test_a_tampered_team_value_is_dropped_not_an_error(bad):
    nursing = make_team("Nursing")
    lead = make_person(team=nursing)
    r = _boss_client().post(f"/staff/{lead.pk}/permissions/", {"teams": [bad, str(nursing.pk)]})
    assert r.status_code == 200
    assert list(TeamManager.objects.filter(person=lead).values_list("team__name", flat=True)) == ["Nursing"]


def test_a_post_for_an_all_teams_manager_writes_nothing():
    nursing = make_team("Nursing")
    other = make_person(first_name="Other")
    make_user_for(other, is_all_teams_manager=True)
    r = _boss_client().post(f"/staff/{other.pk}/permissions/", {"teams": [nursing.pk]})
    assert r.status_code == 200 and "all teams, set in Practice HR" in r.content.decode()
    assert not TeamManager.objects.exists() and not AuditEntry.objects.exists()


def test_a_team_managers_post_is_refused():
    nursing = make_team("Nursing")
    lead = make_person(team=nursing)
    managers.grant(None, lead, nursing)
    c = Client()
    c.force_login(make_user_for(lead))
    assert c.post(f"/staff/{lead.pk}/permissions/", {"teams": []}).status_code == 403
    assert TeamManager.objects.filter(person=lead).exists()


def test_revoking_in_the_dialog_is_audited_as_manager_of():
    nursing = make_team("Nursing")
    lead = make_person(team=nursing)
    managers.grant(None, lead, nursing)
    r = _boss_client().post(f"/staff/{lead.pk}/permissions/", {})
    assert r.status_code == 200 and "Saved." in r.content.decode()
    assert not TeamManager.objects.filter(person=lead).exists()
    row = AuditEntry.objects.get(object_id=lead.pk, field="manager_of", after="")
    assert row.before == "Nursing" and row.actor.is_all_teams_manager
