"""Allowance spec 2026-11-18, section 8: the page at /staff/allowances/."""

import re
from datetime import date
from decimal import Decimal as D

import pytest

from leave.models import BankHoliday
from leave.services import entitlement
from people.models import Allowance
from people.services import health
from tests.factories import (client_for, make_allowance, make_bank_holiday, make_contract, make_person, make_team,
                             make_team_manager)

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 2, 1))]
Y27, Y28 = date(2027, 1, 1), date(2028, 1, 1)
JUNE = date(2027, 6, 1)
RECEPTION = [(1, 23)]
URL = "/staff/allowances/"


@pytest.fixture(autouse=True)
def bank_holidays_2028(db):
    for row in BankHoliday.objects.filter(day__year=2027):
        make_bank_holiday(row.day.replace(year=2028), row.name)


def _sam(weekly="37.5", **kw):
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D(weekly), days_per_week=5, **kw)
    make_contract(sam, weekly, steps=RECEPTION)
    return sam


@pytest.fixture
def world(db):
    """Boss manages everyone; Lead manages Nursing (Nina, and herself for
    the list but not for the buttons); Rec is in Reception."""
    nursing = make_team("Nursing")
    boss = _sam(first_name="Boss", team=make_team("Management"))
    lead = _sam(first_name="Lead", team=nursing, weekly="30")
    make_team_manager(lead, nursing)
    nina, rec = _sam(first_name="Nina", team=nursing), _sam(first_name="Rec")
    entitlement.refresh()
    return {"boss": boss, "lead": lead, "nina": nina, "rec": rec, "nursing": nursing,
            "c_boss": client_for(boss, is_all_teams_manager=True), "c_lead": client_for(lead), "c_rec": client_for(rec)}


def _row(person, year=Y27, from_day=None):
    return Allowance.objects.get(person=person, leave_year=year, from_day=from_day or year)


def _post(row, **extra):
    return {"row": row.pk, f"annual_{row.pk}": str(row.annual_hours), f"bank_holiday_{row.pk}": str(row.bank_holiday_hours), **extra}


def test_the_page_is_for_managers(world):
    assert world["c_rec"].get(URL).status_code == 403
    assert world["c_rec"].post(URL + "confirm/", _post(_row(world["nina"]))).status_code == 403
    assert _row(world["nina"]).needs_checking
    assert world["c_lead"].get(URL).status_code == 200
    from django.test import Client
    assert Client().get(URL).status_code == 302


def test_the_page_lists_each_row_with_its_figures_working_and_buttons(world):
    body = world["c_boss"].get(URL).content.decode()
    assert "<h2 id=\"to-check\">Allowances to check</h2>" in body and "Contracts to look at in Practice HR" in body
    row = _row(world["nina"])
    assert "Nina Patel" in body and "172 h 30 min" in body and "worked out, not yet checked" in body
    assert "23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min" in body
    assert f'name="row" value="{row.pk}"' in body and f'name="annual_{row.pk}" value="172.50"' in body
    assert f'href="/staff/allowances/{row.pk}/change/"' in body
    assert "Confirm all shown (6)" in body                              # Lead, Nina and Rec, two years each; never Boss's own
    own = _row(world["boss"])
    assert "Boss Patel" in body and f'name="row" value="{own.pk}"' not in body
    assert "<script" not in body.split("<main")[1] and "onclick" not in body


def test_a_team_manager_sees_only_their_team_and_no_buttons_on_their_own_rows(world):
    body = world["c_lead"].get(URL).content.decode()
    assert "Nina Patel" in body and "Lead Patel" in body and "Rec Patel" not in body
    assert f'name="row" value="{_row(world["nina"]).pk}"' in body
    assert f'name="row" value="{_row(world["lead"]).pk}"' not in body
    assert "Confirm all shown (2)" in body


def test_confirm_one_row(world):
    row = _row(world["nina"])
    r = world["c_lead"].post(URL + "confirm/", _post(row), follow=True)
    assert r.redirect_chain == [(URL, 302)] and "1 allowance confirmed." in r.content.decode()
    row.refresh_from_db()
    assert not row.needs_checking and row.checked_by == world["lead"].user


def test_nobody_confirms_their_own_or_another_teams(world):
    for person in (world["lead"], world["rec"]):
        r = world["c_lead"].post(URL + "confirm/", _post(_row(person)), follow=True)
        assert "1 skipped" in r.content.decode() and _row(person).needs_checking


