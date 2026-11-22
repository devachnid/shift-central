"""Allowance spec 2026-11-18, section 8: the profile's Pay & time off tab,
the statement and the Leave settings switch."""

import re
from datetime import date
from decimal import Decimal as D

import pytest
from django.core.exceptions import PermissionDenied

from leave.models import LeaveSetting
from leave.services import entitlement
from leave.services import settings as leave_settings
from people.models import Allowance, AuditEntry
from people.services import profiles
from tests.factories import client_for, make_allowance, make_contract, make_person, make_team, make_team_manager

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 2, 1))]
Y27, Y28 = date(2027, 1, 1), date(2028, 1, 1)
JUNE = date(2027, 6, 1)
RECEPTION = [(1, 23)]
WORKING = "23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min"


@pytest.fixture
def world(db):
    nursing = make_team("Nursing")
    boss = make_person(first_name="Boss", team=make_team("Management"))
    lead = make_person(first_name="Lead", team=nursing)
    make_team_manager(lead, nursing)
    nina = make_person(first_name="Nina", team=nursing, start_date=date(2025, 6, 1), weekly_hours=D("37.5"), days_per_week=5)
    make_contract(nina, "37.5", steps=RECEPTION)
    entitlement.refresh()
    return {"boss": boss, "lead": lead, "nina": nina,
            "c_boss": client_for(boss, is_all_teams_manager=True), "c_lead": client_for(lead), "c_nina": client_for(nina)}


def _tab(client, person, **query):
    return client.get(f"/staff/{person.pk}/profile/", {"tab": "hours", **query}).content.decode()


def _row(person, year=Y27, from_day=None):
    return Allowance.objects.get(person=person, leave_year=year, from_day=from_day or year)


# --- the figures, their state, working and buttons ---------------------------------------------

def test_a_manager_sees_each_years_state_working_and_buttons(world):
    body = _tab(world["c_lead"], world["nina"])
    row = _row(world["nina"])
    assert "Where the allowances come from" in body and body.count("worked out, not yet checked") == 2
    assert WORKING in body and "8 bank holidays × 37.5 h ÷ 5 = 60 h" in body
    assert f'name="row" value="{row.pk}"' in body and 'name="allowance_action" value="confirm"' in body
    assert f'href="/staff/allowances/{row.pk}/change/"' in body
    assert 'name="annual_2027" value="172.50"' in body                  # two places in the box, whatever is stored


def test_staff_see_their_figures_with_no_state_no_working_and_no_buttons(world):
    body = _tab(world["c_nina"], world["nina"])
    assert "172.50 h" in body and "60.00 h" in body
    for hidden in ("worked out,", "not yet checked", "Where the allowances come from", WORKING, "allowance_action", "from the contract in Practice HR"):
        assert hidden not in body, hidden


def test_confirm_from_the_profile(world):
    row = _row(world["nina"])
    r = world["c_lead"].post(f"/staff/{world['nina'].pk}/profile/?tab=hours", {"allowance_action": "confirm", "row": row.pk})
    body = r.content.decode()
    assert r.status_code == 200 and "Saved." in body and "worked out, checked by Lead Patel on 1 Feb 2027" in body
    row.refresh_from_db()
    assert row.checked_by == world["lead"].user
    assert world["c_nina"].post(f"/staff/{world['nina'].pk}/profile/?tab=hours", {"allowance_action": "confirm", "row": row.pk}).status_code == 403


def test_a_row_of_someone_else_or_an_unknown_action_is_not_found(world):
    other = make_allowance(make_person(first_name="Other"), Y27, 138, 48, source="worked_out")
    url = f"/staff/{world['nina'].pk}/profile/?tab=hours"
    assert world["c_boss"].post(url, {"allowance_action": "confirm", "row": other.pk}).status_code == 404
    assert world["c_boss"].post(url, {"allowance_action": "delete", "row": _row(world["nina"]).pk}).status_code == 404
    assert other.needs_checking


def test_a_typed_figure_that_differs_shows_what_the_contract_gives_and_can_take_it(world):
    nina = world["nina"]
    row = _row(nina)
    profiles.change_allowance(world["boss"].user, row, D("180"), D("60"), "contract says 24 days")
    body = _tab(world["c_lead"], nina)
    assert "typed" in body and "The contract gives 172 h 30 min and 60 h: " + WORKING in body and "Use the worked-out figure" in body
    r = world["c_lead"].post(f"/staff/{nina.pk}/profile/?tab=hours", {"allowance_action": "use", "row": row.pk})
    assert "worked out, checked by Lead Patel on 1 Feb 2027" in r.content.decode()
    row.refresh_from_db()
    assert (row.annual_hours, row.source) == (D("172.5"), "worked_out")


