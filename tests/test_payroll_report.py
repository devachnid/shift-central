"""PAY-01 to 03: the month's figures per person from the same tables the
statement reads, the days still to come taken from the rota, the snapshot
on Mark as sent and the corrections a later report lists."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from leave.services import bookings, hours
from payroll.models import PayrollRun
from payroll.services import report, runs
from people.models import AuditEntry
from shifts.models import Entry
from tests.factories import make_allowance, make_entry, make_gp_session, make_person, make_sick, make_team, make_team_manager, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 1, 15))]     # mid-month: the rest of January is the rota as it stands
JAN = date(2027, 1, 1)
Y27 = JAN


def h(text):
    return hours.from_hours(Decimal(text))


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss", team=make_team("Office"))
    make_user_for(boss, is_all_teams_manager=True)
    return boss


def weekdays(first, last):
    d = first
    while d <= last:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


@pytest.fixture
def sam(boss):
    """Mon–Fri 9–17 with 30 min break (7.5 h) through January: 21 working
    days = 157.5 h before any leave."""
    sam = make_person(first_name="Sam", team=make_team("Reception"), start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(sam, Y27, Decimal("172.5"), 60)
    for d in weekdays(JAN, date(2027, 1, 31)):
        make_entry(sam, d, start=time(9), finish=time(17), break_minutes=30)
    return sam


def row_for(user, person, month=JAN):
    return next(r for r in report.rows(report.people_for(user, month), month) if r.person == person)


def test_a_plain_month_is_the_rota_hours(boss, sam):
    r = row_for(boss.user, sam)
    assert (r.worked, r.paid_leave, r.total, r.paid_overtime, r.unpaid, r.sickness, r.toil_taken) == (h("157.5"), 0, h("157.5"), 0, 0, 0, 0)
    assert r.team == "Reception" and r.started is None and r.leaves is None and r.types == {}


def test_each_kind_of_absence_lands_in_its_column(boss, sam):
    bookings.book(boss.user, sam, make_type("Holiday"), date(2027, 1, 4), date(2027, 1, 5), "whole")                       # 15 h paid leave, 2 days
    bookings.book(boss.user, sam, make_type("Compassionate"), date(2027, 1, 6), date(2027, 1, 6), "whole", paid=False)      # LV-25: 7.5 h unpaid
    bookings.book(boss.user, sam, make_type("Sick leave", sickness=True), date(2027, 1, 7), date(2027, 1, 7), "whole")       # 7.5 h sickness
    make_entry(sam, date(2027, 1, 8), start=time(17), finish=time(19), break_minutes=0, overtime="paid")                   # 2 h paid overtime
    make_entry(sam, date(2027, 1, 11), start=time(17), finish=time(20), break_minutes=0, overtime="toil")                  # earns TOIL, not paid
    bookings.book(boss.user, sam, make_type("TOIL"), date(2027, 1, 12), date(2027, 1, 12), "whole")                         # 7.5 h TOIL taken, paid
    bookings.book(boss.user, sam, make_type("Holiday"), date(2027, 1, 13), date(2027, 1, 13), "am")                         # half day: 3.75 h, ½ day; the other 3.75 h worked
    Entry.objects.filter(person=sam, day=date(2027, 1, 14)).delete()                                                       # on maternity that day: no shift
    bookings.book(boss.user, sam, make_type("KIT day"), date(2027, 1, 14), date(2027, 1, 14), "times", time(9), time(15))   # KIT-01: 6 h
    bookings.book(boss.user, sam, make_type("Jury service"), date(2027, 1, 20), date(2027, 1, 21), "whole")                # 15 h reported
    make_sick(sam, date(2026, 7, 6), date(2026, 7, 10), dates_only=True)                                                   # history: nowhere
    r = row_for(boss.user, sam)
    assert r.worked == h("150") - h("7.5") * 8 + h("3.75")                # 20 shifts; 7 whole days and the half day's shift covered; the half day's other half added back as worked
    assert r.paid_leave == h("15") + h("7.5") + h("3.75")                 # holiday, TOIL taken, the half day
    assert r.total == r.worked + r.paid_leave
    assert r.paid_overtime == h("2") and r.unpaid == h("7.5") and r.sickness == h("7.5") and r.sickness_instances == 1
    assert r.toil_taken == h("7.5") and r.leave_half_days == 5 and r.leave_days_text == "2½"
    assert r.types == {"KIT day": {"days": 1, "seconds": h("6")}, "Jury service": {"days": 2, "seconds": h("15")}}
    assert report.type_names(report.rows(report.people_for(boss.user, JAN), JAN)) == ["Jury service", "KIT day"]


def test_sickness_instances_count_bookings_that_touch_the_month(boss, sam):
    make_sick(sam, date(2026, 12, 29), date(2027, 1, 2))
    make_sick(sam, date(2027, 1, 25))
    make_sick(sam, date(2027, 2, 1))
    assert row_for(boss.user, sam).sickness_instances == 2


def test_a_gps_sessions_count_as_worked_unless_their_leave_hides_them(boss):
    gp = make_person(first_name="Gail", team=make_team("GPs"), is_gp=True)
    make_allowance(gp, Y27, Decimal("100"), 0)
    for d in (date(2027, 1, 4), date(2027, 1, 5)):
        make_gp_session(gp, d, "AM")
        make_gp_session(gp, d, "PM")
    make_gp_session(gp, date(2027, 1, 6), "AM")
    bookings.book(boss.user, gp, make_type("Holiday"), date(2027, 1, 5), date(2027, 1, 5), "whole")
    bookings.book(boss.user, gp, make_type("Holiday"), date(2027, 1, 6), date(2027, 1, 6), "pm")
    r = row_for(boss.user, gp)
    assert r.worked == 3 * hours.GP_SESSION                                 # 4 Jan both, 6 Jan's morning
    assert r.paid_leave == 2 * hours.GP_SESSION + hours.GP_SESSION // 2    # the whole day, and a half day of the 6 Jan session (half the day's rota)


def test_starters_and_leavers_with_lv_07bs_figure(boss):
    new = make_person(first_name="New", team=make_team("Reception"), start_date=date(2027, 1, 18))
    gone = make_person(first_name="Gone", team=make_team("Reception"), start_date=date(2020, 1, 6), end_date=date(2027, 1, 22),
                       weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(gone, Y27, Decimal("172.5"), 0)
    for d in weekdays(JAN, date(2027, 1, 22)):
        make_entry(gone, d, start=time(9), finish=time(17), break_minutes=30)
    bookings.book(boss.user, gone, make_type("Holiday"), date(2027, 1, 11), date(2027, 1, 15), "whole")     # 37.5 h against 4 weeks' pro-rata
    rows = {r.person: r for r in report.rows(report.people_for(boss.user, JAN), JAN)}
    assert rows[new].started == date(2027, 1, 18) and rows[new].leaves is None
    r = rows[gone]
    assert r.leaves == date(2027, 1, 22) and r.leaver_balance == h("13.5") - h("37.5")        # 172.5 ÷ 52 × 4 = 13.27 → 13.5; 24 h over
    left = make_person(first_name="Left", start_date=date(2020, 1, 6), end_date=date(2026, 12, 31))
    assert left not in rows


def test_people_for_follows_the_managers_reach(boss):
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_user_for(lead)
    make_team_manager(lead, reception)
    ann, nick = make_person(first_name="Ann", team=reception), make_person(first_name="Nick", team=nursing)
    assert set(report.people_for(lead.user, JAN)) == {lead, ann}            # managed_people lists the team's members, the manager among them
    assert {ann, nick, boss, lead} <= set(report.people_for(boss.user, JAN))


def test_month_parsing():
    assert report.month_of("2027-01") == JAN and report.month_end(JAN) == date(2027, 1, 31) and report.month_end(date(2027, 2, 1)) == date(2027, 2, 28)
    assert report.month_of("") == JAN and report.month_of("junk") == JAN            # today's month
    with pytest.raises(ValueError):
        report.month_of("2025-12")
    with pytest.raises(ValueError):
        report.month_of("2028-03")                                                  # more than a year ahead


def test_mark_sent_stores_the_snapshot_and_later_changes_are_corrections(boss, sam):
    dec = date(2026, 12, 1)
    for d in weekdays(dec, date(2026, 12, 31)):
        make_entry(sam, d, start=time(9), finish=time(17), break_minutes=30)
    run = runs.mark_sent(boss.user, dec)
    assert run.month == dec and run.people >= 1 and run.figures["rows"][str(sam.pk)]["worked"] == h("172.5")    # 23 weekdays
    assert AuditEntry.objects.filter(model="payroll.payrollrun", object_id=run.pk, note="marked sent to the bureau").exists()
    assert report.corrections(boss.user, JAN) == []
    make_entry(sam, date(2026, 12, 19), start=time(9), finish=time(12), break_minutes=0)        # a Saturday shift added after the send
    changes = {(c.person, c.field): (c.sent, c.now, c.delta) for c in report.corrections(boss.user, JAN)}
    assert changes[(sam, "worked")] == (h("172.5"), h("175.5"), h("3"))
    assert changes[(sam, "total")] == (h("172.5"), h("175.5"), h("3"))
    assert (sam, "paid_leave") not in changes and all(c.month == dec for c in report.corrections(boss.user, JAN))
    make_sick(sam, date(2026, 12, 23))                                                          # the factory writes no costed day: the count moves, the hours do not
    labels = {c.label for c in report.corrections(boss.user, JAN)}
    assert "Sickness instances" in labels and "Sickness" not in labels
    runs.mark_sent(boss.user, dec)                                                   # sent again: the latest is what was sent
    assert report.corrections(boss.user, JAN) == []


def test_a_new_person_and_a_vanished_one_are_corrections(boss, sam):
    dec = date(2026, 12, 1)
    runs.mark_sent(boss.user, dec)
    late = make_person(first_name="Late", team=sam.team, start_date=date(2026, 12, 1))
    make_entry(late, date(2026, 12, 7), start=time(9), finish=time(12), break_minutes=0)
    fields = {(c.person, c.field) for c in report.corrections(boss.user, JAN)}
    assert (late, "worked") in fields and (late, "total") in fields


def test_only_an_all_teams_manager_marks_sent_and_the_health_line_appears_ten_days_out(boss):
    reception = make_team("Reception")
    lead = make_person(first_name="Lead", team=reception)
    make_user_for(lead)
    make_team_manager(lead, reception)
    with pytest.raises(PermissionDenied):
        runs.mark_sent(lead.user, JAN)
    assert runs.unsent_due(boss.user, today=date(2027, 1, 20)) is None
    assert runs.unsent_due(boss.user, today=date(2027, 1, 21)) == JAN
    assert runs.unsent_due(lead.user, today=date(2027, 1, 21)) is None
    runs.mark_sent(boss.user, JAN)
    assert runs.unsent_due(boss.user, today=date(2027, 1, 25)) is None
    assert runs.latest(JAN).sent_by == boss.user and PayrollRun.objects.count() == 1


def test_a_weekend_inside_a_booking_is_no_leave_day(boss, sam):
    bookings.book(boss.user, sam, make_type("Holiday"), date(2027, 1, 8), date(2027, 1, 11), "whole")                  # Fri–Mon: two working days
    bookings.book(boss.user, sam, make_type("Jury service"), date(2027, 1, 22), date(2027, 1, 25), "whole")            # Fri–Mon again
    r = row_for(boss.user, sam)
    assert r.paid_leave == h("15") and r.leave_half_days == 4 and r.leave_days_text == "2"
    assert r.types == {"Jury service": {"days": 2, "seconds": h("15")}}


def test_negative_half_days_read_with_their_sign():
    assert [report.half_days_text(n) for n in (-1, -3, -4, 0, 1, 5)] == ["−½", "−1½", "−2", "0", "½", "2½"]
    assert report.Row(person=None, team="", leave_half_days=-3).leave_days_text == "−1½"
    from payroll.templatetags.payroll_extras import figure
    assert figure(-1, "leave_half_days") == "−½" and figure(-3, "leave_half_days") == "−1½" and figure(-4, "leave_half_days") == "−2"
    assert figure(-1800, "worked") == "−30 min" and figure(None, "worked") == ""


def test_a_correction_is_sent_once(boss, sam):
    dec = date(2026, 12, 1)
    runs.mark_sent(boss.user, dec)
    make_entry(sam, date(2026, 12, 19), start=time(9), finish=time(12), break_minutes=0)        # changed after December went
    assert {(c.month, c.field) for c in report.corrections(boss.user, JAN)} >= {(dec, "worked"), (dec, "total")}
    run = runs.mark_sent(boss.user, JAN)                                                        # January's report carried December's correction
    assert AuditEntry.objects.get(model="payroll.payrollrun", object_id=run.pk).note == "marked sent to the bureau, with corrections to December 2026"
    assert runs.latest(dec).figures["rows"][str(sam.pk)]["worked"] == h("3")                     # what the bureau has now been told for December
    assert PayrollRun.objects.filter(month=dec).count() == 2
    feb = date(2027, 2, 1)
    assert [c for c in report.corrections(boss.user, feb) if c.month == dec] == []               # not repeated on February's
    make_entry(sam, date(2026, 12, 20), start=time(9), finish=time(11), break_minutes=0)        # a second change: only that one is new
    changes = {(c.month, c.field): (c.sent, c.now, c.delta) for c in report.corrections(boss.user, feb)}
    assert changes[(dec, "worked")] == (h("3"), h("5"), h("2"))
    runs.mark_sent(boss.user, JAN)                                                              # nothing changed in January: no extra January-only run beyond the re-send
    assert report.corrections(boss.user, feb) == []


def test_mark_sent_without_corrections_stores_only_its_own_month(boss, sam):
    dec = date(2026, 12, 1)
    runs.mark_sent(boss.user, dec)
    runs.mark_sent(boss.user, JAN)
    assert PayrollRun.objects.filter(month=dec).count() == 1
    assert AuditEntry.objects.filter(model="payroll.payrollrun", note="marked sent to the bureau").count() == 2


def test_a_team_manager_sees_only_their_peoples_corrections(boss, sam):
    reception = sam.team
    lead = make_person(first_name="Lead", team=reception)
    make_user_for(lead)
    make_team_manager(lead, reception)
    nick = make_person(first_name="Nick", team=make_team("Nursing"), start_date=date(2020, 1, 6))
    dec = date(2026, 12, 1)
    runs.mark_sent(boss.user, dec)
    make_entry(sam, date(2026, 12, 19), start=time(9), finish=time(12), break_minutes=0)
    make_entry(nick, date(2026, 12, 19), start=time(9), finish=time(12), break_minutes=0)
    assert {c.person for c in report.corrections(boss.user, JAN)} == {sam, nick}
    assert {c.person for c in report.corrections(lead.user, JAN)} == {sam}
