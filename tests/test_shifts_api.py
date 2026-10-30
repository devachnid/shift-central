"""The grid's JSON API (spec, sections 3 and 4): one window payload, small
mutations, never a redirect, and the Display switches honoured."""

import json
from datetime import date

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from accounts.models import User
from people.models import Person
from people.services import access
from shifts.models import DayChange, Entry, GridOptions
from shifts.services import options, window
from tests.factories import (make_department, make_entry, make_gp_session, make_person, make_team,
                             make_team_manager, make_user_for)

pytestmark = pytest.mark.django_db
MON = date(2027, 3, 1)


def _client(person, **kw):
    c = Client()
    c.force_login(make_user_for(person, **kw))
    return c


def _post(client, url, body):
    return client.post(url, data=json.dumps(body), content_type="application/json")


@pytest.fixture
def world():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_team_manager(lead, reception)
    return {"lead": lead, "c_lead": _client(lead),
            "nina": make_person(first_name="Nina", team=reception),
            "nurse": make_person(first_name="Nurse", team=nursing),
            "gp": make_person(first_name="Doc", team=make_team("GPs"), is_gp=True),
            "pmc": make_department("Reception PMC")}


def test_signed_out_gets_401_json_not_a_redirect():
    r = Client().get("/rota/api/window/?from=2027-03-01&weeks=1")
    assert r.status_code == 401 and r.json() == {"error": "signed out"}


def test_the_window_has_days_rows_cells_sessions_and_who_may_edit(world):
    make_entry(world["nina"], MON, department=world["pmc"], break_minutes=60)
    make_gp_session(world["gp"], MON, "PM")
    body = world["c_lead"].get("/rota/api/window/?from=2027-03-03&weeks=1").json()
    assert [d["date"] for d in body["days"]][:2] == ["2027-03-01", "2027-03-02"], "snapped to Monday"
    assert len(body["days"]) == 7 and body["days"][0]["label"] == "Mon. Mar. 1"
    rows = {r["name"]: r for r in body["rows"]}
    assert rows["Nina Patel"]["editable"] and not rows["Lead Patel"]["editable"]
    assert not rows["Nurse Patel"]["editable"] and not rows["Doc Patel"]["editable"]
    cell = rows["Nina Patel"]["cells"]["2027-03-01"][0]
    assert cell["line"] == "08:00-16:15 1 hour break Reception PMC" and cell["hours"] == 435
    assert cell["department_colour"] == world["pmc"].colour == "#5B8FD6", "the seeded colour"
    assert rows["Doc Patel"]["sessions"]["2027-03-01"] == [{"part": "PM", "label": "Surgery", "site": "AG", "note": ""}]
    assert body["can_edit"] and body["unnotified"] == 0
    assert "Reception PMC" in [d["name"] for d in body["departments"]], "the departments are offered to the menus"


def test_staff_see_only_rows_shown_to_them_and_cannot_edit(world):
    hidden = make_person(first_name="Hidden", show_to_other_staff=False)
    make_person(first_name="Gone", display_on_rota=False)
    body = _client(world["nina"]).get("/rota/api/window/?from=2027-03-01&weeks=1").json()
    names = {r["name"] for r in body["rows"]}
    assert "Nina Patel" in names and "Lead Patel" in names
    assert "Hidden Patel" not in names and "Gone Patel" not in names
    assert not body["can_edit"] and all(not r["editable"] for r in body["rows"])
    body = _client(hidden).get("/rota/api/window/?from=2027-03-01&weeks=1").json()
    assert "Hidden Patel" in {r["name"] for r in body["rows"]}, "you always see yourself"


def test_a_person_who_cannot_see_others_sees_only_their_row(world):
    me = make_person(first_name="Alone", can_see_other_staff=False)
    body = _client(me).get("/rota/api/window/?from=2027-03-01&weeks=1").json()
    assert [r["name"] for r in body["rows"]] == ["Alone Patel"]