def test_a_refused_action_is_said_above_the_list(world):
    plain = make_person(first_name="Plain", team=world["nina"].team)
    row = make_allowance(plain, Y27, 138, 48)
    r = world["c_lead"].post(f"/staff/{plain.pk}/profile/?tab=hours", {"allowance_action": "use", "row": row.pk})
    assert "This leave year is not worked out from a contract" in r.content.decode() and "Saved." not in r.content.decode()


def test_a_figure_checked_by_the_app_and_a_copied_one_say_so(world):
    typed = make_person(first_name="Typed", team=world["nina"].team, start_date=date(2025, 6, 1))
    make_contract(typed, "37.5", steps=RECEPTION)
    make_allowance(typed, Y27, D("172.5"), 60)
    make_allowance(typed, Y28, 150, 60, source="copied")
    entitlement.refresh()
    Allowance.objects.filter(person=typed, leave_year=Y28).update(source="copied")          # as copied before the contract arrived
    body = _tab(world["c_lead"], typed)
    assert "worked out, checked automatically on 1 Feb 2027" in body and "copied from last year, not yet checked" in body


# --- weekly hours are Practice HR's ------------------------------------------------------------

def test_weekly_hours_are_read_only_from_practice_hr_and_days_stay_typed(world):
    nina = world["nina"]
    body = _tab(world["c_lead"], nina)
    assert 'name="weekly_hours"' not in body and 'name="days_per_week"' in body
    assert "37.50 <span class=\"field-help\">from Practice HR</span>" in body
    r = world["c_lead"].post(f"/staff/{nina.pk}/profile/?tab=hours", {"weekly_hours": "20", "days_per_week": "4", "leave_year_start": "01-01"})
    assert "Saved." in r.content.decode()
    nina.refresh_from_db()
    assert (nina.weekly_hours, nina.days_per_week) == (D("37.5"), 4)


def test_bank_staff_on_a_contract_for_no_hours_are_typed_exactly_as_before(world):
    bank = make_person(first_name="Bank", team=world["nina"].team)
    make_contract(bank, 0, steps=RECEPTION)
    body = _tab(world["c_lead"], bank)
    assert 'name="weekly_hours"' in body and "from Practice HR" not in body
    world["c_lead"].post(f"/staff/{bank.pk}/profile/?tab=hours", {"weekly_hours": "12", "days_per_week": "2"})
    bank.refresh_from_db()
    assert (bank.weekly_hours, bank.days_per_week) == (D("12"), 2)


def test_someone_with_no_copied_contract_is_typed_exactly_as_before(world):
    plain = make_person(first_name="Plain", team=world["nina"].team)
    body = _tab(world["c_lead"], plain)
    assert 'name="weekly_hours"' in body and "from Practice HR" not in body and "Where the allowances come from" not in body
    world["c_lead"].post(f"/staff/{plain.pk}/profile/?tab=hours", {"weekly_hours": "20", "days_per_week": "4", "annual_2027": "92", "bank_holiday_2027": "32"})
    plain.refresh_from_db()
    assert plain.weekly_hours == D("20") and _row(plain).source == "typed"
    assert "typed" in _tab(world["c_lead"], plain)


def test_saving_the_tab_untouched_leaves_a_worked_out_gp_figure_alone(world):
    doc = make_person(first_name="Doc", is_gp=True, team=world["nina"].team, start_date=date(2022, 9, 1))
    make_contract(doc, 8, 6, unit="sessions")
    entitlement.refresh()
    body = _tab(world["c_lead"], doc)
    assert 'name="bank_holiday_2027" value="66.67"' in body and "66 h 40 min" in body
    assert "8 bank holidays × 2 sessions × 8 ÷ 8 = 16 sessions = 66 h 40 min" in body
    boxes = dict(re.findall(r'name="((?:annual|bank_holiday)_20\d\d)" value="([^"]+)"', body))
    assert boxes == {"annual_2027": "200.00", "bank_holiday_2027": "66.67", "annual_2028": "200.00", "bank_holiday_2028": "0.00"}
    r = world["c_lead"].post(f"/staff/{doc.pk}/profile/?tab=hours", {**boxes, "note": ""})       # 2028 has no bank holidays entered yet
    assert "Saved." in r.content.decode()
    row = _row(doc)
    assert (row.bank_holiday_hours, row.source) == (D("66.6667"), "worked_out")


