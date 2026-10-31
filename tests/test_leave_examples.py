"""Every worked example in docs/requirements/06-leave-worked-examples.md
that this release can run, as the pack asks (`11`: "every worked example
gives exactly the expected answer"). The 2026 bank holidays are seeded.
SICK-01 to 04 are spec 4's; LV-15a/b and LV-16's year-end flag are spec
4's, so here the carry-over is the typed Adjustment MIG-04 describes."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.core import mail

from leave.models import BankHoliday, BookingDay
from leave.services import adjustments, balances, bank_holidays, bookings, hours
from leave.services.common import LeaveError
from messaging.models import Outbox
from people.models import AuditEntry
from people.services import profiles
from shifts.models import Entry
from tests import clock
from tests.factories import make_allowance, make_entry, make_gp_session, make_person, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(clock.LATE_2026)]    # set on the 2026-27 calendar
Y26 = date(2026, 1, 1)
Y27 = date(2027, 1, 1)
BH_2026 = [date(2026, 1, 1), date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 4), date(2026, 5, 25), date(2026, 8, 31), date(2026, 12, 25), date(2026, 12, 28)]
BH_2027 = [date(2027, 1, 1), date(2027, 3, 26), date(2027, 3, 29), date(2027, 5, 3), date(2027, 5, 31), date(2027, 8, 30), date(2027, 12, 27), date(2027, 12, 28)]


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss")
    make_user_for(boss, is_all_teams_manager=True)
    return boss


def rota(person, weekdays, start=time(9), finish=time(17), break_minutes=30, year=2026):
    """Lay out the whole year: a shift on each listed weekday (0 = Monday).
    The four weeks before it are laid out too, so a bank holiday on 1 January
    has its "usually works" weeks to look back on (LEAVE-16)."""
    day = date(year, 1, 1) - timedelta(weeks=4)
    while day.year <= year:
        if day.weekday() in weekdays:
            make_entry(person, day, start=start, finish=finish, break_minutes=break_minutes)
        day += timedelta(days=1)


def full_timer(**kw):
    kw.setdefault("start_date", date(2020, 1, 6))
    kw.setdefault("weekly_hours", Decimal("37.5"))
    kw.setdefault("days_per_week", 5)
    p = make_person(**kw)
    make_user_for(p)
    return p


def h(hours_text):
    return hours.from_hours(Decimal(hours_text))


def holiday():
    return make_type("Holiday")


def test_lv_01_full_time_whole_year(boss):
    sam = full_timer()
    rota(sam, (0, 1, 2, 3, 4), time(9), time(17), 30)
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    for bh in BH_2026:
        bank_holidays.book(boss.user, sam, bh, h("7.5"))
    assert balances.statement(sam, Y26).annual_remaining == h("172.5")
    bookings.book(boss.user, sam, make_type("Holiday"), date(2026, 11, 3), date(2026, 11, 3), "whole")
    s = balances.statement(sam, Y26)
    assert s.annual_remaining == h("165") and hours.fmt(s.annual_remaining) == "165 h"


def test_lv_02_part_time_equal_days(boss):
    sam = full_timer(weekly_hours=Decimal("22.5"), days_per_week=3)
    rota(sam, (0, 1, 2), time(9), time(17), 30)
    make_allowance(sam, Y26, Decimal("103.5"), 36)
    for bh in BH_2026:
        bank_holidays.book(boss.user, sam, bh, bookings.suggestion_for(sam, bh))
    s = balances.statement(sam, Y26)
    assert s.taken["bank_holiday"] == h("37.5") and s.annual_remaining == h("102")


def test_lv_03_part_time_uneven_days(boss):
    sam = full_timer(weekly_hours=Decimal("19"), days_per_week=3)
    rota(sam, (0, 1), time(9), time(17), 30)
    rota(sam, (3,), time(9), time(13), 0)
    make_allowance(sam, Y26, Decimal("87.4"), Decimal("30.4"))
    for bh in BH_2026:
        bank_holidays.book(boss.user, sam, bh, bookings.suggestion_for(sam, bh))
    s = balances.statement(sam, Y26)
    assert hours.fmt(s.annual_allowance) == "87 h 24 min" and hours.fmt(s.bank_holiday_allowance) == "30 h 24 min"
    assert s.taken["bank_holiday"] == h("41.5") and hours.fmt(s.annual_remaining) == "76 h 18 min"
    for day, expect in ((date(2026, 3, 2), "7 h 30 min"), (date(2026, 3, 3), "7 h 30 min"), (date(2026, 3, 5), "4 h"), (date(2026, 3, 4), "0 min")):
        assert hours.fmt(bookings.preview(sam, make_type("Holiday"), day, day, "whole")[0].seconds) == expect


def test_lv_04a_half_day(boss):
    sam = full_timer()
    day = date(2026, 3, 2)
    make_entry(sam, day, start=time(9), finish=time(17), break_minutes=30)
    b = bookings.book(boss.user, sam, holiday(), day, day, "am")
    cost = BookingDay.objects.get(booking=b).cost_seconds
    assert cost == 13500 and hours.fmt(cost) == "3 h 45 min"


def test_lv_04b_half_day_on_an_uneven_day(boss):
    sam = full_timer()
    day = date(2026, 3, 2)
    make_entry(sam, day, start=time(8), finish=time(14, 15), break_minutes=60)
    b = bookings.book(boss.user, sam, holiday(), day, day, "pm")
    cost = BookingDay.objects.get(booking=b).cost_seconds
    assert cost == 9450 and hours.fmt(cost) == "2 h 37½ min"


def test_lv_05_partial_day_in_hours(boss):
    sam = full_timer()
    day = date(2026, 3, 2)
    make_entry(sam, day, start=time(8), finish=time(16, 15), break_minutes=60)
    b = bookings.book(boss.user, sam, holiday(), day, day, "times", start=time(14), finish=time(15, 30))
    cost = BookingDay.objects.get(booking=b).cost_seconds
    entry = Entry.objects.get(person=sam, day=day)
    assert cost == 5400 and hours.fmt(cost) == "1 h 30 min"
    assert (entry.start, entry.finish) == (time(8), time(14))


def test_lv_19_gp_in_sessions(boss):
    gp = full_timer(is_gp=True)
    monday = date(2026, 3, 2)
    for offset in (0, 1, 3):                     # Mon, Tue, Thu
        for part in ("AM", "PM"):
            make_gp_session(gp, monday + timedelta(days=offset), part)
    make_allowance(gp, Y26, 150, 0)
    b = bookings.book(boss.user, gp, holiday(), monday, monday + timedelta(days=4), "whole")
    total = sum(BookingDay.objects.filter(booking=b).values_list("cost_seconds", flat=True))
    assert total == 90000 and hours.fmt(total) == "25 h"
    remaining = balances.statement(gp, Y26).annual_remaining
    assert remaining == 450000 and hours.fmt(remaining) == "125 h"


def test_lv_22_placeholder_then_recalculated(boss):
    sam = full_timer(weekly_hours=Decimal("30"), days_per_week=5)
    day = date(2027, 1, 1) - timedelta(weeks=4)
    while day <= date(2027, 6, 30):              # the rota is laid out to the end of June 2027
        if day.weekday() < 5:
            make_entry(sam, day, start=time(9), finish=time(15, 30), break_minutes=30)
        day += timedelta(days=1)
    aug = date(2027, 8, 11)                      # a Wednesday
    b = bookings.book(boss.user, sam, holiday(), aug, aug, "whole")
    bd = BookingDay.objects.get(booking=b)
    assert (bd.cost_seconds, bd.source, bd.placeholder) == (21600, "placeholder", True)
    assert Outbox.objects.filter(to_person=boss, subject__startswith="Leave cost to check").count() == 1
    mail.outbox.clear()
    make_entry(sam, aug, start=time(8), finish=time(16, 15), break_minutes=60)
    assert bookings.after_rota_write(sam, aug) == []
    bd.refresh_from_db()
    assert (bd.cost_seconds, bd.source, bd.placeholder) == (26100, "rota", False)
    assert hours.fmt(bd.cost_seconds) == "7 h 15 min"
    assert mail.outbox and "cost to check" in mail.outbox[0].subject.lower()


def test_lv_23_overtime_excluded(boss):
    sam = full_timer()
    day = date(2026, 3, 2)
    make_entry(sam, day, start=time(8), finish=time(16), break_minutes=60)
    make_entry(sam, day, start=time(16), finish=time(18), break_minutes=0, overtime="paid")
    b = bookings.book(boss.user, sam, holiday(), day, day, "whole")
    cost = BookingDay.objects.get(booking=b).cost_seconds
    assert cost == 25200 and hours.fmt(cost) == "7 h"


def test_lv_06a_starter():
    sam = make_person(start_date=date(2026, 7, 6))
    make_allowance(sam, Y26, 210, 0)
    assert balances.statement(sam, Y26).annual_allowance == h("105.0")


def test_lv_06b_starter_on_the_last_day_of_a_month():
    sam = make_person(start_date=date(2026, 7, 31))
    make_allowance(sam, Y26, 210, 0)
    assert balances.statement(sam, Y26).annual_allowance == h("89.0")


def test_lv_07a_leaver():
    sam = make_person(start_date=date(2020, 1, 6), end_date=date(2026, 10, 14))
    make_allowance(sam, Y26, 210, 0)
    assert balances.statement(sam, Y26).annual_allowance == h("165.5")


def test_lv_20_findmyshift_got_it_wrong():
    sam = make_person(start_date=date(2026, 8, 18))
    make_allowance(sam, Y26, 285, 0)
    s = balances.statement(sam, Y26)
    assert s.annual_allowance == h("109.5") and hours.fmt(s.annual_allowance) == "109 h 30 min"


def test_lv_07b_leaver_with_leave_over_or_remaining(boss):
    sam = full_timer(end_date=date(2026, 10, 14))
    rota(sam, (0, 1, 2, 3, 4), time(9), time(17), 30)
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    for bh in BH_2026[:6]:                                       # the six bank holidays to 14 October
        bank_holidays.book(boss.user, sam, bh, h("7.5"))
    s = balances.statement(sam, Y26)
    assert (s.annual_allowance, s.bank_holiday_allowance) == (h("136.0"), h("47.5"))
    assert s.taken["bank_holiday"] == h("45") and s.annual_remaining == h("138.5")
    bookings.book(boss.user, sam, holiday(), date(2026, 1, 5), date(2026, 2, 1), "whole")      # four weeks: 20 days, 150 h
    s = balances.statement(sam, Y26)
    assert s.taken["annual"] == h("150") and s.annual_remaining == h("-11.5")
    assert hours.fmt(s.annual_remaining) == "−11 h 30 min"


def test_lv_08a_hours_increase_mid_year():
    sam = make_person(start_date=date(2020, 1, 6))
    make_allowance(sam, Y26, 138, 48)
    make_allowance(sam, Y26, Decimal("172.5"), 60, from_day=date(2026, 7, 1), weekly_hours=Decimal("37.5"), days_per_week=5)
    assert balances.statement(sam, Y26).annual_allowance == h("158.5")


def test_lv_08b_hours_decrease_mid_year_with_leave_booked_after(boss):
    sam = full_timer()
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    make_allowance(sam, Y26, 138, 48, from_day=date(2026, 7, 1), weekly_hours=Decimal("30"), days_per_week=5)
    assert balances.statement(sam, Y26).annual_allowance == h("158.0")
    for offset in range(5):                                      # the week of 3 August at 6 h a day
        make_entry(sam, date(2026, 8, 3) + timedelta(days=offset), start=time(9), finish=time(15, 30), break_minutes=30)
    b = bookings.book(boss.user, sam, holiday(), date(2026, 8, 3), date(2026, 8, 7), "whole")
    total = sum(BookingDay.objects.filter(booking=b).values_list("cost_seconds", flat=True))
    assert total == h("30") and hours.fmt(total) == "30 h"


def test_lv_11a_starters_bank_holiday_allowance(boss):
    sam = full_timer(start_date=date(2026, 7, 6), weekly_hours=Decimal("30"))
    make_allowance(sam, Y26, 138, 48)
    for bh in (date(2026, 8, 31), date(2026, 12, 25), date(2026, 12, 28)):
        bank_holidays.book(boss.user, sam, bh, h("6"))
    assert balances.statement(sam, Y26).annual_remaining == h("75.0")


def test_lv_12_a_week_including_a_bank_holiday(boss):
    sam = full_timer()
    rota(sam, (0, 1, 2, 3, 4), time(9), time(17), 30)
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    bookings.book(boss.user, sam, holiday(), date(2026, 4, 6), date(2026, 4, 10), "whole")
    s = balances.statement(sam, Y26)
    assert s.taken["bank_holiday"] == 27000 and s.taken["annual"] == 108000


def test_lv_13_doesnt_work_mondays(boss):
    sam = full_timer(weekly_hours=Decimal("22.5"), days_per_week=3)
    rota(sam, (1, 2, 3), time(9), time(17), 30)
    make_allowance(sam, Y26, Decimal("103.5"), 36)
    for bh in BH_2026:
        bank_holidays.book(boss.user, sam, bh, bookings.suggestion_for(sam, bh))
    costs = {bd.day: bd.cost_seconds for bd in BookingDay.objects.filter(booking__person=sam)}
    assert costs[date(2026, 1, 1)] == h("7.5") and sum(costs.values()) == h("7.5")
    assert balances.statement(sam, Y26).annual_remaining == h("132.0")


def test_lv_14_extra_one_off_bank_holiday(boss):
    sam = full_timer()
    make_allowance(sam, Y27, Decimal("172.5"), 60)
    for bh in BH_2027:
        bank_holidays.book(boss.user, sam, bh, h("7.5"))
    assert balances.statement(sam, Y27).bank_holiday_balance == 0
    profiles.set_allowance(boss.user, sam, Y27, Decimal("172.5"), Decimal("67.5"), note="extra bank holiday 7 May 2027")
    extra = date(2027, 5, 7)
    bank_holidays.add(boss.user, extra, "Extra bank holiday")
    assert BankHoliday.objects.filter(day=extra).exists()
    bank_holidays.book(boss.user, sam, extra, h("7.5"))
    s = balances.statement(sam, Y27)
    assert s.bank_holiday_balance == 0 and s.annual_remaining == h("172.5")
    assert AuditEntry.objects.filter(note="extra bank holiday 7 May 2027").exists()


def test_lv_21_staff_e(boss):
    sam = full_timer(weekly_hours=Decimal("30"), days_per_week=5)
    make_allowance(sam, Y26, 138, 48)
    for bh in BH_2026:
        bank_holidays.book(boss.user, sam, bh, h("8.125"))       # 8 × 8.125 h = 65 h
    s = balances.statement(sam, Y26)
    assert s.taken["bank_holiday"] == h("65") and s.annual_remaining == h("121")


def test_lv_15a_and_15b_carry_over_as_adjustments(boss, today):
    sam = full_timer()
    make_allowance(sam, Y27, Decimal("172.5"), 0)
    adjustments.add(boss.user, sam, Y27, "annual", h("15"), "carried over 2026")
    assert balances.statement(sam, Y27).annual_remaining == h("187.5") == 675000
    today(date(2028, 1, 4))           # 2027's carry-over is made in January 2028
    y28 = date(2028, 1, 1)
    make_allowance(sam, y28, Decimal("172.5"), 0)
    adjustments.add(boss.user, sam, y28, "annual", h("10"), "carried over 2027 (10 h of 20 h)")
    assert balances.statement(sam, y28).annual_remaining == h("182.5") == 657000


def test_lv_16_toil_earned_and_taken(boss):
    sam = full_timer()
    make_allowance(sam, Y26, Decimal("172.5"), 0)
    make_entry(sam, date(2026, 2, 10), start=time(17), finish=time(20), break_minutes=0, overtime="toil")
    make_entry(sam, date(2026, 2, 20), start=time(9), finish=time(17), break_minutes=30)
    annual = balances.statement(sam, Y26).annual_remaining
    assert balances.statement(sam, Y26).toil_remaining == h("3")
    bookings.book(boss.user, sam, make_type("TOIL"), date(2026, 2, 20), date(2026, 2, 20), "times", start=time(9), finish=time(11))
    s = balances.statement(sam, Y26)
    assert s.toil_remaining == h("1") and s.annual_remaining == annual


def test_lv_24_requesting_more_than_the_balance(boss):
    sam = full_timer()
    rota(sam, (0, 1, 2, 3, 4), time(9), time(17), 30)
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    adjustments.add(boss.user, sam, Y26, "annual", -(225 * 3600), "leaves 7 h 30 min")
    assert balances.statement(sam, Y26).annual_available == h("7.5")
    first, last = date(2026, 11, 3), date(2026, 11, 4)           # two days, 15 h
    with pytest.raises(LeaveError) as e:
        bookings.request(sam.user, sam, holiday(), first, last, "whole")
    assert e.value.code == "balance"
    bookings.book(boss.user, sam, holiday(), first, last, "whole")
    remaining = balances.statement(sam, Y26).annual_remaining
    assert remaining == h("-7.5") and hours.fmt(remaining) == "−7 h 30 min"


def test_lv_25_unpaid_compassionate(boss):
    sam = full_timer()
    day = date(2026, 3, 2)
    make_entry(sam, day, start=time(9), finish=time(17), break_minutes=30)
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    before = balances.statement(sam, Y26).annual_remaining
    b = bookings.book(boss.user, sam, make_type("Compassionate"), day, day, "whole", paid=False)
    bd = BookingDay.objects.get(booking=b)
    assert (bd.cost_seconds, bd.account) == (27000, "none")
    assert b.paid is False
    assert balances.statement(sam, Y26).annual_remaining == before


def test_kit_01_kit_day(boss):
    sam = full_timer()
    day = date(2026, 3, 2)
    make_entry(sam, day, start=time(9), finish=time(17), break_minutes=30)
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    before = balances.statement(sam, Y26)
    b = bookings.book(boss.user, sam, make_type("KIT day"), day, day, "times", start=time(9), finish=time(15))
    bd = BookingDay.objects.get(booking=b)
    assert (bd.cost_seconds, bd.account) == (21600, "none")
    after = balances.statement(sam, Y26)
    assert (after.annual_remaining, after.toil_remaining) == (before.annual_remaining, before.toil_remaining)
    assert {k: after.taken[k] for k in ("annual", "bank_holiday", "toil")} == {k: before.taken[k] for k in ("annual", "bank_holiday", "toil")}
