"""Allowance spec 2026-11-18, section 7.7: what a manager does to an
allowance row. Whoever manages the person may; nobody manages themselves."""

from datetime import date
from decimal import Decimal as D

import pytest
from django.core.exceptions import PermissionDenied

from leave.services import entitlement
from people.models import Allowance, AuditEntry
from people.services import profiles
from tests.factories import make_allowance, make_contract, make_person, make_team, make_team_manager, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 2, 1))]
Y27, Y28 = date(2027, 1, 1), date(2028, 1, 1)
JUNE = date(2027, 6, 1)
RECEPTION = [(1, 23)]


@pytest.fixture
def boss(all_teams_user):
    return all_teams_user


def _sam(weekly="37.5", **kw):
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D(weekly), days_per_week=5, **kw)
    make_contract(sam, weekly, steps=RECEPTION)
    return sam


def _worked_out(person, year=Y27, from_day=None):
    entitlement.refresh()
    return Allowance.objects.get(person=person, leave_year=year, from_day=from_day or year)


def _audit(row, note):
    return {a.field: (a.before, a.after) for a in AuditEntry.objects.filter(model="people.allowance", object_id=row.pk, note=note)}


# --- confirm ---------------------------------------------------------------------------------

def test_confirm_sets_who_and_when_and_is_audited(boss):
    row = _worked_out(_sam())
    entries = profiles.confirm_allowance(boss, row)
    row.refresh_from_db()
    assert row.checked_by == boss and row.checked_at is not None and not row.needs_checking and row.source == "worked_out"
    assert [(e.field, e.before, e.after, e.note, e.actor) for e in entries] == [("checked", "", f"by {boss.email}", "allowance checked", boss)]
    assert profiles.confirm_allowance(boss, row) == []                  # already checked: nothing to do


def test_only_someone_who_manages_the_person_confirms_and_never_themselves(boss):
    nursing = make_team("Nursing")
    lead = make_person(first_name="Lead", team=nursing, start_date=date(2025, 6, 1))
    make_contract(lead, "30", steps=RECEPTION)
    make_team_manager(lead, nursing)
    lead_user = make_user_for(lead)
    nurse = _sam(first_name="Nina", team=nursing)
    rec = _sam(first_name="Rec")
    entitlement.refresh()
    rows = {r.person_id: r for r in Allowance.objects.filter(leave_year=Y27)}
    profiles.confirm_allowance(lead_user, rows[nurse.pk])
    for person in (rec, lead):                                          # another team's; her own
        with pytest.raises(PermissionDenied):
            profiles.confirm_allowance(lead_user, rows[person.pk])
    for action in (profiles.use_worked_out, lambda user, row: profiles.change_allowance(user, row, 1, 1, "x")):
        with pytest.raises(PermissionDenied):
            action(lead_user, rows[lead.pk])
    profiles.confirm_allowance(boss, rows[lead.pk])                     # another manager checks hers


def _dated(days=3):
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=days)
    make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(sam, "30", steps=RECEPTION, from_day=JUNE)
    return sam, _worked_out(sam, from_day=JUNE)


def test_days_per_week_corrected_on_a_future_dated_row_wait_for_the_day(boss):
    sam, row = _dated()
    entries = profiles.confirm_allowance(boss, row, days_per_week=4)
    row.refresh_from_db()
    sam.refresh_from_db()
    assert (row.days_per_week, row.hours_applied, sam.days_per_week) == (4, False, 3)
    assert {(e.field, e.before, e.after) for e in entries} == {("checked", "", f"by {boss.email}"), ("days_per_week", "3", "4")}
    assert profiles.apply_due_hours_changes(today=JUNE) == 1            # the sync copies them on the day…
    sam.refresh_from_db()
    assert (sam.days_per_week, sam.weekly_hours) == (4, D("22.5"))      # …and never the weekly hours, which are Practice HR's


