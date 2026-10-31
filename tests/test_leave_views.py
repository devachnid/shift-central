"""The Time off screens by role (spec section 6): list, add, request, my
leave, view and cancel; ACC-05's type-only rule for colleagues."""

from datetime import date, time
from decimal import Decimal

import pytest
from django.test import Client

from leave.models import Booking
from leave.services import bookings
from tests.factories import make_allowance, make_entry, make_person, make_team, make_team_manager, make_type, make_user_for

pytestmark = pytest.mark.django_db
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
    for d in (MON, TUE):
        make_entry(sam, d, start=time(9), finish=time(17), break_minutes=30)
    return sam


def test_the_nav_has_time_off_for_everyone_and_the_manager_children(sam, lead):
    body = _client(sam).get("/time-off/").content.decode()
    assert 'data-nav="time-off"' in body and 'href="/time-off/planner/"' in body and 'href="/time-off/approve/"' not in body
    body = _client(lead).get("/time-off/").content.decode()
    assert 'href="/time-off/approve/"' in body and 'href="/time-off/bank-holidays/"' in body and 'data-nav="settings"' in body


def test_the_list_shows_type_only_to_colleagues_and_everything_to_the_person_and_managers(sam, lead, team):
    bookings.book(lead.user, sam, make_type("Compassionate"), MON, MON, "whole", description="Funeral", paid=False)
    nina = make_person(first_name="Nina", team=team)
    body = _client(nina).get("/time-off/").content.decode()
    assert "Compassionate" in body and "Funeral" not in body and "<td>Unpaid</td>" not in body and "7 h 30 min" not in body
    body = _client(sam).get("/time-off/").content.decode()
    assert "Funeral" in body and "<td>Unpaid</td>" in body and "7 h 30 min" in body
    body = _client(lead).get("/time-off/").content.decode()
    assert "Funeral" in body and f"/time-off/{Booking.objects.get().pk}/edit/" in body
    assert "Add time off" in body and "Download" in body


