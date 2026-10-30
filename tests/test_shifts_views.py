"""The Rota page and its pop-ups (spec, sections 3, 4 and 10)."""

import json
from datetime import date

import pytest
from django.test import Client

from shifts.models import Entry, GridOptions, Template
from tests.factories import make_department, make_entry, make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db
MON = date(2027, 3, 1)


def _client(person, **kw):
    c = Client()
    c.force_login(make_user_for(person, **kw))
    return c


@pytest.fixture
def lead():
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    return lead


def test_the_rota_page_mounts_the_island_with_its_window(lead):
    body = _client(lead).get("/rota/?from=2027-03-03&weeks=2&team=1").content.decode()
    assert 'data-component="rota-grid"' in body and 'data-from="2027-03-01"' in body
    assert 'data-weeks="2"' in body and 'data-api="/rota/api/"' in body and 'data-role="team"' in body
    assert "Notify staff" in body and "Templates" in body and "Options" in body and "Filters" in body
    assert '<h1 class="topbar-title">Rota</h1>' in body
    assert 'data-nav="rota"' in body and 'href="/rota/today/"' in body
    assert f'data-me="{lead.pk}"' in body and 'data-reorder=""' in body and 'data-bar="rota-bar"' in body
    assert 'data-filters="from=2027-03-01&amp;weeks=2&amp;team=1"' in body


def test_home_is_the_rota_and_staff_see_no_manager_actions():
    me = make_person()
    c = _client(me)
    assert c.get("/").url == "/rota/"
    body = c.get("/rota/").content.decode()
    assert "Notify staff" not in body and "Templates" not in body
    assert 'data-nav="rota"' in body and 'href="/rota/today/"' not in body
    assert 'data-nav="reports"' in body


def test_the_phone_list_shows_my_week_first(lead):
    make_entry(lead, MON, text="mine")
    body = _client(lead).get("/rota/?from=2027-03-01").content.decode()
    assert 'class="rota-phone"' in body and "mine" in body


def test_weeks_and_date_are_normalised_and_bad_values_fall_back(lead):
    body = _client(lead).get("/rota/?from=garbage&weeks=0").content.decode()
    assert 'data-weeks="1"' in body


def test_the_shift_dialog_saves_through_the_service_and_asks_for_a_refresh(lead):
    nina = make_person(first_name="Nina", team=lead.team)
    pmc = make_department("Reception PMC")
    c = _client(lead)
    body = c.get(f"/rota/shift/{nina.pk}/2027-03-01/").content.decode()
    assert "Reception PMC" in body and 'name="overtime"' in body
    r = c.post(f"/rota/shift/{nina.pk}/2027-03-01/", {"start": "08:00", "finish": "16:15", "break_minutes": "60",
                                                      "department": pmc.pk, "text": "", "overtime": "", "wfh": "on"})
    assert r.json() == {"refresh": True}
    e = Entry.objects.get()
    assert e.break_minutes == 60 and e.department == pmc and e.wfh
    r = c.post(f"/rota/shift/{nina.pk}/2027-03-01/{e.pk}/", {"start": "09:00", "finish": "08:00", "break_minutes": "0",
                                                             "department": "", "text": "", "overtime": ""})
    assert r.status_code == 200 and "after the start" in r.content.decode()


def test_the_shift_dialog_refuses_people_the_viewer_does_not_manage(lead):
    other = make_person(first_name="Other", team=make_team("Nursing"))
    c = _client(lead)
    assert c.get(f"/rota/shift/{other.pk}/2027-03-01/").status_code == 403
    assert c.get(f"/rota/shift/{lead.pk}/2027-03-01/").status_code == 403


def test_options_save_and_the_filters_dialog_submits_as_the_grids_query(lead):
    c = _client(lead)
    r = c.post("/rota/options/", {"job_titles": "on", "paste": "add", "days": ["0", "1", "2", "3", "4"], "font_size": "lg"})
    assert r.json() == {"refresh": True}
    assert GridOptions.objects.get(user=lead.user).data == {"job_titles": True, "paste": "add", "days": [0, 1, 2, 3, 4],
                                                            "font_size": "lg", "staff_colours": False,
                                                            "department_colours": False, "float_headers": False,
                                                            "my_shifts_on_top": False, "only_my_shifts": False,
                                                            "hide_no_shifts": False, "spacing": "normal"}
    body = c.get("/rota/filters/?from=2027-03-01&weeks=1").content.decode()
    assert 'action="/rota/"' in body and 'name="from" value="2027-03-01"' in body