def test_days_per_week_corrected_on_a_row_already_in_force_go_on_the_person_now(boss, today):
    sam, row = _dated()
    today(date(2027, 7, 1))
    profiles.confirm_allowance(boss, row, days_per_week=4)
    row.refresh_from_db()
    sam.refresh_from_db()
    assert (row.days_per_week, row.hours_applied, sam.days_per_week) == (4, True, 4)
    assert AuditEntry.objects.filter(model="people.person", object_id=sam.pk, field="days_per_week", note="days per week corrected").exists()


def test_days_are_not_taken_for_a_years_first_row_or_when_unchanged(boss):
    sam, dated = _dated()
    first = Allowance.objects.get(person=sam, leave_year=Y27, from_day=Y27)
    profiles.confirm_allowance(boss, first, days_per_week=4)
    first.refresh_from_db()
    assert first.days_per_week is None
    entries = profiles.confirm_allowance(boss, dated, days_per_week=3)
    assert [e.field for e in entries] == ["checked"]


# --- confirm all shown ----------------------------------------------------------------------

def test_confirm_all_skips_a_row_whose_figures_changed_and_says_how_many(boss):
    a, b, c = _sam(first_name="A"), _sam(first_name="B", weekly="30"), _sam(first_name="C")
    entitlement.refresh()
    rows = {r.person_id: r for r in Allowance.objects.filter(leave_year=Y27)}
    items = [(r.pk, r.annual_hours, r.bank_holiday_hours, None) for r in rows.values()]
    Allowance.objects.filter(pk=rows[b.pk].pk).update(annual_hours=D("150"))       # changed since the page was drawn
    profiles.confirm_allowance(boss, rows[c.pk])                                   # someone else got there first
    assert profiles.confirm_allowances(boss, items + [(999999, D("1"), D("1"), None)]) == (1, 3)
    assert not Allowance.objects.get(pk=rows[a.pk].pk).needs_checking
    assert Allowance.objects.get(pk=rows[b.pk].pk).needs_checking


def test_confirm_all_skips_a_row_the_actor_does_not_manage():
    nursing = make_team("Nursing")
    lead = make_person(first_name="Lead", team=nursing)
    make_team_manager(lead, nursing)
    row = _worked_out(_sam(first_name="Rec"))
    assert profiles.confirm_allowances(make_user_for(lead), [(row.pk, row.annual_hours, row.bank_holiday_hours, None)]) == (0, 1)


# --- change ----------------------------------------------------------------------------------

def test_change_types_both_figures_with_a_reason_and_the_row_becomes_typed(boss):
    row = _worked_out(_sam())
    profiles.confirm_allowance(boss, row)
    with pytest.raises(ValueError, match="reason"):
        profiles.change_allowance(boss, row, D("180"), D("60"), " ")
    entries = profiles.change_allowance(boss, row, D("180"), D("60"), "contract says 24 days")
    row.refresh_from_db()
    assert (row.annual_hours, row.bank_holiday_hours, row.source, row.checked_at, row.checked_by) == (D("180"), D("60"), "typed", None, None)
    assert {(e.field, e.before, e.after) for e in entries} == {
        ("annual_hours", "172.50", "180.00"), ("source", "worked_out", "typed"), ("checked", f"by {boss.email}", "")}
    assert {e.note for e in entries} == {"contract says 24 days"}
    assert entitlement.refresh().written == 0                           # a typed row is kept
    row.refresh_from_db()
    assert row.annual_hours == D("180")


def test_change_works_on_a_dated_row(boss):
    _, row = _dated()
    profiles.change_allowance(boss, row, D("140"), D("48"), "agreed with the practice manager")
    row.refresh_from_db()
    assert (row.annual_hours, row.source, row.from_day) == (D("140"), "typed", JUNE)


