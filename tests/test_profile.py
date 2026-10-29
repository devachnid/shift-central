"""The profile pop-up (FMS items 15–18, 21, 22, 24) and the services behind it."""

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from people.models import Allowance, AuditEntry
from people.services import profiles
from tests.factories import make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def years_2026_2027(monkeypatch):
    """The hours tab's year fields follow today's date; pin them so the
    field names below hold whenever the suite runs."""
    monkeypatch.setattr(profiles, "leave_years",
                        lambda today=None: [date(2026, 1, 1), date(2027, 1, 1)])


@pytest.fixture
def world(db):
    nursing = make_team("Nursing")
    nurse = make_person(team=nursing, first_name="Nina")
    lead = make_person(team=nursing, first_name="Lead")
    make_team_manager(lead, nursing)
    rec = make_person(first_name="Rec")
    boss = make_person(first_name="Boss")
    clients = {}
    for key, person, kw in (("nurse", nurse, {}), ("lead", lead, {}), ("rec", rec, {}),
                            ("boss", boss, {"is_all_teams_manager": True})):
        c = Client()
        c.force_login(make_user_for(person, **kw))
        clients[key] = c
    return {"nurse": nurse, "lead": lead, "rec": rec, "boss": boss, "c": clients}


# --- who sees which tabs ---------------------------------------------------------

def test_own_profile_shows_general_and_display_read_only_no_notes(world):
    body = world["c"]["nurse"].get(f"/staff/{world['nurse'].pk}/profile/").content.decode()
    assert "Your profile" in body and "Nina" in body
    assert "?tab=notes" not in body, "notes are managers only"
    assert "?tab=hours" in body, "own hours and allowances are readable"
    assert 'name="job_title"' not in body, "staff cannot edit the display fields"


def test_a_colleagues_profile_is_not_opened_by_staff(world):
    assert world["c"]["rec"].get(f"/staff/{world['nurse'].pk}/profile/").status_code == 403


def test_a_team_manager_edits_their_teams_people_only(world):
    c = world["c"]["lead"]
    body = c.get(f"/staff/{world['nurse'].pk}/profile/?tab=display").content.decode()
    assert "Nina Patel&#x27;s profile" in body and 'name="job_title"' in body and "?tab=notes" in body
    assert c.get(f"/staff/{world['rec'].pk}/profile/").status_code == 403


def test_the_general_tab_shows_hr_fields_read_only(world):
    body = world["c"]["boss"].get(f"/staff/{world['nurse'].pk}/profile/").content.decode()
    assert "from Practice HR" in body and world["nurse"].email in body
    assert 'name="email"' not in body


# --- display ---------------------------------------------------------------------

def test_the_display_form_saves_and_audits(world):
    c, nurse = world["c"]["boss"], world["nurse"]
    r = c.post(f"/staff/{nurse.pk}/profile/?tab=display", {
        "job_title": "Practice nurse", "name_colour": "#C94C4C", "display_order": "20",
        "display_on_rota": "on", "show_to_other_staff": "on"})
    assert r.status_code == 200 and "Saved" in r.content.decode()
    nurse.refresh_from_db()
    assert (nurse.job_title, nurse.name_colour, nurse.display_order) == ("Practice nurse", "#C94C4C", 20)
    assert nurse.display_on_rota and nurse.show_to_other_staff and not nurse.can_see_other_staff
    assert {a.field for a in AuditEntry.objects.filter(object_id=nurse.pk)} == {
        "job_title", "name_colour", "display_order", "can_see_other_staff"}


def test_a_bad_colour_is_refused(world):
    c, nurse = world["c"]["boss"], world["nurse"]
    r = c.post(f"/staff/{nurse.pk}/profile/?tab=display", {
        "job_title": "x", "name_colour": "red", "display_order": "20"})
    assert r.status_code == 200 and "field-error" in r.content.decode()
    nurse.refresh_from_db()
    assert nurse.name_colour == "#143D5C"


# --- hours and allowances ----------------------------------------------------------

def test_leave_years_are_this_year_and_next(monkeypatch):
    monkeypatch.undo()
    assert profiles.leave_years(date(2026, 11, 20)) == [date(2026, 1, 1), date(2027, 1, 1)]


def test_the_hours_tab_saves_hours_days_and_both_years_allowances(world):
    c, nurse = world["c"]["boss"], world["nurse"]
    r = c.post(f"/staff/{nurse.pk}/profile/?tab=hours", {
        "weekly_hours": "30", "days_per_week": "4",
        "annual_2027": "138", "bank_holiday_2027": "48", "note": ""})
    assert r.status_code == 200 and "Saved" in r.content.decode()
    nurse.refresh_from_db()
    assert (nurse.weekly_hours, nurse.days_per_week, nurse.average_day) == (Decimal("30.00"), 4, Decimal("7.5"))
    a = Allowance.objects.get(person=nurse, leave_year=date(2027, 1, 1))
    assert (a.annual_hours, a.bank_holiday_hours) == (Decimal("138.00"), Decimal("48.00"))
    assert not Allowance.objects.filter(person=nurse, leave_year=date(2026, 1, 1)).exists(), "blank year not created"