def test_leavers_and_starters_outside_the_window_are_not_rows(world):
    make_person(first_name="Left", start_date=date(2020, 1, 1), end_date=date(2027, 2, 28))
    make_person(first_name="Soon", start_date=date(2027, 3, 8))
    body = world["c_lead"].get("/rota/api/window/?from=2027-03-01&weeks=1").json()
    names = {r["name"] for r in body["rows"]}
    assert "Left Patel" not in names and "Soon Patel" not in names
    body = world["c_lead"].get("/rota/api/window/?from=2027-03-01&weeks=2").json()
    assert "Soon Patel" in {r["name"] for r in body["rows"]}


def test_filters_by_name_team_and_department(world):
    make_entry(world["nina"], MON, department=world["pmc"])
    c = world["c_lead"]
    assert [r["name"] for r in c.get("/rota/api/window/?from=2027-03-01&weeks=1&name=nin").json()["rows"]] == ["Nina Patel"]
    team = world["nurse"].team.pk
    assert [r["name"] for r in c.get(f"/rota/api/window/?from=2027-03-01&weeks=1&team={team}").json()["rows"]] == ["Nurse Patel"]
    assert [r["name"] for r in c.get(f"/rota/api/window/?from=2027-03-01&weeks=1&dept={world['pmc'].pk}").json()["rows"]] == ["Nina Patel"]


def test_weeks_is_clamped_and_a_bad_date_is_400(world):
    c = world["c_lead"]
    assert len(c.get("/rota/api/window/?from=2027-03-01&weeks=99").json()["days"]) == 140
    assert c.get("/rota/api/window/?from=nope&weeks=1").status_code == 400


def test_cell_text_writes_and_answers_with_the_cell(world):
    r = _post(world["c_lead"], "/rota/api/cell/", {"person": world["nina"].pk, "day": "2027-03-01", "text": "08:00-12:00 Reception PMC"})
    assert r.status_code == 200
    cells = r.json()["cells"]
    assert cells[str(world["nina"].pk)]["2027-03-01"][0]["department_name"] == "Reception PMC"
    assert r.json()["unnotified"] == 1


def test_a_staff_user_is_refused_every_mutation_with_403_json(world):
    c = _client(world["nina"])
    nina = world["nina"].pk
    e = make_entry(world["nina"], MON)
    for url, body in (
        ("/rota/api/cell/", {"person": nina, "day": "2027-03-01", "text": "x"}),
        ("/rota/api/cell/items/", {"person": nina, "day": "2027-03-01", "items": []}),
        (f"/rota/api/entries/{e.pk}/", {"wfh": True}),
        ("/rota/api/move/", {"cells": [[nina, "2027-03-01"]], "days": 1, "rows": 0, "copy": False, "row_order": [nina]}),
        ("/rota/api/paste/", {"anchor": [nina, "2027-03-01"], "block": {"rows": [], "days": 0}, "mode": "replace", "row_order": [nina]}),
        ("/rota/api/clear/", {"cells": [[nina, "2027-03-01"]]}),
        ("/rota/api/replace/", {"cells": [[nina, "2027-03-01"]], "find": "a", "replace": "b", "match_case": False}),
        ("/rota/api/order/", {"people": [nina]}),
    ):
        r = _post(c, url, body)
        assert r.status_code == 403 and "error" in r.json(), url


def test_a_team_manager_is_refused_another_team_with_403_and_nothing_written(world):
    r = _post(world["c_lead"], "/rota/api/cell/", {"person": world["nurse"].pk, "day": "2027-03-01", "text": "08:00-12:00"})
    assert r.status_code == 403 and Entry.objects.count() == 0


def test_bad_input_is_400_with_a_message(world):
    r = _post(world["c_lead"], "/rota/api/cell/items/", {"person": world["nina"].pk, "day": "2027-03-01",
                                                        "items": [{"kind": "shift", "start": "08:00"}]})
    assert r.status_code == 400 and "finish" in r.json()["error"]
    r = world["c_lead"].post("/rota/api/cell/", data="not json", content_type="application/json")
    assert r.status_code == 400
    r = world["c_lead"].get("/rota/api/cell/")
    assert r.status_code == 405


