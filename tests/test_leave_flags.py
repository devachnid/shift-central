"""LEAVE-14 / NOTIF-06 (the leaver flags) and LEAVE-29 / NOTIF-07 (the
return from a long absence): who is emailed, when, and once."""

import json
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.core import mail
from django.test import Client

from leave.services import bank_holidays, bookings, hours, leavers, returns
from people.models import Person
from people.services import health, hr_sync
from tests import clock
from tests.factories import make_allowance, make_booking, make_entry, make_person, make_sick, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(clock.LATE_2026)]
Y26 = date(2026, 1, 1)
BEFORE_LEAVING = date(2026, 10, 1)          # Sam leaves on 14 Oct: still ahead, and more than a week off
BH_TO_OCT = [date(2026, 1, 1), date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 4), date(2026, 5, 25), date(2026, 8, 31)]
FIXTURE = Path(__file__).parent / "fixtures" / "hr_people.json"


def h(text):
    return hours.from_hours(Decimal(text))


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss")
    make_user_for(boss, is_all_teams_manager=True)
    return boss


def rota(person, year=2026):
    day = date(year, 1, 1) - timedelta(weeks=4)
    while day.year <= year:
        if day.weekday() < 5:
            make_entry(person, day, start=time(9), finish=time(17), break_minutes=30)
        day += timedelta(days=1)


@pytest.fixture
def leaver(boss):
    """LV-07b: 37.5 h Mon–Fri, leaves Wed 14 Oct 2026; total 138.5 h."""
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), end_date=date(2026, 10, 14), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_user_for(sam)
    rota(sam)
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    for bh in BH_TO_OCT:
        bank_holidays.book(boss.user, sam, bh, h("7.5"))
    return sam


@pytest.mark.today(BEFORE_LEAVING)
def test_lv_07b_the_flag_names_the_hours_over_or_remaining(boss, leaver):
    bookings.book(boss.user, leaver, make_type("Holiday"), date(2026, 2, 2), date(2026, 2, 27), "whole")     # 20 days = 150 h
    year, s = leavers.figure(leaver)
    assert year == Y26 and s.annual_remaining == -h("11.5") and leavers.figure_text(s) == "11 h 30 min of annual leave over"
    assert leavers.flag(leaver) is True
    assert mail.outbox[-1].subject == "Sam Patel is leaving on 14 Oct 2026" and mail.outbox[-1].to == [boss.email]
    assert "11 h 30 min of annual leave over" in mail.outbox[-1].body
    leaver.refresh_from_db()
    assert leaver.leaver_flagged_for == date(2026, 10, 14) and leaver.leaver_week_flagged_for is None
    assert leavers.flag(leaver) is False and len(mail.outbox) == 1                       # same date: not again


@pytest.mark.today(BEFORE_LEAVING)
def test_lv_07b_remaining_and_the_bookings_after_the_leaving_date(boss, leaver):
    bookings.book(boss.user, leaver, make_type("Holiday"), date(2026, 2, 2), date(2026, 2, 23), "whole")     # 16 days = 120 h
    after = bookings.book(boss.user, leaver, make_type("Holiday"), date(2026, 10, 19), date(2026, 10, 20), "whole")
    year, s = leavers.figure(leaver)
    assert s.annual_remaining == h("18.5") - h("15") and leavers.after_leaving(leaver) == [after]
    leavers.flag(leaver)
    body = mail.outbox[-1].body
    assert "3 h 30 min of annual leave remaining" in body and "to shorten or cancel" in body and "19–20 Oct 2026" in body


def test_a_date_within_a_week_sends_one_email_that_covers_both(boss):
    sam = make_person(first_name="Sam", end_date=date(2026, 11, 6))
    make_allowance(sam, Y26, Decimal("100"), 0)
    assert leavers.flag(sam) is True
    sam.refresh_from_db()
    assert sam.leaver_week_flagged_for == date(2026, 11, 6) and leavers.week_flags() == 0 and len(mail.outbox) == 1


