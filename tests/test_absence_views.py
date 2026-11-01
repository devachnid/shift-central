"""The sickness screens: the join-on warning in Add time off (SICK-04
through the dialog), the past schedule section, dates-only entries on the
grid and the list, the Instances column, the statement's sickness line."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.test import Client

from leave.models import Booking
from tests import clock
from tests.factories import make_allowance, make_entry, make_person, make_sick, make_team, make_team_manager, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(clock.LATE_2026)]


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
    make_allowance(sam, date(2026, 1, 1), Decimal("172.5"), 0)
    day = date(2026, 9, 28)
    while day <= date(2026, 11, 30):
        if day.weekday() < 5:
            make_entry(sam, day, start=time(9), finish=time(17), break_minutes=30)
        day += timedelta(days=1)
    return sam


def sick():
    return make_type("Sick leave", requestable=False, sickness=True)


def _post(c, person, first, last, **extra):
    data = {"person": person.pk, "type": sick().pk, "first_day": first.isoformat(), "last_day": last.isoformat(), "part": "whole", "manager_note": ""}
    return c.post("/time-off/add/", {**data, **extra})


def test_sick_04_the_dialog_warns_and_extend_makes_one_instance(sam, lead):
    first = make_sick(sam, date(2026, 10, 5), date(2026, 10, 9))          # Mon–Fri
    c = _client(lead)
    body = _post(c, sam, date(2026, 10, 12), date(2026, 10, 13), preview="1").content.decode()
    assert "joins on to Sick leave 5 Oct–9 Oct 2026" in body and 'name="join"' in body and "Extend that entry to 5 Oct–13 Oct 2026" in body
    assert "1 instance" in body or "Instances in the last six months after this entry: 1" in body
    r = _post(c, sam, date(2026, 10, 12), date(2026, 10, 13), join="extend")
    assert r.json() == {"refresh": True}
    first.refresh_from_db()
    assert first.last_day == date(2026, 10, 13) and Booking.objects.filter(person=sam, type__sickness=True).count() == 1


def test_sick_04_record_separately_makes_two_instances(sam, lead):
    make_sick(sam, date(2026, 10, 5), date(2026, 10, 9))
    r = _post(_client(lead), sam, date(2026, 10, 12), date(2026, 10, 13), join="separate")
    assert r.json() == {"refresh": True}
    assert Booking.objects.filter(person=sam, type__sickness=True, status="approved").count() == 2


def test_a_long_entry_is_marked_in_the_preview(sam, lead):
    body = _post(_client(lead), sam, date(2026, 10, 1), date(2026, 10, 29), preview="1").content.decode()
    assert "long sickness" in body


def test_a_holiday_preview_has_no_sickness_block(sam, lead):
    c = _client(lead)
    r = c.post("/time-off/add/", {"person": sam.pk, "type": make_type("Holiday").pk, "first_day": "2026-11-09", "last_day": "2026-11-09", "part": "whole", "manager_note": "", "preview": "1"})
    assert 'name="join"' not in r.content.decode() and "Instances in the last six months" not in r.content.decode()


def test_the_past_schedule_lists_adds_and_refuses_staff(sam, lead):
    c = _client(lead)
    assert c.get("/time-off/past/").status_code == 200
    r = c.post("/time-off/past/add/", {"person": sam.pk, "type": sick().pk, "first_day": "2026-07-06", "last_day": "2026-07-10", "preview": "1"})
    assert r.status_code == 200 and "Instances in the last six months after this entry: 1" in r.content.decode()
    r = c.post("/time-off/past/add/", {"person": sam.pk, "type": sick().pk, "first_day": "2026-07-06", "last_day": "2026-07-10"})
    assert r.json() == {"refresh": True}
    row = Booking.objects.get(person=sam, type__sickness=True)
    assert row.dates_only and row.status == "approved" and not row.booking_days.exists()
    body = c.get("/time-off/past/").content.decode()
    assert "Sam Patel" in body and "6 Jul 2026" in body and "10 Jul 2026" in body
    assert "<td>1</td><td></td>" in body                                        # one instance, no trigger yet
    r = c.post("/time-off/past/add/", {"person": sam.pk, "type": sick().pk, "first_day": "2026-11-02", "last_day": "2026-11-02"})
    assert r.status_code == 200 and "already gone" in r.content.decode()
    staff = _client(sam)
    assert staff.get("/time-off/past/").status_code == 403 and staff.get("/time-off/past/add/").status_code == 403
    body = c.get("/time-off/").content.decode()
    assert 'href="/time-off/past/"' in body and 'href="/time-off/past/"' not in staff.get("/time-off/").content.decode()


def test_the_past_schedule_add_offers_extend_too(sam, lead):
    make_sick(sam, date(2026, 7, 6), date(2026, 7, 10), dates_only=True)
    c = _client(lead)
    r = c.post("/time-off/past/add/", {"person": sam.pk, "type": sick().pk, "first_day": "2026-07-13", "last_day": "2026-07-14", "join": "extend"})
    assert r.json() == {"refresh": True}
    assert Booking.objects.filter(person=sam, type__sickness=True).count() == 1 and Booking.objects.get(person=sam, type__sickness=True).last_day == date(2026, 7, 14)


def test_dates_only_entries_show_on_the_list_the_grid_and_the_view(sam, lead):
    row = make_sick(sam, date(2026, 10, 5), date(2026, 10, 7), dates_only=True)
    c = _client(lead)
    body = c.get("/time-off/?from=2026-10-01&to=2026-10-31").content.decode()
    assert "dates only" in body and "0 min" not in body
    payload = c.get("/rota/api/window/?from=2026-10-05&to=2026-10-11").json()
    cell = next(r for r in payload["rows"] if r["person"] == sam.pk)["leave"]["2026-10-06"]
    assert cell["type"] == "Sick leave" and cell["status"] == "approved" and cell["cost"] is None
    assert "Dates only" in c.get(f"/time-off/{row.pk}/").content.decode()
    csv = c.get("/time-off/?from=2026-10-01&to=2026-10-31&download=1").content.decode()
    assert "dates only" in csv


def test_todays_sickness_cannot_extend_a_past_schedule_entry(sam, lead):
    make_sick(sam, date(2026, 10, 26), date(2026, 10, 30), dates_only=True)         # Mon-Fri, all gone
    c = _client(lead)
    body = _post(c, sam, date(2026, 11, 2), date(2026, 11, 2), preview="1").content.decode()      # Mon 2 Nov is today
    assert 'name="join"' not in body and "a past schedule entry" in body and "Extend the existing entry" not in body
    assert _post(c, sam, date(2026, 11, 2), date(2026, 11, 2)).json() == {"refresh": True}
    assert Booking.objects.filter(person=sam, type__sickness=True).count() == 2


def test_the_list_says_dates_only_to_the_person_and_managers_only(sam, lead, team):
    make_sick(sam, date(2026, 10, 5), date(2026, 10, 7), dates_only=True)
    nina = make_person(first_name="Nina", team=team)
    assert "dates only" not in _client(nina).get("/time-off/?from=2026-10-01&to=2026-10-31").content.decode()
    assert "dates only" in _client(sam).get("/time-off/?from=2026-10-01&to=2026-10-31").content.decode()


def test_the_edit_dialog_of_a_dates_only_entry_has_no_cost_boxes(sam, lead):
    row = make_sick(sam, date(2026, 10, 5), date(2026, 10, 7), dates_only=True)
    body = _client(lead).get(f"/time-off/{row.pk}/edit/").content.decode()
    assert "cost_2026-10-05" not in body


def test_the_leave_report_shows_instances_and_trigger(sam, lead):
    for d in (date(2026, 6, 1), date(2026, 8, 3), date(2026, 10, 5)):
        make_sick(sam, d)
    body = _client(lead).get("/reports/leave/?from=2026-01-01&to=2026-12-31").content.decode()
    assert "<th>Instances</th>" in body and "<th>Trigger</th>" in body and "Trigger 1" in body
    csv = _client(lead).get("/reports/leave/?from=2026-01-01&to=2026-12-31&download=1").content.decode()
    assert csv.splitlines()[0].endswith("Instances,Trigger") and ",3,Trigger 1" in csv


def test_the_statement_carries_the_persons_sickness_line(sam, lead):
    make_sick(sam, date(2026, 9, 7))
    assert "Sickness: 1 instance in the last six months" in _client(sam).get("/time-off/mine/").content.decode()
    body = _client(lead).get(f"/staff/{sam.pk}/profile/?tab=hours").content.decode()
    assert "Sickness: 1 instance in the last six months" in body
    nina = make_person(first_name="Nina", team=sam.team)
    assert _client(nina).get(f"/staff/{sam.pk}/profile/?tab=hours").status_code == 403      # the instances count is for the person and their managers only


def test_a_booked_entry_never_extends_a_past_schedule_entry(sam, lead):
    past = make_sick(sam, date(2026, 10, 5), date(2026, 10, 9), dates_only=True)     # Mon–Fri, typed as history
    c = _client(lead)
    body = _post(c, sam, date(2026, 10, 12), date(2026, 10, 13), preview="1").content.decode()     # Mon–Tue, wholly past, joins on
    assert 'name="join"' not in body and "Extend the existing entry" not in body
    assert "recorded as a separate instance because the other entry is a past schedule entry" in body
    assert _post(c, sam, date(2026, 10, 12), date(2026, 10, 13), join="extend").json() == {"refresh": True}
    past.refresh_from_db()
    assert (past.first_day, past.last_day) == (date(2026, 10, 5), date(2026, 10, 9))
    booked = Booking.objects.get(person=sam, type__sickness=True, dates_only=False)
    assert (booked.first_day, booked.last_day) == (date(2026, 10, 12), date(2026, 10, 13)) and booked.booking_days.count() == 2     # costed: it reaches payroll


def test_a_past_schedule_entry_never_extends_a_booked_one(sam, lead):
    c = _client(lead)
    assert _post(c, sam, date(2026, 10, 12), date(2026, 10, 13), join="separate").json() == {"refresh": True}
    booked = Booking.objects.get(person=sam, type__sickness=True)
    data = {"person": sam.pk, "type": sick().pk, "first_day": "2026-10-05", "last_day": "2026-10-09"}
    body = c.post("/time-off/past/add/", {**data, "preview": "1"}).content.decode()
    assert 'name="join"' not in body and "recorded as a separate instance because the other entry has hours" in body
    assert c.post("/time-off/past/add/", {**data, "join": "extend"}).json() == {"refresh": True}
    booked.refresh_from_db()
    assert (booked.first_day, booked.last_day, booked.booking_days.count()) == (date(2026, 10, 12), date(2026, 10, 13), 2)
    past = Booking.objects.get(person=sam, dates_only=True)
    assert (past.first_day, past.last_day) == (date(2026, 10, 5), date(2026, 10, 9)) and not past.booking_days.exists()


def test_a_2026_dates_only_entry_is_edited_from_the_dialog_in_2027(sam, lead, today):
    row = make_sick(sam, date(2026, 7, 6), date(2026, 7, 10), dates_only=True)
    today(date(2027, 1, 15))
    c = _client(lead)
    body = c.get(f"/time-off/{row.pk}/edit/").content.decode()
    assert "Leave can be booked" not in body and "Costs can be set" not in body and "cost_2026-07-06" not in body
    data = {"person": sam.pk, "type": sick().pk, "description": "", "first_day": "2026-07-06", "last_day": "2026-07-14", "part": "whole",
            "start": "", "finish": "", "paid": "unknown", "manager_note": ""}
    assert c.post(f"/time-off/{row.pk}/edit/", data).json() == {"refresh": True}
    row.refresh_from_db()
    assert (row.first_day, row.last_day, row.dates_only) == (date(2026, 7, 6), date(2026, 7, 14), True) and not row.booking_days.exists()
    r = c.post(f"/time-off/{row.pk}/edit/", {**data, "last_day": "2027-01-15"})                  # still only for days already gone
    assert r.status_code == 200 and "already gone" in r.content.decode()


def test_colleagues_see_neither_the_dates_only_nor_the_long_sickness_note(sam, lead, team):
    row = make_sick(sam, date(2026, 8, 3), date(2026, 9, 11), dates_only=True)                   # 40 days: long
    nina = make_person(first_name="Nina", team=team)
    body = _client(nina).get(f"/time-off/{row.pk}/").content.decode()
    assert "Sick leave" in body and "Dates only" not in body and "Long sickness" not in body
    body = _client(lead).get(f"/time-off/{row.pk}/").content.decode()
    assert "Dates only" in body and "Long sickness" in body
    nursing = make_team("Nursing")
    nora = make_person(first_name="Nora", team=nursing)
    make_user_for(nora)
    make_team_manager(nora, nursing)
    csv = _client(nora).get("/time-off/?from=2026-08-01&to=2026-09-30&download=1").content.decode()
    assert "Sam Patel" in csv and "dates only" not in csv
    assert "dates only" in _client(lead).get("/time-off/?from=2026-08-01&to=2026-09-30&download=1").content.decode()
