"""Allowance spec 2026-11-18, section 7: refresh keeps the Allowance rows in
step with the contracts after each read of Practice HR. The table in 7.2 is
tested row by row."""

import json
import logging
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from django.utils import timezone

from leave.models import BankHoliday
from leave.services import entitlement
from leave.services import settings as leave_settings
from people.models import Allowance, AuditEntry, Person
from people.services import hr_sync, profiles
from tests.factories import make_allowance, make_bank_holiday, make_contract, make_person

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2026, 11, 2))]
Y26, Y27, Y28 = date(2026, 1, 1), date(2027, 1, 1), date(2028, 1, 1)
JUNE = date(2027, 6, 1)
RECEPTION = [(1, 23)]
SAMPLE = Path(__file__).parent / "data" / "people_feed.json"


def _sam(weekly="37.5", **kw):
    """Full time since June 2025: 23 days in 2027, so 172 h 30 min and 60 h."""
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D(weekly), days_per_week=5, **kw)
    make_contract(sam, weekly, steps=RECEPTION)
    return sam


def _rows(person, year=Y27):
    return list(Allowance.objects.filter(person=person, leave_year=year).order_by("from_day"))


def _figures(person, year=Y27):
    return [(r.from_day, r.annual_hours, r.bank_holiday_hours, r.source, r.checked_at is not None) for r in _rows(person, year)]


def _audit(row):
    return {a.field: (a.before, a.after) for a in AuditEntry.objects.filter(model="people.allowance", object_id=row.pk)}


def _check(row, user):
    """As a manager's Confirm leaves a row."""
    profiles.write_allowance(user, row, {"checked_at": timezone.now(), "checked_by": user}, note="allowance checked")


# --- 7.2, row by row ---------------------------------------------------------------------------

def test_no_row_creates_one_worked_out_and_waiting():
    sam = _sam()
    result = entitlement.refresh()
    assert (result.written, result.failed) == (1, 0)
    assert _figures(sam) == [(Y27, D("172.5"), D("60"), "worked_out", False)]
    (row,) = _rows(sam)
    assert row.needs_checking and row.checked_by is None and row.weekly_hours is None
    assert _audit(row) == {"annual_hours": ("", "172.50"), "bank_holiday_hours": ("", "60.00"), "source": ("", "worked_out")}
    entry = AuditEntry.objects.filter(model="people.allowance", object_id=row.pk).first()
    assert entry.actor is None and entry.actor_email == "practice-hr"
    assert entry.note == ("from Practice HR: 23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min; "
                          "8 bank holidays × 37.5 h ÷ 5 = 60 h")
    assert not Allowance.objects.filter(leave_year=Y26).exists()          # 2026 ended before launch: never worked out


def test_a_worked_out_row_with_the_same_figures_is_left_alone(all_teams_user):
    sam = _sam()
    entitlement.refresh()
    _check(_rows(sam)[0], all_teams_user)
    audited = AuditEntry.objects.count()
    assert entitlement.refresh().written == 0
    (row,) = _rows(sam)
    assert row.checked_by == all_teams_user and AuditEntry.objects.count() == audited


def test_a_worked_out_row_with_different_figures_is_rewritten_and_waits_again(all_teams_user):
    sam = _sam()
    entitlement.refresh()
    _check(_rows(sam)[0], all_teams_user)
    make_bank_holiday(date(2027, 6, 14), "An extra bank holiday")           # nine in the year now
    AuditEntry.objects.all().delete()
    assert entitlement.refresh().written == 1
    (row,) = _rows(sam)
    assert (row.bank_holiday_hours, row.source, row.checked_at, row.checked_by) == (D("67.5"), "worked_out", None, None)
    assert _audit(row) == {"bank_holiday_hours": ("60.00", "67.50"), "checked": (f"by {all_teams_user.email}", "")}


