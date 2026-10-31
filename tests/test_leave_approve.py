"""Waiting for approval and its decisions; the statement and its two
pop-ups; the own-leave flag; the Activity log."""

from datetime import date, time
from decimal import Decimal

import pytest
from django.test import Client

from leave.models import Adjustment, Booking
from leave.services import bookings
from people.models import Allowance, AuditEntry
from tests import clock
from tests.factories import make_allowance, make_entry, make_person, make_team, make_team_manager, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(clock.LATE_2026)]    # set on the 2026-27 calendar
MON, TUE = date(2027, 3, 1), date(2027, 3, 2)
Y27 = date(2027, 1, 1)


def _client(person, **kw):
    c = Client()
    c.force_login(person.user or make_user_for(person, **kw))
    return c


@pytest.fixture
def team():
    return make_team("Reception")


@pytest.fixture
def lead(team):
    lead = make_person(first_name="Lead", team=team)
    make_user_for(lead)
    make_team_manager(lead, team)
    return lead


@pytest.fixture
def sam(team):
    sam = make_person(first_name="Sam", team=team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_user_for(sam)
    make_allowance(sam, Y27, Decimal("172.5"), 60)
    make_entry(sam, MON, start=time(9), finish=time(17), break_minutes=30)
    return sam


def test_waiting_for_approval_lists_my_peoples_requests_oldest_first(sam, lead):
    b = bookings.request(sam.user, sam, make_type("Holiday"), MON, MON, "whole", note="dentist")
    other = make_person(first_name="Nur", team=make_team("Nursing"))
    make_user_for(other)
    make_allowance(other, Y27, 100, 30)
    make_entry(other, TUE, start=time(9), finish=time(17))
    bookings.request(other.user, other, make_type("Holiday"), TUE, TUE, "whole")
    body = _client(lead).get("/time-off/approve/").content.decode()
    assert "Sam Patel" in body and "Nur Patel" not in body and "dentist" in body and f"/time-off/{b.pk}/decide/" in body
    assert _client(sam).get("/time-off/approve/").status_code == 403


def test_waiting_for_approval_is_oldest_first(sam, lead):
    first = bookings.request(sam.user, sam, make_type("Holiday"), TUE, TUE, "whole")
    second = bookings.request(sam.user, sam, make_type("Holiday"), MON, MON, "whole")
    body = _client(lead).get("/time-off/approve/").content.decode()
    assert body.index(f"/time-off/{first.pk}/decide/") < body.index(f"/time-off/{second.pk}/decide/")


def test_the_decision_dialog_approves_or_declines_with_a_note(sam, lead):
    b = bookings.request(sam.user, sam, make_type("Holiday"), MON, MON, "whole")
    c = _client(lead)
    body = c.get(f"/time-off/{b.pk}/decide/").content.decode()
    assert "7 h 30 min" in body and "Balance" in body and "Approve" in body and "Decline" in body
    assert c.post(f"/time-off/{b.pk}/decide/", {"decision": "decline", "note": "short staffed"}).json() == {"refresh": True}
    b.refresh_from_db()
    assert b.status == "declined" and b.manager_note == "short staffed"
    b2 = bookings.request(sam.user, sam, make_type("Holiday"), TUE, TUE, "whole")
    assert c.post(f"/time-off/{b2.pk}/decide/", {"decision": "approve"}).json() == {"refresh": True}
    assert Booking.objects.get(pk=b2.pk).status == "approved"


def test_a_cancellation_request_is_decided_in_the_same_dialog(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    bookings.request_cancel(sam.user, b)
    c = _client(lead)
    body = c.get("/time-off/approve/").content.decode()
    assert "asked to cancel" in body
    body = c.get(f"/time-off/{b.pk}/decide/").content.decode()
    assert "Approve cancellation" in body and "Refuse cancellation" in body and "7 h 30 min" in body
    assert c.post(f"/time-off/{b.pk}/decide/", {"decision": "approve"}).json() == {"refresh": True}
    assert Booking.objects.get(pk=b.pk).status == "cancelled"


def test_only_a_manager_of_the_person_may_decide(sam, lead):
    b = bookings.request(sam.user, sam, make_type("Holiday"), MON, MON, "whole")
    nina = make_person(first_name="Nina", team=lead.team)
    assert _client(nina).get(f"/time-off/{b.pk}/decide/").status_code == 403
    assert _client(sam).post(f"/time-off/{b.pk}/decide/", {"decision": "approve"}).status_code == 403
    assert Booking.objects.get(pk=b.pk).status == "pending"


def test_the_statement_is_on_the_pay_and_time_off_tab_and_on_my_leave(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    body = _client(lead).get(f"/staff/{sam.pk}/profile/?tab=hours").content.decode()
    assert "Annual leave remaining" in body and "225 h" in body and "Adjust…" in body and "Add hours change…" in body
    body = _client(sam).get("/time-off/mine/").content.decode()
    assert "225 h" in body and "Adjust…" not in body
    body = _client(sam).get(f"/staff/{sam.pk}/profile/?tab=hours").content.decode()
    assert "Annual leave remaining" in body and "Adjust…" not in body
    nina = make_person(first_name="Nina", team=lead.team)
    assert _client(nina).get(f"/staff/{sam.pk}/profile/?tab=hours").status_code == 403


def test_the_statement_switches_year(sam, lead):
    body = _client(lead).get(f"/staff/{sam.pk}/profile/?tab=hours&year=2027-01-01").content.decode()
    assert 'name="year"' in body and "225 h" not in body and "232 h 30 min" in body
    # a year that is not one of the person's two is ignored
    assert _client(lead).get(f"/staff/{sam.pk}/profile/?tab=hours&year=1999-01-01").status_code == 200


def test_the_adjust_dialog_writes_a_logged_adjustment(sam, lead):
    c = _client(lead)
    body = c.get(f"/staff/{sam.pk}/leave/adjust/").content.decode()
    assert 'name="hours"' in body and 'name="reason"' in body
    r = c.post(f"/staff/{sam.pk}/leave/adjust/", {"leave_year": "2027-01-01", "account": "annual", "hours": "15:00", "reason": "carried over from FindMyShift 2026"})
    assert r.json() == {"refresh": True}
    assert Adjustment.objects.get().seconds == 54000
    body = c.post(f"/staff/{sam.pk}/leave/adjust/", {"leave_year": "2027-01-01", "account": "annual", "hours": "-2:30", "reason": ""}).content.decode()
    assert "reason" in body.lower() and Adjustment.objects.count() == 1


def test_the_adjust_dialog_takes_hours_away_and_refuses_zero(sam, lead):
    c = _client(lead)
    for text, seconds in (("-2:30", -9000), ("−1.5", -5400)):
        assert c.post(f"/staff/{sam.pk}/leave/adjust/", {"leave_year": "2027-01-01", "account": "annual", "hours": text, "reason": "correction"}).json() == {"refresh": True}
        assert Adjustment.objects.latest("pk").seconds == seconds
    body = c.post(f"/staff/{sam.pk}/leave/adjust/", {"leave_year": "2027-01-01", "account": "annual", "hours": "0:00", "reason": "nothing"}).content.decode()
    assert "Type the hours" in body and Adjustment.objects.count() == 2
    nina = make_person(first_name="Nina", team=lead.team)
    assert _client(nina).get(f"/staff/{sam.pk}/leave/adjust/").status_code == 403


def test_the_hours_change_dialog_adds_a_dated_allowance_row(sam, lead):
    c = _client(lead)
    assert "from_day" in c.get(f"/staff/{sam.pk}/leave/hours-change/").content.decode()
    r = c.post(f"/staff/{sam.pk}/leave/hours-change/", {"from_day": "2027-07-01", "weekly_hours": "30", "days_per_week": "5",
                                                      "annual_hours": "138", "bank_holiday_hours": "48", "note": "part time from July"})
    assert r.json() == {"refresh": True}
    row = Allowance.objects.get(person=sam, from_day=date(2027, 7, 1))
    assert row.weekly_hours == Decimal("30.00") and AuditEntry.objects.filter(object_id=row.pk, note="part time from July").exists()


def test_an_hours_change_the_service_refuses_is_shown_in_the_dialog(sam, lead):
    body = _client(lead).post(f"/staff/{sam.pk}/leave/hours-change/", {"from_day": "2027-01-01", "weekly_hours": "30", "days_per_week": "5",
                                                                     "annual_hours": "138", "bank_holiday_hours": "48", "note": "x"}).content.decode()
    assert "starts after the year" in body or "change starts after" in body


def test_the_own_leave_flag_is_set_on_the_permissions_page_by_an_all_teams_manager(lead):
    boss = make_person(first_name="Boss")
    c = _client(boss, is_all_teams_manager=True)
    body = c.get(f"/staff/{lead.pk}/permissions/").content.decode()
    assert 'name="own_leave_without_approval"' in body
    c.post(f"/staff/{lead.pk}/permissions/", {"teams": [lead.team.pk], "own_leave_without_approval": "on"})
    lead.refresh_from_db()
    assert lead.own_leave_without_approval
    assert AuditEntry.objects.filter(model="people.person", object_id=lead.pk, field="own_leave_without_approval", after="True").exists()
    c.post(f"/staff/{lead.pk}/permissions/", {"teams": [lead.team.pk]})
    lead.refresh_from_db()
    assert not lead.own_leave_without_approval


def test_the_own_leave_flag_can_be_set_for_an_all_teams_person_too():
    boss = make_person(first_name="Boss")
    other = make_person(first_name="Other")
    make_user_for(other, is_all_teams_manager=True)
    c = _client(boss, is_all_teams_manager=True)
    body = c.get(f"/staff/{other.pk}/permissions/").content.decode()
    assert "set in Practice HR" in body and 'name="own_leave_without_approval"' in body
    c.post(f"/staff/{other.pk}/permissions/", {"own_leave_without_approval": "on"})
    other.refresh_from_db()
    assert other.own_leave_without_approval


def test_the_leave_year_start_is_on_the_profile_and_refuses_to_move_a_year_with_bookings(sam, lead):
    c = _client(lead)
    r = c.post(f"/staff/{sam.pk}/profile/?tab=hours", {"weekly_hours": "37.5", "days_per_week": "5", "leave_year_start": "04-01", "note": ""})
    assert r.status_code == 200 and "already has" in r.content.decode()      # the 2027 allowance would move
    sam.refresh_from_db()
    assert sam.leave_year_start == "01-01"
    sam.allowances.all().delete()
    c.post(f"/staff/{sam.pk}/profile/?tab=hours", {"weekly_hours": "37.5", "days_per_week": "5", "leave_year_start": "04-01", "note": ""})
    sam.refresh_from_db()
    assert sam.leave_year_start == "04-01"


def test_a_year_start_that_is_not_a_date_is_refused(sam, lead):
    sam.allowances.all().delete()
    body = _client(lead).post(f"/staff/{sam.pk}/profile/?tab=hours", {"weekly_hours": "37.5", "days_per_week": "5", "leave_year_start": "02-30", "note": ""}).content.decode()
    sam.refresh_from_db()
    assert sam.leave_year_start == "01-01" and "field-error" in body


def test_the_activity_log_and_history_show_leave_rows(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    c = _client(lead)
    body = c.get("/activity/").content.decode()
    assert "Sam Patel" in body
    assert "Holiday 1 Mar 2027, whole day, 7 h 30 min, approved" in body
    body = c.get(f"/staff/{sam.pk}/history/").content.decode()
    assert "Holiday 1 Mar 2027" in body and "booking" in body and "leave.booking" not in body


def test_the_activity_log_shows_adjustments_for_my_people_only(sam, lead):
    from leave.services import adjustments
    adjustments.add(lead.user, sam, Y27, "annual", 3600, "carried over")
    other = make_person(first_name="Nur", team=make_team("Nursing"))
    boss = make_person(first_name="Boss")
    adjustments.add(make_user_for(boss, is_all_teams_manager=True), other, Y27, "annual", 7200, "elsewhere")
    body = _client(lead).get("/activity/").content.decode()
    assert "carried over" in body and "elsewhere" not in body
    body = _client(lead).get(f"/activity/?person={sam.pk}").content.decode()
    assert "carried over" in body
    body = _client(lead).get(f"/staff/{sam.pk}/history/").content.decode()
    assert "carried over" in body and "adjustment" in body


# --- the negative-balance email after an hours change ------------------------

HOURS_CHANGE = {"from_day": "2027-07-01", "weekly_hours": "30", "days_per_week": "5",
                "annual_hours": "138", "bank_holiday_hours": "48", "note": "part time from July"}


def test_an_hours_change_that_leaves_the_balance_negative_emails_the_managers(sam, lead):
    from django.core import mail

    from leave.services import adjustments
    adjustments.add(lead.user, sam, Y27, "annual", -(230 * 3600), "used elsewhere")
    mail.outbox.clear()
    assert _client(lead).post(f"/staff/{sam.pk}/leave/hours-change/", HOURS_CHANGE).json() == {"refresh": True}
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [lead.email] and mail.outbox[0].subject == "Sam Patel's leave balance is negative"


def test_an_hours_change_that_leaves_the_balance_positive_sends_no_email(sam, lead):
    from django.core import mail
    mail.outbox.clear()
    assert _client(lead).post(f"/staff/{sam.pk}/leave/hours-change/", HOURS_CHANGE).json() == {"refresh": True}
    assert mail.outbox == []


def test_a_refused_hours_change_sends_no_email(sam, lead):
    from django.core import mail

    from leave.services import adjustments
    adjustments.add(lead.user, sam, Y27, "annual", -(230 * 3600), "used elsewhere")
    mail.outbox.clear()
    r = _client(lead).post(f"/staff/{sam.pk}/leave/hours-change/", {**HOURS_CHANGE, "note": ""})
    assert r.status_code == 200 and mail.outbox == [] and Allowance.objects.filter(person=sam).count() == 1
    # the service's own refusal (a change on the year's first day) is shown and sends nothing either
    r = _client(lead).post(f"/staff/{sam.pk}/leave/hours-change/", {**HOURS_CHANGE, "from_day": "2027-01-01"})
    assert r.status_code == 200 and mail.outbox == [] and Allowance.objects.filter(person=sam).count() == 1


# --- a leave year that does not start on 1 January ---------------------------

def test_allowances_typed_with_a_new_year_start_land_under_the_new_years(team, lead):
    from django.utils import timezone

    from leave.services import balances, years
    from people.services import health
    ann = make_person(first_name="Ann", team=team, weekly_hours=Decimal("37.5"), days_per_week=5)
    c = _client(lead)
    this = years.years_for(type("P", (), {"leave_year_start": "04-01"})())
    body = c.get(f"/staff/{ann.pk}/profile/?tab=hours").content.decode()
    assert 'name="leave_year_start"' in body
    data = {"weekly_hours": "37.5", "days_per_week": "5", "leave_year_start": "04-01", "note": "",
            f"annual_{this[0].year}": "187.5", f"bank_holiday_{this[0].year}": "60",
            f"annual_{this[1].year}": "187.5", f"bank_holiday_{this[1].year}": "60"}
    r = c.post(f"/staff/{ann.pk}/profile/?tab=hours", data)
    assert r.status_code == 200 and "Saved" in r.content.decode()
    ann.refresh_from_db()
    assert ann.leave_year_start == "04-01"
    assert set(Allowance.objects.filter(person=ann).values_list("leave_year", flat=True)) == set(this)
    assert this[0].month == 4 and this[0].day == 1
    today = timezone.localdate()
    assert not balances.statement(ann, years.year_of(ann, today)).missing
    # the form now names the years by their first day
    body = c.get(f"/staff/{ann.pk}/profile/?tab=hours").content.decode()
    assert f"Annual leave allowance from 1 Apr {this[0].year}" in body
    assert ann not in health.figures(lead.user)["needs_setup"]
    # the Health card lists the person when no allowance is near
    Allowance.objects.filter(person=ann).delete()
    assert ann in health.figures(lead.user)["needs_setup"]


# --- typed hours: two shapes only, and bounded (S12)

@pytest.mark.parametrize("text, seconds", [("7:30", 27000), ("0:45", 2700), ("7.5", 27000), ("7.5h", 27000), ("7.5 h", 27000),
                                           (" 7 ", 25200), ("7h", 25200), ("12", 43200), ("", None)])
def test_hours_are_typed_as_h_mm_or_decimal_hours(text, seconds):
    from leave.forms import parse_hours
    assert parse_hours(text) == seconds


@pytest.mark.parametrize("text", ["7h30", "1e3", "9e999999", "7:5", "7:60", "1234:00", "-1", "+2", "7.5.5", ".5", "7,5", "h", "NaN", "Infinity", "٣"])
def test_any_other_shape_of_hours_is_refused(text):
    from django import forms

    from leave.forms import parse_hours
    with pytest.raises(forms.ValidationError) as e:
        parse_hours(text)
    assert e.value.messages == ["Type hours as 7:30 or 7.5"]


def test_a_typed_day_cost_is_read_or_refused_never_a_server_error(sam, lead):
    c = _client(lead)
    base = {"person": sam.pk, "type": make_type("Holiday").pk, "first_day": MON, "last_day": MON, "part": "whole"}
    for text, message in (("9e999999", f"Could not read the hours for {MON}"), ("7h30", f"Could not read the hours for {MON}"),
                          ("24:30", f"A day has 24 hours: check the hours for {MON}")):
        r = c.post("/time-off/add/", {**base, f"cost_{MON}": text})
        assert r.status_code == 200 and message in r.content.decode()
    assert not Booking.objects.exists()
    assert c.post("/time-off/add/", {**base, f"cost_{MON}": "24:00"}).json() == {"refresh": True}


def test_an_adjustment_is_bounded_and_a_bad_figure_is_a_form_error(sam, lead):
    c = _client(lead)
    url = f"/staff/{sam.pk}/leave/adjust/"
    data = {"leave_year": "2027-01-01", "account": "annual", "reason": "correction"}
    for text in ("9e999999", "7h30", "2000:30", "-2001"):
        r = c.post(url, {**data, "hours": text})
        assert r.status_code == 200 and "refresh" not in r.content.decode()
    assert "An adjustment is at most 2000 hours either way" in c.post(url, {**data, "hours": "-2000.5"}).content.decode()
    assert not Adjustment.objects.exists()
    assert c.post(url, {**data, "hours": "-2000"}).json() == {"refresh": True}


def test_the_everyone_page_refuses_a_bad_figure_without_a_server_error(sam, lead):
    from tests.factories import make_bank_holiday
    day = date(2027, 5, 3)
    make_bank_holiday(day, "Early May bank holiday")
    boss = make_person(first_name="Boss")
    c = _client(boss, is_all_teams_manager=True)
    r = c.post(f"/time-off/bank-holidays/{day}/everyone/", {f"tick_{sam.pk}": "on", f"hours_{sam.pk}": "9e999999"})
    assert r.status_code == 200 and "Type hours as 7:30 or 7.5" in r.content.decode()


# --- nobody sets "Own leave needs no approval" on themselves (S14)

def test_an_all_teams_manager_cannot_tick_their_own_leave_flag():
    boss = make_person(first_name="Boss")
    c = _client(boss, is_all_teams_manager=True)
    body = c.get(f"/staff/{boss.pk}/permissions/").content.decode()
    assert 'name="own_leave_without_approval"' not in body
    assert "Another all-teams manager sets this for you" in body
    c.post(f"/staff/{boss.pk}/permissions/", {"own_leave_without_approval": "on"})
    boss.refresh_from_db()
    assert not boss.own_leave_without_approval
    assert not AuditEntry.objects.filter(field="own_leave_without_approval").exists()


def test_the_service_refuses_the_own_leave_flag_on_oneself():
    from django.core.exceptions import PermissionDenied

    from people.services import managers
    boss = make_person(first_name="Boss")
    user = make_user_for(boss, is_all_teams_manager=True)
    with pytest.raises(PermissionDenied):
        managers.set_own_leave_flag(user, boss, True)
    boss.refresh_from_db()
    assert not boss.own_leave_without_approval


def test_a_self_set_flag_is_kept_when_the_dialog_is_saved():
    """A flag another manager set stands when the person saves their own dialog."""
    boss = make_person(first_name="Boss", own_leave_without_approval=True)
    c = _client(boss, is_all_teams_manager=True)
    c.post(f"/staff/{boss.pk}/permissions/", {})
    boss.refresh_from_db()
    assert boss.own_leave_without_approval
