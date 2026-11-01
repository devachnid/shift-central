"""Sickness as LEAVE-40 to 44 define it, over Sick leave bookings: the
rolling window, instances, triggers and their email, long sickness, the
join-on rule, and dates-only entries from the past schedule section."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.core import mail

from leave.models import Booking, BookingDay
from leave.services import balances, bookings, feed, sickness
from leave.services.common import LeaveError
from people.models import AuditEntry
from tests.factories import make_allowance, make_entry, make_gp_session, make_person, make_sick, make_type, make_user_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss")
    make_user_for(boss, is_all_teams_manager=True)
    return boss


def sick_type():
    return make_type("Sick leave", requestable=False, sickness=True)


def sent():
    """The emails sent, less the "Leave cost to check" notices a booking on a
    person with no rota rightly sends (LEAVE-06): these tests are about the
    trigger email."""
    return [m for m in mail.outbox if not m.subject.startswith("Leave cost to check")]


def test_the_window_is_six_months_back_plus_a_day():
    assert sickness.window(date(2026, 7, 1)) == (date(2026, 1, 2), date(2026, 7, 1))        # SICK-01
    assert sickness.window(date(2026, 8, 31)) == (date(2026, 3, 1), date(2026, 8, 31))      # 28 Feb clamped, plus a day
    assert sickness.window(date(2027, 3, 30)) == (date(2026, 10, 1), date(2027, 3, 30))     # 30 Sep, plus a day
    assert sickness.window(date(2026, 1, 15)) == (date(2025, 7, 16), date(2026, 1, 15))


def test_levels():
    assert [sickness.level(n) for n in range(7)] == [0, 0, 0, 1, 2, 3, 3]
    assert sickness.level_label(0) == "" and sickness.level_label(1) == "Trigger 1" and sickness.level_label(3) == "Trigger 3+"


@pytest.mark.today(date(2026, 7, 1))
def test_sick_01_rolling_six_months_four_instances_trigger_2(boss):
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6))
    make_sick(sam, date(2025, 12, 20), date(2026, 1, 5))        # A: ends inside the window, counts
    make_sick(sam, date(2026, 2, 10))                           # B
    make_sick(sam, date(2026, 4, 20))                           # C
    make_sick(sam, date(2025, 6, 1), date(2025, 6, 3))          # before the window: does not count
    make_sick(sam, date(2026, 5, 1), status="cancelled")        # cancelled: does not count
    assert len(sickness.instances(sam)) == 3 and sickness.level_for(sam) == 1
    bookings.book(boss.user, sam, sick_type(), date(2026, 6, 15), date(2026, 6, 15), "whole")    # D
    rows = sickness.instances(sam)
    assert [b.first_day for b in rows] == [date(2025, 12, 20), date(2026, 2, 10), date(2026, 4, 20), date(2026, 6, 15)]
    assert sickness.level_for(sam) == 2
    assert [m.subject for m in sent()] == ["Sam Patel has reached Trigger 2"]
    assert "4 instances" in sent()[0].body and "20 Dec 2025" in sent()[0].body
    assert AuditEntry.objects.filter(model="leave.booking", object_id=sam.pk, note__contains="Trigger 2 reached").exists()


@pytest.mark.today(date(2026, 7, 1))
def test_the_trigger_email_goes_once_per_level_reached_and_never_on_the_way_down(boss):
    sam = make_person(first_name="Sam")
    for d in (date(2026, 2, 1), date(2026, 3, 1)):
        bookings.book(boss.user, sam, sick_type(), d, d, "whole")
    assert sent() == []
    third = bookings.book(boss.user, sam, sick_type(), date(2026, 4, 1), date(2026, 4, 1), "whole")
    assert [m.subject for m in sent()] == ["Sam Patel has reached Trigger 1"]
    bookings.edit(boss.user, third, first=date(2026, 4, 2), last=date(2026, 4, 3))      # still three: no mail
    assert len(sent()) == 1
    bookings.cancel(boss.user, third)
    assert len(sent()) == 2 and "cancelled" in sent()[1].subject       # the person's cancel mail only
    bookings.book(boss.user, sam, sick_type(), date(2026, 5, 1), date(2026, 5, 1), "whole")    # back to three: Trigger 1 again
    assert sent()[-1].subject == "Sam Patel has reached Trigger 1"


def test_sick_02_long_sickness_is_twenty_nine_days():
    sam = make_person()
    assert not sickness.is_long(make_sick(sam, date(2026, 6, 1), date(2026, 6, 28)))
    assert sickness.is_long(make_sick(sam, date(2026, 7, 1), date(2026, 7, 29)))
    assert sickness.is_long(make_sick(sam, date(2026, 8, 1), date(2026, 9, 1)))


def test_sick_04_entries_that_join_on():
    sam = make_person()
    day = date(2025, 12, 29)
    while day <= date(2026, 1, 31):               # Mon–Fri rota through January
        if day.weekday() < 5:
            make_entry(sam, day, start=time(9), finish=time(17))
        day += timedelta(days=1)
    a = make_sick(sam, date(2026, 1, 1), date(2026, 1, 5))
    assert sickness.joins_on(sam, date(2026, 1, 6), date(2026, 1, 13)) == a            # (a) adjacent
    b = make_sick(sam, date(2026, 1, 20), date(2026, 1, 23))                            # Tue–Fri 23 Jan
    assert sickness.joins_on(sam, date(2026, 1, 26), date(2026, 1, 27)) == b           # (b) only a weekend between
    assert sickness.joins_on(sam, date(2026, 1, 28), date(2026, 1, 28)) is None         # Tue 27 Jan is worked
    assert sickness.joins_on(sam, date(2026, 1, 15), date(2026, 1, 16)) is None         # worked days either side
    assert sickness.joins_on(sam, date(2026, 1, 14), date(2026, 1, 19)) == b            # before b, Mon 19 → Tue 20 adjacent
    assert sickness.joins_on(sam, date(2026, 1, 26), date(2026, 1, 27), exclude=b) is None


def test_the_join_on_rule_treats_a_rota_less_day_as_not_worked_and_stops_at_a_week():
    sam = make_person()
    a = make_sick(sam, date(2026, 3, 2), date(2026, 3, 6))
    assert sickness.joins_on(sam, date(2026, 3, 12), date(2026, 3, 12)) == a           # 7–11 Mar, no rota: not worked
    assert sickness.joins_on(sam, date(2026, 3, 16), date(2026, 3, 16)) is None         # nine days between: never joins
    make_gp_session(sam, date(2026, 3, 9))
    assert sickness.joins_on(sam, date(2026, 3, 12), date(2026, 3, 12)) is None         # a session is work


@pytest.mark.today(date(2027, 1, 15))
def test_a_dates_only_entry_has_no_days_covers_nothing_and_skips_the_year_rule(boss):
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(sam, date(2027, 1, 1), Decimal("172.5"), 0)       # no bank holiday allowance: remaining is the plain 172.5 h
    shift = make_entry(sam, date(2026, 7, 6), start=time(9), finish=time(17))
    row = bookings.book(boss.user, sam, sick_type(), date(2026, 7, 6), date(2026, 7, 10), "whole", dates_only=True)   # last year: allowed
    assert row.status == "approved" and row.dates_only and not BookingDay.objects.filter(booking=row).exists()
    shift.refresh_from_db()
    assert shift.covered_by is None
    assert mail.outbox == []
    assert sickness.instances(sam, date(2026, 7, 20)) == [row]
    assert balances.statement(sam, date(2027, 1, 1)).annual_remaining == 621000
    assert AuditEntry.objects.filter(object_id=sam.pk, note="dates only (past schedule)").exists()
    with pytest.raises(LeaveError):
        bookings.book(boss.user, sam, sick_type(), date(2027, 1, 15), date(2027, 1, 15), "whole", dates_only=True)   # today: not past
    with pytest.raises(LeaveError):
        bookings.book(boss.user, sam, make_type("Holiday"), date(2026, 8, 3), date(2026, 8, 3), "whole", dates_only=True)   # not sickness
    bookings.edit(boss.user, row, last=date(2026, 7, 13))
    row.refresh_from_db()
    assert row.last_day == date(2026, 7, 13) and not BookingDay.objects.filter(booking=row).exists()
    with pytest.raises(LeaveError):
        bookings.edit(boss.user, row, part="am", first=date(2026, 7, 6), last=date(2026, 7, 6))
    with pytest.raises(LeaveError):
        bookings.book(boss.user, sam, sick_type(), date(2026, 8, 3), date(2026, 8, 3), "whole", dates_only=True, costs={date(2026, 8, 3): 3600})
    assert not Booking.objects.filter(person=sam, first_day=date(2026, 8, 3)).exists()
    before = len(mail.outbox)
    bookings.cancel(boss.user, row)
    row.refresh_from_db()
    assert row.status == "cancelled" and len(mail.outbox) == before


@pytest.mark.today(date(2027, 1, 15))
def test_a_dates_only_entry_never_emails_but_still_counts_towards_the_level(boss):
    sam = make_person(first_name="Sam")
    for d in (date(2026, 9, 7), date(2026, 10, 5), date(2026, 11, 2)):
        bookings.book(boss.user, sam, sick_type(), d, d, "whole", dates_only=True)
    assert sickness.level_for(sam) == 1 and mail.outbox == []
    assert AuditEntry.objects.filter(object_id=sam.pk, note__contains="Trigger 1 reached").exists()


def test_a_gps_dates_only_entry_is_in_the_feed():
    gp = make_person(first_name="Gail", is_gp=True, email="gail@example.org")
    make_sick(gp, date(2026, 5, 4), date(2026, 5, 6), dates_only=True)
    (rec,) = feed.records(date(2026, 5, 1), date(2026, 5, 31))
    assert rec == {"email": "gail@example.org", "first_day": "2026-05-04", "last_day": "2026-05-06", "part": "whole", "type": "Sick leave"}


def test_overlaps_window():
    assert sickness.overlaps_window(date(2026, 1, 1), date(2026, 1, 3), today=date(2026, 7, 1))
    assert not sickness.overlaps_window(date(2025, 12, 1), date(2026, 1, 1), today=date(2026, 7, 1))


@pytest.mark.today(date(2026, 7, 1))
def test_changing_a_booking_to_sick_leave_through_edit_reaches_the_trigger(boss):
    sam = make_person(first_name="Sam")
    for d in (date(2026, 2, 2), date(2026, 3, 2)):
        bookings.book(boss.user, sam, sick_type(), d, d, "whole")
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), date(2026, 4, 1), date(2026, 4, 1), "whole")
    assert sent() == [] and sickness.level_for(sam) == 0
    bookings.edit(boss.user, holiday, type=sick_type())
    assert sickness.level_for(sam) == 1
    assert [m.subject for m in sent()] == ["Sam Patel has reached Trigger 1"]
    assert AuditEntry.objects.filter(model="leave.booking", object_id=sam.pk, note__contains="Trigger 1 reached").exists()
