"""Allowance spec 2026-11-18, section 6: full-year allowances worked out
from a person's contracts. The table in the spec and its service example
are these tests, figure for figure."""

from datetime import date
from decimal import Decimal as D

import pytest

from leave.services import entitlement, hours
from tests.factories import make_bank_holiday, make_contract, make_person

pytestmark = pytest.mark.django_db
Y27 = date(2027, 1, 1)
RECEPTION = [(1, 23)]                # 22 days; 23 after 1 year


def _year(person, year=Y27, bank_holidays=8):
    return entitlement.periods(list(person.contracts.all()), person.start_date, person.end_date, year, bank_holidays)


def _one(person, **kw):
    result = _year(person, **kw)
    assert result.ok, result.reason
    (period,) = result.periods
    return period


def _fmt(period):
    return hours.fmt(hours.from_hours(period.annual)), hours.fmt(hours.from_hours(period.bank_holiday))


# --- service ------------------------------------------------------------------------------

def test_service_is_complete_years_on_the_first_day_of_the_leave_year():
    start = date(2025, 6, 1)
    assert entitlement.service_years(start, date(2026, 1, 1)) == 0
    assert entitlement.service_years(start, date(2027, 1, 1)) == 1        # 1 complete year on 1 Jan 2027
    assert entitlement.service_years(start, date(2028, 1, 1)) == 2        # 3 years are reached on 1 June 2028…
    assert entitlement.service_years(start, date(2029, 1, 1)) == 3        # …so a 3-year step applies from 1 Jan 2029
    assert entitlement.service_years(date(2027, 3, 1), Y27) == 0          # a year the person starts in has none
    assert entitlement.service_years(date(2026, 1, 1), Y27) == 1          # a year to the day
    assert entitlement.service_years(date(2026, 4, 1), date(2027, 4, 1)) == 1


def test_the_step_in_force_is_the_highest_one_reached():
    sam = make_person(start_date=date(2021, 6, 1))
    make_contract(sam, steps=[(1, 23), (5, 25), (10, 27)])
    (contract,) = sam.contracts.all()
    assert [entitlement.entitled(contract, n) for n in (0, 1, 4, 5, 9, 10, 30)] == [D("22"), D("23"), D("23"), D("25"), D("25"), D("27"), D("27")]


# --- the spec's table, with 8 bank holidays in the year -----------------------------------

def test_full_time_with_one_complete_year():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "37.5", steps=RECEPTION)
    p = _one(sam)
    assert (p.annual, p.bank_holiday, p.weekly_hours) == (D("172.5"), D("60"), D("37.5"))
    assert _fmt(p) == ("172 h 30 min", "60 h")
    assert p.working == ("23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min",
                         "8 bank holidays × 37.5 h ÷ 5 = 60 h")


def test_part_time_under_a_year():
    sam = make_person(start_date=date(2026, 6, 1))
    make_contract(sam, "22.5", steps=RECEPTION)
    p = _one(sam)
    assert _fmt(p) == ("99 h", "36 h")
    assert p.working[0] == "22 days (no complete years on 1 Jan 2027) × 22.5 h ÷ 5 = 99 h"


def test_a_quarter_hour_rounds_up_to_the_half_hour():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "18.75", steps=RECEPTION)
    p = _one(sam)
    assert _fmt(p) == ("86 h 30 min", "30 h")
    assert p.working[0] == "23 days (1 complete year on 1 Jan 2027) × 18.75 h ÷ 5 = 86 h 15 min, rounded to 86 h 30 min"


def test_under_a_quarter_hour_rounds_down():
    sam = make_person(start_date=date(2026, 6, 1))
    make_contract(sam, "18.8", steps=RECEPTION)          # 22 × 18.8 ÷ 5 = 82.72 h; 8 × 18.8 ÷ 5 = 30.08 h
    assert _fmt(_one(sam)) == ("82 h 30 min", "30 h")


def test_a_partner_on_6_sessions():
    doc = make_person(is_gp=True, start_date=date(2019, 4, 1))
    make_contract(doc, 6, 8, unit="sessions", type_name="Partner")
    p = _one(doc)
    assert (p.annual, p.bank_holiday, p.weekly_hours) == (D("200"), D("50"), None)
    assert p.working == ("8 weeks × 6 sessions = 48 sessions = 200 h",
                         "8 bank holidays × 2 sessions × 6 ÷ 8 = 12 sessions = 50 h")


def test_a_salaried_gp_on_8_sessions():
    doc = make_person(is_gp=True, start_date=date(2022, 9, 1))
    make_contract(doc, 8, 6, unit="sessions")
    p = _one(doc)
    assert (p.annual, p.bank_holiday) == (D("200"), D("66.6667"))
    assert _fmt(p) == ("200 h", "66 h 40 min")
    assert hours.from_hours(p.bank_holiday) == 16 * hours.GP_SESSION


