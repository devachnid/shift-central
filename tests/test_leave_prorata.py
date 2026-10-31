"""LEAVE-10 to 13 as the worked examples state them: weeks on contract
over 52, part weeks whole, rounded once to the nearest half hour, capped
at the full-year figure."""

from datetime import date
from decimal import Decimal

import pytest

from leave.services import prorata
from people.models import AuditEntry
from people.services import profiles
from tests.factories import make_allowance, make_person

pytestmark = pytest.mark.django_db
Y26 = date(2026, 1, 1)


def _hours(pr):
    return Decimal(pr.seconds) / 3600


def test_lv_06a_starter_in_july():
    sam = make_person(start_date=date(2026, 7, 6))
    make_allowance(sam, Y26, 210, 0)
    pr = prorata.allowance(sam, Y26, "annual")
    assert _hours(pr) == Decimal("105.0") and pr.lines[0].weeks == 26 and not pr.capped


def test_lv_06b_starter_on_the_last_day_of_july_rounds_up():
    sam = make_person(start_date=date(2026, 7, 31))
    make_allowance(sam, Y26, 210, 0)
    assert _hours(prorata.allowance(sam, Y26, "annual")) == Decimal("89.0")


def test_lv_07a_leaver_in_october_rounds_down():
    sam = make_person(start_date=date(2020, 1, 6), end_date=date(2026, 10, 14))
    make_allowance(sam, Y26, 210, 0)
    pr = prorata.allowance(sam, Y26, "annual")
    assert _hours(pr) == Decimal("165.5") and pr.lines[0].weeks == 41


def test_lv_07b_leavers_bank_holiday_allowance():
    sam = make_person(start_date=date(2020, 1, 6), end_date=date(2026, 10, 14))
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    assert _hours(prorata.allowance(sam, Y26, "annual")) == Decimal("136.0")
    assert _hours(prorata.allowance(sam, Y26, "bank_holiday")) == Decimal("47.5")


def test_lv_20_findmyshift_got_it_wrong():
    sam = make_person(start_date=date(2026, 8, 18))
    make_allowance(sam, Y26, 285, 0)
    assert _hours(prorata.allowance(sam, Y26, "annual")) == Decimal("109.5")


def test_lv_08a_hours_increase_counts_the_week_of_the_change_twice():
    sam = make_person(start_date=date(2020, 1, 6))
    make_allowance(sam, Y26, 138, 48)
    make_allowance(sam, Y26, Decimal("172.5"), 60, from_day=date(2026, 7, 1), weekly_hours=Decimal("37.5"), days_per_week=5)
    pr = prorata.allowance(sam, Y26, "annual")
    assert [(l.weeks, l.share_hours.quantize(Decimal("0.01"))) for l in pr.lines] == [(26, Decimal("69.00")), (27, Decimal("89.57"))]
    assert _hours(pr) == Decimal("158.5")


def test_lv_08b_hours_decrease():
    sam = make_person(start_date=date(2020, 1, 6))
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    make_allowance(sam, Y26, 138, 48, from_day=date(2026, 7, 1), weekly_hours=Decimal("30"), days_per_week=5)
    assert _hours(prorata.allowance(sam, Y26, "annual")) == Decimal("158.0")


def test_lv_11a_starters_bank_holiday_allowance():
    sam = make_person(start_date=date(2026, 7, 6))
    make_allowance(sam, Y26, 138, 48)
    assert _hours(prorata.allowance(sam, Y26, "bank_holiday")) == Decimal("24.0")


def test_lv_13_a_whole_year_is_exactly_the_full_allowance():
    sam = make_person(start_date=date(2020, 1, 6))
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    pr = prorata.allowance(sam, Y26, "annual")
    assert _hours(pr) == Decimal("172.5") and pr.capped        # 53 weeks counted, then capped


def test_a_small_change_is_capped_at_the_larger_figure():
    sam = make_person(start_date=date(2020, 1, 6))
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    make_allowance(sam, Y26, Decimal("170.2"), 60, from_day=date(2026, 7, 1))
    assert _hours(prorata.allowance(sam, Y26, "annual")) == Decimal("172.5")


