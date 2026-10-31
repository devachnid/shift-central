"""REP-04: the sickness one-pager, practice then teams then people, as a
page, a PDF or an Excel file; managers only, their people."""

import io
from datetime import date

import pytest
from django.test import Client
from openpyxl import load_workbook

from absence.services import onepager
from tests.factories import make_person, make_sick, make_team, make_team_manager, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2026, 12, 31))]
START, END = date(2026, 7, 1), date(2026, 12, 31)


def _client(person, **kw):
    c = Client()
    c.force_login(person.user or make_user_for(person, **kw))
    return c


@pytest.fixture
def world():
    boss = make_person(first_name="Boss", team=make_team("Management"))
    make_user_for(boss, is_all_teams_manager=True)
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_user_for(lead)
    make_team_manager(lead, reception)
    ann = make_person(first_name="Ann", team=reception)
    bea = make_person(first_name="Bea", team=reception)
    nick = make_person(first_name="Nick", team=nursing)
    for d in (date(2026, 7, 6), date(2026, 8, 3), date(2026, 9, 7), date(2026, 10, 5)):
        make_sick(ann, d)                                                     # 4 instances: Trigger 2
    make_sick(bea, date(2026, 6, 29), date(2026, 8, 7))                       # 40 days, long; 38 of them in the range
    make_sick(nick, date(2026, 11, 2), date(2026, 11, 3), dates_only=True)
    make_sick(nick, date(2026, 3, 2))                                          # before the range and the window
    return {"boss": boss, "lead": lead, "ann": ann, "bea": bea, "nick": nick}


def test_the_figures(world):
    s = onepager.summary(world["boss"].user, START, END)
    p = s["practice"]
    assert (p.instances, p.days, p.trigger_1, p.trigger_2, p.trigger_3) == (6, 4 + 38 + 2, 0, 1, 0)
    teams = {t.name: t for t in s["teams"]}
    assert (teams["Reception"].instances, teams["Reception"].people, teams["Nursing"].instances) == (5, 3, 1)      # Lead is in Reception too
    people = {r.person.first_name: r for r in s["people"]}
    assert (people["Ann"].instances, people["Ann"].trigger, people["Ann"].days) == (4, "Trigger 2", 4)
    assert (people["Bea"].longest, people["Bea"].long, people["Bea"].days, people["Bea"].instances) == (40, True, 38, 1)
    assert (people["Nick"].instances, people["Nick"].days, people["Nick"].trigger) == (1, 2, "")
    assert people["Nick"].seconds == 0                                        # dates only: no hours
    lead_rows = [r.person.first_name for r in onepager.summary(world["lead"].user, START, END)["people"]]
    assert sorted(lead_rows) == ["Ann", "Bea", "Lead"]


def test_the_page_pdf_and_excel(world):
    c = _client(world["boss"])
    body = c.get("/reports/sickness/?from=2026-07-01&to=2026-12-31").content.decode()
    assert "Sickness summary" in body and "Trigger 2" in body and "Reception" in body and "long" in body
    r = c.get("/reports/sickness/?from=2026-07-01&to=2026-12-31&format=pdf")
    assert r["Content-Type"] == "application/pdf" and r.content.startswith(b"%PDF") and 'filename="sickness-2026-07-01-2026-12-31.pdf"' in r["Content-Disposition"]
    r = c.get("/reports/sickness/?from=2026-07-01&to=2026-12-31&format=xlsx")
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Practice", "Teams", "People"] and wb["People"]["A1"].value == "Name"
    assert _client(world["ann"]).get("/reports/sickness/").status_code == 403
    assert 'href="/reports/sickness/"' in c.get("/reports/hours/").content.decode()


def test_the_default_range_is_the_rolling_six_months(world):
    body = _client(world["boss"]).get("/reports/sickness/").content.decode()
    assert 'value="2026-07-01"' in body and 'value="2026-12-31"' in body
