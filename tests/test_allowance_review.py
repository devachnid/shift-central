"""Allowance spec 2026-11-18, section 8: the four lists, built on demand
for the people a manager manages, and their counts on the Health card."""

from datetime import date
from decimal import Decimal as D

import pytest

from leave.models import BankHoliday
from leave.services import entitlement
from people.services import profiles
from tests.factories import make_allowance, make_bank_holiday, make_contract, make_person, make_team, make_team_manager, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 2, 1))]
Y26, Y27, Y28 = date(2026, 1, 1), date(2027, 1, 1), date(2028, 1, 1)
JUNE = date(2027, 6, 1)
RECEPTION = [(1, 23)]


@pytest.fixture(autouse=True)
def bank_holidays_2028(db):
    """2026 and 2027 are seeded; give 2028 its eight too, so only the test
    about a year with none has one."""
    for row in BankHoliday.objects.filter(day__year=2027):
        make_bank_holiday(row.day.replace(year=2028), row.name)


@pytest.fixture
def boss(all_teams_user):
    return all_teams_user


def _sam(weekly="37.5", **kw):
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D(weekly), days_per_week=5, **kw)
    make_contract(sam, weekly, steps=RECEPTION)
    return sam


def _lines(items):
    return [(i.person.first_name, i.year, i.text) for i in items]


def test_with_no_contracts_anywhere_every_list_is_empty(boss):
    plain = make_person(weekly_hours=D("30"), days_per_week=4)
    make_allowance(plain, Y27, 138, 48)
    BankHoliday.objects.filter(day__year=2028).delete()                # a year with none is not news either, yet
    entitlement.refresh()
    r = entitlement.review(boss)
    assert (r.to_check, r.differ, r.bank_holidays, r.contracts) == ([], [], [], [])
    assert not plain.allowances.filter(leave_year=Y28).exists()         # and nothing was copied forward


def test_rows_that_need_checking_are_listed_until_confirmed(boss):
    sam = _sam()
    entitlement.refresh()
    r = entitlement.review(boss)
    assert _lines(r.to_check) == [("Sam", Y27, "worked out, not yet checked"), ("Sam", Y28, "worked out, not yet checked")]
    first = r.to_check[0]
    assert first.can_act and first.shown.row.leave_year == Y27 and not first.shown.dated
    assert first.shown.working == ("23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min", "8 bank holidays × 37.5 h ÷ 5 = 60 h")
    for item in r.to_check:
        profiles.confirm_allowance(boss, item.shown.row)
    assert entitlement.review(boss).to_check == []
    assert sam.allowances.count() == 2


def test_a_copied_row_is_listed_to_check(boss):
    doc = make_person(first_name="Riley", is_gp=True, start_date=date(2026, 8, 5))
    make_contract(doc, 8, None, unit="sessions", type_name="GP trainee")
    make_allowance(doc, Y27, 250, 60)
    entitlement.refresh()
    r = entitlement.review(boss)
    assert _lines(r.to_check) == [("Riley", Y28, "copied from last year, not yet checked")]
    assert r.to_check[0].shown.working is None and r.contracts == []    # a contract with no terms is not one to look at


def test_a_change_of_hours_in_a_typed_year_is_listed_until_the_hours_change_is_added(boss):
    doc = make_person(first_name="Riley", is_gp=True, start_date=date(2026, 8, 5))
    make_contract(doc, 8, None, unit="sessions", type_name="GP trainee", to_day=date(2027, 5, 31))
    make_contract(doc, 6, None, unit="sessions", type_name="GP trainee", from_day=JUNE)
    make_allowance(doc, Y27, 250, 60)
    make_allowance(doc, Y28, 200, 50)
    r = entitlement.review(boss)
    assert _lines(r.to_check) == [("Riley", Y27, "sessions changed on 1 June; add the hours change")]
    assert r.to_check[0].shown is None
    profiles.add_hours_change(boss, doc, JUNE, None, 5, 200, 50, "six sessions from June")
    assert entitlement.review(boss).to_check == []


def test_typed_figures_that_differ_are_listed_with_what_the_contract_gives(boss):
    sam = _sam()
    make_allowance(sam, Y27, 180, 60)
    make_allowance(sam, Y28, D("172.5"), 60)
    entitlement.refresh()
    r = entitlement.review(boss)
    assert _lines(r.differ) == [("Sam", Y27, "typed figures that are not the contract's")]
    item = r.differ[0]
    assert (item.shown.row.annual_hours, item.shown.rule.annual, item.shown.orphan) == (D("180"), D("172.5"), False)
    assert r.to_check == []                                             # the 2028 figures matched, and were adopted as checked
    profiles.use_worked_out(boss, item.shown.row)
    assert entitlement.review(boss).differ == []


