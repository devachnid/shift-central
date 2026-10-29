import pytest
from django.test import Client

from accounts.models import LoginEvent
from people.services import profiles
from tests.factories import make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


def _client(person, **kw):
    c = Client()
    c.force_login(make_user_for(person, **kw))
    return c


def test_team_managers_see_their_teams_entries_only():
    nursing = make_team("Nursing")
    lead = make_person(team=nursing)
    make_team_manager(lead, nursing)
    nurse = make_person(first_name="Nina", team=nursing)
    rec = make_person(first_name="Rec")
    boss = make_user_for(make_person(first_name="Boss"), is_all_teams_manager=True)
    profiles.update_display(boss, nurse, job_title="Nurse")
    profiles.update_display(boss, rec, job_title="Receptionist")
    body = _client(lead).get("/activity/").content.decode()
    assert "Nurse" in body and "Receptionist" not in body


def test_filters_by_person_and_field():
    boss_person = make_person(first_name="Boss")
    c = _client(boss_person, is_all_teams_manager=True)
    p = make_person(first_name="Nina")
    profiles.update_display(boss_person.user, p, job_title="Nurse", display_order=5)
    body = c.get(f"/activity/?person={p.pk}&field=job_title").content.decode()
    assert "Nurse" in body and ">5<" not in body


def test_staff_get_403():
    assert _client(make_person()).get("/activity/").status_code == 403


def test_login_logs_are_all_teams_only():
    nursing = make_team("Nursing")
    lead = make_person(team=nursing)
    make_team_manager(lead, nursing)
    boss = make_person(first_name="Boss")
    LoginEvent.objects.create(user=make_user_for(boss, is_all_teams_manager=True), ip="203.0.113.9")
    c = Client()
    c.force_login(boss.user)
    body = c.get("/activity/logins/").content.decode()
    assert "203.0.113.9" in body and boss.user.email in body
    assert _client(lead).get("/activity/logins/").status_code == 403


def test_the_activity_page_links_to_the_login_logs_for_all_teams_managers_only():
    nursing = make_team("Nursing")
    lead = make_person(team=nursing)
    make_team_manager(lead, nursing)
    boss = make_person(first_name="Boss")
    link = 'class="topbar-action" href="/activity/logins/"'
    assert link in _client(boss, is_all_teams_manager=True).get("/activity/").content.decode()
    assert 'href="/activity/logins/"' not in _client(lead).get("/activity/").content.decode()
