"""Allowance spec 2026-11-18, sections 5.1 and 5.4: the sync copies each
person's contracts from Practice HR's feed and, for a person with a copied
contract with fixed hours, owns their weekly hours. tests/data/people_feed.json is the same
file, byte for byte, as Practice HR's: that app tests that it produces it,
this one that it reads it."""

import copy
import hashlib
import json
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from people.models import AuditEntry, Contract, Person
from people.services import contracts, hr_sync, profiles
from tests.factories import make_allowance, make_contract, make_person

pytestmark = pytest.mark.django_db
SAMPLE = Path(__file__).parent / "data" / "people_feed.json"
SAMPLE_SHA256 = "4bf3b639cb705d048a9e9b5aa2c938adcc55ad80d63c563c9f8fccd2d8933940"


class Feed:
    def __init__(self, people):
        self.records = people

    def people(self):
        return self.records


def _sample():
    return json.loads(SAMPLE.read_text())["people"]


def _person(hr_id):
    return Person.objects.get(hr_employee_id=hr_id)


def test_the_sample_file_is_the_one_practice_hr_produces():
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == SAMPLE_SHA256, \
        "tests/data/people_feed.json changed: change it in practice-hr too, then this hash"


def test_the_sync_reads_the_sample_feed():
    run = hr_sync.sync(Feed(_sample()))
    assert run.ok and run.people_seen == 5 and run.message == ""
    sam = _person(101)
    rows = list(sam.contracts.all())
    assert [(c.hr_id, c.type_name, c.unit, c.from_day, c.to_day, c.weekly_amount, c.full_time_weekly, c.leave_base, c.leave_steps) for c in rows] == [
        (41, "Reception", "hours", date(2025, 6, 1), date(2026, 8, 31), D("22.5"), D("37.5"), D("22"), [[1, "23.00"], [5, "25.00"]]),
        (42, "Reception", "hours", date(2026, 9, 1), None, D("30"), D("37.5"), D("22"), [[1, "23.00"], [5, "25.00"]])]
    alex = _person(102).contracts.get()
    assert (alex.unit, alex.weekly_amount, alex.full_time_weekly, alex.leave_base, alex.leave_steps) == ("sessions", D("6"), D("8"), D("8"), [])
    assert _person(103).contracts.get().leave_steps == [[10, "30.00"]]
    riley = _person(104).contracts.get()
    assert (riley.type_name, riley.leave_base, riley.leave_steps) == ("GP trainee", None, [])
    assert not _person(105).contracts.exists()
    assert Contract.objects.count() == 5
    assert not AuditEntry.objects.filter(model="people.contract").exists()       # Practice HR audits the contract


def test_a_second_identical_run_writes_nothing():
    hr_sync.sync(Feed(_sample()))
    ids = list(Contract.objects.values_list("pk", flat=True))
    audited = AuditEntry.objects.count()
    assert hr_sync.sync(Feed(_sample())).ok
    assert list(Contract.objects.values_list("pk", flat=True)) == ids and AuditEntry.objects.count() == audited


def test_a_record_with_no_contracts_key_leaves_the_copy_alone():
    hr_sync.sync(Feed(_sample()))
    older = _sample()
    for record in older:
        del record["contracts"]
    assert hr_sync.sync(Feed(older)).ok
    assert Contract.objects.count() == 5


def test_an_empty_list_empties_the_copy_and_a_changed_one_replaces_it():
    hr_sync.sync(Feed(_sample()))
    feed = _sample()
    feed[0]["contracts"] = []
    feed[1]["contracts"][0]["weekly_amount"] = "7.00"
    feed[2]["contracts"].append({**copy.deepcopy(feed[2]["contracts"][0]), "id": 50, "from": "2027-04-01", "weekly_amount": "30.00"})
    assert hr_sync.sync(Feed(feed)).ok
    assert not _person(101).contracts.exists()
    assert _person(102).contracts.get().weekly_amount == D("7")
    assert [c.hr_id for c in _person(103).contracts.all()] == [44, 50]


def test_a_contract_id_that_moves_to_another_person_moves_here_too():
    hr_sync.sync(Feed(_sample()))
    feed = _sample()
    feed[4]["contracts"] = [feed[0]["contracts"].pop()]          # contract 42 now arrives under Casey, listed after Sam
    feed.reverse()                                               # …and Casey's record comes first
    assert hr_sync.sync(Feed(feed)).ok
    assert [c.hr_id for c in _person(105).contracts.all()] == [42] and [c.hr_id for c in _person(101).contracts.all()] == [41]