def test_patch_move_clear_and_order_answer_with_their_cells(world):
    c, nina = world["c_lead"], world["nina"]
    e = make_entry(nina, MON)
    r = _post(c, f"/rota/api/entries/{e.pk}/", {"overtime": "toil", "appearance": {"bold": True}})
    assert r.json()["cells"][str(nina.pk)]["2027-03-01"][0]["overtime"] == "toil"
    r = _post(c, "/rota/api/move/", {"cells": [[nina.pk, "2027-03-01"]], "days": 1, "rows": 0, "copy": True, "row_order": [nina.pk]})
    assert set(r.json()["cells"][str(nina.pk)]) == {"2027-03-02"}, "a copy reports only what it wrote"
    r = _post(c, "/rota/api/clear/", {"cells": [[nina.pk, "2027-03-02"]]})
    assert r.json()["cells"][str(nina.pk)]["2027-03-02"] == []
    r = _post(c, "/rota/api/order/", {"people": [nina.pk, world["lead"].pk]})
    assert r.status_code == 200
    nina.refresh_from_db()
    assert nina.display_order == 10


def test_options_common_and_recent_ride_the_window(world):
    GridOptions.objects.create(user=world["lead"].user, data={"job_titles": True})
    make_entry(world["nina"], MON, department=world["pmc"], created_by=world["lead"].user)
    body = world["c_lead"].get("/rota/api/window/?from=2027-03-01&weeks=1").json()
    assert body["options"]["job_titles"] is True and body["options"]["paste"] == "replace"
    assert body["common"][0]["label"] == "08:00–16:15 Reception PMC"
    assert body["recent"][0]["department"] == world["pmc"].pk


def test_hide_staff_with_no_shifts_and_my_shifts_on_top(world):
    make_entry(world["nina"], MON)
    GridOptions.objects.create(user=world["lead"].user, data={"hide_no_shifts": True})
    body = world["c_lead"].get("/rota/api/window/?from=2027-03-01&weeks=1").json()
    assert [r["name"] for r in body["rows"]] == ["Nina Patel"]
    GridOptions.objects.filter(user=world["lead"].user).update(data={"my_shifts_on_top": True})
    body = world["c_lead"].get("/rota/api/window/?from=2027-03-01&weeks=1").json()
    assert body["rows"][0]["name"] == "Lead Patel"


def test_unnotified_counts_people_the_viewer_manages(world):
    DayChange.objects.create(person=world["nina"], day=MON, before="no shift")
    DayChange.objects.create(person=world["nurse"], day=MON, before="no shift")
    assert world["c_lead"].get("/rota/api/window/?from=2027-03-01&weeks=1").json()["unnotified"] == 1


def test_saving_options_drops_unknown_keys_and_coerces_values(world):
    saved = options.save(world["lead"].user, {"job_titles": 1, "font_size": "huge", "days": ["1", "9", "x", 3],
                                              "paste": "add", "nonsense": True})
    assert saved["job_titles"] is True and saved["font_size"] == "md" and saved["paste"] == "add"
    assert saved["days"] == [1, 3] and "nonsense" not in saved
    assert "nonsense" not in GridOptions.objects.get(user=world["lead"].user).data


def test_editable_agrees_with_can_manage_for_every_kind_of_viewer(world):
    make_person(first_name="Teamless", team=None)
    boss = make_user_for(make_person(first_name="Boss", team=world["nurse"].team), is_all_teams_manager=True)
    staff = make_user_for(world["nina"])
    for viewer in (world["lead"].user, boss, staff):
        viewer = User.objects.get(pk=viewer.pk)  # fresh, as a request has it
        body = window.payload(viewer, MON, 1, {})
        assert len(body["rows"]) >= 5
        for row in body["rows"]:
            assert row["editable"] == access.can_manage(viewer, Person.objects.get(pk=row["person"])), (viewer, row["name"])
        assert body["can_edit"] == access.is_manager(viewer)


def test_the_window_costs_the_same_queries_for_three_rows_or_twelve(world):
    def cost():
        viewer = User.objects.get(pk=world["lead"].user.pk)
        with CaptureQueriesContext(connection) as ctx:
            body = window.payload(viewer, MON, 1, {})
        return len(ctx), len(body["rows"])

    few_queries, few_rows = cost()
    for i in range(9):
        make_person(first_name=f"Extra{i}", team=world["lead"].team)
    many_queries, many_rows = cost()
    assert many_rows >= few_rows + 9
    assert many_queries == few_queries
