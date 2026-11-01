"""The manager's dashboard (spec 5, section 8)."""

from datetime import date, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from leave.services import bookings
from people.services import dashboard
from shifts.services import open_shifts
from tests.factories import (client_for, make_booking, make_department, make_entry, make_person, make_sick, make_team,
                             make_team_manager, make_type, make_user_for)

pytestmark = pytest.mark.django_db
TODAY = date(2026, 11, 2)       # the pinned Monday


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")

    def staff(first, team, **kw):
        p = make_person(first_name=first, team=team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5, **kw)
        make_user_for(p)
        return p

    lead = staff("Lead", reception)
    make_team_manager(lead, reception)
    boss = make_person(first_name="Boss", team=reception)
    make_user_for(boss, is_all_teams_manager=True)
    return SimpleNamespace(reception=reception, nursing=nursing, lead=lead, boss=boss, sam=staff("Sam", reception),
                           ann=staff("Ann", reception), wfh=staff("Wendy", reception), nina=staff("Nina", nursing))


def test_the_today_card_counts_people_in_by_site_working_from_home_and_off(cast):
    ag, pmc = make_department("Reception AG"), make_department("Reception PMC")
    make_entry(cast.sam, TODAY, department=ag)
    make_entry(cast.ann, TODAY, department=pmc)
    make_entry(cast.wfh, TODAY, wfh=True)
    make_entry(cast.nina, TODAY, department=ag)
    make_entry(cast.lead, TODAY)                                                # no site
    bookings.book(cast.boss.user, cast.nina, make_type("Training"), TODAY, TODAY, "whole")
    card = dashboard.build(cast.boss.user, TODAY)["today"]
    assert dict(card["sites"]) == {"PMC": 1, "AG": 1, "Either": 1}
    assert card["wfh"] == 1 and card["off"] == 1


def test_a_team_manager_sees_only_their_own_teams_people(cast):
    make_entry(cast.sam, TODAY, department=make_department("Reception AG"))
    make_entry(cast.nina, TODAY, department=make_department("Nursing AG"))
    assert dict(dashboard.build(cast.lead.user, TODAY)["today"]["sites"]) == {"AG": 1}
    assert dict(dashboard.build(cast.boss.user, TODAY)["today"]["sites"]) == {"AG": 2}


def test_the_waiting_card_counts_leave_requests_and_open_shift_claims(cast):
    make_booking(cast.sam, TODAY + timedelta(days=7), status="pending")
    make_booking(cast.nina, TODAY + timedelta(days=8), status="pending")
    post = open_shifts.post(cast.lead.user, cast.reception, TODAY + timedelta(days=7), time(9), time(13), audience_teams=[cast.reception])
    open_shifts.claim(cast.sam.user, post)
    assert dashboard.build(cast.lead.user, TODAY)["waiting"] == {"leave": 1, "leave_oldest_days": 0, "claims": 1}
    assert dashboard.build(cast.boss.user, TODAY)["waiting"]["leave"] == 2


def test_your_own_request_is_not_waiting_for_you(cast):
    make_booking(cast.lead, TODAY + timedelta(days=7), status="pending")
    assert dashboard.build(cast.lead.user, TODAY)["waiting"]["leave"] == 0


def test_the_next_fourteen_days_list_leave_starting_and_open_shifts(cast):
    inside = make_booking(cast.sam, TODAY + timedelta(days=13))
    make_booking(cast.ann, TODAY + timedelta(days=14))                           # the fifteenth day: outside
    post = open_shifts.post(cast.lead.user, cast.reception, TODAY + timedelta(days=3), time(9), time(13), audience_teams=[cast.reception])
    filled = open_shifts.post(cast.lead.user, cast.reception, TODAY + timedelta(days=4), time(9), time(13), audience_teams=[cast.reception])
    open_shifts.approve(cast.lead.user, open_shifts.claim(cast.sam.user, filled))
    nxt = dashboard.build(cast.lead.user, TODAY)["next"]
    assert nxt["leave"] == [inside] and nxt["open_shifts"] == [post] and nxt["end"] == TODAY + timedelta(days=13)


def test_flags_list_triggers_leavers_and_people_returning(cast):
    for n in range(3):                                                           # three instances: trigger 1
        make_sick(cast.sam, TODAY - timedelta(days=60 - 14 * n))
    cast.ann.end_date = TODAY + timedelta(days=10)
    cast.ann.save()
    maternity = make_type("Maternity", flag_return=True)
    returning = make_booking(cast.wfh, TODAY - timedelta(days=20), TODAY - timedelta(days=2), type=maternity)
    flags = dashboard.build(cast.lead.user, TODAY)["flags"]
    assert [(t["person"], t["label"]) for t in flags["triggers"]] == [(cast.sam, "Trigger 1")]
    assert [r["person"] for r in flags["leaving"]] == [cast.ann]
    assert flags["returning"] == [returning]


def test_the_system_card_is_for_all_teams_managers_only(cast, push_on):
    assert dashboard.build(cast.lead.user, TODAY)["system"] is None
    system = dashboard.build(cast.boss.user, TODAY)["system"]
    assert system["push"]["configured"] and system["outbox_failures"] == 0 and system["hr"] is None


def test_the_page(cast):
    make_entry(cast.sam, TODAY, department=make_department("Reception AG"))
    assert client_for(cast.sam).get("/reports/dashboard/").status_code == 403
    page = client_for(cast.lead).get("/reports/dashboard/").content.decode()
    assert "Today" in page and "Waiting for you" in page and "Next 14 days" in page and "Flags" in page
    assert "System" not in page
    assert "System" in client_for(cast.boss).get("/reports/dashboard/").content.decode()
    assert 'href="/reports/dashboard/"' in client_for(cast.lead).get("/rota/").content.decode()