def test_a_copied_row_with_different_figures_becomes_worked_out():
    sam = _sam()
    make_allowance(sam, Y27, 150, 60, source="copied")
    entitlement.refresh()
    assert _figures(sam) == [(Y27, D("172.5"), D("60"), "worked_out", False)]


def test_a_copied_row_with_the_same_figures_becomes_worked_out_and_its_check_is_left_as_it_is(all_teams_user):
    waiting = _sam(first_name="Waiting")
    row = make_allowance(waiting, Y27, D("172.5"), 60, source="copied")
    checked = _sam(first_name="Checked")
    _check(make_allowance(checked, Y27, D("172.5"), 60, source="copied"), all_teams_user)
    AuditEntry.objects.all().delete()
    assert entitlement.refresh().written == 2
    assert _figures(waiting) == [(Y27, D("172.5"), D("60"), "worked_out", False)]         # still "not yet checked"
    assert _audit(row) == {"source": ("copied", "worked_out")}
    (kept,) = _rows(checked)
    assert (kept.source, kept.checked_by) == ("worked_out", all_teams_user) and not kept.needs_checking
    assert entitlement.refresh().written == 0


def test_a_typed_row_with_the_same_figures_follows_the_contract_from_now_on():
    sam = _sam()
    make_allowance(sam, Y27, D("172.50"), D("60.00"))
    assert entitlement.refresh().written == 1
    (row,) = _rows(sam)
    assert (row.source, row.checked_by) == ("worked_out", None) and row.checked_at is not None and not row.needs_checking
    assert _audit(row) == {"source": ("typed", "worked_out"), "checked": ("", "automatically")}


def test_a_typed_row_with_different_figures_is_never_changed():
    sam = _sam()
    make_allowance(sam, Y27, 180, 60)
    assert entitlement.refresh().written == 0
    assert _figures(sam) == [(Y27, D("180"), D("60"), "typed", False)]
    assert not AuditEntry.objects.filter(model="people.allowance").exists()


# --- 7.3: changes during the year ---------------------------------------------------------------

def _part_time_then_30_from_june():
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=3)
    old = make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    new = make_contract(sam, "30", steps=RECEPTION, from_day=JUNE)
    return sam, old, new


def test_a_mid_year_contract_adds_a_dated_row_with_the_hours_and_the_days_then_in_force():
    sam, _, _ = _part_time_then_30_from_june()
    assert entitlement.refresh().written == 2
    assert _figures(sam) == [(Y27, D("103.5"), D("36"), "worked_out", False), (JUNE, D("138"), D("48"), "worked_out", False)]
    dated = _rows(sam)[1]
    assert (dated.weekly_hours, dated.days_per_week, dated.hours_applied) == (D("30"), 3, True)
    assert _audit(dated) == {"annual_hours": ("", "138.00"), "bank_holiday_hours": ("", "48.00"), "weekly_hours": ("", "30.00"),
                             "days_per_week": ("", "3"), "source": ("", "worked_out"), "from_day": ("", "2027-06-01")}


def test_the_days_then_in_force_come_from_the_row_before_when_it_carries_them():
    sam, _, new = _part_time_then_30_from_june()
    new.to_day = date(2027, 8, 31)
    new.save()
    make_contract(sam, "37.5", steps=RECEPTION, from_day=date(2027, 9, 1))
    entitlement.refresh()
    june = _rows(sam)[1]
    june.days_per_week = 4
    june.save()
    Allowance.objects.filter(person=sam, from_day=date(2027, 9, 1)).delete()
    entitlement.refresh()
    assert [r.days_per_week for r in _rows(sam)] == [None, 4, 4]


def test_a_typed_dated_row_on_the_same_day_is_kept_and_a_typed_one_that_matches_is_adopted():
    sam, _, _ = _part_time_then_30_from_june()
    make_allowance(sam, Y27, D("103.5"), 36)
    make_allowance(sam, Y27, 140, 48, from_day=JUNE, weekly_hours=D("30"), days_per_week=4)
    entitlement.refresh()
    assert _figures(sam) == [(Y27, D("103.5"), D("36"), "worked_out", True), (JUNE, D("140"), D("48"), "typed", False)]


