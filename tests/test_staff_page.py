"""The Staff list (FMS item 27), the Health card and Sync now."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone

from people.models import Allowance, SyncRun
from tests.factories import make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


def _client(person, **kw):
    c = Client()
    c.force_login(make_user_for(person, **kw))
    return c


def test_staff_see_current_people_with_name_title_and_team_only():
    me = make_person(job_title="Receptionist")
    make_person(first_name="Gone", end_date=date(2020, 1, 1), start_date=date(2019, 1, 1))
    body = _client(me).get("/staff/").content.decode()
    assert "Sam Patel" in body and "Receptionist" in body and "Reception" in body
    assert "Gone" not in body
    assert me.email not in body, "staff do not see emails"
    assert "health" not in body


def test_managers_see_emails_start_dates_and_the_health_card():
    boss = make_person()
    body = _client(boss, is_all_teams_manager=True).get("/staff/").content.decode()
    assert boss.email in body and "8 Jan 2024" in body
    assert 'class="health"' in body


def test_the_filter_shows_left_and_starting_people():
    boss = make_person()
    make_person(first_name="Gone", start_date=date(2019, 1, 1), end_date=date(2020, 1, 1))
    make_person(first_name="Soon", start_date=timezone.localdate() + timedelta(days=30))
    c = _client(boss, is_all_teams_manager=True)
    assert "Gone" not in c.get("/staff/").content.decode()
    assert "Gone" in c.get("/staff/?show=left").content.decode()
    assert "Soon" in c.get("/staff/?show=starting").content.decode()


def test_team_filter():
    boss = make_person()
    make_person(first_name="Nina", team=make_team("Nursing"))
    c = _client(boss, is_all_teams_manager=True)
    body = c.get("/staff/?team=Nursing").content.decode()
    table = body.split("<tbody>")[1]    # the shell and the Health card also name people
    assert "Nina" in table and "Sam Patel" not in table


def test_managers_can_download_the_visible_rows_as_csv():
    boss = make_person(first_name="Bea", last_name="Boss")
    make_person(first_name="Nina", last_name="Nurse", job_title="Nurse",
                team=make_team("Nursing"), start_date=date(2023, 5, 2))
    make_person(first_name="Gone", start_date=date(2019, 1, 1), end_date=date(2020, 1, 1))
    r = _client(boss, is_all_teams_manager=True).get("/staff/?download=1")
    assert r["Content-Type"].startswith("text/csv")
    assert r["Content-Disposition"] == 'attachment; filename="staff.csv"'
    lines = r.content.decode().splitlines()
    assert lines[0] == "Name,Job title,Team,Email,Start date,Finish date"
    assert any(line.startswith("Nina Nurse,Nurse,Nursing,") and line.endswith(",2023-05-02,")
               for line in lines)
    assert not any("Gone" in line for line in lines), "the CSV carries the same rows as the page"


def test_staff_cannot_download():
    r = _client(make_person()).get("/staff/?download=1")
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/html")


def _set_up(person, years_on=0):
    """An allowance for this leave year, or `years_on` years from it."""
    Allowance.objects.create(person=person, leave_year=date(timezone.localdate().year + years_on, 1, 1),
                             annual_hours=Decimal("187.5"), bank_holiday_hours=Decimal("60"))
    return person


def test_health_card_figures():
    from people.services import health
    boss = _set_up(make_person(weekly_hours=Decimal("37.5"), days_per_week=5))
    user = make_user_for(boss, is_all_teams_manager=True)
    make_person(first_name="New")                        # no hours yet
    make_person(first_name="Leaving", end_date=timezone.localdate() + timedelta(days=10))
    stale = make_person(first_name="Stale")
    stale.last_seen_from_hr = timezone.now() - timedelta(days=3)
    stale.save()
    SyncRun.objects.create(ok=True, people_seen=4, finished_at=timezone.now())
    f = health.figures(user)
    assert f["last_run"].ok and f["last_run"].people_seen == 4
    assert {p.first_name for p in f["needs_setup"]} == {"New", "Leaving", "Stale"}
    assert [p.first_name for p in f["not_seen"]] == ["Stale"]
    assert [r["person"].first_name for r in f["leaving_soon"]] == ["Leaving"]


def test_gps_do_not_need_hours():
    from people.services import health
    boss = _set_up(make_person(weekly_hours=Decimal("37.5"), days_per_week=5))
    user = make_user_for(boss, is_all_teams_manager=True)
    make_person(first_name="Doc", is_gp=True)
    assert not health.figures(user)["needs_setup"].exists()


def test_a_team_manager_sees_only_their_teams_figures():
    from people.services import health
    nursing = make_team("Nursing")
    lead = _set_up(make_person(team=nursing, weekly_hours=Decimal("30"), days_per_week=4))
    make_team_manager(lead, nursing)
    make_person(first_name="Nurse", team=nursing)
    make_person(first_name="Rec")
    assert {p.first_name for p in health.figures(make_user_for(lead))["needs_setup"]} == {"Nurse"}


def test_hours_and_days_without_an_allowance_still_need_setting_up():
    from people.services import health
    boss = _set_up(make_person(first_name="Boss", weekly_hours=Decimal("37.5"), days_per_week=5))
    user = make_user_for(boss, is_all_teams_manager=True)
    make_person(first_name="Hours", weekly_hours=Decimal("22.5"), days_per_week=3)
    _set_up(make_person(first_name="Next", weekly_hours=Decimal("22.5"), days_per_week=3), years_on=1)
    _set_up(make_person(first_name="Old", weekly_hours=Decimal("22.5"), days_per_week=3), years_on=-1)
    assert {p.first_name for p in health.figures(user)["needs_setup"]} == {"Hours", "Old"}


def test_sync_now_runs_the_sync_and_reports(monkeypatch):
    from people.services import hr_sync
    boss = make_person()
    c = _client(boss, is_all_teams_manager=True)
    monkeypatch.setattr(hr_sync, "sync", lambda client=None: SyncRun.objects.create(
        ok=True, people_seen=12, finished_at=timezone.now()))
    r = c.post("/staff/sync/", follow=True)
    assert "12 people read from Practice HR" in r.content.decode()


def test_a_get_of_sync_now_goes_back_to_the_staff_page():
    """Signing in again after the session ended mid-POST returns here as a GET."""
    r = _client(make_person(), is_all_teams_manager=True).get("/staff/sync/")
    assert r.status_code == 302 and r["Location"] == "/staff/"
    assert not SyncRun.objects.exists()


def test_a_get_of_sync_now_signed_out_goes_to_the_login_page(client):
    r = client.get("/staff/sync/")
    assert r.status_code == 302 and r["Location"].startswith("/accounts/login/?next=/staff/sync/")


def test_staff_cannot_sync():
    assert _client(make_person()).post("/staff/sync/").status_code == 403


def test_add_staff_points_at_practice_hr(oidc_on):
    boss = make_person()
    body = _client(boss, is_all_teams_manager=True).get("/staff/add/").content.decode()
    assert "Practice HR" in body and 'href="https://hr.example/admin/people/employee/add/"' in body
    assert 'action="/staff/sync/"' in body


def test_a_team_manager_sees_contact_details_for_their_own_team_only():
    nursing = make_team("Nursing")
    lead = make_person(first_name="Lead", team=nursing)
    make_team_manager(lead, nursing)
    nurse = make_person(first_name="Nina", team=nursing)
    rec = make_person(first_name="Rec", start_date=date(2021, 3, 4))
    c = _client(lead)
    table = c.get("/staff/").content.decode().split("<tbody>")[1]
    assert nurse.email in table
    assert rec.name in table and rec.email not in table and "4 Mar 2021" not in table
    csv_text = c.get("/staff/?download=1").content.decode()
    assert nurse.email in csv_text
    assert rec.email not in csv_text and "2021-03-04" not in csv_text
    assert any(line.startswith("Rec Patel,") and line.endswith(",,,") for line in csv_text.splitlines())
