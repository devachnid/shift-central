"""The year planner, the leave report, the bank holiday pages, blackouts,
leave types, leave settings and the Health card's new lines."""

from datetime import date, time
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone

from leave.services import adjustments, bookings
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