def test_a_fractional_number_of_sessions_rounds_to_the_nearest_whole_one():
    doc = make_person(is_gp=True, start_date=date(2022, 9, 1))
    make_contract(doc, 5, 6, unit="sessions")
    p = _one(doc, bank_holidays=9)
    assert _fmt(p) == ("125 h", "45 h 50 min")            # 30 sessions; 11.25 rounded to 11
    assert p.working == ("6 weeks × 5 sessions = 30 sessions = 125 h",
                         "9 bank holidays × 2 sessions × 5 ÷ 8 = 11.25 sessions, rounded to 11 sessions = 45 h 50 min")


def test_half_a_session_rounds_up():
    doc = make_person(is_gp=True, start_date=date(2022, 9, 1))
    make_contract(doc, 2, 6, unit="sessions")              # 9 × 2 × 2 ÷ 8 = 4.5 sessions
    assert hours.from_hours(_one(doc, bank_holidays=9).bank_holiday) == 5 * hours.GP_SESSION


def test_sixty_four_sessions_is_held_exactly():
    doc = make_person(is_gp=True, start_date=date(2019, 4, 1))
    make_contract(doc, 8, 8, unit="sessions", type_name="Partner")
    p = _one(doc)
    assert p.annual == D("266.6667") and hours.from_hours(p.annual) == 960000


def test_no_bank_holidays_entered_gives_none():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "37.5", steps=RECEPTION)
    p = _one(sam, bank_holidays=0)
    assert p.bank_holiday == 0 and p.working[1] == "0 bank holidays × 37.5 h ÷ 5 = 0 min"


# --- several contracts, and changes in the year -----------------------------------------------

def test_two_contracts_in_force_together_are_each_rounded_then_added():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "18.75", steps=RECEPTION)           # 86.25 → 86.5; 30
    make_contract(sam, "7.5", base=20)                     # 30; 12
    p = _one(sam)
    assert (p.annual, p.bank_holiday, p.weekly_hours) == (D("116.5"), D("42"), D("26.25"))
    assert p.working[0] == ("23 days (1 complete year on 1 Jan 2027) × 18.75 h ÷ 5 = 86 h 15 min, rounded to 86 h 30 min; "
                            "20 days × 7.5 h ÷ 5 = 30 h; together 116 h 30 min")


def test_a_new_contract_in_the_year_starts_a_period_on_its_first_day():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(sam, "30", steps=RECEPTION, from_day=date(2027, 6, 1))
    result = _year(sam)
    assert [(p.from_day, p.annual, p.bank_holiday, p.weekly_hours) for p in result.periods] == [
        (Y27, D("103.5"), D("36"), D("22.5")), (date(2027, 6, 1), D("138"), D("48"), D("30"))]
    assert result.changes == (date(2027, 6, 1),) and result.gaps == ()


def test_a_second_contract_ending_starts_a_period_the_day_after():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "22.5", steps=RECEPTION)
    make_contract(sam, "7.5", steps=RECEPTION, to_day=date(2027, 3, 31))
    assert [(p.from_day, p.weekly_hours) for p in _year(sam).periods] == [(Y27, D("30")), (date(2027, 4, 1), D("22.5"))]


def test_a_renewal_on_the_same_terms_starts_no_period():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(sam, "22.5", steps=RECEPTION, from_day=date(2027, 6, 1))
    result = _year(sam)
    assert len(result.periods) == 1 and result.changes == ()


def test_a_starter_in_the_year_is_worked_out_from_the_contract_on_their_start_date():
    sam = make_person(start_date=date(2027, 7, 1))
    make_contract(sam, "30", steps=RECEPTION)
    p = _one(sam)
    assert (p.from_day, p.annual) == (Y27, D("132"))        # the year's first row is dated the year's first day; pro-rata does the rest


def test_a_contract_that_starts_before_the_start_date_counts_from_the_start_date():
    """Practice HR does not guarantee a contract sits inside its employment."""
    sam = make_person(start_date=date(2027, 7, 1))
    make_contract(sam, "22.5", steps=RECEPTION, from_day=date(2027, 3, 1), to_day=date(2027, 8, 31))
    make_contract(sam, "30", steps=RECEPTION, from_day=date(2027, 9, 1))
    result = _year(sam)
    assert [(p.from_day, p.weekly_hours) for p in result.periods] == [(Y27, D("22.5")), (date(2027, 9, 1), D("30"))]
    assert result.gaps == () and result.changes == (date(2027, 9, 1),)    # 1 March is before they start: no period, no change
    early = make_person(first_name="Early", start_date=date(2027, 7, 1))
    make_contract(early, "30", steps=RECEPTION, from_day=date(2026, 11, 1))
    p = _one(early)
    assert (p.from_day, p.annual) == (Y27, D("132"))                      # 22 days: service runs from the start date, not the contract's
    ended = make_person(first_name="Ended", start_date=date(2027, 7, 1))
    make_contract(ended, "30", steps=RECEPTION, from_day=date(2027, 3, 1), to_day=date(2027, 6, 30))      # over before they start
    assert _year(ended).reason == entitlement.NOT_IN_FORCE


