"""LEAVE-21, 22, 24 and NOTIF-08: at the start of a leave year the managers
are flagged about everyone with leave or TOIL left; for each they carry it
all, lose it, or carry part, written as Adjustments in the new year."""

from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.core import mail
from django.core.management import call_command
from django.test import Client

from leave.models import Adjustment, YearEnd
from leave.services import adjustments, balances, bookings, hours, yearend
from people.models import AuditEntry
from people.services import health
from tests.factories import make_allowance, make_entry, make_person, make_sick, make_team, make_team_manager, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 11, 2))]    # late 2027: the fixtures book 2027 leave
Y27, Y28 = date(2027, 1, 1), date(2028, 1, 1)
J3 = date(2028, 1, 3)                                                           # the flag runs in the new year
ROOT = Path(__file__).resolve().parents[1]


def h(text):
    return hours.from_hours(Decimal(text))


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss")
    make_user_for(boss, is_all_teams_manager=True)
    return boss


@pytest.fixture
def sam(boss):
    """LV-15a's person: 172.5 h for 2027 plus 15 h carried from 2026, 167.5 h
    taken, so 20 h left at the end of 2027. Bank holiday allowance 0 so the
    annual figure is the plain one."""
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_user_for(sam)
    make_allowance(sam, Y27, Decimal("172.5"), 0)
    make_allowance(sam, Y28, Decimal("172.5"), 0)
    adjustments.add(boss.user, sam, Y27, "annual", h("15"), "carried over from FindMyShift 2026")
    day = date(2027, 3, 1)
    for _ in range(22):                       # 22 working days at 7.5 h = 165 h
        while day.weekday() >= 5:
            day += timedelta(days=1)
        make_entry(sam, day, start=time(9), finish=time(17), break_minutes=30)
        bookings.book(boss.user, sam, make_type("Holiday"), day, day, "whole")
        day += timedelta(days=1)
    bookings.book(boss.user, sam, make_type("Holiday"), date(2027, 6, 1), date(2027, 6, 1), "whole", costs={date(2027, 6, 1): h("2.5")})
    assert balances.statement(sam, Y27).annual_remaining == h("20")
    return sam


def test_lv_15a_the_flag_offers_whatever_is_left_and_carry_all_adds_it(boss, sam):
    (row,) = yearend.open_due(today=J3)
    assert (row.person, row.year_ended, row.annual_remaining, row.toil_remaining, row.decided) == (sam, Y27, h("20"), 0, False)
    assert yearend.open_due(today=J3) == []                                           # once
    assert yearend.notify_opened([row]) == 1
    assert mail.outbox[-1].subject == "Year end: 1 person has leave or TOIL left" and "Sam Patel" in mail.outbox[-1].body and "20 h" in mail.outbox[-1].body
    row.refresh_from_db()
    assert row.notified_at is not None
    yearend.decide(boss.user, row, h("20"))
    assert balances.statement(sam, Y28).annual_remaining == h("192.5")
    adj = Adjustment.objects.get(person=sam, leave_year=Y28)
    assert (adj.account, adj.seconds, adj.reason) == ("annual", h("20"), "carried over from 2027")
    row.refresh_from_db()
    assert (row.annual_carried, row.annual_lost, row.toil_lost, row.decided_by) == (h("20"), 0, 0, boss.user)


def test_lv_15b_partial_carry_over_is_logged(boss, sam):
    (row,) = yearend.open_due(today=J3)
    yearend.decide(boss.user, row, h("10"), note="agreed with Sam")
    assert balances.statement(sam, Y28).annual_remaining == h("182.5")
    row.refresh_from_db()
    assert row.annual_carried == h("10") and row.annual_lost == h("10")
    assert AuditEntry.objects.filter(model="leave.yearend", object_id=sam.pk, note="agreed with Sam").exists()
    with pytest.raises(ValueError):
        yearend.decide(boss.user, row, h("5"))                                 # already decided