def test_the_list_filters_and_downloads(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    bookings.book(lead.user, sam, make_type("Training"), TUE, TUE, "whole")
    c = _client(lead)
    body = c.get("/time-off/?type=Training").content.decode()
    assert "<td>Training</td>" in body and "<td>Holiday</td>" not in body       # the type filter's options still list Holiday
    csv = c.get("/time-off/?download=1").content.decode()
    assert csv.splitlines()[0].startswith("Staff,First day off,Last day off,Days,Type") and "Sam Patel" in csv


def test_add_time_off_dialog_previews_costs_and_books(sam, lead):
    c = _client(lead)
    body = c.get(f"/time-off/add/?person={sam.pk}&day={MON}").content.decode()
    assert 'name="person"' in body and f'value="{sam.pk}" selected' in body and f'value="{MON}"' in body
    data = {"person": sam.pk, "type": make_type("Holiday").pk, "first_day": MON, "last_day": TUE, "part": "whole", "preview": "1"}
    body = c.post("/time-off/add/", data).content.decode()
    assert "7 h 30 min" in body and "15 h" in body and "232 h 30 min" in body and "217 h 30 min" in body     # before and after
    data.pop("preview")
    r = c.post("/time-off/add/", data)
    assert r.json() == {"refresh": True}
    b = Booking.objects.get()
    assert b.status == "approved" and b.booking_days.count() == 2


def test_add_time_off_with_an_overridden_day(sam, lead):
    c = _client(lead)
    data = {"person": sam.pk, "type": make_type("Holiday").pk, "first_day": MON, "last_day": MON, "part": "whole",
            f"cost_{MON}": "4:00", "manager_note": "half pay"}
    assert c.post("/time-off/add/", data).json() == {"refresh": True}
    bd = Booking.objects.get().booking_days.get()
    assert (bd.cost_seconds, bd.source, bd.override_note) == (14400, "override", "half pay")


def test_a_manager_adding_their_own_leave_without_the_flag_gets_a_pending_request(lead):
    make_allowance(lead, Y27, 100, 30)
    make_entry(lead, MON, start=time(9), finish=time(17))
    c = _client(lead)
    data = {"person": lead.pk, "type": make_type("Holiday").pk, "first_day": MON, "last_day": MON, "part": "whole"}
    body = c.post("/time-off/add/", data).content.decode()
    assert "will wait for another manager" in body and Booking.objects.get().status == "pending"


def test_staff_cannot_open_add_and_managers_cannot_add_outside_their_teams(sam, lead):
    assert _client(sam).get("/time-off/add/").status_code == 403
    other = make_person(first_name="Nur", team=make_team("Nursing"))
    data = {"person": other.pk, "type": make_type("Holiday").pk, "first_day": MON, "last_day": MON, "part": "whole"}
    body = _client(lead).post("/time-off/add/", data).content.decode()
    assert "Select a valid choice" in body and not Booking.objects.exists()


def test_the_request_page_shows_balances_and_refuses_over_balance_and_blackouts(sam, lead):
    c = _client(sam)
    body = c.get("/time-off/request/").content.decode()
    assert "Request time off" in body and "232 h 30 min" in body and "Sick leave" not in body
    data = {"type": make_type("Holiday").pk, "first_day": MON, "last_day": MON, "part": "whole", "preview": "1"}
    body = c.post("/time-off/request/", data).content.decode()
    assert "7 h 30 min" in body and "225 h" in body and "data-send" in body
    from leave.services import adjustments
    adjustments.add(lead.user, sam, Y27, "annual", -(230 * 3600), "test")
    body = c.post("/time-off/request/", data).content.decode()
    assert "available" in body and "data-send" not in body
    data.pop("preview")
    assert c.post("/time-off/request/", data).status_code == 200 and not Booking.objects.exists()


def test_a_request_is_made_and_appears_under_my_leave(sam, lead):
    c = _client(sam)
    data = {"type": make_type("Holiday").pk, "first_day": MON, "last_day": MON, "part": "whole", "staff_note": "dentist"}
    r = c.post("/time-off/request/", data)
    assert r.status_code == 302 and r.url == "/time-off/mine/"
    body = c.get("/time-off/mine/").content.decode()
    assert "Waiting for approval" in body and "dentist" in body and "Annual leave remaining" in body


def test_view_and_cancel_dialogs(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, TUE, "whole")
    me, boss = _client(sam), _client(lead)
    body = me.get(f"/time-off/{b.pk}/").content.decode()
    assert "Holiday" in body and "15 h" in body and f"/time-off/{b.pk}/cancel/" in body
    nina = make_person(first_name="Nina", team=lead.team)
    body = _client(nina).get(f"/time-off/{b.pk}/").content.decode()
    assert "Holiday" in body and "15 h" not in body
    assert me.post(f"/time-off/{b.pk}/cancel/", {"note": "plans"}).json() == {"refresh": True}
    b.refresh_from_db()
    assert b.status == "cancel_requested"
    assert boss.post(f"/time-off/{b.pk}/cancel/", {"note": "ok"}).json() == {"refresh": True}
    b.refresh_from_db()
    assert b.status == "cancelled"


def test_edit_dialog_changes_an_approved_booking(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    c = _client(lead)
    body = c.get(f"/time-off/{b.pk}/edit/").content.decode()
    assert f'value="{MON}"' in body
    data = {"person": sam.pk, "type": make_type("Holiday").pk, "first_day": MON, "last_day": TUE, "part": "whole", "description": "Spring"}
    assert c.post(f"/time-off/{b.pk}/edit/", data).json() == {"refresh": True}
    b.refresh_from_db()
    assert b.last_day == TUE and b.description == "Spring" and b.booking_days.count() == 2


def test_the_request_page_refuses_a_blackout_day(sam, lead):
    from leave.services import blackouts
    blackouts.add(lead.user, MON, MON, [], "audit week")
    data = {"type": make_type("Holiday").pk, "first_day": MON, "last_day": MON, "part": "whole", "preview": "1"}
    body = _client(sam).post("/time-off/request/", data).content.decode()
    assert "blackout period" in body and "data-send" not in body


def test_the_add_preview_keeps_typed_hours_and_edit_does_not_count_the_booking_twice(sam, lead):
    c = _client(lead)
    data = {"person": sam.pk, "type": make_type("Holiday").pk, "first_day": MON, "last_day": MON, "part": "whole", "preview": "1", f"cost_{MON}": "4:00"}
    body = c.post("/time-off/add/", data).content.decode()
    assert f'name="cost_{MON}" value="4:00"' in body
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    data.pop(f"cost_{MON}")
    body = c.post(f"/time-off/{b.pk}/edit/", data).content.decode()
    assert "Balance before <strong>232 h 30 min</strong>, after <strong>225 h</strong>" in body


def test_edit_keeps_and_previews_a_stored_override_and_saves_a_typed_one(sam, lead):
    from leave.models import BookingDay
    from tests.factories import make_bank_holiday
    day = date(2027, 5, 3)
    make_bank_holiday(day, "Early May bank holiday")
    from leave.services import bank_holidays
    b = bank_holidays.book(lead.user, sam, day, 27000)
    c = _client(lead)
    data = {"person": sam.pk, "type": b.type.pk, "first_day": day, "last_day": day, "part": "whole", "description": "Spring"}
    body = c.post(f"/time-off/{b.pk}/edit/", {**data, "preview": "1"}).content.decode()
    assert "7 h 30 min" in body and f'name="cost_{day}" value="7:30"' in body
    assert c.post(f"/time-off/{b.pk}/edit/", {**data, f"cost_{day}": "7:30"}).json() == {"refresh": True}
    bd = BookingDay.objects.get(booking=b)
    assert (bd.cost_seconds, bd.source, bd.override_note) == (27000, "override", "bank holiday")
    assert c.post(f"/time-off/{b.pk}/edit/", {**data, f"cost_{day}": "4:00"}).json() == {"refresh": True}
    bd.refresh_from_db()
    assert (bd.cost_seconds, bd.source) == (14400, "override")


def test_the_list_hides_declined_and_cancelled_unless_asked_and_pending_shows_no_cost(sam, lead):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    pending = bookings.request(sam.user, sam, make_type("Holiday"), TUE, TUE, "whole")
    c = _client(lead)
    row = next(r for r in c.get("/time-off/").context["rows"] if r["booking"].pk == pending.pk)
    assert row["cost"] is None
    bookings.cancel(lead.user, b)
    assert b.pk not in [r["booking"].pk for r in c.get("/time-off/").context["rows"]]
    assert [r["booking"].pk for r in c.get("/time-off/?status=cancelled").context["rows"]] == [b.pk]