def test_find_and_replace_dialog_posts_to_the_service(lead):
    nina = make_person(first_name="Nina", team=lead.team)
    make_entry(nina, MON, kind="comment", text="old text")
    c = _client(lead)
    body = c.get(f"/rota/replace/?cells={nina.pk}:2027-03-01").content.decode()
    assert f'value="{nina.pk}:2027-03-01"' in body
    r = c.post("/rota/replace/", {"cells": f"{nina.pk}:2027-03-01", "find": "old", "replace": "new"})
    assert r.json() == {"refresh": True}
    assert Entry.objects.get().text == "new text"


def test_save_template_dialog_has_an_empty_block_field_for_the_grid_to_fill(lead):
    c = _client(lead)
    body = c.get("/rota/templates/save/").content.decode()
    assert 'name="block" value=""' in body
    given = c.get("/rota/templates/save/", {"block": '{"days": 1}'}).content.decode()
    assert 'name="block" value="{&quot;days&quot;: 1}"' in given


def test_templates_save_apply_rename_delete(lead):
    nina = make_person(first_name="Nina", team=lead.team)
    c = _client(lead)
    block = json.dumps({"days": 1, "rows": [[[{"kind": "comment", "text": "tpl"}]]]})
    r = c.post("/rota/templates/save/", {"name": "Mon off", "block": block})
    assert r.json() == {"refresh": True}
    t = Template.objects.get(name="Mon off")
    body = c.get(f"/rota/templates/?cell={nina.pk}:2027-03-01&row_order={nina.pk}").content.decode()
    assert "Mon off" in body and "Apply" in body
    r = c.post(f"/rota/templates/{t.pk}/apply/", {"cell": f"{nina.pk}:2027-03-01", "row_order": str(nina.pk)})
    assert r.json() == {"refresh": True} and Entry.objects.get().text == "tpl"
    c.post(f"/rota/templates/{t.pk}/rename/", {"name": "Monday off"})
    assert Template.objects.get(pk=t.pk).name == "Monday off"
    c.post(f"/rota/templates/{t.pk}/delete/")
    assert not Template.objects.filter(pk=t.pk).exists()


def test_download_is_a_csv_of_the_window(lead):
    nina = make_person(first_name="Nina", team=lead.team)
    make_entry(nina, MON)
    r = _client(lead).get("/rota/download/?from=2027-03-01&weeks=1")
    assert r["Content-Type"] == "text/csv" and 'filename="rota-2027-03-01.csv"' in r["Content-Disposition"]
    text = r.content.decode()
    assert text.splitlines()[0].startswith("Name,Team,Mon 1 Mar")
    assert "Nina Patel,Reception,08:00-16:15" in text


def test_weeks_that_are_not_a_number_fall_back_to_one(lead):
    assert 'data-weeks="1"' in _client(lead).get("/rota/?weeks=abc").content.decode()


def test_done_sorting_leaves_reorder_mode_and_no_link_carries_it(lead):
    body = _client(lead).get("/rota/?from=2027-03-01&weeks=1&reorder=1").content.decode()
    assert 'data-reorder="1"' in body
    assert 'href="/rota/?from=2027-03-01&amp;weeks=1">Done sorting' in body
    assert 'data-filters="from=2027-03-01&amp;weeks=1"' in body
    assert "reorder=1" not in body.split("</header>")[0] and "reorder=1" not in body.split("<main")[1]


def test_the_shift_dialog_404s_on_a_day_that_is_not_a_date(lead):
    nina = make_person(first_name="Nina", team=lead.team)
    c = _client(lead)
    assert c.get(f"/rota/shift/{nina.pk}/not-a-day/").status_code == 404
    assert c.post(f"/rota/shift/{nina.pk}/2027-13-45/", {}).status_code == 404


