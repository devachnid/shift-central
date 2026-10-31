"""SICK-03 and LEAVE-28: a manager turns days of booked annual leave into
sickness; the hours come back, one instance is recorded."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.test import Client

from absence.services import convert
from leave.models import Booking, BookingDay
from leave.services import balances, bookings, sickness
from leave.services.common import LeaveError
from people.models import AuditEntry
from tests import clock
from tests.factories import make_allowance, make_entry, make_person, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(clock.LATE_2026)]
Y27 = date(2027, 1, 1)
MON = date(2027, 3, 1)


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss")
    make_user_for(boss, is_all_teams_manager=True)
    return boss


@pytest.fixture
def sam():
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_user_for(sam)
    make_allowance(sam, Y27, Decimal("172.5"), 0)
    for n in range(5):
        make_entry(sam, MON + timedelta(days=n), start=time(9), finish=time(17), break_minutes=30)
    return sam


def sick():
    return make_type("Sick leave", requestable=False, sickness=True)


def test_sick_03_wednesday_and_thursday_of_a_booked_week(boss, sam):
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON, MON + timedelta(days=4), "whole")
    assert balances.statement(sam, Y27).taken["annual"] == 135000           # 37.5 h
    sick_row = convert.convert(boss.user, holiday, sick(), MON + timedelta(days=2), MON + timedelta(days=3))
    s = balances.statement(sam, Y27)
    assert s.taken["annual"] == 81000                                         # 15 h back: 22.5 h left charged
    assert sick_row.type.sickness and sick_row.status == "approved" and (sick_row.first_day, sick_row.last_day) == (MON + timedelta(days=2), MON + timedelta(days=3))
    assert sum(BookingDay.objects.filter(booking=sick_row).values_list("cost_seconds", flat=True)) == 54000      # 15 h, drawing on nothing
    assert set(BookingDay.objects.filter(booking=sick_row).values_list("account", flat=True)) == {"none"}
    holiday.refresh_from_db()
    assert (holiday.first_day, holiday.last_day, holiday.status) == (MON, MON + timedelta(days=1), "approved")
    tail = Booking.objects.get(person=sam, first_day=MON + timedelta(days=4))
    assert tail.type.name == "Holiday" and tail.last_day == MON + timedelta(days=4) and tail.status == "approved"
    assert len(sickness.instances(sam, MON + timedelta(days=10))) == 1
    assert "converted from Holiday 1–5 Mar 2027" in sick_row.manager_note
    notes = list(AuditEntry.objects.filter(object_id=sam.pk, model="leave.booking").order_by("pk").values_list("note", flat=True))
    assert notes.count("converted to sickness") == 1 and notes[-1].startswith("booked by a manager")
    assert [m.subject for m in mail.outbox] == ["Your time off has been changed"]
    assert "3–4 Mar 2027 is now recorded as Sick leave" in mail.outbox[0].body


def test_converting_the_whole_booking_cancels_it(boss, sam):
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON, MON + timedelta(days=1), "whole")
    convert.convert(boss.user, holiday, sick(), MON, MON + timedelta(days=1))
    holiday.refresh_from_db()
    assert holiday.status == "cancelled" and balances.statement(sam, Y27).taken["annual"] == 0
    assert Booking.objects.filter(person=sam, type__name="Holiday", status="approved").count() == 0


def test_a_typed_figure_on_a_tail_day_survives_the_conversion(boss, sam):
    friday = MON + timedelta(days=4)
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON, friday, "whole", costs={friday: 18000})      # Friday typed as 5 h
    convert.convert(boss.user, holiday, sick(), MON + timedelta(days=2), MON + timedelta(days=3))
    tail = BookingDay.objects.get(booking__person=sam, day=friday, booking__type__name="Holiday")
    assert (tail.cost_seconds, tail.source) == (18000, "override")


def test_converting_the_first_days_keeps_the_tail_in_the_same_booking(boss, sam):
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON, MON + timedelta(days=4), "whole", description="Spain")
    convert.convert(boss.user, holiday, sick(), MON, MON + timedelta(days=1))
    holiday.refresh_from_db()
    assert (holiday.first_day, holiday.last_day, holiday.description) == (MON + timedelta(days=2), MON + timedelta(days=4), "Spain")
    assert Booking.objects.filter(person=sam, type__name="Holiday").count() == 1


def test_refusals(boss, sam):
    pending = bookings.request(sam.user, sam, make_type("Holiday"), MON, MON, "whole")
    with pytest.raises(LeaveError):
        convert.check(pending, sick(), MON, MON)
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON + timedelta(days=1), MON + timedelta(days=2), "whole")
    with pytest.raises(LeaveError):
        convert.check(holiday, sick(), MON, MON + timedelta(days=1))              # outside the booking
    with pytest.raises(LeaveError):
        convert.check(holiday, make_type("Training"), MON + timedelta(days=1), MON + timedelta(days=1))   # not sickness
    training = bookings.book(boss.user, sam, make_type("Training"), MON + timedelta(days=3), MON + timedelta(days=3), "whole")
    with pytest.raises(LeaveError):
        convert.check(training, sick(), MON + timedelta(days=3), MON + timedelta(days=3))   # not annual leave
    assert convert.eligible(holiday) and not convert.eligible(training) and not convert.eligible(pending)
    assert convert.hours_back(holiday, MON + timedelta(days=1), MON + timedelta(days=1)) == 27000


def test_the_dialog_previews_then_converts(boss, sam, today):
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON, MON + timedelta(days=4), "whole")
    today(MON + timedelta(days=9))                  # the sick days fall inside the rolling six months
    c = Client()
    c.force_login(boss.user)
    body = c.get(f"/time-off/{holiday.pk}/").content.decode()
    assert f'href="/time-off/{holiday.pk}/convert/"' in body
    r = c.post(f"/time-off/{holiday.pk}/convert/", {"first_day": "2027-03-03", "last_day": "2027-03-04", "type": sick().pk, "note": "", "preview": "1"})
    assert r.status_code == 200 and "15 h" in r.content.decode() and "1 instance" in r.content.decode()
    r = c.post(f"/time-off/{holiday.pk}/convert/", {"first_day": "2027-03-03", "last_day": "2027-03-04", "type": sick().pk, "note": "called in"})
    assert r.json() == {"refresh": True}
    assert Booking.objects.filter(person=sam, type__sickness=True).count() == 1
    staff = Client()
    staff.force_login(sam.user)
    assert staff.get(f"/time-off/{holiday.pk}/convert/").status_code == 403


def test_a_booking_with_a_cancellation_requested_is_not_convertible(boss, sam):
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON, MON + timedelta(days=4), "whole")
    bookings.request_cancel(sam.user, holiday)
    holiday.refresh_from_db()
    assert holiday.status == "cancel_requested"
    assert not convert.eligible(holiday)
    with pytest.raises(LeaveError):
        convert.check(holiday, sick(), MON, MON)
    c = Client()
    c.force_login(boss.user)
    body = c.get(f"/time-off/{holiday.pk}/").content.decode()
    assert f"/time-off/{holiday.pk}/convert/" not in body