def test_days_per_week_change_at_any_time_and_leave_a_worked_out_row_worked_out(boss):
    sam, row = _dated()
    profiles.confirm_allowance(boss, row)                               # checked weeks ago; the days turn out wrong
    with pytest.raises(ValueError, match="reason"):
        profiles.change_allowance(boss, row, row.annual_hours, row.bank_holiday_hours, "", days_per_week=4)
    entries = profiles.change_allowance(boss, row, D("138.00"), D("48.00"), "works four days from June", days_per_week=4)
    row.refresh_from_db()
    assert (row.days_per_week, row.source, row.checked_by, row.annual_hours) == (4, "worked_out", boss, D("138"))
    assert [(e.field, e.before, e.after, e.note) for e in entries] == [("days_per_week", "3", "4", "works four days from June")]
    assert entitlement.refresh().written == 0                           # still what the contract gives
    assert profiles.change_allowance(boss, row, D("138"), D("48"), "again", days_per_week=4) == []


def test_days_per_week_and_figures_changed_together_make_the_row_typed(boss):
    _, row = _dated()
    entries = profiles.change_allowance(boss, row, D("140"), D("48"), "agreed", days_per_week=4)
    row.refresh_from_db()
    assert (row.annual_hours, row.days_per_week, row.source) == (D("140"), 4, "typed")
    assert {e.field for e in entries} == {"annual_hours", "source", "days_per_week"}


def test_days_per_week_are_not_taken_by_change_for_a_years_first_row(boss):
    sam, _ = _dated()
    first = Allowance.objects.get(person=sam, leave_year=Y27, from_day=Y27)
    assert not profiles.takes_days(first)
    assert profiles.change_allowance(boss, first, first.annual_hours, first.bank_holiday_hours, "x", days_per_week=4) == []
    first.refresh_from_db()
    assert first.days_per_week is None


def test_the_same_figures_to_two_places_are_no_change(boss):
    doc = make_person(is_gp=True, start_date=date(2022, 9, 1))
    make_contract(doc, 8, 6, unit="sessions")
    row = _worked_out(doc)                                              # 200 h and 66.6667 h
    assert profiles.change_allowance(boss, row, D("200.00"), D("66.67"), "") == []
    assert profiles.set_allowance(boss, doc, Y27, D("200"), D("66.67"), note="") == []      # the profile's boxes, saved untouched
    row.refresh_from_db()
    assert (row.bank_holiday_hours, row.source) == (D("66.6667"), "worked_out")


def test_the_profiles_boxes_make_a_worked_out_row_typed(boss):
    sam = _sam()
    row = _worked_out(sam)
    profiles.set_allowance(boss, sam, Y27, D("180"), D("60"), note="contract says 24 days")
    row.refresh_from_db()
    assert (row.annual_hours, row.source) == (D("180"), "typed")


# --- use the worked-out figure ------------------------------------------------------------------

def test_use_the_worked_out_figure_on_a_typed_row_that_differs(boss):
    sam = _sam()
    row = make_allowance(sam, Y27, 180, 60)
    entries = profiles.use_worked_out(boss, row)
    row.refresh_from_db()
    assert (row.annual_hours, row.bank_holiday_hours, row.source, row.checked_by) == (D("172.5"), D("60"), "worked_out", boss)
    assert not row.needs_checking
    assert {(e.field, e.before, e.after) for e in entries} == {
        ("annual_hours", "180.00", "172.50"), ("source", "typed", "worked_out"), ("checked", "", f"by {boss.email}")}
    assert entries[0].note == ("worked-out figure used: 23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min; "
                               "8 bank holidays × 37.5 h ÷ 5 = 60 h")


def test_use_the_worked_out_figure_removes_a_typed_dated_row_the_contracts_have_no_change_for(boss):
    sam = _sam()
    make_allowance(sam, Y27, D("172.5"), 60)
    row = make_allowance(sam, Y27, 138, 48, from_day=JUNE, weekly_hours=D("30"), days_per_week=4)
    profiles.use_worked_out(boss, row)
    assert not Allowance.objects.filter(pk=row.pk).exists()
    gone = AuditEntry.objects.get(model="people.person", object_id=sam.pk, field="allowance from 1 Jun 2027")
    assert (gone.before, gone.after, gone.note, gone.actor) == ("138.00 h and 48.00 h", "", "the contracts have no change on this day", boss)