def test_a_corrected_contract_date_moves_the_dated_row(all_teams_user):
    sam, old, new = _part_time_then_30_from_june()
    entitlement.refresh()
    old.to_day, new.from_day = date(2027, 6, 30), date(2027, 7, 1)        # Practice HR corrects the date
    old.save()
    new.save()
    AuditEntry.objects.all().delete()
    assert entitlement.refresh().written == 2
    assert [r.from_day for r in _rows(sam)] == [Y27, date(2027, 7, 1)]
    gone = AuditEntry.objects.get(model="people.person", object_id=sam.pk)
    assert (gone.field, gone.before, gone.after) == ("allowance from 1 Jun 2027", "138.00 h and 48.00 h", "")
    assert gone.note == "from Practice HR: the contracts no longer change on this day"


def test_a_typed_dated_row_is_never_deleted():
    sam = _sam()
    make_allowance(sam, Y27, D("172.5"), 60)
    make_allowance(sam, Y27, 138, 48, from_day=JUNE, weekly_hours=D("30"), days_per_week=4)
    entitlement.refresh()
    assert [(r.from_day, r.source) for r in _rows(sam)] == [(Y27, "worked_out"), (JUNE, "typed")]


def test_a_change_to_the_terms_alters_every_period_and_they_wait_again(all_teams_user):
    sam, old, new = _part_time_then_30_from_june()
    entitlement.refresh()
    for row in _rows(sam):
        _check(row, all_teams_user)
    for contract in (old, new):
        contract.leave_base, contract.leave_steps = D("25"), []
        contract.save()
    assert entitlement.refresh().written == 2
    assert _figures(sam) == [(Y27, D("112.5"), D("36"), "worked_out", False), (JUNE, D("150"), D("48"), "worked_out", False)]


# --- 7.6: the setting ----------------------------------------------------------------------------

def test_with_the_setting_off_rows_are_written_already_checked_and_waiting_ones_are_left():
    waiting = _sam(first_name="Waiting")
    entitlement.refresh()
    setting = leave_settings.get()
    setting.allowances_need_checking = False
    setting.save()
    new = _sam(first_name="New")
    make_bank_holiday(date(2027, 6, 14), "An extra bank holiday")           # changes Waiting's row as well
    entitlement.refresh()
    (row,) = _rows(new)
    assert row.checked_at is not None and row.checked_by is None and not row.needs_checking
    assert _audit(row)["checked"] == ("", "automatically")
    (changed,) = _rows(waiting)
    assert changed.bank_holiday_hours == D("67.5") and not changed.needs_checking

    untouched = _sam(first_name="Untouched")
    make_allowance(untouched, Y27, D("172.5"), D("67.5"), source="worked_out")     # waiting since before, and still right
    entitlement.refresh()
    assert _rows(untouched)[0].needs_checking


# --- 7.1 and 7.4: which years ---------------------------------------------------------------------

def test_before_1_january_only_next_year_is_worked_out_and_from_1_january_both(today):
    sam = _sam()
    entitlement.refresh()
    assert not _rows(sam, Y26) and len(_rows(sam, Y27)) == 1 and not _rows(sam, Y28)
    for day in BankHoliday.objects.filter(day__year=2027):
        make_bank_holiday(day.day.replace(year=2028), day.name)
    today(date(2027, 1, 1))
    entitlement.refresh()
    assert _figures(sam, Y27) == [(Y27, D("172.5"), D("60"), "worked_out", False)]
    assert _figures(sam, Y28) == [(Y28, D("172.5"), D("60"), "worked_out", False)]      # next year's exists from the first day of this one


