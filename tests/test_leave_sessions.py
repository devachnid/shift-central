"""The rule that leave hides the GP sessions it falls on (leave spec,
Revisit): a whole day hides both, a morning the AM, an afternoon the PM, a
timed booking none; only active, costed bookings count."""

from datetime import date, time, timedelta
from types import SimpleNamespace

import pytest

from leave.services import sessions
from tests.factories import make_booking, make_person, make_sick

pytestmark = pytest.mark.django_db
FIRST, LAST = date(2027, 3, 2), date(2027, 3, 4)


def test_a_whole_day_booking_straddling_the_range_hides_only_the_days_inside_it():
    p = make_person(is_gp=True)
    make_booking(p, FIRST - timedelta(days=3), LAST + timedelta(days=3), part="whole")
    hidden = sessions.hidden([p], FIRST, LAST)
    assert hidden == {(p.pk, FIRST + timedelta(days=n)): {"AM", "PM"} for n in range(3)}


def test_a_booking_ending_inside_the_range_hides_up_to_its_last_day():
    p = make_person(is_gp=True)
    make_booking(p, FIRST - timedelta(days=2), FIRST + timedelta(days=1), part="whole")
    assert set(sessions.hidden([p], FIRST, LAST)) == {(p.pk, FIRST), (p.pk, FIRST + timedelta(days=1))}


def test_a_morning_hides_am_an_afternoon_pm_and_a_timed_booking_nothing():
    am, pm, timed = make_person(is_gp=True), make_person(is_gp=True), make_person(is_gp=True)
    make_booking(am, FIRST, part="am")
    make_booking(pm, FIRST, part="pm")
    make_booking(timed, FIRST, part="times", start=time(9), finish=time(11))
    hidden = sessions.hidden([am, pm, timed], FIRST, LAST)
    assert hidden[(am.pk, FIRST)] == {"AM"} and hidden[(pm.pk, FIRST)] == {"PM"}
    assert hidden.get((timed.pk, FIRST), set()) == set()


@pytest.mark.parametrize("status", ["pending", "cancelled", "declined"])
def test_a_booking_that_is_not_active_hides_nothing(status):
    p = make_person(is_gp=True)
    make_booking(p, FIRST, status=status)
    assert sessions.hidden([p], FIRST, LAST) == {}


def test_a_dates_only_booking_hides_nothing():
    p = make_person(is_gp=True)
    make_sick(p, FIRST, dates_only=True)
    assert sessions.hidden([p], FIRST, LAST) == {}


def test_visible_filters_by_person_day_and_part():
    a, b = SimpleNamespace(person_id=1, day=FIRST, part="AM"), SimpleNamespace(person_id=1, day=FIRST, part="PM")
    c, d = SimpleNamespace(person_id=2, day=FIRST, part="AM"), SimpleNamespace(person_id=1, day=LAST, part="AM")
    hidden = {(1, FIRST): {"AM"}}
    assert sessions.visible([a, b, c, d], hidden) == [b, c, d]
    assert sessions.visible([a, b], {}) == [a, b]
