"""Spec 2026-11-18, section 6.1: a GP's part-year allowance is rounded once
to the nearest whole session (4 h 10 min), not the half hour. Staff on
hours are untouched."""

from datetime import date
from decimal import Decimal

import pytest

from leave.services import balances, hours, prorata
from tests.factories import make_allowance, make_person

pytestmark = pytest.mark.django_db
Y27 = date(2027, 1, 1)
SALARIED_8 = (Decimal("200"), Decimal("66.6667"))        # 48 and 16 sessions


def test_sixty_four_sessions_is_exact_to_the_second():
    assert hours.from_hours(Decimal("266.6667")) == 960000 == 64 * hours.GP_SESSION


def test_a_gp_starting_on_1_july_gets_whole_sessions():
    gp = make_person(is_gp=True, start_date=date(2027, 7, 1))
    make_allowance(gp, Y27, *SALARIED_8)
    annual, bank = prorata.allowance(gp, Y27, "annual"), prorata.allowance(gp, Y27, "bank_holiday")
    assert annual.lines[0].weeks == 27
    assert annual.seconds == 25 * hours.GP_SESSION and hours.fmt(annual.seconds) == "104 h 10 min"
    assert bank.seconds == 8 * hours.GP_SESSION and hours.fmt(bank.seconds) == "33 h 20 min"


def test_staff_on_hours_with_the_same_figures_still_round_to_the_half_hour():
    sam = make_person(start_date=date(2027, 7, 1))
    make_allowance(sam, Y27, Decimal("200"), Decimal("66.67"))
    assert hours.fmt(prorata.allowance(sam, Y27, "annual").seconds) == "104 h"
    assert hours.fmt(prorata.allowance(sam, Y27, "bank_holiday").seconds) == "34 h 30 min"


def test_half_a_session_rounds_up():
    # 13 weeks of 52 at 50 h is 12.5 h: three sessions exactly. At 58.3333 h (14 sessions)
    # it is 14.58 h, 3.5 sessions, which rounds up to 4.
    gp = make_person(is_gp=True, start_date=date(2027, 10, 2))
    make_allowance(gp, Y27, Decimal("50"), Decimal("58.3333"))
    assert prorata.allowance(gp, Y27, "annual").seconds == 3 * hours.GP_SESSION
    assert prorata.allowance(gp, Y27, "bank_holiday").seconds == 4 * hours.GP_SESSION


def test_a_gp_here_all_year_gets_exactly_the_full_figure():
    gp = make_person(is_gp=True, start_date=date(2020, 1, 6))
    make_allowance(gp, Y27, *SALARIED_8)
    annual, bank = prorata.allowance(gp, Y27, "annual"), prorata.allowance(gp, Y27, "bank_holiday")
    assert (annual.seconds, annual.capped) == (48 * hours.GP_SESSION, True)
    assert (bank.seconds, bank.capped) == (16 * hours.GP_SESSION, True)


def test_a_typed_figure_that_is_not_whole_sessions_is_still_met_in_full_by_a_whole_year():
    # 55 h is 13.2 sessions. 53 weeks of 52 is 56.06 h, 13.45 sessions, which rounds DOWN to
    # 13 sessions (54 h 10 min): without the rule for a GP at the cap, LEAVE-13 would not hold.
    gp = make_person(is_gp=True, start_date=date(2020, 1, 6))
    make_allowance(gp, Y27, Decimal("210"), Decimal("55"))
    assert hours.fmt(prorata.allowance(gp, Y27, "annual").seconds) == "210 h"
    assert hours.fmt(prorata.allowance(gp, Y27, "bank_holiday").seconds) == "55 h"


def test_a_gps_change_of_sessions_is_rounded_once_to_a_whole_session():
    gp = make_person(is_gp=True, start_date=date(2020, 1, 6))
    make_allowance(gp, Y27, Decimal("200"), Decimal("50"))                                   # 6 sessions a week
    make_allowance(gp, Y27, Decimal("266.6667"), Decimal("66.6667"), from_day=date(2027, 7, 1))   # 8 from July
    pr = prorata.allowance(gp, Y27, "annual")
    assert [l.weeks for l in pr.lines] == [26, 27]
    # 200 × 26/52 + 266.6667 × 27/52 = 238.46 h = 57.23 sessions
    assert pr.seconds == 57 * hours.GP_SESSION and not pr.capped


def test_the_statement_says_which_rounding_was_used():
    gp = make_person(is_gp=True, start_date=date(2027, 7, 1))
    make_allowance(gp, Y27, *SALARIED_8)
    texts = [text for kind, text, _ in balances.statement(gp, Y27).lines if kind == "allowance"]
    assert "Annual leave allowance rounded to the whole session" in texts
    sam = make_person(start_date=date(2027, 7, 1))
    make_allowance(sam, Y27, Decimal("200"), Decimal("66.67"))
    texts = [text for kind, text, _ in balances.statement(sam, Y27).lines if kind == "allowance"]
    assert "Annual leave allowance rounded to the half hour" in texts
