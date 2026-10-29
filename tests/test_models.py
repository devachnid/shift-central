from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError

from people.models import Allowance, Department, Person, Team
from tests.factories import make_person, make_team

pytestmark = pytest.mark.django_db


def test_average_day_is_weekly_hours_over_days(db):
    p = make_person(weekly_hours=Decimal("30.00"), days_per_week=5)
    assert p.average_day == Decimal("6")


def test_average_day_is_none_without_hours_or_days(db):
    assert make_person().average_day is None
    assert make_person(weekly_hours=Decimal("30.00")).average_day is None


def test_current_reads_the_employment_dates(db):
    p = make_person(start_date=date(2026, 1, 5), end_date=date(2026, 6, 30))
    assert not p.current(date(2026, 1, 4))
    assert p.current(date(2026, 1, 5)) and p.current(date(2026, 6, 30))
    assert not p.current(date(2026, 7, 1))
    assert make_person(start_date=date(2026, 1, 5)).current(date(2030, 1, 1))


def test_current_queryset_matches_the_method(db):
    here = make_person(start_date=date(2026, 1, 5))
    gone = make_person(start_date=date(2025, 1, 5), end_date=date(2026, 1, 31))
    soon = make_person(start_date=date(2026, 9, 1))
    assert set(Person.objects.current(on=date(2026, 3, 1))) == {here}
    assert gone not in Person.objects.current(on=date(2026, 3, 1))
    assert soon not in Person.objects.current(on=date(2026, 3, 1))


def test_hr_employee_id_is_unique(db):
    make_person(hr_employee_id=7)
    with pytest.raises(IntegrityError):
        make_person(hr_employee_id=7)


def test_one_allowance_per_person_per_leave_year(db):
    p = make_person()
    Allowance.objects.create(person=p, leave_year=date(2027, 1, 1),
                             annual_hours=Decimal("172.50"), bank_holiday_hours=Decimal("60.00"))
    with pytest.raises(IntegrityError):
        Allowance.objects.create(person=p, leave_year=date(2027, 1, 1),
                                 annual_hours=Decimal("1"), bank_holiday_hours=Decimal("1"))


def test_the_seventeen_departments_are_seeded(db):
    names = set(Department.objects.values_list("name", flat=True))
    assert names == {"Reception AG", "Reception PMC", "Cleaning PMC", "Prescriptions",
                     "Private Income", "Workflow", "VAS/Enhanced", "Scanning", "Pharmacy",
                     "Secretarial", "Management", "Salaried GP", "Nursing", "HCA",
                     "Phlebotomist", "Pharmacist", "Pharmacy Technician"}
    assert len({d.colour for d in Department.objects.all()}) == 17, "distinct default colours"


def test_teams_order_by_display_order_then_name(db):
    make_team("Pharmacy", display_order=20)
    make_team("Admin/Secretarial", display_order=10)
    make_team("Nursing", display_order=10)
    assert [t.name for t in Team.objects.all()] == [
        "Admin/Secretarial", "Nursing", "Pharmacy"]