def test_confirm_all_shown_skips_a_row_that_changed_after_the_page_was_drawn(world):
    body = world["c_boss"].get(URL).content.decode()
    form = body.split("Confirm all shown")[0].rsplit("<form", 1)[1]
    data = dict(re.findall(r'name="((?:annual|bank_holiday)_\d+)" value="([^"]+)"', form))
    data["row"] = re.findall(r'name="row" value="(\d+)"', form)
    assert len(data["row"]) == 6
    Allowance.objects.filter(pk=_row(world["rec"]).pk).update(annual_hours=D("150"))       # a contract changed meanwhile
    r = world["c_boss"].post(URL + "confirm/", data, follow=True)
    body = r.content.decode()
    assert "5 allowances confirmed." in body and "1 skipped: its figures changed after this page was drawn." in body
    assert _row(world["rec"]).needs_checking and not _row(world["nina"]).needs_checking
    assert "Confirm all shown (1)" in body


def test_confirm_all_as_filtered_keeps_the_team_box(world):
    nursing = world["nursing"]
    body = world["c_boss"].get(f"{URL}?team={nursing.pk}").content.decode()
    assert "Confirm all shown (4)" in body and "Rec Patel" not in body
    assert f'action="/staff/allowances/confirm/?team={nursing.pk}"' in body
    r = world["c_boss"].post(f"{URL}confirm/?team={nursing.pk}", _post(_row(world["nina"])))
    assert r.status_code == 302 and r["Location"] == f"{URL}?team={nursing.pk}"


