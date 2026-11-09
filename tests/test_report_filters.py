"""Filters asked for on staging: a Person box on the Hours, Leave and Payroll
reports, and a Team box on the Sickness and Leave summaries. A filter only
ever narrows what the viewer may already see, and the downloads and the
previous / next links keep it."""

import csv
import io
from datetime import date
from decimal import Decimal

import pytest
from openpyxl import load_workbook

from tests.factories import client_for, make_allowance, make_entry, make_person, make_team, make_team_manager

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 1, 25))]
Y27 = date(2027, 1, 1)


@pytest.fixture
def world():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    ann = make_person(first_name="Annabel", last_name="Ash", team=reception, start_date=date(2020, 1, 6))
    zeb = make_person(first_name="Zebedee", last_name="Zinc", team=nursing, start_date=date(2020, 1, 6))
    for p in (ann, zeb):
        make_allowance(p, Y27, Decimal("172.5"), 60)
        make_entry(p, date(2027, 1, 18))
    boss = make_person(first_name="Boss", team=make_team("Management"), start_date=date(2020, 1, 6))
    lead = make_person(first_name="Lead", team=reception, start_date=date(2020, 1, 6))
    make_team_manager(lead, reception)
    return {"ann": ann, "zeb": zeb, "reception": reception, "nursing": nursing,
            "boss": client_for(boss, is_all_teams_manager=True), "lead": client_for(lead), "staff": client_for(ann)}


def _names(body):
    return {name for name in ("Annabel Ash", "Zebedee Zinc") if name in body}


# --- a Person box on Hours, Leave and Payroll --------------------------------------------------------

@pytest.mark.parametrize("url", ["/reports/hours/?from=2027-01-18&to=2027-01-24", "/reports/leave/?from=2027-01-01&to=2027-12-31",
                                 "/reports/payroll/?month=2027-01"])
def test_choosing_a_person_shows_only_them(world, url):
    body = world["boss"].get(url).content.decode()
    assert _names(body) == {"Annabel Ash", "Zebedee Zinc"} and 'name="person"' in body
    body = world["boss"].get(f"{url}&person={world['zeb'].pk}").content.decode()
    assert "Zebedee Zinc" in body and "Annabel Ash" not in body.split("</select>")[-1]      # listed in the box, not the report
    assert f'<option value="{world["zeb"].pk}" selected>' in body


@pytest.mark.parametrize("url", ["/reports/hours/?from=2027-01-18&to=2027-01-24", "/reports/leave/?from=2027-01-01&to=2027-12-31",
                                 "/reports/payroll/?month=2027-01"])
def test_a_person_the_viewer_does_not_manage_is_no_filter(world, url):
    body = world["lead"].get(f"{url}&person={world['zeb'].pk}").content.decode()
    assert "Zebedee Zinc" not in body and "Annabel Ash" in body


@pytest.mark.parametrize("url", ["/reports/hours/", "/reports/leave/"])
def test_staff_see_only_themselves_and_no_person_box(world, url):
    body = world["staff"].get(url).content.decode()
    assert 'name="person"' not in body


def test_the_hours_download_keeps_the_person(world):
    body = world["boss"].get(f"/reports/hours/?from=2027-01-18&to=2027-01-24&person={world['ann'].pk}").content.decode()
    assert f"download=1&amp;person={world['ann'].pk}" in body
    rows = list(csv.reader(io.StringIO(world["boss"].get(
        f"/reports/hours/?from=2027-01-18&to=2027-01-24&person={world['ann'].pk}&download=1").content.decode())))
    assert {r[0] for r in rows[1:]} == {"Annabel Ash"}


def test_the_leave_download_keeps_the_person(world):
    body = world["boss"].get(f"/reports/leave/?from=2027-01-01&to=2027-12-31&person={world['ann'].pk}").content.decode()
    assert f"download=1&amp;person={world['ann'].pk}" in body
    rows = list(csv.reader(io.StringIO(world["boss"].get(
        f"/reports/leave/?from=2027-01-01&to=2027-12-31&person={world['ann'].pk}&download=1").content.decode())))
    assert {r[0] for r in rows[1:]} == {"Annabel Ash"}


def test_the_payroll_page_keeps_the_person_and_says_mark_as_sent_covers_everyone(world):
    body = world["boss"].get(f"/reports/payroll/?month=2027-01&person={world['ann'].pk}").content.decode()
    assert f"month=2027-01&amp;download=1&amp;person={world['ann'].pk}" in body
    assert f"month=2026-12&amp;person={world['ann'].pk}" in body                     # the previous month keeps it
    assert "Showing Annabel Ash only" in body and "Mark as sent covers everyone" in body
    book = load_workbook(io.BytesIO(world["boss"].get(f"/reports/payroll/?month=2027-01&person={world['ann'].pk}&download=1").content))
    sheet = book.worksheets[0]
    assert "Annabel Ash only" in sheet.cell(2, 1).value                         # row 1 is the headings
    names = {sheet.cell(r, 1).value for r in range(3, sheet.max_row + 1)} - {None}
    assert names == {"Annabel Ash"}


# --- a Team box on the two summaries -------------------------------------------------------------------

@pytest.mark.parametrize("url", ["/reports/sickness/?from=2026-07-01&to=2027-01-25", "/reports/leave-summary/?year=2027"])
def test_choosing_a_team_shows_only_its_people_and_totals(world, url):
    body = world["boss"].get(url).content.decode()
    assert _names(body) == {"Annabel Ash", "Zebedee Zinc"} and 'name="team"' in body
    body = world["boss"].get(f"{url}&team={world['nursing'].pk}").content.decode()
    report = body.split("</form>", 1)[1]
    assert "Zebedee Zinc" in report and "Annabel Ash" not in report and "Practice" not in report
    assert f'<option value="{world["nursing"].pk}" selected>' in body


@pytest.mark.parametrize("url", ["/reports/sickness/?from=2026-07-01&to=2027-01-25", "/reports/leave-summary/?year=2027"])
def test_a_team_manager_chooses_only_among_their_teams(world, url):
    body = world["lead"].get(f"{url}&team={world['nursing'].pk}").content.decode()
    assert "Zebedee Zinc" not in body and "Annabel Ash" in body and ">Nursing</option>" not in body


@pytest.mark.parametrize("url", ["/reports/sickness/?from=2026-07-01&to=2027-01-25", "/reports/leave-summary/?year=2027"])
def test_the_summary_downloads_keep_the_team_and_name_it(world, url):
    team = world["nursing"].pk
    body = world["boss"].get(f"{url}&team={team}").content.decode()
    assert f"format=pdf&amp;team={team}" in body and f"format=xlsx&amp;team={team}" in body
    book = load_workbook(io.BytesIO(world["boss"].get(f"{url}&team={team}&format=xlsx").content))
    cells = {c.value for sheet in book.worksheets for row in sheet.iter_rows() for c in row} - {None}
    assert "Zebedee Zinc" in cells and "Annabel Ash" not in cells and "Practice" not in cells
    pdf = world["boss"].get(f"{url}&team={team}&format=pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")


def test_the_leave_summarys_year_links_keep_the_team(world):
    team = world["nursing"].pk
    body = world["boss"].get(f"/reports/leave-summary/?year=2027&team={team}").content.decode()
    assert f"year=2026&amp;team={team}" in body and f"year=2028&amp;team={team}" in body
