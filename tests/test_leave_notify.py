"""The reminder after N working days (REQ-13), once per request, and the
timer that runs it."""

import re
from datetime import date, datetime, timezone as tz
from pathlib import Path

import pytest
from django.core import mail
from django.core.management import call_command

from leave.models import Booking
from leave.services import reminders, settings as leave_settings
from tests import clock
from tests.factories import make_bank_holiday, make_booking, make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[1]


def test_working_days_skip_weekends_and_bank_holidays():
    make_bank_holiday(date(2027, 5, 3))
    assert reminders.working_days_between(date(2027, 4, 30), date(2027, 5, 5)) == 2      # Fri → Tue, Wed: Mon 3 May is a bank holiday
    assert reminders.working_days_between(date(2027, 3, 1), date(2027, 3, 1)) == 0


def test_a_request_waiting_three_working_days_is_reminded_once():
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_user_for(lead)
    make_team_manager(lead, team)
    sam = make_person(first_name="Sam", team=team)
    b = make_booking(sam, date(2027, 6, 1), status="pending")
    Booking.objects.filter(pk=b.pk).update(requested_at=datetime(2027, 3, 1, 9, tzinfo=tz.utc))     # a Monday
    assert reminders.due(now=datetime(2027, 3, 3, 9, tzinfo=tz.utc)) == []                        # two working days
    assert reminders.due(now=datetime(2027, 3, 4, 9, tzinfo=tz.utc)) == [b]                       # three
    assert reminders.send(now=datetime(2027, 3, 4, 9, tzinfo=tz.utc)) == 1
    assert mail.outbox[-1].to == [lead.email] and "still waiting" in mail.outbox[-1].subject
    assert reminders.send(now=datetime(2027, 3, 5, 9, tzinfo=tz.utc)) == 0
    s = leave_settings.get()
    s.reminder_working_days = 1
    s.save()
    b2 = make_booking(sam, date(2027, 7, 1), status="pending")
    Booking.objects.filter(pk=b2.pk).update(requested_at=datetime(2027, 3, 1, 9, tzinfo=tz.utc))
    assert reminders.due(now=datetime(2027, 3, 2, 9, tzinfo=tz.utc)) == [b2]


def test_the_command_and_its_units():
    call_command("leave_reminders")
    unit = (ROOT / "deploy" / "shift-central-leave-reminders.service").read_text()
    assert "manage.py leave_reminders" in unit and "EnvironmentFile=/etc/shift-central.env" in unit
    timer = (ROOT / "deploy" / "shift-central-leave-reminders.timer").read_text()
    assert re.search(r"OnCalendar=Mon\.\.Fri \*-\*-\* 08:20:00", timer) and "WantedBy=timers.target" in timer


# --- the emails of spec section 7 (S5, S8, S21) ----------------------------

@pytest.fixture
def office():
    """Sam in Reception, managed by Lead; Sam's Monday is rostered."""
    from datetime import time
    from decimal import Decimal

    from tests.factories import make_allowance, make_entry
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_user_for(lead)
    make_team_manager(lead, team)
    sam = make_person(first_name="Sam", team=team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_user_for(sam)
    make_allowance(sam, date(2027, 1, 1), Decimal("172.5"), 60)
    make_entry(sam, date(2027, 3, 1), start=time(9), finish=time(17), break_minutes=30)
    return lead, sam


def _holiday():
    from tests.factories import make_type
    return make_type("Holiday")


@pytest.mark.today(clock.LATE_2026)
def test_a_rota_write_mails_an_absolute_link_when_no_request_gave_one(office, settings, django_capture_on_commit_callbacks):
    """S5: entries._write passes no base URL; the link falls back to the
    first trusted origin, as the reminder command's does."""
    from leave.services import bookings
    from shifts.services import entries
    settings.CSRF_TRUSTED_ORIGINS = ["https://shifts.example.org"]
    lead, sam = office
    week = date(2027, 3, 15)
    bookings.book(lead.user, sam, _holiday(), week, week, "whole")       # an average day: the cost is to check
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        entries.set_cell(lead.user, sam, week, [{"kind": "shift", "start": "08:00", "finish": "16:00"}])
    body = next(m.body for m in mail.outbox if "Leave cost to check" in m.subject)
    assert f"Check it here: https://shifts.example.org/staff/{sam.pk}/profile/?tab=hours" in body


@pytest.mark.today(clock.LATE_2026)
def test_no_mail_goes_to_a_manager_who_has_left_or_cannot_sign_in(office):
    """S8: recipients are active users whose person is current."""
    from leave.services import bookings
    lead, sam = office
    gone = make_person(first_name="Gone", team=sam.team, start_date=date(2019, 1, 1), end_date=date(2026, 6, 30))
    make_user_for(gone)
    make_team_manager(gone, sam.team)
    off = make_person(first_name="Off", team=sam.team)
    make_user_for(off, is_active=False)
    make_team_manager(off, sam.team)
    boss = make_person(first_name="Boss", start_date=date(2019, 1, 1), end_date=date(2026, 1, 31))
    make_user_for(boss, is_all_teams_manager=True)
    bookings.request(sam.user, sam, _holiday(), date(2027, 3, 1), date(2027, 3, 1), "whole")
    assert [m.to for m in mail.outbox] == [[lead.email]]


@pytest.mark.today(clock.LATE_2026)
def test_the_declined_email(office):
    from leave.services import bookings
    lead, sam = office
    b = bookings.request(sam.user, sam, _holiday(), date(2027, 3, 1), date(2027, 3, 1), "whole")
    mail.outbox.clear()
    bookings.decline(lead.user, b, "Two of the team are off already", base_url="https://shifts.example.org/")
    [m] = mail.outbox
    assert m.to == [sam.email] and m.subject == "Your time off has been declined"
    assert "Your Holiday for 1 Mar 2027 has been declined." in m.body
    assert "Note from your manager: Two of the team are off already" in m.body
    assert "https://shifts.example.org/time-off/mine/" in m.body


@pytest.mark.today(clock.LATE_2026)
def test_the_cancellation_requested_email(office):
    from leave.services import bookings
    lead, sam = office
    b = bookings.book(lead.user, sam, _holiday(), date(2027, 3, 1), date(2027, 3, 1), "whole", description="private trip")
    mail.outbox.clear()
    bookings.request_cancel(sam.user, b, "my plans changed", base_url="https://shifts.example.org/")
    [m] = mail.outbox
    assert m.to == [lead.email] and m.subject == "Sam Patel has asked to cancel time off"
    assert "Sam Patel has asked to cancel Holiday for 1 Mar 2027." in m.body
    assert "https://shifts.example.org/time-off/approve/" in m.body
    assert "private trip" not in m.body and "my plans changed" not in m.body


@pytest.mark.today(clock.LATE_2026)
@pytest.mark.parametrize("approve, word", [(True, "cancelled"), (False, "kept")])
def test_the_cancellation_decided_email(office, approve, word):
    from leave.services import bookings
    lead, sam = office
    b = bookings.book(lead.user, sam, _holiday(), date(2027, 3, 1), date(2027, 3, 1), "whole")
    bookings.request_cancel(sam.user, b, "")
    mail.outbox.clear()
    bookings.decide_cancel(lead.user, b, approve, "", base_url="https://shifts.example.org/")
    [m] = mail.outbox
    assert m.to == [sam.email] and m.subject == f"Your time off has been {word}"
    assert f"Your Holiday for 1 Mar 2027 has been {word}." in m.body
    assert "https://shifts.example.org/time-off/mine/" in m.body
