"""Free-typed text becomes a shift, a comment or a separator (spec,
section 5). The cases live in frontend/src/rota-grid/parser.cases.json so
the TypeScript preview is tested against the same table."""

import json
from datetime import date, time, timedelta
from pathlib import Path

import pytest

from people.models import Department
from shifts.services import parse, render
from tests.factories import make_department, make_entry, make_person

pytestmark = pytest.mark.django_db
CASES = json.loads((Path(__file__).resolve().parents[1] / "frontend/src/rota-grid/parser.cases.json").read_text())


@pytest.fixture
def departments():
    return [make_department(name) for name in CASES["departments"]]


def _as_json(item):
    out = dict(item)
    if out["kind"] == "shift":
        out["start"], out["finish"] = out["start"].strftime("%H:%M"), out["finish"].strftime("%H:%M")
        out["department"] = out["department"].name if out["department"] else None
    return out


@pytest.mark.parametrize("case", CASES["cases"], ids=[c["line"] for c in CASES["cases"]])
def test_every_case_in_the_shared_table(departments, case):
    assert _as_json(parse.line(case["line"], departments)) == case["expect"]


def test_a_cell_is_one_item_per_line_and_blank_lines_are_skipped(departments):
    items = parse.cell("08:00-12:00\n\n---\nTraining day\n", departments)
    assert [i["kind"] for i in items] == ["shift", "separator", "comment"]


def test_an_archived_department_is_not_matched(departments):
    Department.objects.filter(name="HCA").update(archived=True)
    offered = Department.objects.filter(archived=False)
    assert parse.line("08:00-12:00 HCA", offered)["department"] is None


def test_a_comment_is_cut_at_200_characters(departments):
    assert len(parse.line("x" * 300, departments)["text"]) == 200


def test_render_round_trips_through_parse(departments):
    p = make_person()
    hca = Department.objects.get(name="HCA")
    e = make_entry(p, date(2027, 3, 1), start=time(8), finish=time(16, 15), break_minutes=60,
                   department=hca, text="flu clinic", wfh=True, overtime="toil")
    line = render.line(e)
    assert line == "08:00-16:15 1 hour break HCA WFH TOIL flu clinic"
    back = parse.line(line, departments)
    assert (back["start"], back["finish"], back["break_minutes"], back["department"], back["text"],
            back["wfh"], back["overtime"]) == (time(8), time(16, 15), 60, hca, "flu clinic", True, "toil")


def test_day_text_and_cell_text(departments):
    p = make_person()
    day = date(2027, 3, 1)
    assert render.day_text(p, day) == "no shift"
    make_entry(p, day, start=time(8), finish=time(12))
    make_entry(p, day, kind="comment", text="then PMC")
    assert render.day_text(p, day) == "08:00-12:00 / then PMC"
    assert render.cell_text(p.entries.filter(day=day)) == "08:00-12:00\nthen PMC"


def test_durations_and_the_audit_note():
    assert render.duration(timedelta(hours=7, minutes=15)) == "7 h 15 min"
    assert render.duration(timedelta(hours=8)) == "8 h"
    assert render.duration(timedelta(minutes=30)) == "30 min"
    assert render.duration(timedelta(0)) == "0 min"
    p = make_person(first_name="Nina")
    assert render.audit_note(p, date(2027, 3, 1)) == "Mon 1 Mar 2027 · Nina Patel"