def test_lv_16_toil_left_is_offered_and_only_a_loss_writes_anything(boss):
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(sam, Y27, Decimal("172.5"), 0)
    make_allowance(sam, Y28, Decimal("172.5"), 0)
    make_entry(sam, date(2027, 10, 11), start=time(17), finish=time(20), break_minutes=0, overtime="toil")      # LV-16 moved a month earlier: TOIL earned counts to today
    make_entry(sam, date(2027, 10, 20), start=time(9), finish=time(11), break_minutes=0)
    bookings.book(boss.user, sam, make_type("TOIL", draws_from="toil"), date(2027, 10, 20), date(2027, 10, 20), "whole")
    assert balances.statement(sam, Y27).toil_remaining == h("1")
    (row,) = yearend.open_due(today=J3)
    assert row.toil_remaining == h("1") and row.annual_remaining == h("172.5")
    yearend.decide(boss.user, row, h("172.5"), toil_keep=h("1"))            # keep all TOIL
    assert not Adjustment.objects.filter(person=sam, account="toil").exists()
    row2 = YearEnd.objects.create(person=make_person(first_name="Tom"), year_ended=Y27, annual_remaining=0, toil_remaining=h("1"))
    yearend.decide(boss.user, row2, 0, toil_keep=0)
    adj = Adjustment.objects.get(person=row2.person, account="toil")
    assert (adj.leave_year, adj.seconds, adj.reason) == (Y28, -h("1"), "TOIL lost at year end 2027")


def test_a_deficit_is_carried_as_a_negative_or_written_off(boss):
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(sam, Y27, Decimal("10"), 0)
    make_allowance(sam, Y28, Decimal("172.5"), 0)
    bookings.book(boss.user, sam, make_type("Holiday"), date(2027, 6, 1), date(2027, 6, 1), "whole", costs={date(2027, 6, 1): h("15")})
    (row,) = yearend.open_due(today=J3)
    assert row.annual_remaining == -h("5")
    with pytest.raises(ValueError):
        yearend.decide(boss.user, row, h("5"))                                 # outside remaining..0
    yearend.decide(boss.user, row, -h("5"))
    assert Adjustment.objects.get(person=sam, leave_year=Y28).reason == "deficit carried over from 2027"
    assert balances.statement(sam, Y28).annual_remaining == h("167.5")


