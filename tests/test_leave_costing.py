"""LEAVE-05 to 09, 16 to 18, 20, 23: what a day costs and which account it
comes from; the statement that explains a balance."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest

from leave.models import Adjustment, BookingDay
from leave.services import balances, costing, hours
from tests.factories import (make_allowance, make_bank_holiday, make_booking, make_entry, make_gp_session, make_person,
                             make_type)

pytestmark = pytest.mark.django_db
MON = date(2027, 3, 1)            # a Monday
Y27 = date(2027, 1, 1)
Y26 = date(2026, 1, 1)


def _week(person, pattern):
    """pattern: {weekday: (start, finish, break_minutes)} for the week of MON."""
    for wd, (s, f, b) in pattern.items():
        make_entry(person, date(2027, 3, 1 + wd), start=s, finish=f, break_minutes=b)


def test_lv_01_a_full_time_day_costs_its_scheduled_hours():
    sam = make_person()
    make_entry(sam, MON, start=time(9, 0), finish=time(17, 0), break_minutes=30)
    assert costing.rota_seconds(sam, MON) == 7 * 3600 + 30 * 60
    c = costing.cost(sam, make_type("Holiday"), MON, "whole")
    assert (c.seconds, c.source, c.account, c.placeholder) == (27000, "rota", "annual", False)


def test_lv_03_a_day_with_no_shift_in_a_rota_week_costs_nothing():
    sam = make_person()
    _week(sam, {0: (time(9), time(17), 30), 1: (time(9), time(17), 30), 3: (time(9), time(13), 0)})
    wed = date(2027, 3, 3)
    assert not costing.is_placeholder(sam, wed)
    c = costing.cost(sam, make_type("Holiday"), wed, "whole")
    assert (c.seconds, c.source) == (0, "none")
    assert costing.cost(sam, make_type("Holiday"), date(2027, 3, 4), "whole").seconds == 4 * 3600


def test_lv_04a_and_04b_half_days_are_exactly_half():
    sam = make_person()
    make_entry(sam, MON, start=time(9, 0), finish=time(17, 0), break_minutes=30)
    assert costing.cost(sam, make_type("Holiday"), MON, "am").seconds == 13500            # 3 h 45 min
    tue = date(2027, 3, 2)
    make_entry(sam, tue, start=time(8, 0), finish=time(14, 15), break_minutes=60)
    c = costing.cost(sam, make_type("Holiday"), tue, "pm")
    assert c.seconds == 9450 and c.source == "half" and hours.fmt(c.seconds) == "2 h 37½ min"


def test_lv_05_times_cost_exactly_their_span():
    sam = make_person()
    make_entry(sam, MON, start=time(8, 0), finish=time(16, 15), break_minutes=60)
    c = costing.cost(sam, make_type("Holiday"), MON, "times", start=time(14, 0), finish=time(15, 30))
    assert (c.seconds, c.source) == (5400, "times")


def test_lv_19_a_gp_day_is_its_sessions_at_four_hours_ten():
    doc = make_person(is_gp=True)
    make_gp_session(doc, MON, "AM")
    make_gp_session(doc, MON, "PM")
    assert costing.cost(doc, make_type("Holiday"), MON, "whole").seconds == 30000
    assert costing.cost(doc, make_type("Holiday"), date(2027, 3, 3), "whole").seconds == 0    # a GP has no placeholder


def test_lv_22_an_empty_week_is_a_placeholder_at_the_average_day():
    sam = make_person(weekly_hours=Decimal("30"), days_per_week=5)
    make_allowance(sam, Y27, 138, 48)
    wed = date(2027, 8, 11)
    assert costing.is_placeholder(sam, wed)
    c = costing.cost(sam, make_type("Holiday"), wed, "whole")
    assert (c.seconds, c.source, c.placeholder, c.hours_known) == (6 * 3600, "placeholder", True, True)
    assert costing.cost(sam, make_type("Holiday"), wed, "am").seconds == 3 * 3600


def test_a_placeholder_uses_the_hours_in_force_on_the_day_and_flags_unknown_hours():
    sam = make_person(weekly_hours=Decimal("30"), days_per_week=5)
    make_allowance(sam, Y27, 138, 48)
    make_allowance(sam, Y27, Decimal("172.5"), 60, from_day=date(2027, 7, 1), weekly_hours=Decimal("37.5"), days_per_week=5)
    assert costing.placeholder_seconds(sam, date(2027, 8, 11)) == (27000, True)
    nobody = make_person()
    assert costing.placeholder_seconds(nobody, date(2027, 8, 11)) == (0, False)


def test_lv_23_overtime_never_counts_and_covered_entries_count_only_for_their_own_day():
    sam = make_person()
    make_entry(sam, MON, start=time(8, 0), finish=time(16, 0), break_minutes=60)
    make_entry(sam, MON, start=time(16, 0), finish=time(18, 0), overtime="paid")
    assert costing.rota_seconds(sam, MON) == 7 * 3600
    booking = make_booking(sam, MON)
    bd = BookingDay.objects.create(booking=booking, day=MON, cost_seconds=0)
    sam.entries.filter(overtime="").update(covered_by=bd)
    assert costing.rota_seconds(sam, MON) == 0
    assert costing.rota_seconds(sam, MON, include=bd) == 7 * 3600


def test_lv_12_a_bank_holiday_inside_a_holiday_booking_draws_on_the_bank_holiday_allowance():
    make_bank_holiday(date(2026, 4, 6), "Easter Monday")
    assert costing.account_for(make_type("Holiday"), date(2026, 4, 6)) == "bank_holiday"
    assert costing.account_for(make_type("Holiday"), date(2026, 4, 7)) == "annual"
    assert costing.account_for(make_type("Training"), date(2026, 4, 6)) == "none"


def test_lv_13_the_suggestion_is_the_usual_hours_on_that_weekday():
    sam = make_person()
    bh = date(2026, 5, 4)                                       # Early May bank holiday, a Monday
    for weeks in (1, 2, 3, 4):
        make_entry(sam, bh - timedelta(weeks=weeks), start=time(9), finish=time(17), break_minutes=30)
    make_entry(sam, bh - timedelta(weeks=1), start=time(17), finish=time(21))     # one 11 h 30 Monday; 7 h 30 wins three to one
    assert costing.suggestion(sam, bh) == 27000
    assert costing.suggestion(sam, date(2026, 5, 1)) == 0                        # never works a Friday


def test_the_statement_combines_bank_holiday_credit_into_annual_leave():
    sam = make_person(start_date=date(2020, 1, 6))
    make_allowance(sam, Y27, Decimal("103.5"), 36)
    s = balances.statement(sam, Y27)
    assert s.annual_allowance == hours.from_hours(Decimal("103.5")) and s.bank_holiday_allowance == 36 * 3600
    assert s.taken == {"annual": 0, "bank_holiday": 0, "toil": 0, "none": 0}
    assert s.annual_remaining == hours.from_hours(Decimal("139.5"))      # nothing taken: 103.5 + the 36 h bank holiday credit
    assert s.annual_available == s.annual_remaining and not s.missing


def test_adjustments_and_approved_days_move_the_balances_and_pending_only_moves_available():
    sam = make_person(start_date=date(2020, 1, 6))
    make_allowance(sam, Y27, Decimal("172.5"), 60)
    Adjustment.objects.create(person=sam, leave_year=Y27, account="annual", seconds=15 * 3600, reason="carried over from FindMyShift 2026")
    approved = make_booking(sam, MON, status="approved")
    BookingDay.objects.create(booking=approved, day=MON, cost_seconds=27000, source="rota", account="annual")
    bh = make_booking(sam, date(2027, 1, 1), type_name="Bank holiday", status="approved")
    BookingDay.objects.create(booking=bh, day=date(2027, 1, 1), cost_seconds=27000, source="override", account="bank_holiday")
    make_entry(sam, date(2027, 3, 2), start=time(9), finish=time(17), break_minutes=30)
    make_booking(sam, date(2027, 3, 2), status="pending")
    s = balances.statement(sam, Y27)
    assert s.adjustments["annual"] == 15 * 3600 and s.taken == {"annual": 27000, "bank_holiday": 27000, "toil": 0, "none": 0}
    assert s.bank_holiday_balance == 60 * 3600 - 27000
    assert s.annual_remaining == hours.from_hours(Decimal("172.5")) + 15 * 3600 - 27000 + (60 * 3600 - 27000)
    assert s.pending == {"annual": 27000, "bank_holiday": 0, "toil": 0, "none": 0}
    assert s.annual_available == s.annual_remaining - 27000
    assert balances.available(sam, Y27, "none") is None


# Dated in 2026 so the earned shift is in the past whenever the suite runs.
def test_lv_16_toil_is_earned_from_marked_shifts_up_to_today_and_spent_by_toil_bookings():
    sam = make_person(start_date=date(2020, 1, 6))
    make_allowance(sam, Y26, 100, 0)
    make_entry(sam, date(2026, 1, 10), start=time(17), finish=time(20), overtime="toil")
    make_entry(sam, date(2099, 1, 10), start=time(17), finish=time(20), overtime="toil")      # not yet worked
    s = balances.statement(sam, Y26)
    assert s.toil_earned == 3 * 3600 and s.toil_remaining == 3 * 3600
    toil = make_booking(sam, date(2026, 1, 20), type_name="TOIL", status="approved")
    BookingDay.objects.create(booking=toil, day=date(2026, 1, 20), cost_seconds=2 * 3600, source="times", account="toil")
    assert balances.statement(sam, Y26).toil_remaining == 1 * 3600


def test_toil_is_a_running_balance_across_leave_years():
    sam = make_person(start_date=date(2020, 1, 6))
    make_allowance(sam, Y26, 100, 0)
    make_allowance(sam, Y27, 100, 0)
    make_entry(sam, date(2026, 1, 10), start=time(17), finish=time(22), overtime="toil")
    toil = make_booking(sam, date(2026, 2, 3), type_name="TOIL", status="approved")
    BookingDay.objects.create(booking=toil, day=date(2026, 2, 3), cost_seconds=2 * 3600, source="times", account="toil")
    Adjustment.objects.create(person=sam, leave_year=Y26, account="toil", seconds=3600, reason="TOIL brought in")
    s = balances.statement(sam, Y27)
    assert (s.taken["toil"], s.adjustments["toil"]) == (0, 0)                  # nothing in 2027 itself
    assert (s.toil_taken, s.toil_adjustments) == (2 * 3600, 3600)
    assert s.toil_remaining == 5 * 3600 + 3600 - 2 * 3600
    assert s.toil_available == s.toil_remaining


def test_the_statement_lines_explain_every_figure():
    sam = make_person(start_date=date(2026, 7, 6))
    make_allowance(sam, date(2026, 1, 1), 210, 0)
    s = balances.statement(sam, date(2026, 1, 1))
    kinds = [k for k, _, _ in s.lines]
    assert kinds[0] == "allowance" and "26 weeks" in s.lines[0][1] and s.lines[0][2] == 105 * 3600
    assert "remaining" in kinds
    assert kinds[-5:] == ["remaining", "available", "toil", "toil_remaining", "toil_available"]
    assert "pending" not in kinds


def test_pending_requests_are_listed_but_do_not_reduce_remaining():
    sam = make_person(start_date=date(2020, 1, 6))
    make_allowance(sam, Y27, 100, 0)
    make_entry(sam, date(2027, 3, 2), start=time(9), finish=time(17), break_minutes=30)
    make_booking(sam, date(2027, 3, 2), status="pending")
    s = balances.statement(sam, Y27)
    assert [(k, t, n) for k, t, n in s.lines if k == "pending"] == [("pending", "Requested: Holiday 2 Mar", -27000)]
    by_kind = {k: n for k, _, n in s.lines}
    assert by_kind["remaining"] == 100 * 3600 and by_kind["available"] == 100 * 3600 - 27000
    assert by_kind["toil_available"] == 0


def test_missing_allowance_is_said_not_guessed():
    sam = make_person()
    s = balances.statement(sam, Y27)
    assert s.missing and s.annual_allowance == 0 and s.annual_remaining == 0
