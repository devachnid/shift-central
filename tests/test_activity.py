from datetime import date, datetime, time

import pytest
from django.test import Client
from django.utils import timezone

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
    assert "Nurse" in body and "display_order" not in body


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


@pytest.mark.parametrize("bad", ["abc", "²", "①", "-1"])
def test_a_bad_person_filter_shows_nothing_rather_than_an_error(bad):
    boss_person = make_person(first_name="Boss")
    c = _client(boss_person, is_all_teams_manager=True)
    profiles.update_display(boss_person.user, make_person(first_name="Nina"), job_title="Nurse")
    response = c.get("/activity/", {"person": bad})
    assert response.status_code == 200
    assert "Nurse" not in response.content.decode()


def _boss():
    boss = make_person(first_name="Boss")
    return boss, _client(boss, is_all_teams_manager=True)


def _on(row, day):
    """Move a log row to noon on a given day (at is auto_now_add)."""
    at = timezone.make_aware(datetime.combine(day, time(12)))
    type(row).objects.filter(pk=row.pk).update(at=at)


def test_login_logs_filter_by_date():
    boss, c = _boss()
    early = LoginEvent.objects.create(user=boss.user, ip="203.0.113.1")
    inside = LoginEvent.objects.create(user=boss.user, ip="203.0.113.2")
    late = LoginEvent.objects.create(user=boss.user, ip="203.0.113.3")
    for row, day in ((early, date(2026, 9, 30)), (inside, date(2026, 10, 15)), (late, date(2026, 11, 1))):
        _on(row, day)
    body = c.get("/activity/logins/", {"from": "2026-10-01", "to": "2026-10-31"}).content.decode()
    assert "203.0.113.2" in body and "203.0.113.1" not in body and "203.0.113.3" not in body
    assert 'value="2026-10-01"' in body and 'value="2026-10-31"' in body


def test_login_logs_filter_by_person():
    boss, c = _boss()
    nina = make_user_for(make_person(first_name="Nina"))
    LoginEvent.objects.create(user=boss.user, ip="203.0.113.1")
    LoginEvent.objects.create(user=nina, ip="203.0.113.2")
    body = c.get("/activity/logins/", {"person": str(nina.pk)}).content.decode()
    assert "203.0.113.2" in body and "203.0.113.1" not in body
    assert f'<option value="{nina.pk}" selected>{nina.email}</option>' in body


@pytest.mark.parametrize("params", [{"from": "yesterday"}, {"to": "2026-13-45"}, {"from": ""}])
def test_a_bad_date_is_ignored_not_an_error(params):
    boss, c = _boss()
    LoginEvent.objects.create(user=boss.user, ip="203.0.113.1")
    profiles.update_display(boss.user, make_person(first_name="Nina"), job_title="Nurse")
    for url, seen in (("/activity/logins/", "203.0.113.1"), ("/activity/", "Nurse")):
        response = c.get(url, params)
        assert response.status_code == 200 and seen in response.content.decode()


def test_a_bad_login_person_filter_shows_nothing():
    boss, c = _boss()
    LoginEvent.objects.create(user=boss.user, ip="203.0.113.1")
    response = c.get("/activity/logins/", {"person": "²"})
    assert response.status_code == 200 and "203.0.113.1" not in response.content.decode()


def test_the_activity_log_filters_by_date():
    boss, c = _boss()
    nina = make_person(first_name="Nina")
    [old] = profiles.update_display(boss.user, nina, display_order=5)
    [new] = profiles.update_display(boss.user, nina, job_title="Nurse")
    _on(old, date(2026, 9, 1))
    _on(new, date(2026, 10, 20))
    body = c.get("/activity/", {"from": "2026-10-01"}).content.decode()
    assert "<td>job_title</td>" in body and "<td>display_order</td>" not in body
    body = c.get("/activity/", {"from": "2026-08-01", "to": "2026-09-30"}).content.decode()
    assert "<td>display_order</td>" in body and "<td>job_title</td>" not in body


def test_allowance_rows_name_the_person():
    boss, c = _boss()
    nina = make_person(first_name="Nina", last_name="Shah")
    profiles.set_allowance(boss.user, nina, date(2026, 1, 1), "187.5", "60")
    body = c.get("/activity/", {"field": "annual_hours"}).content.decode()
    assert "<td>Nina Shah</td>" in body and "<td>allowance</td>" not in body


def test_a_rota_cell_edit_appears_under_that_persons_filter():
    from shifts.services import entries
    boss, c = _boss()
    nina = make_person(first_name="Nina", last_name="Shah")
    other = make_person(first_name="Omar", last_name="Ali")
    entries.set_cell_text(boss.user, nina, date(2027, 3, 1), "08:00-12:00")
    entries.set_cell_text(boss.user, other, date(2027, 3, 1), "13:00-17:00")
    body = c.get("/activity/", {"person": str(nina.pk)}).content.decode()
    assert "<td>Nina Shah</td>" in body and "<td>cell</td>" in body and "08:00" in body
    assert "13:00" not in body and "Omar Ali</td>" not in body


def test_a_team_manager_sees_rota_changes_for_their_team_only():
    from shifts.services import entries
    nursing = make_team("Nursing")
    lead = make_person(team=nursing)
    make_team_manager(lead, nursing)
    boss = make_user_for(make_person(first_name="Boss"), is_all_teams_manager=True)
    entries.set_cell_text(boss, make_person(first_name="Nina", team=nursing), date(2027, 3, 1), "08:00-12:00")
    entries.set_cell_text(boss, make_person(first_name="Rec"), date(2027, 3, 1), "13:00-17:00")
    body = _client(lead).get("/activity/").content.decode()
    assert "08:00" in body and "13:00" not in body


def test_template_changes_appear_labelled_template():
    from shifts.services import templates
    boss, c = _boss()
    templates.save(boss.user, "Monday cover", {"days": 1, "rows": []})
    body = c.get("/activity/").content.decode()
    assert "<td>template</td>" in body and "Monday cover" in body


def test_a_staff_users_activity_log_is_still_forbidden_with_rota_changes_in_it():
    from shifts.services import entries
    boss, _ = _boss()
    nina = make_person(first_name="Nina")
    entries.set_cell_text(boss.user, nina, date(2027, 3, 1), "08:00-12:00")
    assert _client(nina).get("/activity/").status_code == 403
