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
