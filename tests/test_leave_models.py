"""The leave app's tables, their seeds and the two helpers every other
module leans on: hours as text, and a person's leave year."""

from datetime import date, time
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from leave.models import BankHoliday, BookingDay, LeaveType
from leave.services import hours, years
from people.models import Allowance
from shifts.models import Entry
from tests.factories import make_booking, make_entry, make_person

pytestmark = pytest.mark.django_db


def test_fmt_shows_hours_and_minutes_and_a_half_minute():
    assert hours.fmt(7 * 3600 + 30 * 60) == "7 h 30 min"
    assert hours.fmt(8 * 3600) == "8 h"
    assert hours.fmt(45 * 60) == "45 min"
    assert hours.fmt(0) == "0 min"
    assert hours.fmt(9450) == "2 h 37½ min"          # LV-04b: half of 5 h 15 min
    assert hours.fmt(-(90 * 60)) == "−1 h 30 min"
    assert hours.fmt(274680) == "76 h 18 min"        # LV-03: 76.3 h


def test_from_hours_is_exact_for_the_allowances_managers_type():
    assert hours.from_hours(Decimal("87.40")) == 314640
    assert hours.from_hours(Decimal("172.5")) == 621000
    assert hours.GP_SESSION == 15000


def test_the_fifteen_types_are_seeded_in_order_with_their_accounts():
    rows = list(LeaveType.objects.order_by("display_order").values_list("name", "draws_from", "requestable", "paid_choice", "on_payroll"))
    assert rows[:3] == [("Holiday", "annual", True, False, "leavers"),
                        ("Bank holiday", "bank_holiday", False, False, "never"),
                        ("TOIL", "toil", True, False, "never")]
    assert ("Sick leave", "none", False, False, "always") in rows
    assert ("Unpaid leave", "none", True, False, "always") in rows
    assert ("Compassionate", "none", True, True, "if_unpaid") in rows
    assert len(rows) == 15 and all(LeaveType.objects.values_list("seeded", flat=True))
    assert LeaveType.objects.get(name="Unpaid leave").default_paid is False


def test_bank_holidays_for_2026_and_2027_are_seeded():
    assert BankHoliday.objects.filter(day__year=2026).count() == 8
    assert BankHoliday.objects.get(day=date(2026, 12, 28)).name == "Boxing Day (substitute day)"
    assert BankHoliday.objects.filter(day__year=2027).count() == 8
    assert BankHoliday.objects.filter(day=date(2027, 4, 2)).exists()


def test_a_booking_is_whole_days_unless_it_is_one_day():
    sam = make_person()
    with pytest.raises(IntegrityError):
        make_booking(sam, date(2027, 3, 1), date(2027, 3, 2), part="am")


def test_a_timed_booking_needs_start_before_finish_and_others_have_no_times():
    sam = make_person()
    with pytest.raises(IntegrityError), transaction.atomic():
        make_booking(sam, date(2027, 3, 1), part="times", start=time(15, 0), finish=time(14, 0))
    with pytest.raises(IntegrityError), transaction.atomic():
        make_booking(sam, date(2027, 3, 1), part="whole", start=time(9, 0), finish=time(10, 0))


def test_an_entry_can_be_covered_by_a_booking_day_and_survives_its_deletion():
    sam = make_person()
    booking = make_booking(sam, date(2027, 3, 1), status="approved")
    day = BookingDay.objects.create(booking=booking, day=date(2027, 3, 1), cost_seconds=27000, source="rota", account="annual")
    entry = make_entry(sam, date(2027, 3, 1), covered_by=day)
    day.delete()
    entry.refresh_from_db()
    assert entry.covered_by is None and Entry.objects.filter(pk=entry.pk).exists()


def test_allowance_rows_are_unique_per_person_year_and_from_day():
    sam = make_person()
    Allowance.objects.create(person=sam, leave_year=date(2027, 1, 1), from_day=date(2027, 1, 1), annual_hours=172, bank_holiday_hours=60)
    Allowance.objects.create(person=sam, leave_year=date(2027, 1, 1), from_day=date(2027, 7, 1), annual_hours=138, bank_holiday_hours=48,
                             weekly_hours=Decimal("30.00"), days_per_week=5)
    with pytest.raises(IntegrityError):
        Allowance.objects.create(person=sam, leave_year=date(2027, 1, 1), from_day=date(2027, 7, 1), annual_hours=1, bank_holiday_hours=1)


def test_a_persons_leave_year_starts_on_the_first_of_january_unless_set():
    sam = make_person()
    assert years.year_of(sam, date(2027, 6, 1)) == date(2027, 1, 1)
    assert years.year_end(date(2027, 1, 1)) == date(2027, 12, 31)
    sam.leave_year_start = "04-01"
    assert years.year_of(sam, date(2027, 3, 31)) == date(2026, 4, 1)
    assert years.year_of(sam, date(2027, 4, 1)) == date(2027, 4, 1)
    assert years.year_end(date(2027, 4, 1)) == date(2028, 3, 31)
    assert years.years_for(sam, today=date(2027, 2, 1)) == [date(2026, 4, 1), date(2027, 4, 1)]
    assert years.parse_start("04-01") == (4, 1)
    with pytest.raises(ValueError):
        years.parse_start("02-30")