@pytest.mark.parametrize("spoil", [
    lambda c: c.pop("from"),
    lambda c: c.update({"from": None}),
    lambda c: c.update({"to": "next year"}),
    lambda c: c.update({"weekly_amount": "lots"}),
    lambda c: c.update({"weekly_amount": 22.5}),
    lambda c: c.update({"weekly_amount": "-1.00"}),
    lambda c: c.update({"full_time_weekly": None}),
    lambda c: c.update({"unit": "days"}),
    lambda c: c.update({"id": "41"}),
    lambda c: c.update({"contract_type": None}),
    lambda c: c.pop("leave"),
    lambda c: c.update({"leave": {"base": "22.00"}}),
    lambda c: c.update({"leave": {"base": "22.00", "steps": [{"after_years": "1", "total": "23.00"}]}}),
    lambda c: c.update({"leave": {"base": "22.00", "steps": [{"after_years": 1}]}}),
])
def test_a_malformed_contract_fails_the_run_and_the_previous_data_stands(spoil):
    hr_sync.sync(Feed(_sample()))
    feed = _sample()
    feed[0]["email"] = "sam.patel@practice.example"
    spoil(feed[2]["contracts"][0])
    run = hr_sync.sync(Feed(feed))
    assert not run.ok and run.message == "record 3 in the feed: missing or bad contracts"
    assert Contract.objects.count() == 5 and _person(101).email == "sam@practice.example"


def test_contracts_that_are_not_a_list_or_repeat_an_id_fail_the_run():
    for bad in (None, {"id": 41}, "none"):
        feed = _sample()
        feed[0]["contracts"] = bad
        assert hr_sync.sync(Feed(feed)).message == "record 1 in the feed: missing or bad contracts"
    feed = _sample()
    feed[0]["contracts"][1]["id"] = 41
    assert hr_sync.sync(Feed(feed)).message == "record 1 in the feed: missing or bad contracts"
    assert Person.objects.count() == 0


def test_a_bank_contract_and_steps_that_do_not_rise_are_copied_as_sent():
    feed = _sample()
    feed[0]["contracts"][1]["weekly_amount"] = "0.00"                                        # bank staff: no fixed hours
    feed[2]["contracts"][0]["leave"]["steps"] = [{"after_years": 10, "total": "20.00"}]      # falls
    assert hr_sync.sync(Feed(feed)).ok
    assert _person(101).contracts.get(hr_id=42).weekly_amount == 0
    assert _person(103).contracts.get().leave_steps == [[10, "20.00"]]


# --- weekly hours are Practice HR's while the hours contracts in force add up to more than 0 (5.4) ---

def test_weekly_hours_are_the_hours_contracts_in_force_today_audited_as_practice_hr():
    hr_sync.sync(Feed(_sample()))                            # the suite's clock: 2 November 2026
    sam = _person(101)
    assert sam.weekly_hours == D("30") and sam.days_per_week is None
    entry = AuditEntry.objects.get(model="people.person", object_id=sam.pk, field="weekly_hours")
    assert (entry.before, entry.after, entry.actor_email, entry.note) == ("", "30.00", "practice-hr", "from Practice HR")
    assert _person(103).weekly_hours == D("37.5")
    assert _person(102).weekly_hours is None and _person(104).weekly_hours is None        # GPs keep none
    assert _person(105).weekly_hours is None                                              # no contract: typed, as today


@pytest.mark.today(date(2026, 8, 31))
def test_weekly_hours_follow_the_contracts_as_the_days_pass(today):
    hr_sync.sync(Feed(_sample()))
    assert _person(101).weekly_hours == D("22.5")
    today(date(2026, 9, 1))
    hr_sync.sync(Feed(_sample()))
    assert _person(101).weekly_hours == D("30")


@pytest.mark.today(date(2026, 7, 1))
def test_a_starters_weekly_hours_are_those_on_their_start_date():
    hr_sync.sync(Feed(_sample()))
    assert _person(104).start_date == date(2026, 8, 5)
    feed = _sample()
    feed[3].update({"unit": "hours", "contract_type": "Reception"})
    feed[3]["contracts"][0].update({"unit": "hours", "contract_type": "Reception", "weekly_amount": "20.00", "full_time_weekly": "37.50"})
    hr_sync.sync(Feed(feed))
    assert _person(104).weekly_hours == D("20")


def test_two_hours_contracts_in_force_are_added_up():
    feed = _sample()
    feed[2]["contracts"].append({**copy.deepcopy(feed[2]["contracts"][0]), "id": 50, "from": "2026-01-01", "weekly_amount": "4.00"})
    hr_sync.sync(Feed(feed))
    assert _person(103).weekly_hours == D("41.5")