def test_a_typed_dated_row_on_a_day_the_contracts_do_not_change_is_listed(boss):
    sam = _sam()
    make_allowance(sam, Y27, D("172.5"), 60)
    make_allowance(sam, Y27, 138, 48, from_day=JUNE, weekly_hours=D("30"), days_per_week=4)
    make_allowance(sam, Y28, D("172.5"), 60)
    entitlement.refresh()
    r = entitlement.review(boss)
    assert _lines(r.differ) == [("Sam", Y27, "the contracts do not change on this day")]
    assert r.differ[0].shown.orphan and r.differ[0].shown.rule is None


def test_a_finished_year_whose_rows_are_not_what_the_contracts_now_give_is_listed(boss, today):
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=3)
    old = make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    new = make_contract(sam, "30", steps=RECEPTION, from_day=JUNE)
    entitlement.refresh()
    today(date(2028, 1, 10))
    for row in BankHoliday.objects.filter(day__year=2027):
        make_bank_holiday(row.day.replace(year=2029), row.name)
    entitlement.refresh()
    for row in sam.allowances.all():
        profiles.confirm_allowance(boss, row)
    assert entitlement.review(boss).differ == []
    old.to_day, new.from_day = date(2027, 6, 30), date(2027, 7, 1)      # a change dated inside 2027, made in 2028
    old.save()
    new.save()
    entitlement.refresh()
    r = entitlement.review(boss)
    assert _lines(r.differ) == [("Sam", Y27, entitlement.FINISHED)] and r.differ[0].shown is None
    assert [a.from_day for a in sam.allowances.filter(leave_year=Y27)] == [Y27, JUNE]      # the finished year is not rewritten


def test_a_leave_year_with_no_bank_holidays_is_listed(boss):
    _sam()
    BankHoliday.objects.filter(day__year=2028).delete()
    r = entitlement.review(boss)
    assert r.bank_holidays == [Y28]
    entitlement.refresh()
    row = entitlement.review(boss).to_check[1].shown
    assert row.row.bank_holiday_hours == 0 and row.working[1] == "0 bank holidays × 37.5 h ÷ 5 = 0 min"


def test_contracts_to_look_at(boss):
    _sam(first_name="Fine")
    make_person(first_name="None")                                       # nothing from Practice HR
    ended = make_person(first_name="Ended", start_date=date(2025, 6, 1))
    make_contract(ended, "30", steps=RECEPTION, to_day=date(2027, 1, 31))
    gap = make_person(first_name="Gap", start_date=date(2025, 6, 1))
    make_contract(gap, "30", steps=RECEPTION, to_day=date(2027, 6, 30))
    bad = make_person(first_name="Bad")
    make_contract(bad, steps=[(1, 23), (5, 23)])                         # steps that do not rise
    bank = make_person(first_name="Bank")                                # no fixed hours: typed, and not one to look at
    make_contract(bank, 0, steps=RECEPTION)
    starter = make_person(first_name="Starter", start_date=date(2027, 4, 1))
    make_contract(starter, "30", from_day=date(2027, 5, 1))
    left = make_person(first_name="Left", end_date=date(2027, 1, 15))    # not current: not listed
    make_contract(left, "30", to_day=date(2026, 12, 31))
    assert {(i.person.first_name, i.text) for i in entitlement.review(boss).contracts} == {
        ("None", "no contract from Practice HR"), ("Ended", "no contract in force today"), ("Gap", "no contract from 1 July 2027"),
        ("Bad", "leave terms that cannot be worked out"), ("Starter", "no contract in force on the start date")}


def test_a_team_manager_sees_only_their_teams_and_cannot_act_on_their_own():
    nursing = make_team("Nursing")
    lead = make_person(first_name="Lead", team=nursing, start_date=date(2025, 6, 1))
    make_contract(lead, "30", steps=RECEPTION)
    make_team_manager(lead, nursing)
    _sam(first_name="Nina", team=nursing)
    _sam(first_name="Rec")
    entitlement.refresh()
    r = entitlement.review(make_user_for(lead))
    assert {(i.person.first_name, i.can_act) for i in r.to_check} == {("Lead", False), ("Nina", True)}


def test_the_team_box_narrows_the_lists(boss):
    nursing = make_team("Nursing")
    _sam(first_name="Nina", team=nursing)
    _sam(first_name="Rec")
    entitlement.refresh()
    assert {i.person.first_name for i in entitlement.review(boss, team=nursing).to_check} == {"Nina"}


def test_the_review_costs_the_same_queries_however_many_people(boss, django_assert_max_num_queries):
    for n in range(12):
        _sam(first_name=f"P{n}")
    entitlement.refresh()
    with django_assert_max_num_queries(8):
        assert len(entitlement.review(boss).to_check) == 24