def test_changing_an_existing_allowance_needs_a_reason(world):
    nurse, boss = world["nurse"], world["boss"].user
    profiles.set_allowance(boss, nurse, date(2027, 1, 1), Decimal("138"), Decimal("48"), note="")
    with pytest.raises(ValueError, match="reason"):
        profiles.set_allowance(boss, nurse, date(2027, 1, 1), Decimal("140"), Decimal("48"), note="")
    rows = profiles.set_allowance(boss, nurse, date(2027, 1, 1), Decimal("140"), Decimal("48"),
                                  note="extra bank holiday 2027")
    assert [(r.field, r.before, r.after, r.note) for r in rows] == [
        ("annual_hours", "138.00", "140.00", "extra bank holiday 2027")]


def test_the_hours_form_refuses_a_change_without_a_reason(world):
    c, nurse = world["c"]["boss"], world["nurse"]
    profiles.set_allowance(world["boss"].user, nurse, date(2027, 1, 1), Decimal("138"), Decimal("48"), note="")
    r = c.post(f"/staff/{nurse.pk}/profile/?tab=hours", {
        "weekly_hours": "30", "days_per_week": "4", "annual_2027": "140", "bank_holiday_2027": "48", "note": ""})
    assert "reason" in r.content.decode().lower()
    assert Allowance.objects.get(person=nurse, leave_year=date(2027, 1, 1)).annual_hours == Decimal("138.00")


def test_a_gp_has_no_hours_fields(world):
    doc = make_person(first_name="Doc", is_gp=True, team=make_team("GPs"))
    body = world["c"]["boss"].get(f"/staff/{doc.pk}/profile/?tab=hours").content.decode()
    assert 'name="weekly_hours"' not in body and "sessions, from the GP rota" in body
    assert 'name="annual_2027"' in body


def test_staff_see_their_own_hours_tab_read_only(world):
    nurse = world["nurse"]
    profiles.update_hours(world["boss"].user, nurse, Decimal("30"), 4)
    body = world["c"]["nurse"].get(f"/staff/{nurse.pk}/profile/?tab=hours").content.decode()
    assert "30" in body and 'name="weekly_hours"' not in body


# --- notes and history ---------------------------------------------------------------

def test_notes_are_managers_only(world):
    c, nurse = world["c"]["lead"], world["nurse"]
    assert c.post(f"/staff/{nurse.pk}/profile/?tab=notes", {"notes": "Prefers Tuesdays"}).status_code == 200
    nurse.refresh_from_db()
    assert nurse.notes == "Prefers Tuesdays"
    assert world["c"]["nurse"].get(f"/staff/{nurse.pk}/profile/?tab=notes").status_code == 403


def test_notes_about_a_manager_never_reach_her_through_the_logs(world):
    """ACC-04: the lead nurse manages her own team, so the Activity log
    covers her own record; the audit says the notes changed, never what
    they say."""
    lead, c = world["lead"], world["c"]["lead"]
    profiles.set_notes(world["boss"].user, lead, "Struggling since the move")
    profiles.set_notes(world["boss"].user, lead, "Better after the review")
    activity = c.get("/activity/").content.decode()
    assert "notes" in activity and "(notes changed)" in activity
    assert "Struggling" not in activity and "Better after" not in activity
    history = c.get(f"/staff/{lead.pk}/history/")
    assert history.status_code == 403 or "Struggling" not in history.content.decode()
    assert c.get(f"/staff/{lead.pk}/profile/?tab=notes").status_code == 403
    assert [(e.before, e.after) for e in AuditEntry.objects.filter(field="notes").order_by("pk")] == [
        ("", "(notes changed)"), ("(notes)", "(notes changed)")]


def test_saving_the_same_notes_writes_no_audit_row(world):
    profiles.set_notes(world["boss"].user, world["nurse"], "Prefers Tuesdays")
    assert profiles.set_notes(world["boss"].user, world["nurse"], "Prefers Tuesdays") == []
    assert AuditEntry.objects.filter(field="notes").count() == 1


def test_history_lists_the_persons_audit_entries_for_managers(world):
    nurse = world["nurse"]
    profiles.update_display(world["boss"].user, nurse, job_title="Practice nurse")
    body = world["c"]["lead"].get(f"/staff/{nurse.pk}/history/").content.decode()
    assert "job_title" in body and "Practice nurse" in body and "boss" in body
    assert world["c"]["nurse"].get(f"/staff/{nurse.pk}/history/").status_code == 403