def test_the_year_boxes_hold_the_years_first_row_not_a_dated_one(world):
    part = make_person(first_name="Part", team=world["nina"].team, start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=3)
    make_contract(part, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(part, "30", steps=RECEPTION, from_day=JUNE)
    entitlement.refresh()
    body = _tab(world["c_lead"], part)
    assert 'name="annual_2027" value="103.50"' in body                  # not June's 138
    assert 'name="days_per_week" min="1" max="7" value="3"' in body     # beside the dated row's Confirm
    dated = _row(part, from_day=JUNE)
    world["c_lead"].post(f"/staff/{part.pk}/profile/?tab=hours", {"allowance_action": "confirm", "row": dated.pk, "days_per_week": "4"})
    dated.refresh_from_db()
    assert (dated.days_per_week, dated.needs_checking) == (4, False)


# --- the statement ---------------------------------------------------------------------------

def test_the_statement_gains_the_working_for_managers_only(world):
    nina = world["nina"]
    body = _tab(world["c_lead"], nina, year="2027-01-01")
    assert "Full-year figures, from the contract in Practice HR" in body
    assert f"From 1 Jan 2027, annual leave: {WORKING}" in body
    mine = world["c_nina"].get("/time-off/mine/").content.decode()
    assert "Annual leave allowance" in mine and "Full-year figures" not in mine and WORKING not in mine


def test_add_hours_change_is_not_offered_for_a_year_that_is_worked_out(world):
    nina = world["nina"]
    body = _tab(world["c_lead"], nina)
    assert "Hours changes come from Practice HR." in body and "Add hours change" not in body and "Adjust…" in body
    plain = make_person(first_name="Plain", team=nina.team)
    make_allowance(plain, Y27, 138, 48)
    body = _tab(world["c_lead"], plain)
    assert f'href="/staff/{plain.pk}/leave/hours-change/"' in body and "Hours changes come from Practice HR." not in body
    assert "Hours changes come from Practice HR." not in _tab(world["c_nina"], nina)      # staff never had the link


def test_add_hours_change_is_still_refused_by_its_dialog(world):
    nina = world["nina"]
    r = world["c_lead"].post(f"/staff/{nina.pk}/leave/hours-change/", {
        "from_day": "2027-06-01", "weekly_hours": "30", "days_per_week": "4", "annual_hours": "138", "bank_holiday_hours": "48", "note": "x"})
    assert r.status_code == 200 and "Enter the new contract in Practice HR" in r.content.decode()


# --- Leave settings ------------------------------------------------------------------------------

def test_an_all_teams_manager_turns_checking_off_and_it_is_audited(world):
    c = world["c_boss"]
    body = c.get("/settings/leave/").content.decode()
    assert '<select name="allowances_need_checking"' in body and '<option value="yes" selected>' in body
    r = c.post("/settings/leave/", {"reminder_working_days": "3", "allowances_need_checking": "no"})
    assert "Saved." in r.content.decode() and '<option value="no" selected>' in r.content.decode()
    assert LeaveSetting.objects.get().allowances_need_checking is False
    entry = AuditEntry.objects.get(model="leave.leavesetting", field="allowances_need_checking")
    assert (entry.before, entry.after, entry.actor) == ("on", "off", world["boss"].user)
    c.post("/settings/leave/", {"reminder_working_days": "5"})          # a post without the choice leaves it alone
    setting = LeaveSetting.objects.get()
    assert (setting.reminder_working_days, setting.allowances_need_checking) == (5, False)


def test_other_managers_see_the_setting_and_cannot_change_it(world):
    c = world["c_lead"]
    body = c.get("/settings/leave/").content.decode()
    assert 'name="allowances_need_checking"' not in body and "Wait for a manager to check them" in body
    assert "An all-teams manager changes this." in body
    r = c.post("/settings/leave/", {"reminder_working_days": "4", "allowances_need_checking": "no"})
    assert "Saved." in r.content.decode()
    setting = LeaveSetting.objects.get()
    assert (setting.reminder_working_days, setting.allowances_need_checking) == (4, True)
    with pytest.raises(PermissionDenied):
        leave_settings.update(world["lead"].user, 4, allowances_need_checking=False)
    assert leave_settings.update(world["lead"].user, 4, allowances_need_checking=True).allowances_need_checking      # no change: allowed