def test_the_shift_dialog_shows_errors_under_each_field(lead):
    nina = make_person(first_name="Nina", team=lead.team)
    body = _client(lead).post(f"/rota/shift/{nina.pk}/2027-03-01/", {
        "start": "08:00", "finish": "16:00", "break_minutes": "7", "department": "9999", "overtime": "bogus"}).content.decode()
    assert body.count('class="field-error"') == 3


def test_find_and_replace_shows_field_errors_and_survives_a_bad_cell_date(lead):
    c = _client(lead)
    body = c.post("/rota/replace/", {"cells": "1:2027-03-01", "find": "", "replace": "x"}).content.decode()
    assert "This field is required." in body
    r = c.post("/rota/replace/", {"cells": "1:not-a-date", "find": "a", "replace": "b"})
    assert r.status_code == 200 and "flash-error" in r.content.decode()


def test_staff_cannot_open_the_manager_dialogs():
    c = _client(make_person())
    for url in ("/rota/replace/", "/rota/templates/", "/rota/templates/save/"):
        assert c.get(url).status_code == 403


def test_template_names_must_be_present_and_unique_on_rename(lead):
    c = _client(lead)
    block = json.dumps({"days": 1, "rows": [[[{"kind": "comment", "text": "x"}]]]})
    c.post("/rota/templates/save/", {"name": "One", "block": block})
    c.post("/rota/templates/save/", {"name": "Two", "block": block})
    one = Template.objects.get(name="One")
    body = c.post(f"/rota/templates/{one.pk}/rename/", {"name": "Two"}).content.decode()
    assert "already exists" in body and Template.objects.get(pk=one.pk).name == "One"
    body = c.post(f"/rota/templates/{one.pk}/rename/", {"name": " "}).content.decode()
    assert "This field is required." in body and Template.objects.get(pk=one.pk).name == "One"


def test_template_apply_and_delete_refuse_a_get(lead):
    c = _client(lead)
    c.post("/rota/templates/save/", {"name": "One", "block": json.dumps({"rows": []})})
    t = Template.objects.get()
    assert c.get(f"/rota/templates/{t.pk}/apply/").status_code == 403
    assert c.get(f"/rota/templates/{t.pk}/delete/").status_code == 403
    assert Template.objects.filter(pk=t.pk).exists()


@pytest.mark.parametrize("block", ["{}", "[]", "not json"])
def test_saving_a_template_without_rows_is_a_field_error(lead, block):
    r = _client(lead).post("/rota/templates/save/", {"name": "Bad", "block": block})
    assert r.status_code == 200 and "field-error" in r.content.decode() and not Template.objects.exists()


def test_applying_a_template_to_a_bad_cell_re_renders_the_dialog_with_the_reason(lead):
    c = _client(lead)
    c.post("/rota/templates/save/", {"name": "One", "block": json.dumps({"rows": [[[{"kind": "comment", "text": "x"}]]]})})
    t = Template.objects.get()
    for post in ({}, {"cell": "garbage"}, {"cell": "1:not-a-date"}, {"cell": "999:2027-03-01", "row_order": "1"}):
        r = c.post(f"/rota/templates/{t.pk}/apply/", post)
        assert r.status_code == 200 and "flash-error" in r.content.decode(), post


def test_a_paste_that_skips_rows_says_so_instead_of_refreshing(lead):
    nina = make_person(first_name="Nina", team=lead.team)
    c = _client(lead)
    block = {"days": 1, "rows": [[[{"kind": "comment", "text": "a"}]], [[{"kind": "comment", "text": "b"}]]]}
    t = Template.objects.create(name="Two rows", block=block)
    r = c.post(f"/rota/templates/{t.pk}/apply/", {"cell": f"{nina.pk}:2027-03-01", "row_order": str(nina.pk)})
    body = r.content.decode()
    assert "flash-warning" in body and "1 row couldn&#x27;t be pasted onto" in body
    assert Entry.objects.get().text == "a"


def test_modal_js_honours_refresh():
    from pathlib import Path
    js = Path("static/js/modal.js").read_text()
    assert "j.refresh" in js and "shift-central:refresh" in js
