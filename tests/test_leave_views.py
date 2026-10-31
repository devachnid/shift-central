"""The Time off screens by role (spec section 6): list, add, request, my
leave, view and cancel; ACC-05's type-only rule for colleagues."""

from datetime import date, time
from decimal import Decimal

import pytest
from django.test import Client

from leave.models import Booking
from leave.services import bookings
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


def test_the_edit_dialog_of_a_pending_booking_has_no_cost_boxes(sam, lead):
    b = bookings.request(sam.user, sam, make_type("Holiday"), MON, MON, "whole")
    c = _client(lead)
    assert 'name="cost_' not in c.get(f"/time-off/{b.pk}/edit/").content.decode()
    data = {"person": sam.pk, "type": b.type.pk, "first_day": MON, "last_day": MON, "part": "whole", "preview": "1"}
    body = c.post(f"/time-off/{b.pk}/edit/", data).content.decode()
    assert "7 h 30 min" in body and 'name="cost_' not in body and "Costs can be set once the request is approved" in body


def test_colleagues_never_see_cancelled_bookings_even_by_status(sam, lead, team):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    bookings.cancel(lead.user, b)
    nina = make_person(first_name="Nina", team=team)
    assert _client(nina).get("/time-off/?status=cancelled").context["rows"] == []
    assert len(_client(lead).get("/time-off/?status=cancelled").context["rows"]) == 1
    assert len(_client(sam).get("/time-off/?status=cancelled").context["rows"]) == 1


# --- the balance previews pool annual leave and bank holidays, year by year (S1)