def test_changes_after_the_end_date_are_ignored():
    sam = make_person(start_date=date(2025, 6, 1), end_date=date(2027, 5, 31))
    make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    result = _year(sam)
    assert len(result.periods) == 1 and result.gaps == ()


def test_a_day_with_no_contract_starts_no_period_and_is_a_gap():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 6, 30))
    result = _year(sam)
    assert result.ok and len(result.periods) == 1 and result.gaps == (date(2027, 7, 1),)


def test_a_step_reached_in_the_year_waits_for_the_next_leave_year():
    sam = make_person(start_date=date(2026, 6, 1))
    make_contract(sam, "37.5", steps=RECEPTION)
    assert _one(sam).annual == D("165")                      # 22 days all of 2027, though a year is reached on 1 June
    assert _one(sam, year=date(2028, 1, 1)).annual == D("172.5")


# --- not worked out ------------------------------------------------------------------------

def test_each_reason_a_year_is_not_worked_out():
    nobody = make_person(first_name="Nobody")
    assert _year(nobody).reason == entitlement.NO_CONTRACT

    trainee = make_person(first_name="Trainee", is_gp=True)
    make_contract(trainee, 8, None, unit="sessions", type_name="GP trainee")
    assert _year(trainee).reason == entitlement.NO_TERMS

    bank = make_person(first_name="Bank")
    make_contract(bank, 0, steps=RECEPTION)                     # a bank contract: no fixed hours, so nothing to multiply
    assert _year(bank).reason == entitlement.NO_HOURS

    both = make_person(first_name="Both", start_date=date(2025, 6, 1))
    make_contract(both, "22.5", steps=RECEPTION)
    make_contract(both, 0, steps=RECEPTION, from_day=date(2027, 6, 1))        # a bank contract beside a fixed one
    assert _year(both).reason == entitlement.NO_HOURS

    falling = make_person(first_name="Falling")
    make_contract(falling, steps=[(1, 23), (5, 23)])
    assert _year(falling).reason == entitlement.BAD_TERMS

    backwards = make_person(first_name="Backwards")
    make_contract(backwards, 0, steps=[(5, 25), (1, 23)])       # steps that do not rise are said first, whatever else is true
    assert _year(backwards).reason == entitlement.BAD_TERMS

    mixed = make_person(first_name="Mixed", start_date=date(2025, 6, 1))
    make_contract(mixed, "22.5", to_day=date(2027, 5, 31))
    make_contract(mixed, 4, 6, unit="sessions", from_day=date(2027, 6, 1))
    result = _year(mixed)
    assert result.reason == entitlement.MIXED and result.changes == (date(2027, 6, 1),)
    assert _year(mixed, year=date(2028, 1, 1)).ok                 # the next year holds only sessions

    late = make_person(first_name="Late", start_date=date(2025, 6, 1))
    make_contract(late, from_day=date(2027, 2, 1))
    result = _year(late)
    assert result.reason == entitlement.NOT_IN_FORCE and result.gaps == (Y27,)

    gone = make_person(first_name="Gone", start_date=date(2020, 1, 6), end_date=date(2026, 10, 14))
    make_contract(gone)
    assert _year(gone).reason == entitlement.NOT_EMPLOYED


def test_a_year_that_is_not_worked_out_has_no_periods():
    trainee = make_person(is_gp=True)
    make_contract(trainee, 8, None, unit="sessions")
    result = _year(trainee)
    assert not result.ok and result.periods == ()


# --- loading ----------------------------------------------------------------------------------

def test_the_bank_holidays_counted_are_the_rows_in_the_leave_year():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "37.5", steps=RECEPTION)
    data = entitlement.load([sam])
    assert data.holidays_in(Y27) == 8                      # seeded
    make_bank_holiday(date(2027, 6, 14), "An extra bank holiday")
    data = entitlement.load([sam])
    assert data.holidays_in(Y27) == 9
    assert entitlement.worked(sam, Y27, data).periods[0].bank_holiday == D("67.5")
    assert entitlement.worked_for(sam, Y27).periods[0].bank_holiday == D("67.5")
    assert data.holidays_in(date(2029, 1, 1)) == 0


def test_the_arithmetic_runs_no_queries(django_assert_num_queries):
    people = [make_person(first_name=f"P{n}", start_date=date(2025, 6, 1)) for n in range(5)]
    for p in people:
        make_contract(p, "30", steps=RECEPTION)
    with django_assert_num_queries(3):
        data = entitlement.load(people)
    with django_assert_num_queries(0):
        assert all(entitlement.worked(p, Y27, data).ok for p in people)


@pytest.mark.today(date(2026, 11, 2))
def test_the_years_covered_leave_out_one_that_ended_before_launch():
    sam = make_person()
    assert entitlement.covered(sam) == [Y27]
    assert entitlement.covered(sam, date(2027, 1, 1)) == [Y27, date(2028, 1, 1)]
