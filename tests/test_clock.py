"""The suite's clock (tests/clock.py): no test reads the real date."""

from datetime import date

import pytest
from django.utils import timezone

from tests import clock


def test_today_is_the_pin():
    assert timezone.localdate() == clock.PIN.date()


@pytest.mark.today(date(2031, 2, 3))
def test_a_test_can_be_set_on_a_day_of_its_own():
    assert timezone.localdate() == date(2031, 2, 3)
    assert timezone.localtime().hour == 9


def test_the_clock_ticks_on_from_the_pin():
    first = timezone.now()
    assert timezone.now() >= first and first >= clock.PIN


def test_the_today_fixture_moves_the_clock(today):
    today(date(2030, 7, 1))
    assert timezone.localdate() == date(2030, 7, 1)