def test_nothing_left_closes_at_once_and_a_missing_year_opens_nothing(boss):
    done = make_person(first_name="Done", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(done, Y27, Decimal("7.5"), 0)
    make_allowance(done, Y28, Decimal("7.5"), 0)
    make_entry(done, date(2027, 6, 1), start=time(9), finish=time(17), break_minutes=30)
    bookings.book(boss.user, done, make_type("Holiday"), date(2027, 6, 1), date(2027, 6, 1), "whole")
    make_person(first_name="New", start_date=date(2027, 11, 1))               # no 2027 allowance: nothing to ask
    assert yearend.run(today=J3) == 0
    row = YearEnd.objects.get(person=done)
    assert row.decided and row.note == "nothing left" and row.decided_by is None and mail.outbox == []
    assert not YearEnd.objects.filter(person__first_name="New").exists()


def test_a_row_never_emailed_is_sent_by_the_next_run_and_one_failure_stops_nobody(boss, sam, monkeypatch):
    stranded = YearEnd.objects.create(person=make_person(first_name="Strand"), year_ended=Y27, annual_remaining=h("4"))
    assert stranded.notified_at is None
    assert yearend.run(today=J3) == 1                                         # Sam's row is the one opened today
    stranded.refresh_from_db()
    assert stranded.notified_at is not None
    assert "Strand" in mail.outbox[-1].body and "Sam Patel" in mail.outbox[-1].body
    n = len(mail.outbox)
    assert yearend.run(today=J3) == 0 and len(mail.outbox) == n               # each is sent once

    YearEnd.objects.all().delete()
    real = balances.statement

    def flaky(person, year):
        if person == sam:
            raise RuntimeError("broken")
        return real(person, year)

    other = make_person(first_name="Zed", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(other, Y27, Decimal("7.5"), 0)
    monkeypatch.setattr(balances, "statement", flaky)
    assert [r.person for r in yearend.open_due(today=J3)] == [other]          # Sam fails, Zed after her still opens


def test_a_manager_typing_nothing_left_does_not_hide_the_row(boss):
    p = make_person(first_name="Typed")
    row = YearEnd.objects.create(person=p, year_ended=Y27, annual_remaining=h("5"))
    yearend.decide(boss.user, row, h("5"), note="nothing left")
    c = Client()
    c.force_login(boss.user)
    assert "Typed" in c.get("/time-off/year-end/").content.decode().split("<h2>Decided</h2>")[1]


def test_a_leave_year_starting_in_april_opens_in_april_and_the_window_is_a_month():
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5, leave_year_start="04-01")
    make_allowance(sam, date(2027, 4, 1), Decimal("100"), 0)
    make_allowance(sam, date(2028, 4, 1), Decimal("100"), 0)
    assert yearend.open_due(today=date(2028, 1, 3)) == []
    assert yearend.open_due(today=date(2028, 5, 3)) == []                     # more than 31 days in: left alone
    (row,) = yearend.open_due(today=date(2028, 4, 20))
    assert row.year_ended == date(2027, 4, 1) and row.annual_remaining == h("100")


def test_each_manager_gets_one_email_for_their_people(boss):
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_user_for(lead)
    make_team_manager(lead, team)
    rows = []
    for name, t in (("Ann", team), ("Nick", make_team("Nursing"))):
        p = make_person(first_name=name, team=t)
        rows.append(YearEnd.objects.create(person=p, year_ended=Y27, annual_remaining=h("5")))
    assert yearend.notify_opened(rows) == 2
    by_to = {m.to[0]: m for m in mail.outbox}
    assert "Ann" in by_to[lead.email].body and "Nick" not in by_to[lead.email].body
    assert by_to[boss.email].subject == "Year end: 2 people have leave or TOIL left"


def test_the_page_and_the_dialog(boss, sam, today):
    team = make_team("Nursing")
    other = make_person(first_name="Other", team=team)
    lead = make_person(first_name="Lead", team=team)
    make_user_for(lead)
    make_team_manager(lead, team)
    YearEnd.objects.create(person=other, year_ended=Y27, annual_remaining=h("3"))
    make_sick(sam, date(2027, 8, 2), date(2027, 9, 3))                        # long sickness in the year: marked
    today(J3)
    (row,) = yearend.open_due()
    c = Client()
    c.force_login(boss.user)
    body = c.get("/time-off/year-end/").content.decode()
    assert "Sam Patel" in body and "Other" in body and "long absence" in body and "20 h" in body
    assert health.figures(boss.user)["year_end_waiting"] == 2
    body = Client()
    body.force_login(lead.user)
    page = body.get("/time-off/year-end/").content.decode()
    assert "Other" in page and "Sam Patel" not in page
    assert body.get(f"/time-off/year-end/{row.pk}/decide/").status_code == 403
    r = c.post(f"/time-off/year-end/{row.pk}/decide/", {"annual_choice": "part", "annual_hours": "10", "toil_choice": "keep", "toil_hours": "", "note": ""})
    assert r.json() == {"refresh": True}
    row.refresh_from_db()
    assert row.annual_carried == h("10")
    decided = c.get("/time-off/year-end/").content.decode().split("<h2>Decided</h2>")[1]
    assert "Sam Patel" in decided and "10 h" in decided
    staff = Client()
    staff.force_login(sam.user)
    assert staff.get("/time-off/year-end/").status_code == 403
    assert 'href="/time-off/year-end/"' in c.get("/time-off/").content.decode()


def test_the_daily_command_and_its_units(boss, sam, today):
    today(J3)
    call_command("daily_flags")
    assert YearEnd.objects.filter(person=sam).exists()
    unit = (ROOT / "deploy" / "shift-central-daily-flags.service").read_text()
    assert "manage.py daily_flags" in unit
    timer = (ROOT / "deploy" / "shift-central-daily-flags.timer").read_text()
    assert "OnCalendar=*-*-* 08:25:00" in timer and "Persistent=true" in timer