def test_a_day_between_contracts_keeps_the_hours_the_person_had():
    feed = _sample()
    del feed[0]["contracts"][1]                              # Sam's only contract ended on 31 August
    hr_sync.sync(Feed(feed))
    sam = _person(101)
    assert sam.weekly_hours is None
    Person.objects.filter(pk=sam.pk).update(weekly_hours=D("22.5"))
    hr_sync.sync(Feed(feed))
    assert _person(101).weekly_hours == D("22.5")


def test_bank_staff_keep_the_weekly_hours_typed_here(all_teams_user):
    feed = _sample()
    feed[0]["contracts"][1]["weekly_amount"] = "0.00"            # Sam's only contract in force is for 0 hours
    hr_sync.sync(Feed(feed))
    sam = _person(101)
    assert sam.weekly_hours is None and not contracts.hours_from_hr(sam)
    assert not AuditEntry.objects.filter(model="people.person", object_id=sam.pk, field="weekly_hours").exists()
    profiles.update_hours(all_teams_user, sam, D("12"), 2)       # typed, exactly as before this release
    hr_sync.sync(Feed(feed))
    sam.refresh_from_db()
    assert (sam.weekly_hours, sam.days_per_week) == (D("12"), 2)
    feed[0]["contracts"].append({**copy.deepcopy(feed[0]["contracts"][1]), "id": 51, "from": "2026-10-01", "weekly_amount": "15.00"})
    hr_sync.sync(Feed(feed))                                     # a fixed contract beside it: 0 + 15 is more than 0
    sam.refresh_from_db()
    assert sam.weekly_hours == D("15") and contracts.hours_from_hr(sam)


def test_in_force_and_weekly_hours_on_a_day():
    sam = make_person(start_date=date(2025, 6, 1))
    old = make_contract(sam, "22.5", to_day=date(2026, 8, 31))
    new = make_contract(sam, "30", from_day=date(2026, 9, 1))
    held = [old, new]
    assert contracts.in_force(held, date(2026, 8, 31)) == [old] and contracts.in_force(held, date(2026, 9, 1)) == [new]
    assert contracts.in_force(held, date(2025, 5, 31)) == []
    assert contracts.weekly_hours_on(held, date(2026, 9, 1)) == D("30") and contracts.weekly_hours_on(held, date(2025, 5, 31)) is None
    doc = make_person(is_gp=True)
    assert contracts.weekly_hours_on([make_contract(doc, 6, 8, unit="sessions")], date(2026, 9, 1)) is None
    assert contracts.hours_from_hr(sam) and not contracts.hours_from_hr(make_person())
    assert contracts.hours_from_hr(sam, date(2025, 5, 31))                # before day one they are read on the start date
    assert not contracts.hours_from_hr(doc)                               # a GP has no weekly hours
    bank = make_person(first_name="Bank")
    make_contract(bank, 0)
    assert contracts.weekly_hours_on(list(bank.contracts.all()), date(2026, 9, 1)) == 0 and not contracts.hours_from_hr(bank)


def test_nothing_else_writes_the_weekly_hours_of_a_person_whose_contract_gives_them(all_teams_user):
    sam = make_person(weekly_hours=D("30"), days_per_week=4)
    make_contract(sam, "30")
    rows = profiles.update_hours(all_teams_user, sam, D("37.5"), 5)
    sam.refresh_from_db()
    assert (sam.weekly_hours, sam.days_per_week) == (D("30"), 5) and [r.field for r in rows] == ["days_per_week"]
    typed = make_person(weekly_hours=D("30"), days_per_week=4)              # no copied contract: typed exactly as before
    profiles.update_hours(all_teams_user, typed, D("37.5"), 5)
    typed.refresh_from_db()
    assert (typed.weekly_hours, typed.days_per_week) == (D("37.5"), 5)


def test_a_due_hours_change_copies_only_days_per_week_for_such_a_person():
    sam = make_person(weekly_hours=D("30"), days_per_week=4)
    make_contract(sam, "30")
    make_allowance(sam, date(2026, 1, 1), 138, 48)
    make_allowance(sam, date(2026, 1, 1), D("172.5"), 60, from_day=date(2026, 7, 1), weekly_hours=D("37.5"), days_per_week=5)
    assert profiles.apply_due_hours_changes() == 1
    sam.refresh_from_db()
    assert (sam.weekly_hours, sam.days_per_week) == (D("30"), 5)
    assert profiles.apply_due_hours_changes() == 0
