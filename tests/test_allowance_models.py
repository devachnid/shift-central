"""Allowance spec 2026-11-18, section 5: what is stored."""

from datetime import date
from decimal import Decimal as D

import pytest
from django.db import IntegrityError, transaction

from leave.models import LeaveSetting
from leave.services import balances, hours
from leave.services import settings as leave_settings
from people.models import Allowance, Contract, Person
from tests.factories import client_for, make_allowance, make_contract, make_person

pytestmark = pytest.mark.django_db
Y27 = date(2027, 1, 1)


def test_a_contract_is_a_copy_of_the_feeds_with_one_row_per_hr_id():
    sam = make_person(start_date=date(2025, 6, 1))
    c = make_contract(sam, "22.5", steps=[(1, 23), (5, 25)])
    c.refresh_from_db()
    assert (c.type_name, c.unit, c.from_day, c.to_day) == ("Reception", "hours", date(2025, 6, 1), None)
    assert (c.weekly_amount, c.full_time_weekly, c.leave_base) == (D("22.5"), D("37.5"), D("22"))
    assert c.leave_steps == [[1, "23.00"], [5, "25.00"]]                # totals as strings, so the decimals are exact
    assert str(c) == "Reception, 22.50 hours a week from 1 Jun 2025"
    with pytest.raises(IntegrityError), transaction.atomic():
        make_contract(sam, hr_id=c.hr_id)
    doc = make_person(is_gp=True)
    gp = make_contract(doc, 6, 8, unit="sessions", type_name="Partner")
    assert (gp.unit, gp.full_time_weekly, gp.leave_steps) == ("sessions", D("8"), [])
    assert make_contract(doc, 8, None, unit="sessions").leave_base is None           # no terms: its allowances are typed
    assert [x.hr_id for x in sam.contracts.all()] == [c.hr_id]
    sam.delete()
    assert not Contract.objects.filter(pk=c.pk).exists()


def test_every_existing_allowance_is_typed_and_needs_no_check():
    row = make_allowance(make_person(), Y27, 138, 48)
    row.refresh_from_db()
    assert (row.source, row.checked_at, row.checked_by) == ("typed", None, None) and not row.needs_checking


@pytest.mark.parametrize("source, checked, needs", [("typed", False, False), ("worked_out", False, True), ("copied", False, True),
                                                    ("worked_out", True, False), ("copied", True, False)])
def test_a_worked_out_or_copied_row_needs_checking_until_it_is_checked(source, checked, needs, all_teams_user):
    from django.utils import timezone
    row = make_allowance(make_person(), Y27, 138, 48, source=source, checked_at=timezone.now() if checked else None,
                         checked_by=all_teams_user if checked else None)
    assert row.needs_checking is needs
    assert row.get_source_display() == {"typed": "typed", "worked_out": "worked out", "copied": "copied from last year"}[source]


def test_the_figures_hold_four_places_so_whole_sessions_are_exact():
    row = make_allowance(make_person(is_gp=True), Y27, D("266.6667"), D("66.6667"))
    row.refresh_from_db()
    assert (row.annual_hours, row.bank_holiday_hours) == (D("266.6667"), D("66.6667"))
    assert hours.from_hours(row.annual_hours) == 960000 == 64 * hours.GP_SESSION        # 64 sessions, to the second
    assert hours.from_hours(row.bank_holiday_hours) == 16 * hours.GP_SESSION


def test_a_typed_figure_still_reads_to_two_places():
    assert hours.plain(D("138.0000")) == "138.00" and hours.plain(D("172.5")) == "172.50" and hours.plain(138) == "138.00"
    assert hours.plain(D("266.6667")) == "266.6667"
    sam = make_person(start_date=date(2027, 7, 6))
    make_allowance(sam, Y27, 210, 0)
    texts = [text for kind, text, _ in balances.statement(sam, Y27).lines if kind == "allowance"]
    assert texts[0] == "Annual leave allowance 6 Jul–31 Dec: 26 weeks of 52 at 210.00 h"


def test_worked_out_allowances_need_checking_unless_the_setting_says_otherwise():
    assert leave_settings.get().allowances_need_checking is True
    assert LeaveSetting._meta.get_field("allowances_need_checking").default is True


def test_the_superuser_deletes_a_person_with_a_copied_contract(root_client):
    sam = make_person(end_date=date(2026, 3, 31))
    make_contract(sam)
    make_allowance(sam, Y27, 138, 48)
    assert root_client.get("/admin/people/contract/").status_code == 200
    assert root_client.get("/admin/people/contract/add/").status_code == 403
    r = root_client.post(f"/admin/people/person/{sam.pk}/delete/", {"post": "yes"})
    assert r.status_code == 302 and not Person.objects.filter(pk=sam.pk).exists()
    assert not Contract.objects.exists() and not Allowance.objects.exists()


def test_the_hours_tab_shows_a_stored_figure_to_two_places_and_saves_it_back_untouched(monkeypatch):
    """The boxes take two decimal places; a figure read back from four must not be refused by them."""
    from leave.services import years
    real = years.years_for
    monkeypatch.setattr(years, "years_for", lambda person, today=None: real(person, today or date(2026, 11, 20)))
    nina = make_person(first_name="Nina", weekly_hours=D("30"), days_per_week=4)
    make_allowance(nina, Y27, 138, 48)
    c = client_for(make_person(first_name="Boss"), is_all_teams_manager=True)
    url = f"/staff/{nina.pk}/profile/?tab=hours"
    body = c.get(url).content.decode()
    assert 'name="annual_2027" value="138.00"' in body and 'name="bank_holiday_2027" value="48.00"' in body
    r = c.post(url, {"weekly_hours": "30.00", "days_per_week": "4", "annual_2027": "138.00", "bank_holiday_2027": "48.00", "note": ""})
    assert "Saved." in r.content.decode()
    assert "138.00 h" in client_for(nina).get(url).content.decode()      # and the person reads it as before
