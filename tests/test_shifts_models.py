"""The cell model: ordered items, a shift's hours, the constraints."""

from datetime import date, time, timedelta

import pytest
from django.db import IntegrityError, transaction

from shifts.models import DayChange, Entry, GpSession, GridOptions, Template
from tests.factories import make_entry, make_gp_session, make_person

pytestmark = pytest.mark.django_db
DAY = date(2027, 3, 1)


def test_a_shift_knows_its_hours_minus_the_break():
    e = make_entry(make_person(), DAY, start=time(8, 0), finish=time(16, 15), break_minutes=60)
    assert e.hours == timedelta(hours=7, minutes=15)


def test_a_comment_and_a_separator_have_no_hours():
    p = make_person()
    assert make_entry(p, DAY, kind="comment", text="Training").hours == timedelta(0)
    assert make_entry(p, DAY, kind="separator", position=1).hours == timedelta(0)


def test_two_items_cannot_share_a_slot():
    p = make_person()
    make_entry(p, DAY, position=0)
    with pytest.raises(IntegrityError):
        make_entry(p, DAY, position=0)


def test_a_shift_must_have_both_times_and_a_comment_neither():
    p = make_person()
    with pytest.raises(IntegrityError), transaction.atomic():
        Entry.objects.create(person=p, day=DAY, position=0, kind="shift", start=time(8))
    with pytest.raises(IntegrityError), transaction.atomic():
        Entry.objects.create(person=p, day=DAY, position=1, kind="comment", start=time(8), finish=time(9))


def test_a_gp_session_is_four_hours_ten():
    s = make_gp_session(make_person(is_gp=True), DAY)
    assert GpSession.HOURS == timedelta(hours=4, minutes=10)
    assert s.part == "AM" and s.label == "Surgery"


def test_one_day_change_per_person_and_day():
    p = make_person()
    DayChange.objects.create(person=p, day=DAY, before="no shift")
    with pytest.raises(IntegrityError):
        DayChange.objects.create(person=p, day=DAY, before="08:00-16:15")


def test_templates_are_named_once_and_options_are_one_per_user(all_teams_user):
    Template.objects.create(name="Reception week", created_by=all_teams_user, block={"rows": [], "days": 7})
    with pytest.raises(IntegrityError), transaction.atomic():
        Template.objects.create(name="Reception week", created_by=all_teams_user, block={})
    GridOptions.objects.create(user=all_teams_user, data={})
    with pytest.raises(IntegrityError), transaction.atomic():
        GridOptions.objects.create(user=all_teams_user, data={})