def test_a_step_is_reached_for_the_next_leave_year(today):
    sam = make_person(start_date=date(2026, 6, 1), weekly_hours=D("37.5"), days_per_week=5)
    make_contract(sam, "37.5", steps=RECEPTION)
    today(date(2027, 1, 1))
    entitlement.refresh()
    assert _rows(sam, Y27)[0].annual_hours == D("165") and _rows(sam, Y28)[0].annual_hours == D("172.5")


def test_a_finished_year_is_never_written(today):
    sam, old, new = _part_time_then_30_from_june()
    today(date(2027, 3, 1))
    entitlement.refresh()
    before = _figures(sam, Y27)
    today(date(2028, 1, 1))
    old.to_day, new.from_day = date(2027, 6, 30), date(2027, 7, 1)        # a change dated inside the year that has ended
    old.save()
    new.save()
    entitlement.refresh()
    assert _figures(sam, Y27) == before


def test_a_year_the_person_is_not_employed_in_gets_nothing():
    sam = _sam(end_date=date(2026, 12, 31))
    assert entitlement.refresh().written == 0 and not Allowance.objects.filter(person=sam).exists()


def test_someone_who_has_left_is_not_refreshed():
    sam = _sam(end_date=date(2026, 10, 14))
    assert entitlement.refresh().written == 0 and not Allowance.objects.filter(person=sam).exists()


def test_a_starter_is_worked_out_before_day_one():
    sam = make_person(start_date=date(2027, 3, 1))
    make_contract(sam, "30", steps=RECEPTION)
    entitlement.refresh()
    assert _figures(sam) == [(Y27, D("132"), D("48"), "worked_out", False)]


# --- 7.5: a year that is not worked out -----------------------------------------------------------

def _trainee():
    doc = make_person(first_name="Riley", is_gp=True, start_date=date(2026, 8, 5))
    make_contract(doc, 8, None, unit="sessions", type_name="GP trainee")
    return doc


def test_next_year_is_copied_from_this_years_last_row_and_waits(today):
    doc = _trainee()
    assert entitlement.refresh().written == 0                             # nothing typed yet: nothing to copy
    today(date(2027, 2, 1))
    make_allowance(doc, Y27, 250, D("66.6667"))
    make_allowance(doc, Y27, 200, 50, from_day=date(2027, 8, 4))
    assert entitlement.refresh().written == 1
    assert _figures(doc, Y28) == [(Y28, D("200"), D("50"), "copied", False)]
    (row,) = _rows(doc, Y28)
    assert row.needs_checking
    assert AuditEntry.objects.filter(model="people.allowance", object_id=row.pk).first().note == "from Practice HR: copied from 2027"
    assert entitlement.refresh().written == 0                             # once only
    assert _figures(doc, Y27) == [(Y27, D("250"), D("66.6667"), "typed", False), (date(2027, 8, 4), D("200"), D("50"), "typed", False)]


def test_nothing_is_copied_until_practice_hr_has_sent_someone_a_contract(today):
    today(date(2027, 2, 1))
    plain = make_person(first_name="Plain")
    make_allowance(plain, Y27, 138, 48)
    assert entitlement.refresh().written == 0 and not _rows(plain, Y28)          # exactly as before this release


def test_nothing_is_copied_over_a_year_that_has_rows_or_for_a_leaver(today):
    today(date(2027, 2, 1))
    doc = _trainee()
    make_allowance(doc, Y27, 250, 60)
    make_allowance(doc, Y28, 260, 60)
    plain = make_person(first_name="Plain")                               # no contract in Practice HR yet: copied too (7.5)
    make_allowance(plain, Y27, 138, 48)
    leaver = make_person(first_name="Leaver", end_date=date(2027, 6, 30))
    make_allowance(leaver, Y27, 138, 48)
    entitlement.refresh()
    assert _figures(doc, Y28) == [(Y28, D("260"), D("60"), "typed", False)]
    assert _figures(plain, Y28) == [(Y28, D("138"), D("48"), "copied", False)]
    assert not _rows(leaver, Y28)


