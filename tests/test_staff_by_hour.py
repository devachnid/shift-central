"""Staff by hour (spec 5, section 10)."""

import io
from datetime import date, time, timedelta
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from shifts.services import staff_by_hour
from tests.factories import (client_for, make_department, make_entry, make_person, make_team, make_team_manager, make_user_for)

pytestmark = pytest.mark.django_db
MON = date(2026, 11, 9)


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_team_manager(lead, reception)
    c = SimpleNamespace(reception=reception, nursing=nursing, lead=lead, boss=make_person(first_name="Boss", team=reception),
                        sam=make_person(first_name="Sam", team=reception), ann=make_person(first_name="Ann", team=reception),
                        nina=make_person(first_name="Nina", team=nursing))
    for p in (lead, c.sam, c.nina):
        make_user_for(p)
    make_user_for(c.boss, is_all_teams_manager=True)
    return c


def day(report, d=MON):
    (row,) = [r for r in report["rows"] if r["day"] == d]
    return dict(zip(report["columns"], row["counts"])), row


def test_a_shift_counts_in_every_hour_it_touches_and_a_quarter_hour_still_counts(cast):
    make_entry(cast.sam, MON, start=time(8), finish=time(16, 15))
    report = staff_by_hour.report(cast.boss.user, MON, MON)
    counts, _ = day(report)
    assert report["columns"] == list(range(8, 17)) and set(counts.values()) == {1}
    assert report["labels"][0] == "08:00" and report["labels"][-1] == "16:00"


def test_a_shift_ending_on_the_hour_does_not_count_in_that_hour(cast):
    make_entry(cast.sam, MON, start=time(9), finish=time(12))
    counts, _ = day(staff_by_hour.report(cast.boss.user, MON, MON))
    assert counts == {9: 1, 10: 1, 11: 1}


def test_overlapping_people_add_up_and_the_peak_is_the_busiest_hour(cast):
    make_entry(cast.sam, MON, start=time(8), finish=time(12))
    make_entry(cast.ann, MON, start=time(10), finish=time(14))
    counts, row = day(staff_by_hour.report(cast.boss.user, MON, MON))
    assert counts == {8: 1, 9: 1, 10: 2, 11: 2, 12: 1, 13: 1} and row["peak"] == 2


def test_one_person_with_two_shifts_in_an_hour_counts_once(cast):
    make_entry(cast.sam, MON, start=time(8), finish=time(10))
    make_entry(cast.sam, MON, start=time(9, 30), finish=time(11))
    counts, _ = day(staff_by_hour.report(cast.boss.user, MON, MON))
    assert counts == {8: 1, 9: 1, 10: 1}


def test_working_from_home_people_count_and_have_their_own_line(cast):
    make_entry(cast.sam, MON, start=time(8), finish=time(10))
    make_entry(cast.ann, MON, start=time(8), finish=time(10), wfh=True)
    report = staff_by_hour.report(cast.boss.user, MON, MON)
    counts, row = day(report)
    assert counts == {8: 2, 9: 2} and row["wfh"] == [1, 1]


def test_the_site_filter_keeps_only_that_sites_shifts(cast):
    ag, pmc = make_department("Reception AG"), make_department("Reception PMC")
    make_entry(cast.sam, MON, start=time(8), finish=time(10), department=ag)
    make_entry(cast.ann, MON, start=time(8), finish=time(10), department=pmc)
    make_entry(cast.nina, MON, start=time(8), finish=time(10))                       # no site
    boss = cast.boss.user
    assert day(staff_by_hour.report(boss, MON, MON, site="AG"))[0] == {8: 1, 9: 1}
    assert day(staff_by_hour.report(boss, MON, MON, site="PMC"))[0] == {8: 1, 9: 1}
    assert day(staff_by_hour.report(boss, MON, MON))[0] == {8: 3, 9: 3}


def test_the_team_filter_and_a_team_managers_scope(cast):
    make_entry(cast.sam, MON, start=time(8), finish=time(10))
    make_entry(cast.nina, MON, start=time(8), finish=time(10))
    assert day(staff_by_hour.report(cast.boss.user, MON, MON, team=cast.nursing))[0] == {8: 1, 9: 1}
    assert day(staff_by_hour.report(cast.lead.user, MON, MON))[0] == {8: 1, 9: 1}


def test_gps_are_left_out(cast):
    gp = make_person(first_name="Gina", team=cast.reception, is_gp=True)
    make_entry(gp, MON, start=time(8), finish=time(10))
    assert staff_by_hour.report(cast.boss.user, MON, MON)["columns"] == []


def test_the_range_is_capped_at_thirty_one_days_and_an_empty_range_has_rows_but_no_columns(cast):
    r = staff_by_hour.report(cast.boss.user, MON, MON + timedelta(days=90))
    assert len(r["rows"]) == 31 and r["columns"] == [] and all(row["counts"] == [] for row in r["rows"])
    swapped = staff_by_hour.report(cast.boss.user, MON + timedelta(days=2), MON)
    assert swapped["start"] == MON and len(swapped["rows"]) == 3


def test_the_page_and_the_download(cast):
    make_entry(cast.sam, MON, start=time(8), finish=time(10))
    assert client_for(cast.sam).get("/reports/staff-by-hour/").status_code == 403
    c = client_for(cast.lead)
    page = c.get(f"/reports/staff-by-hour/?from={MON}&to={MON}").content.decode()
    assert "08:00" in page and "09:00" in page and "of which WFH" in page and "GPs" in page
    r = c.get(f"/reports/staff-by-hour/?from={MON}&to={MON}&download=1")
    ws = load_workbook(io.BytesIO(r.content)).active
    assert [c.value for c in ws[1]][:4] == ["Date", "Day", "08:00", "09:00"] and ws["C2"].value == 1
    assert 'href="/reports/staff-by-hour/"' in c.get("/rota/").content.decode()