def test_no_row_means_no_allowance_and_a_missing_flag():
    sam = make_person()
    pr = prorata.allowance(sam, Y26, "annual")
    assert pr.seconds == 0 and pr.missing and pr.lines == []


def test_the_row_in_force_on_a_day():
    sam = make_person()
    first = make_allowance(sam, Y26, 138, 48)
    second = make_allowance(sam, Y26, 160, 50, from_day=date(2026, 7, 1), weekly_hours=Decimal("37.5"), days_per_week=5)
    assert prorata.row_in_force(sam, date(2026, 3, 1)) == first
    assert prorata.row_in_force(sam, date(2026, 7, 1)) == second
    assert prorata.row_in_force(sam, date(2025, 3, 1)) is None


def test_add_hours_change_writes_a_dated_row_and_audits_it(all_teams_user):
    sam = make_person(weekly_hours=Decimal("30"), days_per_week=5)
    make_allowance(sam, Y26, 138, 48)
    row = profiles.add_hours_change(all_teams_user, sam, date(2026, 7, 1), Decimal("37.5"), 5, Decimal("172.5"), 60, "full time from July")
    assert row.from_day == date(2026, 7, 1) and row.weekly_hours == Decimal("37.50")
    sam.refresh_from_db()
    assert sam.weekly_hours == Decimal("37.50")       # 1 Jul 2026 is already past, so the hours are copied straight away
    notes = set(AuditEntry.objects.filter(model="people.allowance", object_id=row.pk).values_list("note", flat=True))
    assert notes == {"full time from July"}
    person_notes = set(AuditEntry.objects.filter(model="people.person", object_id=sam.pk).values_list("note", flat=True))
    assert person_notes == {"full time from July"}     # the copy onto the person carries the reason too


def test_a_future_hours_change_waits_for_its_day(all_teams_user):
    sam = make_person(weekly_hours=Decimal("30"), days_per_week=5)
    make_allowance(sam, Y26, 138, 48)
    make_allowance(sam, date(2099, 1, 1), 138, 48)     # the change's own year needs its first row
    profiles.add_hours_change(all_teams_user, sam, date(2099, 7, 1), Decimal("37.5"), 5, Decimal("172.5"), 60, "later")
    sam.refresh_from_db()
    assert sam.weekly_hours == Decimal("30.00")
    assert profiles.apply_due_hours_changes(today=date(2099, 7, 1)) == 1
    sam.refresh_from_db()
    assert sam.weekly_hours == Decimal("37.50")
    assert profiles.apply_due_hours_changes(today=date(2099, 7, 2)) == 0


def test_add_hours_change_refuses_a_year_with_no_first_row_and_a_blank_reason(all_teams_user):
    sam = make_person()
    with pytest.raises(ValueError):
        profiles.add_hours_change(all_teams_user, sam, date(2026, 7, 1), 30, 5, 138, 48, "x")
    make_allowance(sam, Y26, 138, 48)
    with pytest.raises(ValueError):
        profiles.add_hours_change(all_teams_user, sam, date(2026, 7, 1), 30, 5, 138, 48, "  ")
    with pytest.raises(ValueError):
        profiles.add_hours_change(all_teams_user, sam, Y26, 30, 5, 138, 48, "the year's first day is set_allowance's")


@pytest.mark.parametrize("annual, expected", [(145, "36.5"), (119, "30"), (171, "43"), (197, "49.5")])
def test_a_quarter_hour_tie_rounds_up_from_the_exact_sum(annual, expected):
    # 2 Oct to 31 Dec 2026 is 91 days: 13 whole weeks. 145 h over 52 weeks times 13 is 36.25 exactly.
    sam = make_person(start_date=date(2026, 10, 2))
    make_allowance(sam, Y26, annual, 0)
    assert _hours(prorata.allowance(sam, Y26, "annual")) == Decimal(expected)