def test_a_date_already_past_is_announced_as_left_once(boss):
    sam = make_person(first_name="Sam", end_date=date(2026, 10, 14))
    make_allowance(sam, Y26, Decimal("100"), 0)
    assert leavers.flag(sam) is True
    assert [m.subject for m in mail.outbox] == ["Sam Patel left on 14 Oct 2026"] and mail.outbox[0].body.startswith("Sam Patel left on 14 Oct 2026.")
    sam.refresh_from_db()
    assert sam.leaver_flagged_for == sam.leaver_week_flagged_for == date(2026, 10, 14)
    assert leavers.week_flags() == 0 and leavers.flag(sam) is False and len(mail.outbox) == 1


def test_the_week_reminder_goes_once_seven_days_out(boss):
    sam = make_person(first_name="Sam", end_date=date(2026, 11, 20))
    make_allowance(sam, Y26, Decimal("100"), 0)
    leavers.flag(sam)
    assert leavers.week_flags(today=date(2026, 11, 12)) == 0            # eight days out
    assert leavers.week_flags(today=date(2026, 11, 13)) == 1 and mail.outbox[-1].subject == "Sam Patel leaves in a week, on 20 Nov 2026"
    assert leavers.week_flags(today=date(2026, 11, 14)) == 0
    sam.refresh_from_db()
    assert sam.leaver_week_flagged_for == date(2026, 11, 20)


def test_a_cleared_end_date_resets_the_flags_and_a_changed_one_is_announced_again(boss):
    sam = make_person(first_name="Sam", end_date=date(2026, 12, 18))
    make_allowance(sam, Y26, Decimal("100"), 0)
    leavers.flag(sam)
    sam.end_date = None
    sam.save()
    assert leavers.flag(sam) is False
    sam.refresh_from_db()
    assert sam.leaver_flagged_for is None
    sam.end_date = date(2026, 12, 11)
    sam.save()
    assert leavers.flag(sam) is True and len(mail.outbox) == 2


def test_the_hr_sync_flags_a_leaving_date_when_it_arrives_or_changes(boss):
    payload = json.loads(FIXTURE.read_text())

    class Fake:
        def __init__(self, p):
            self.p = p

        def people(self):
            return self.p["people"]

    hr_sync.sync(Fake(payload))
    sam = Person.objects.get(hr_employee_id=1)
    make_allowance(sam, Y26, Decimal("100"), 0)
    sent = len(mail.outbox)
    for rec in payload["people"]:
        if rec["id"] == 1:
            rec["employment"]["end"] = "2026-12-31"
    hr_sync.sync(Fake(payload))
    assert len(mail.outbox) == sent + 1 and "Sam Patel is leaving on 31 Dec 2026" == mail.outbox[-1].subject
    hr_sync.sync(Fake(payload))
    assert len(mail.outbox) == sent + 1
    sam.refresh_from_db()
    assert sam.leaver_flagged_for == date(2026, 12, 31)


@pytest.mark.today(BEFORE_LEAVING)
def test_the_statement_and_the_health_card_carry_the_leaver_line(boss, leaver):
    bookings.book(boss.user, leaver, make_type("Holiday"), date(2026, 10, 19), date(2026, 10, 19), "whole")
    c = Client()
    c.force_login(boss.user)
    body = c.get(f"/staff/{leaver.pk}/profile/?tab=hours").content.decode()
    assert "Leaves on 14 Oct 2026" in body and "of annual leave remaining" in body
    f = health.figures(boss.user)
    (row,) = [r for r in f["leaving_soon"] if r["person"] == leaver]
    assert row["after"] == 1 and "annual leave remaining" in row["text"]
    body = c.get("/staff/").content.decode()
    assert "Sam Patel" in body and "1 booking after" in body
    body = c.get("/time-off/?from=2026-10-01&to=2026-10-31").content.decode()
    assert "after leaving date" in body


def test_the_statement_says_left_for_a_date_already_past(boss, leaver):
    c = Client()
    c.force_login(boss.user)
    body = c.get(f"/staff/{leaver.pk}/profile/?tab=hours").content.decode()      # the suite clock is 2 Nov: 14 Oct is behind us
    assert "Left on 14 Oct 2026" in body and "Leaves on 14 Oct 2026" not in body


# --- returns ---------------------------------------------------------------------