def test_days_per_week_can_be_corrected_as_a_dated_row_is_confirmed(world):
    part = make_person(first_name="Part", start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=3)
    make_contract(part, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(part, "30", steps=RECEPTION, from_day=JUNE)
    entitlement.refresh()
    row = _row(part, from_day=JUNE)
    body = world["c_boss"].get(URL).content.decode()
    assert f'name="days_{row.pk}" min="1" max="7" value="3"' in body
    assert f'name="days_{_row(part).pk}"' not in body                    # not on the year's first row
    world["c_boss"].post(URL + "confirm/", _post(row, **{f"days_{row.pk}": "4"}))
    row.refresh_from_db()
    assert (row.days_per_week, row.needs_checking) == (4, False)


def test_a_bad_post_confirms_nothing(world):
    row = _row(world["nina"])
    for data in ({"row": "x"}, {"row": row.pk}, _post(row, **{f"annual_{row.pk}": "lots"}), _post(row, **{f"days_{row.pk}": "9"})):
        assert world["c_boss"].post(URL + "confirm/", data).status_code == 302
    assert _row(world["nina"]).needs_checking
    assert world["c_boss"].get(URL + "confirm/").status_code == 405


def test_use_the_worked_out_figure_from_the_second_list(world):
    typed = _sam(first_name="Typed")
    row = make_allowance(typed, Y27, 180, 60)
    make_allowance(typed, Y28, D("172.5"), 60)
    body = world["c_boss"].get(URL).content.decode()
    differ = body.split('id="differ"')[1].split('id="bank-holidays"')[0]
    assert "Typed Patel" in differ and "180 h and 60 h" in differ and "172 h 30 min and 60 h" in differ
    assert f'action="/staff/allowances/{row.pk}/use/"' in differ and "Use the worked-out figure" in differ
    assert world["c_rec"].post(f"{URL}{row.pk}/use/").status_code == 403
    assert world["c_lead"].post(f"{URL}{row.pk}/use/").status_code == 403        # another team's
    r = world["c_boss"].post(f"{URL}{row.pk}/use/", follow=True)
    assert "Typed Patel: the worked-out figure is in use." in r.content.decode()
    row.refresh_from_db()
    assert (row.annual_hours, row.source) == (D("172.5"), "worked_out")


def test_remove_a_typed_change_the_contracts_do_not_have(world):
    sam = world["rec"]
    row = make_allowance(sam, Y27, 138, 48, from_day=JUNE, weekly_hours=D("30"), days_per_week=4)
    body = world["c_boss"].get(URL).content.decode()
    assert "Remove this change" in body and "the contracts do not change on this day" in body
    r = world["c_boss"].post(f"{URL}{row.pk}/use/", follow=True)
    assert "Rec Patel: the change is removed." in r.content.decode() and not Allowance.objects.filter(pk=row.pk).exists()


def test_a_refusal_is_shown_on_the_page(world):
    plain = make_person(first_name="Plain")
    row = make_allowance(plain, Y27, 138, 48)
    r = world["c_boss"].post(f"{URL}{row.pk}/use/", follow=True)
    assert "This leave year is not worked out from a contract" in r.content.decode()


def test_the_change_dialog_types_both_figures_with_a_reason(world):
    row = _row(world["nina"])
    url = f"{URL}{row.pk}/change/"
    body = world["c_lead"].get(url).content.decode()
    assert 'name="annual_hours" value="172.50"' in body and "worked out, not yet checked" in body and "data-dialog-form" in body
    r = world["c_lead"].post(url, {"annual_hours": "180", "bank_holiday_hours": "60", "note": ""})
    assert r.status_code == 200 and "field-error" in r.content.decode()
    r = world["c_lead"].post(url, {"annual_hours": "180", "bank_holiday_hours": "60", "note": "contract says 24 days"})
    assert r.json() == {"refresh": True}
    row.refresh_from_db()
    assert (row.annual_hours, row.source) == (D("180"), "typed")
    assert world["c_lead"].get(f"{URL}{_row(world['lead']).pk}/change/").status_code == 403      # her own
    assert world["c_rec"].get(url).status_code == 403


def test_the_change_dialog_takes_days_per_week_on_a_dated_row_at_any_time(world):
    part = make_person(first_name="Part", start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=3)
    make_contract(part, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(part, "30", steps=RECEPTION, from_day=JUNE)
    entitlement.refresh()
    row = _row(part, from_day=JUNE)
    world["c_boss"].post(URL + "confirm/", _post(row))                   # already checked: Change is still there
    assert 'name="days_per_week"' not in world["c_boss"].get(f"{URL}{_row(part).pk}/change/").content.decode()
    url = f"{URL}{row.pk}/change/"
    body = world["c_boss"].get(url).content.decode()
    assert 'name="days_per_week" value="3"' in body and "Changing only the days per week leaves the figures as they are." in body
    figures = {"annual_hours": "138.00", "bank_holiday_hours": "48.00"}
    r = world["c_boss"].post(url, {**figures, "days_per_week": "4", "note": ""})
    assert r.status_code == 200 and "field-error" in r.content.decode()
    assert world["c_boss"].post(url, {**figures, "days_per_week": "8", "note": "x"}).status_code == 200
    r = world["c_boss"].post(url, {**figures, "days_per_week": "4", "note": "works four days from June"})
    assert r.json() == {"refresh": True}
    row.refresh_from_db()
    assert (row.days_per_week, row.source, row.needs_checking) == (4, "worked_out", False)


def test_the_other_lists_and_their_empty_states(world):
    body = world["c_boss"].get(URL).content.decode()
    assert "Every typed figure is what its contract gives." in body and "Nothing to look at." in body
    assert "Every leave year being worked out has its bank holidays." in body
    BankHoliday.objects.filter(day__year=2028).delete()
    make_person(first_name="None")
    body = world["c_boss"].get(URL).content.decode()
    assert '<a href="/time-off/bank-holidays/?year=2028">2028</a>' in body
    assert "None Patel" in body and "no contract from Practice HR" in body


def test_the_sidebar_offers_the_page_to_managers_only(world):
    assert 'href="/staff/allowances/"' in world["c_lead"].get("/staff/").content.decode()
    assert 'href="/staff/allowances/"' not in world["c_rec"].get("/staff/").content.decode()


# --- the Health card ------------------------------------------------------------------------------

def test_the_health_card_counts_the_four_lists_and_links_to_the_page(all_teams_user):
    sam = _sam()
    make_allowance(sam, Y27, 180, 60)
    make_person(first_name="None")
    BankHoliday.objects.filter(day__year=2028).delete()
    entitlement.refresh()
    a = health.figures(all_teams_user)["allowances"]
    assert (len(a.to_check), len(a.differ), a.bank_holidays, len(a.contracts)) == (1, 1, [Y28], 1)
    body = client_for(make_person(first_name="Boss"), is_all_teams_manager=True).get("/staff/").content.decode()       # Boss has no contract either
    for line in ("Allowances to check<strong>1</strong>", "Allowances that differ from the contract<strong>1</strong>",
                 "Bank holidays not entered<strong>1</strong>", "Contracts to look at in Practice HR<strong>2</strong>"):
        assert line in body, line
    assert 'href="/staff/allowances/#to-check"' in body


def test_the_health_card_shows_zeros_before_practice_hr_sends_any_contract():
    make_allowance(make_person(weekly_hours=D("30"), days_per_week=4), Y27, 138, 48)
    BankHoliday.objects.filter(day__year=2028).delete()
    body = client_for(make_person(first_name="Boss"), is_all_teams_manager=True).get("/staff/").content.decode()
    for line in ("Allowances to check<strong>0</strong>", "Allowances that differ from the contract<strong>0</strong>",
                 "Bank holidays not entered<strong>0</strong>", "Contracts to look at in Practice HR<strong>0</strong>"):
        assert line in body, line
    assert "/staff/allowances/#" not in body