def test_bank_staff_are_typed_and_copied_forward_like_anyone_whose_year_is_not_worked_out(today):
    today(date(2027, 2, 1))
    bank = make_person(first_name="Bank", start_date=date(2025, 6, 1))
    make_contract(bank, 0, steps=RECEPTION)                               # a weekly amount of 0
    make_allowance(bank, Y27, 40, 0)
    assert entitlement.refresh().written == 1
    assert _figures(bank, Y27) == [(Y27, D("40"), D("0"), "typed", False)]
    assert _figures(bank, Y28) == [(Y28, D("40"), D("0"), "copied", False)]


def test_a_worked_out_year_is_copied_into_a_next_year_with_no_contract(today):
    today(date(2027, 2, 1))
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "37.5", steps=RECEPTION, to_day=date(2027, 12, 31))           # nothing after it
    entitlement.refresh()
    assert _figures(sam, Y28) == [(Y28, D("172.5"), D("60"), "copied", False)]


# --- failures, and the sync -----------------------------------------------------------------------

def test_one_persons_failure_is_logged_by_id_and_the_rest_are_done(monkeypatch, caplog):
    bad, good = _sam(first_name="Bad"), _sam(first_name="Good")
    real = entitlement._refresh_person

    def flaky(person, *args):
        if person.pk == bad.pk:
            Allowance.objects.create(person=person, leave_year=Y27, annual_hours=1, bank_holiday_hours=1)
            raise RuntimeError("boom")
        return real(person, *args)
    monkeypatch.setattr(entitlement, "_refresh_person", flaky)
    with caplog.at_level(logging.INFO, logger="leave.entitlement"):
        result = entitlement.refresh()
    assert (result.written, result.failed) == (1, 1)
    assert not _rows(bad) and len(_rows(good)) == 1                       # the failed person's half-written row is rolled back
    assert f"allowances: person {bad.pk}" in caplog.text
    assert "Bad" not in caplog.text and "172" not in caplog.text


class Feed:
    def people(self):
        return json.loads(SAMPLE.read_text())["people"]


def test_the_sync_works_the_sample_feed_out():
    run = hr_sync.sync(Feed())
    assert run.ok and run.message == ""
    by_id = {p.hr_employee_id: p for p in Person.objects.all()}
    assert _figures(by_id[101]) == [(Y27, D("138"), D("48"), "worked_out", False)]            # 23 days at 30 h
    assert _figures(by_id[102]) == [(Y27, D("200"), D("50"), "worked_out", False)]            # 8 weeks at 6 sessions
    assert _figures(by_id[103]) == [(Y27, D("225"), D("60"), "worked_out", False)]            # 30 days after 10 years
    assert not _rows(by_id[104]) and not _rows(by_id[105])                                    # no terms; no contract
    assert hr_sync.sync(Feed()).ok and Allowance.objects.count() == 3


def test_a_failed_refresh_is_on_the_runs_message_and_the_people_stand(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")
    monkeypatch.setattr(entitlement, "refresh", boom)
    run = hr_sync.sync(Feed())
    run.refresh_from_db()
    assert run.ok and run.message == "allowances failed; see the journal" and Person.objects.count() == 5


def test_one_persons_failure_is_on_the_runs_message_too(monkeypatch):
    monkeypatch.setattr(entitlement, "refresh", lambda today=None: entitlement.Refreshed(written=2, failed=1))
    run = hr_sync.sync(Feed())
    run.refresh_from_db()
    assert run.ok and run.message == "allowances failed; see the journal"


def test_refresh_runs_before_the_due_hours_changes(monkeypatch):
    order = []
    monkeypatch.setattr(entitlement, "refresh", lambda today=None: order.append("allowances") or entitlement.Refreshed(0, 0))
    monkeypatch.setattr(profiles, "apply_due_hours_changes", lambda today=None: order.append("hours"))
    hr_sync.sync(Feed())
    assert order == ["allowances", "hours"]