def test_use_the_worked_out_figure_is_refused_where_there_is_none(boss, today):
    typed = make_person(first_name="Typed")
    row = make_allowance(typed, Y27, 138, 48)
    with pytest.raises(ValueError, match="not worked out"):
        profiles.use_worked_out(boss, row)
    sam = _sam()
    old = make_allowance(sam, Y27, 180, 60)
    today(date(2028, 1, 4))
    with pytest.raises(ValueError, match="has ended"):
        profiles.use_worked_out(boss, old)


def test_the_years_first_row_is_never_removed(boss):
    row = make_allowance(_sam(), Y27, 180, 60)
    with pytest.raises(ValueError):
        profiles.remove_allowance(boss, row, "x")


# --- add hours change ---------------------------------------------------------------------------

def test_add_hours_change_is_refused_for_a_year_that_is_worked_out(boss):
    sam = _sam()
    entitlement.refresh()
    with pytest.raises(ValueError) as e:
        profiles.add_hours_change(boss, sam, JUNE, D("30"), 4, 138, 48, "going part time")
    assert str(e.value) == "Enter the new contract in Practice HR"


def test_add_hours_change_still_works_where_allowances_are_typed(boss):
    doc = make_person(is_gp=True, start_date=date(2026, 8, 5))
    make_contract(doc, 8, None, unit="sessions", type_name="GP trainee")           # no terms: typed
    make_allowance(doc, Y27, 250, 60)
    row = profiles.add_hours_change(boss, doc, JUNE, None, 5, 200, 50, "six sessions from June")
    assert (row.source, row.from_day) == ("typed", JUNE)
    plain = make_person(weekly_hours=D("37.5"), days_per_week=5)                   # no copied contract: exactly as before
    make_allowance(plain, Y27, D("172.5"), 60)
    assert profiles.add_hours_change(boss, plain, JUNE, D("30"), 4, 138, 48, "part time").weekly_hours == D("30")


# --- the final review's fixes -----------------------------------------------------------------------

def test_change_refuses_new_figures_for_a_leave_year_that_has_ended(boss, today):
    part = make_person(first_name="Part", start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=3)
    make_contract(part, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(part, "30", steps=RECEPTION, from_day=JUNE)
    dated = _worked_out(part, from_day=JUNE)
    first = Allowance.objects.get(person=part, leave_year=Y27, from_day=Y27)
    today(date(2028, 1, 4))
    with pytest.raises(ValueError, match="^That leave year has ended; correct it with an adjustment$"):
        profiles.change_allowance(boss, first, D("150"), D("36"), "a late correction")
    first.refresh_from_db()
    assert (first.annual_hours, first.source) == (D("103.5"), "worked_out")
    profiles.change_allowance(boss, dated, dated.annual_hours, dated.bank_holiday_hours, "works four days", days_per_week=4)
    dated.refresh_from_db()
    assert (dated.days_per_week, dated.source, dated.annual_hours) == (4, "worked_out", D("138"))      # the days alone still change
    profiles.confirm_allowance(boss, first)                                                        # and Confirm still works
    first.refresh_from_db()
    assert not first.needs_checking


def test_a_worked_out_row_whose_contract_has_gone_can_be_taken_over_as_typed(boss):
    sam = _sam()
    row = _worked_out(sam)
    sam.contracts.all().delete()
    with pytest.raises(ValueError, match="reason"):
        profiles.change_allowance(boss, row, D("172.50"), D("60.00"), "")
    entries = profiles.change_allowance(boss, row, D("172.50"), D("60.00"), "contract being re-entered in Practice HR")
    row.refresh_from_db()
    assert (row.annual_hours, row.source, row.checked_at) == (D("172.5"), "typed", None)
    assert {(e.field, e.before, e.after) for e in entries} == {("source", "worked_out", "typed")}


def test_the_same_figures_on_a_worked_out_year_are_still_no_change(boss):
    sam = _sam()
    row = _worked_out(sam)
    assert profiles.change_allowance(boss, row, D("172.50"), D("60.00"), "nothing new") == []
    row.refresh_from_db()
    assert row.source == "worked_out"
