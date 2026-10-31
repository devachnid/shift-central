"""The fields and tables spec 4 adds: the two type flags and their seeds,
dates-only bookings, the year-end row, the leaver flag dates, the payroll
run, and the two new apps."""

from datetime import date
from pathlib import Path

import pytest
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from leave.models import LeaveType, YearEnd
from payroll.models import PayrollRun
from tests.factories import make_booking, make_person, make_sick, make_user_for

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[1]


def test_sick_leave_counts_as_sickness_and_family_leave_flags_the_return():
    assert LeaveType.objects.get(name="Sick leave").sickness is True
    assert set(LeaveType.objects.filter(flag_return=True).values_list("name", flat=True)) == {"Maternity", "Adoption / shared parental"}
    assert LeaveType.objects.filter(sickness=True).count() == 1
    assert LeaveType.objects.get(name="Paternity").flag_return is False


def test_a_dates_only_booking_is_whole_days():
    sam = make_person()
    row = make_sick(sam, date(2026, 3, 2), date(2026, 3, 6), dates_only=True)
    assert row.dates_only and row.part == "whole" and row.return_flagged_at is None
    with pytest.raises(IntegrityError):
        make_booking(sam, date(2026, 3, 9), part="am", dates_only=True, type_name="Sick leave")


def test_make_sick_books_the_seeded_type_approved():
    sam = make_person()
    row = make_sick(sam, date(2027, 1, 4))
    assert row.type.name == "Sick leave" and row.type.sickness and row.status == "approved" and row.last_day == date(2027, 1, 4)


def test_one_year_end_row_per_person_and_year():
    sam = make_person()
    row = YearEnd.objects.create(person=sam, year_ended=date(2027, 1, 1), annual_remaining=72000, toil_remaining=3600)
    assert row.decided is False
    row.decided_at = timezone.now()
    assert row.decided is True
    with pytest.raises(IntegrityError):
        YearEnd.objects.create(person=sam, year_ended=date(2027, 1, 1))


def test_a_person_starts_with_no_leaver_flags():
    sam = make_person()
    assert sam.leaver_flagged_for is None and sam.leaver_week_flagged_for is None


def test_a_payroll_run_keeps_its_figures_as_json():
    boss = make_person(first_name="Boss")
    user = make_user_for(boss, is_all_teams_manager=True)
    run = PayrollRun.objects.create(month=date(2027, 1, 1), sent_by=user, people=2,
                                    figures={"generated_at": "2027-01-24T10:00:00+00:00", "rows": {"1": {"worked": 27000}}})
    run.refresh_from_db()
    assert run.figures["rows"]["1"]["worked"] == 27000 and run.sent_at is not None
    assert str(run) == "Payroll January 2027"


def test_the_two_apps_are_installed_and_the_libraries_pinned():
    assert "absence" in settings.INSTALLED_APPS and "payroll" in settings.INSTALLED_APPS
    pins = (ROOT / "requirements.txt").read_text()
    assert "openpyxl==3.1.5" in pins and "reportlab==5.1.0" in pins and "et_xmlfile==2.0.0" in pins and "pillow==13.0.0" in pins