@pytest.fixture
def pat(team):
    pat = make_person(first_name="Pat", team=team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_user_for(pat)
    make_allowance(pat, date(2026, 1, 1), Decimal("7.5"), 0)
    make_allowance(pat, Y27, Decimal("187.5"), 0)
    return pat


def test_the_add_preview_shows_each_leave_year_a_booking_crosses(pat, lead):
    data = {"person": pat.pk, "type": make_type("Holiday").pk, "first_day": date(2026, 12, 31), "last_day": date(2027, 1, 5),
            "part": "whole", "preview": "1"}
    r = _client(lead).post("/time-off/add/", data)
    assert r.context["preview"]["over"] is False
    body = r.content.decode()
    assert "Balance for 2026 before <strong>7 h 30 min</strong>, after <strong>0 min</strong></p>" in body
    assert "Balance for 2027 before <strong>187 h 30 min</strong>, after <strong>150 h</strong></p>" in body


def test_the_request_page_marks_the_year_that_is_over(pat):
    data = {"type": make_type("Holiday").pk, "first_day": date(2026, 12, 30), "last_day": date(2027, 1, 1), "part": "whole", "preview": "1"}
    r = _client(pat).post("/time-off/request/", data)
    assert r.context["preview"]["over"] is True and not r.context["can_send"]
    assert "Balance for 2026 before <strong>7 h 30 min</strong>, after <strong>−7 h 30 min</strong> — " in r.content.decode()


def test_a_managers_own_request_over_the_balance_is_refused_by_the_service(lead, team):
    """The manager's own leave (no own-leave flag) is a request: the
    service refuses it, whatever the preview said."""
    make_allowance(lead, Y27, Decimal("7.5"), 0)
    lead.weekly_hours, lead.days_per_week = Decimal("37.5"), 5
    lead.save()
    data = {"person": lead.pk, "type": make_type("Holiday").pk, "first_day": MON, "last_day": TUE, "part": "whole"}
    body = _client(lead).post("/time-off/add/", data).content.decode()
    assert "This would take 15 h of annual leave (bank holidays included) and 7 h 30 min is available" in body
    assert not Booking.objects.filter(person=lead).exists()


def test_the_decide_dialog_shows_each_leave_year(pat, lead):
    b = bookings.request(pat.user, pat, make_type("Holiday"), date(2026, 12, 31), date(2027, 1, 1), "whole")
    body = _client(lead).get(f"/time-off/{b.pk}/decide/").content.decode()
    assert "Balance for 2026 before <strong>7 h 30 min</strong>, after <strong>0 min</strong></p>" in body
    assert "Balance for 2027 before <strong>187 h 30 min</strong>, after <strong>180 h</strong></p>" in body


# --- the Time off list follows Show to other staff and Can see other staff (S10)

def _table(response):
    return response.content.decode().split("<tbody>")[1].split("</tbody>")[0]


def test_the_list_leaves_out_a_person_hidden_from_other_staff(sam, lead, team):
    hidden = make_person(first_name="Hidden", team=make_team("Nursing"), show_to_other_staff=False)
    from tests.factories import make_booking
    make_booking(hidden, MON, type_name="Sick leave")
    make_booking(sam, TUE, type_name="Training")
    nina = make_person(first_name="Nina", team=team)
    body = _table(_client(nina).get("/time-off/"))
    assert "Hidden" not in body and "Sick leave" not in body
    assert "Sam Patel" in body and "Training" in body
    assert "Hidden Patel" in _table(_client(lead).get("/time-off/")), "a manager sees everyone on the rota, as the grid does"


def test_a_viewer_who_may_not_see_other_staff_sees_only_their_own_rows(sam, lead, team):
    from tests.factories import make_booking
    make_booking(sam, MON, type_name="Training")
    nina = make_person(first_name="Nina", team=team, can_see_other_staff=False)
    make_booking(nina, TUE, type_name="Holiday")
    body = _table(_client(nina).get("/time-off/"))
    assert "Nina Patel" in body and "Sam Patel" not in body and "Training" not in body


def test_the_managers_screen_and_csv_carry_the_same_rows(sam, lead, team):
    """Q4: managed people in full, other visible people type only, and
    nobody the grid would not show the manager."""
    from tests.factories import make_booking
    make_booking(sam, MON, type_name="Holiday", description="Lisbon")
    nurse = make_person(first_name="Nurse", team=make_team("Nursing"))
    make_booking(nurse, MON, type_name="Holiday", description="Rome")
    off_rota = make_person(first_name="Offrota", team=make_team("Nursing"), display_on_rota=False)
    make_booking(off_rota, TUE, type_name="Training")
    c = _client(lead)
    body = _table(c.get("/time-off/"))
    assert "Lisbon" in body and "Nurse Patel" in body and "Rome" not in body and "Offrota" not in body
    lines = c.get("/time-off/?download=1").content.decode().splitlines()
    assert len(lines) == 3
    assert any(line.startswith("Sam Patel,") and ",Lisbon," in line for line in lines)
    assert any(line.startswith("Nurse Patel,") and "Rome" not in line for line in lines)
    assert not any("Offrota" in line for line in lines)


# --- the View dialog for someone without the detail (S11)

def test_a_colleague_cannot_open_a_declined_or_cancelled_booking(sam, lead, team):
    nina = _client(make_person(first_name="Nina", team=team))
    b = bookings.request(sam.user, sam, make_type("Holiday"), MON, MON, "whole")
    assert nina.get(f"/time-off/{b.pk}/").status_code == 200, "pending is shown to colleagues"
    bookings.decline(lead.user, b, "no cover")
    assert nina.get(f"/time-off/{b.pk}/").status_code == 404
    assert _client(sam).get(f"/time-off/{b.pk}/").status_code == 200, "the person still sees their own"
    assert _client(lead).get(f"/time-off/{b.pk}/").status_code == 200, "and their manager"
    c = bookings.book(lead.user, sam, make_type("Holiday"), TUE, TUE, "whole")
    bookings.cancel(lead.user, c, "")
    assert nina.get(f"/time-off/{c.pk}/").status_code == 404


def test_a_colleague_cannot_open_a_hidden_persons_booking(lead, team):
    hidden = make_person(first_name="Hidden", team=team, show_to_other_staff=False)
    b = bookings.book(lead.user, hidden, make_type("Holiday"), MON, MON, "whole")
    assert _client(make_person(first_name="Nina", team=team)).get(f"/time-off/{b.pk}/").status_code == 404
    shy = make_person(first_name="Shy", team=team, can_see_other_staff=False)
    sam_b = bookings.book(lead.user, make_person(first_name="Open", team=team), make_type("Holiday"), MON, MON, "whole")
    assert _client(shy).get(f"/time-off/{sam_b.pk}/").status_code == 404


def test_a_colleague_sees_no_decider_and_a_cancellation_request_as_approved(sam, lead, team):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    bookings.request_cancel(sam.user, b, "plans changed")
    nina = _client(make_person(first_name="Nina", team=team))
    body = nina.get(f"/time-off/{b.pk}/").content.decode()
    assert "<dd>Approved</dd>" in body and "Cancellation requested" not in body
    assert "Decided by" not in body and "Lead Patel" not in body
    assert "Cancellation requested" not in _table(nina.get("/time-off/"))
    own = _client(sam).get(f"/time-off/{b.pk}/").content.decode()
    assert "Cancellation requested" in own and "Decided by" in own


def test_colleagues_filtering_by_cancellation_requested_see_nothing_of_others(sam, lead, team):
    b = bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    bookings.request_cancel(sam.user, b, "")
    nina = _client(make_person(first_name="Nina", team=team))
    assert "Sam Patel" not in _table(nina.get("/time-off/?status=cancel_requested"))
    assert "Sam Patel" in _table(_client(lead).get("/time-off/?status=cancel_requested"))
