"""The year planner, the leave report, the bank holiday pages, blackouts,
leave types, leave settings and the Health card's new lines."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone

from leave.models import BankHoliday, Blackout, Booking, LeaveSetting, LeaveType
from leave.services import adjustments, bookings
from people.services import health
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


def test_the_planner_shows_a_year_of_leave_as_initials_by_type(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, TUE, "whole", description="Secret")
    nina = make_person(first_name="Nina", team=lead.team)
    body = _client(nina).get("/time-off/planner/?year=2027").content.decode()
    assert 'class="planner"' in body and body.count('title="Sam Patel · Holiday"') == 2 and "Secret" not in body and ">SP<" in body
    assert "March" in body and 'data-day="2027-03-01"' in body
    body = _client(nina).get("/time-off/planner/?year=2027&type=Training").content.decode()
    assert "SP" not in body.split('class="planner"')[1]


def test_the_leave_report_is_per_person_with_team_subtotals_and_a_csv(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    adjustments.add(lead.user, sam, Y27, "annual", 3600, "test")
    c = _client(lead)
    body = c.get("/reports/leave/?from=2027-01-01&to=2027-12-31").content.decode()
    assert "Sam Patel" in body and "232 h 30 min" in body and "1 h" in body and "7 h 30 min" in body and "226 h" in body and "Reception" in body
    csv = c.get("/reports/leave/?from=2027-01-01&to=2027-12-31&download=1").content.decode()
    assert csv.splitlines()[0] == "Name,Team,Allowance,Adjustments,Days,Deducted,Remaining,TOIL"
    body = _client(sam).get("/reports/leave/").content.decode()
    assert "Sam Patel" in body and "Lead Patel" not in body


def test_bank_holidays_page_lists_adds_and_books_for_everyone(sam, lead, team):
    c = _client(lead)
    body = c.get("/time-off/bank-holidays/?year=2027").content.decode()
    assert "Good Friday" in body and "Add for everyone" in body
    assert c.post("/time-off/bank-holidays/", {"day": "2027-05-07", "name": "Coronation"}).status_code == 302
    assert BankHoliday.objects.filter(day=date(2027, 5, 7)).exists()
    for w in range(1, 5):
        make_entry(sam, date(2027, 5, 3) - timedelta(weeks=w), start=time(9), finish=time(17), break_minutes=30)
    body = c.get("/time-off/bank-holidays/2027-05-03/everyone/").content.decode()
    assert "Sam Patel" in body and 'value="7:30"' in body
    r = c.post("/time-off/bank-holidays/2027-05-03/everyone/", {f"hours_{sam.pk}": "7:30", f"tick_{sam.pk}": "on"})
    assert "1 person" in r.content.decode()
    bd = Booking.objects.get(person=sam, type__name="Bank holiday").booking_days.get()
    assert (bd.cost_seconds, bd.account) == (27000, "bank_holiday")
    assert _client(sam).get("/time-off/bank-holidays/").status_code == 403


def test_blackouts_crud(lead, team):
    c = _client(lead)
    r = c.post("/time-off/blackouts/add/", {"first_day": "2027-12-20", "last_day": "2027-12-31", "teams": [team.pk], "note": "Christmas"})
    assert r.json() == {"redirect": "/time-off/blackouts/"}
    b = Blackout.objects.get()
    assert list(b.teams.all()) == [team]
    body = c.get("/time-off/blackouts/").content.decode()
    assert "Christmas" in body and "Reception" in body
    c.post(f"/time-off/blackouts/{b.pk}/edit/", {"first_day": "2027-12-20", "last_day": "2027-12-24", "note": "Christmas"})
    b.refresh_from_db()
    assert b.last_day == date(2027, 12, 24) and not b.teams.exists()
    c.post(f"/time-off/blackouts/{b.pk}/delete/")
    assert not Blackout.objects.exists()


def test_leave_types_page_edits_and_archives_but_keeps_a_seeded_types_account(lead):
    c = _client(lead)
    body = c.get("/settings/leave-types/").content.decode()
    assert "Holiday" in body and "Jury service" in body
    holiday = LeaveType.objects.get(name="Holiday")
    body = c.get(f"/settings/leave-types/{holiday.pk}/edit/").content.decode()
    assert 'name="colour"' in body and 'name="draws_from"' not in body
    c.post(f"/settings/leave-types/{holiday.pk}/edit/", {"name": "Annual leave", "colour": "#123456", "requestable": "on", "display_order": "10"})
    holiday.refresh_from_db()
    assert holiday.name == "Annual leave" and holiday.draws_from == "annual"
    c.post("/settings/leave-types/add/", {"name": "Study leave", "colour": "#654321", "draws_from": "none", "requestable": "on", "on_payroll": "never"})
    assert LeaveType.objects.get(name="Study leave").requestable
    c.post(f"/settings/leave-types/{holiday.pk}/edit/", {"name": "Annual leave", "colour": "#123456", "display_order": "10", "archived": "on"})
    assert LeaveType.objects.get(pk=holiday.pk).archived


def test_leave_settings_page(lead):
    c = _client(lead)
    assert c.post("/settings/leave/", {"reminder_working_days": "5"}).status_code == 200
    assert LeaveSetting.objects.get().reminder_working_days == 5


def test_health_card_counts_requests_waiting_placeholders_and_negative_balances(sam, lead, monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda: date(2027, 2, 1))     # the figures are "this leave year"; pin it
    bookings.request(sam.user, sam, make_type("Holiday"), MON, MON, "whole")
    bookings.book(lead.user, sam, make_type("Holiday"), date(2027, 8, 11), date(2027, 8, 11), "whole")
    adjustments.add(lead.user, sam, Y27, "annual", -(300 * 3600), "test")
    f = health.figures(lead.user)
    assert f["waiting"] == 1 and len(f["placeholders"]) == 1 and [p.pk for p in f["negative"]] == [sam.pk]
    body = _client(lead).get("/staff/").content.decode()
    assert "Requests waiting" in body and "Leave costs to check" in body and "Negative leave balances" in body


# --- what the first tests do not reach --------------------------------------

def test_the_planner_marks_pending_and_bank_holidays_and_hides_what_is_not_live(sam, lead):
    holiday = make_type("Holiday")
    bookings.request(sam.user, sam, holiday, MON, MON, "whole")
    declined = bookings.request(sam.user, sam, holiday, TUE, TUE, "whole")
    bookings.decline(lead.user, declined)
    body = _client(lead).get("/time-off/planner/?year=2027").content.decode()
    assert body.count("planner-chip is-pending") == 1 and body.count('title="Sam Patel · Holiday"') == 1
    assert 'is-holiday" title="Good Friday"' in body          # 26 March 2027, seeded
    assert _client(lead).get("/time-off/planner/?year=banana").status_code == 200
    assert _client(lead).get("/time-off/planner/?year=99999").status_code == 200


def test_a_member_of_staff_who_may_not_see_colleagues_sees_only_their_own_leave(sam, lead):
    bookings.book(lead.user, sam, make_type("Holiday"), MON, MON, "whole")
    nina = make_person(first_name="Nina", team=lead.team, can_see_other_staff=False)
    assert "SP" not in _client(nina).get("/time-off/planner/?year=2027").content.decode().split('class="planner"')[1]


def test_the_leave_report_defaults_to_the_leave_year_and_writes_names_safely(sam, lead):
    sam.leave_year_start = "04-01"
    sam.save()
    me = make_person(first_name="=Eve", team=lead.team, leave_year_start="04-01")
    assert me.name == "=Eve Patel"
    r = _client(me).get("/reports/leave/")
    year = timezone.localdate()
    start = date(year.year if year >= date(year.year, 4, 1) else year.year - 1, 4, 1)
    assert f'name="from" value="{start.isoformat()}"' in r.content.decode()
    row = _client(me).get("/reports/leave/?download=1").content.decode().splitlines()[1]
    assert row.startswith("'=Eve Patel,")


def test_bank_holidays_page_refuses_staff_and_unknown_days_and_deletes(sam, lead):
    c = _client(lead)
    assert _client(sam).post("/time-off/bank-holidays/", {"day": "2027-05-07", "name": "x"}).status_code == 403
    assert c.get("/time-off/bank-holidays/2027-05-07/everyone/").status_code == 404      # not on the list
    assert c.get("/time-off/bank-holidays/notaday/everyone/").status_code == 404
    assert c.post("/time-off/bank-holidays/", {"day": "nope", "name": "x"}).status_code == 200
    r = c.post("/time-off/bank-holidays/", {"delete": "2027-05-03"})
    assert r.status_code == 302 and not BankHoliday.objects.filter(day=date(2027, 5, 3)).exists()
    assert c.post("/time-off/bank-holidays/", {"delete": "garbage"}).status_code == 404


def test_add_for_everyone_lists_gps_unticked_never_the_manager_and_checks_the_hours(sam, lead, team):
    gp = make_person(first_name="Gail", team=team, is_gp=True)
    c = _client(lead)
    body = c.get("/time-off/bank-holidays/2027-05-03/everyone/").content.decode()
    assert "Gail Patel" in body and "Lead Patel" not in body
    assert f'name="tick_{gp.pk}" id="tick_{gp.pk}" aria-label' in body        # a GP's box is not ticked
    assert f'name="tick_{sam.pk}" id="tick_{sam.pk}" checked' in body
    r = c.post("/time-off/bank-holidays/2027-05-03/everyone/", {f"hours_{sam.pk}": "lots", f"tick_{sam.pk}": "on"})
    assert "Type hours as 7:30 or 7.5" in r.content.decode() and not Booking.objects.filter(type__name="Bank holiday").exists()
    r = c.post("/time-off/bank-holidays/2027-05-03/everyone/", {f"hours_{sam.pk}": "25:00", f"tick_{sam.pk}": "on"})
    assert "A day has 24 hours" in r.content.decode()
    r = c.post("/time-off/bank-holidays/2027-05-03/everyone/", {f"hours_{sam.pk}": "7.5", f"tick_{sam.pk}": "on"})
    assert "Added for 1 person" in r.content.decode()
    r = c.post("/time-off/bank-holidays/2027-05-03/everyone/", {f"hours_{sam.pk}": "7.5", f"tick_{sam.pk}": "on"})
    assert "Added for 0 people (1 skipped" in r.content.decode()            # already booked


def test_a_renamed_bank_holiday_type_still_books(sam, lead):
    row = LeaveType.objects.get(name="Bank holiday")
    row.name = "Public holiday"
    row.save()
    r = _client(lead).post("/time-off/bank-holidays/2027-05-03/everyone/", {f"hours_{sam.pk}": "7:30", f"tick_{sam.pk}": "on"})
    assert "Added for 1 person" in r.content.decode()
    assert "Booked for 1 person" in _client(lead).get("/time-off/bank-holidays/?year=2027").content.decode()


def test_blackout_dialogs_render_validate_and_are_for_managers(lead, sam, team):
    c = _client(lead)
    assert "Reception" in c.get("/time-off/blackouts/add/").content.decode()
    r = c.post("/time-off/blackouts/add/", {"first_day": "2027-12-24", "last_day": "2027-12-20"})
    assert "The last day is before the first" in r.content.decode() and not Blackout.objects.exists()
    b = Blackout.objects.create(first_day=date(2027, 12, 20), last_day=date(2027, 12, 24), note="Christmas")
    b.teams.set([team])
    body = c.get(f"/time-off/blackouts/{b.pk}/edit/").content.decode()
    assert "Christmas" in body and "checked" in body
    s = _client(sam)
    assert s.get("/time-off/blackouts/").status_code == 403 and s.get("/time-off/blackouts/add/").status_code == 403
    assert s.post(f"/time-off/blackouts/{b.pk}/delete/").status_code == 403 and Blackout.objects.exists()
    assert c.get(f"/time-off/blackouts/{b.pk}/delete/").status_code == 405


def test_blackout_changes_are_audited(lead, team):
    from people.models import AuditEntry
    c = _client(lead)
    c.post("/time-off/blackouts/add/", {"first_day": "2027-12-20", "last_day": "2027-12-31", "note": "Christmas"})
    assert AuditEntry.objects.filter(model="leave.blackout", actor=lead.user).exists()


def test_leave_type_dialogs_validate_and_fix_what_must_not_change(lead, sam):
    c = _client(lead)
    r = c.post("/settings/leave-types/add/", {"name": "holiday", "colour": "#123456", "draws_from": "none", "on_payroll": "never"})
    assert "There is already a type with that name" in r.content.decode()
    r = c.post("/settings/leave-types/add/", {"name": "Study leave", "colour": "red", "draws_from": "none", "on_payroll": "never"})
    assert "Choose a colour" in r.content.decode()
    c.post("/settings/leave-types/add/", {"name": "Study leave", "colour": "#654321", "draws_from": "none", "on_payroll": "never"})
    study = LeaveType.objects.get(name="Study leave")
    assert not study.seeded and not study.requestable
    assert 'name="draws_from"' in c.get(f"/settings/leave-types/{study.pk}/edit/").content.decode()
    # Until it has a booking a type's account may change; after, it is fixed.
    c.post(f"/settings/leave-types/{study.pk}/edit/", {"name": "Study leave", "colour": "#654321", "draws_from": "annual", "on_payroll": "never"})
    study.refresh_from_db()
    assert study.draws_from == "annual"
    bookings.book(lead.user, sam, study, MON, MON, "whole")
    assert 'name="draws_from"' not in c.get(f"/settings/leave-types/{study.pk}/edit/").content.decode()
    c.post(f"/settings/leave-types/{study.pk}/edit/", {"name": "Study leave", "colour": "#654321", "draws_from": "none", "on_payroll": "never"})
    study.refresh_from_db()
    assert study.draws_from == "annual"
    assert _client(sam).get("/settings/leave-types/").status_code == 403
    assert _client(sam).post("/settings/leave-types/add/", {"name": "x"}).status_code == 403


def test_leave_settings_are_validated_audited_and_for_managers(lead, sam):
    from people.models import AuditEntry
    c = _client(lead)
    assert "Saved." in c.post("/settings/leave/", {"reminder_working_days": "5"}).content.decode()
    assert AuditEntry.objects.filter(model="leave.leavesetting", field="reminder_working_days", before="3", after="5").exists()
    assert "Saved." not in c.post("/settings/leave/", {"reminder_working_days": "0"}).content.decode()
    assert "Saved." not in c.post("/settings/leave/", {"reminder_working_days": "x"}).content.decode()
    assert LeaveSetting.objects.get().reminder_working_days == 5
    assert 'value="5"' in c.get("/settings/leave/").content.decode()
    assert _client(sam).get("/settings/leave/").status_code == 403 and _client(sam).post("/settings/leave/", {"reminder_working_days": "9"}).status_code == 403


def test_the_nav_links_all_resolve(lead, sam):
    c = _client(lead)
    for url in ("/time-off/planner/", "/time-off/bank-holidays/", "/time-off/blackouts/", "/reports/leave/", "/settings/leave-types/", "/settings/leave/"):
        assert c.get(url).status_code == 200, url


def test_health_leaves_out_the_managers_own_request_and_dates_a_cancellation_by_its_request(sam, lead, monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda: date(2027, 2, 1))
    holiday = make_type("Holiday")
    mine = bookings.request(lead.user, lead, holiday, date(2027, 6, 7), date(2027, 6, 7), "whole")
    assert health.figures(lead.user)["waiting"] == 0         # another manager decides that one
    assert mine.status == "pending"
    old = bookings.book(lead.user, sam, holiday, date(2027, 6, 8), date(2027, 6, 8), "whole")
    bookings.request_cancel(sam.user, old)
    Booking.objects.filter(pk=old.pk).update(requested_at=timezone.now() - timedelta(days=90),
                                             cancel_requested_at=timezone.now() - timedelta(days=2))
    f = health.figures(lead.user)
    assert f["waiting"] == 1 and f["waiting_oldest_days"] == 2


def test_the_health_card_does_not_show_other_teams_leave(sam, lead, monkeypatch):
    monkeypatch.setattr(timezone, "localdate", lambda: date(2027, 2, 1))
    other = make_person(first_name="Olly", team=make_team("Nursing"), start_date=date(2020, 1, 6))
    bookings.request(make_user_for(other) and other.user, other, make_type("Holiday"), MON, MON, "whole")
    f = health.figures(lead.user)
    assert f["waiting"] == 0 and f["placeholders"] == [] and f["negative"] == []