def test_the_return_flag_goes_the_day_after_a_long_sickness_ends_once(boss):
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(sam, Y26, Decimal("172.5"), 0)
    long = make_sick(sam, date(2026, 9, 1), date(2026, 10, 2))      # 32 days
    make_sick(sam, date(2026, 10, 12), date(2026, 10, 16))          # short: never flagged
    assert returns.due(today=date(2026, 10, 2)) == []
    assert returns.due(today=date(2026, 10, 3)) == [long]
    assert returns.send(today=date(2026, 10, 3)) == 1
    assert mail.outbox[-1].subject == "Sam Patel is back after 5 weeks of Sick leave" and "172 h 30 min" in mail.outbox[-1].body
    assert returns.send(today=date(2026, 10, 4)) == 0
    long.refresh_from_db()
    assert long.return_flagged_at is not None


def test_family_leave_is_flagged_on_return_and_history_is_not(boss):
    sam = make_person(first_name="Sam")
    make_allowance(sam, Y26, Decimal("100"), 0)
    mat = make_booking(sam, date(2026, 3, 2), date(2026, 10, 30), type_name="Maternity")
    old = make_booking(sam, date(2025, 1, 6), date(2025, 9, 26), type_name="Maternity")
    make_sick(sam, date(2026, 8, 3), date(2026, 9, 25), dates_only=True)
    assert set(returns.due(today=date(2026, 11, 2))) == {mat}        # the dates-only one and last year's are not due
    assert returns.send(today=date(2026, 11, 2)) == 1 and "Maternity" in mail.outbox[-1].subject
    old.refresh_from_db()
    assert old.return_flagged_at is None


def test_a_leaver_is_not_flagged_on_return(boss):
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), end_date=date(2026, 10, 2))
    make_sick(sam, date(2026, 9, 1), date(2026, 10, 2))
    assert returns.due(today=date(2026, 10, 3)) == []


def test_one_failing_person_stops_neither_the_week_reminders_nor_the_returns(boss, monkeypatch):
    ann = make_person(first_name="Ann", start_date=date(2020, 1, 6), end_date=date(2026, 11, 20))
    zed = make_person(first_name="Zed", start_date=date(2020, 1, 6), end_date=date(2026, 11, 20))
    for p in (ann, zed):
        make_allowance(p, Y26, Decimal("100"), 0)
    real = leavers.balances.statement

    def flaky(person, year):
        if person == ann:
            raise RuntimeError("broken")
        return real(person, year)

    monkeypatch.setattr(leavers.balances, "statement", flaky)
    assert leavers.week_flags(today=date(2026, 11, 13)) == 1 and "Zed" in mail.outbox[-1].subject
    ann.refresh_from_db()
    assert ann.leaver_week_flagged_for is None                       # not claimed, so tomorrow's run tries again
    monkeypatch.setattr(leavers.balances, "statement", real)
    assert leavers.week_flags(today=date(2026, 11, 14)) == 1 and "Ann" in mail.outbox[-1].subject

    a_sick = make_sick(make_person(first_name="Amy", start_date=date(2020, 1, 6)), date(2026, 9, 1), date(2026, 10, 2))
    z_sick = make_sick(make_person(first_name="Zoe", start_date=date(2020, 1, 6)), date(2026, 9, 1), date(2026, 10, 2))

    def flaky_return(person, year):
        if person == a_sick.person:
            raise RuntimeError("broken")
        return real(person, year)

    monkeypatch.setattr(returns.balances, "statement", flaky_return)
    assert returns.send(today=date(2026, 10, 3)) == 1 and "Zoe" in mail.outbox[-1].subject
    a_sick.refresh_from_db()
    z_sick.refresh_from_db()
    assert a_sick.return_flagged_at is None and z_sick.return_flagged_at is not None


def test_a_failed_leaver_flag_shows_on_the_sync_line(boss, monkeypatch):
    payload = json.loads(FIXTURE.read_text())

    class Fake:
        def people(self):
            return payload["people"]

    hr_sync.sync(Fake())
    for rec in payload["people"]:
        if rec["id"] == 1:
            rec["employment"]["end"] = "2026-12-31"

    def broken(person, base_url=""):
        raise RuntimeError("broken")

    monkeypatch.setattr(leavers, "flag", broken)
    run = hr_sync.sync(Fake())
    assert run.ok and run.message == "leaver flag failed; see the journal"
    c = Client()
    c.force_login(boss.user)
    assert "leaver flag failed; see the journal" in c.get("/staff/").content.decode()
