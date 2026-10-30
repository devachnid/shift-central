"""The one writer of cells (spec, section 4): access checked per person
before any write, a DayChange before a day's first unnotified change, one
audit row per cell, and nothing partial."""

from datetime import date, time, timedelta

import pytest
from django.core.exceptions import PermissionDenied

from people.models import AuditEntry
from shifts.models import DayChange, Entry
from shifts.services import entries
from tests.factories import (make_department, make_entry, make_person, make_team,
                             make_team_manager, make_user_for)

pytestmark = pytest.mark.django_db
MON = date(2027, 3, 1)
TUE = MON + timedelta(days=1)


@pytest.fixture
def world():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_team_manager(lead, reception)
    return {
        "reception": reception, "nursing": nursing,
        "lead": lead, "u_lead": make_user_for(lead),
        "nina": make_person(first_name="Nina", team=reception),
        "nurse": make_person(first_name="Nurse", team=nursing),
        "boss": make_user_for(make_person(first_name="Boss", team=reception), is_all_teams_manager=True),
        "pmc": make_department("Reception PMC"),
    }


def _lines(person, day):
    return [e for e in Entry.objects.filter(person=person, day=day).order_by("position")]


def test_set_cell_text_parses_and_stores_in_order(world):
    rows = entries.set_cell_text(world["u_lead"], world["nina"], MON, "08:00-16:15 1 hour break Reception PMC\nthen training")
    assert [(r.kind, r.position) for r in rows] == [("shift", 0), ("comment", 1)]
    assert rows[0].start == time(8) and rows[0].break_minutes == 60 and rows[0].department == world["pmc"]
    assert rows[0].created_by == world["u_lead"]


def test_a_team_manager_cannot_write_another_teams_cell_or_their_own(world):
    with pytest.raises(PermissionDenied):
        entries.set_cell_text(world["u_lead"], world["nurse"], MON, "08:00-12:00")
    with pytest.raises(PermissionDenied):
        entries.set_cell_text(world["u_lead"], world["lead"], MON, "08:00-12:00")
    assert Entry.objects.count() == 0


def test_an_all_teams_manager_writes_anyone_but_themselves(world):
    entries.set_cell_text(world["boss"], world["nurse"], MON, "08:00-12:00")
    with pytest.raises(PermissionDenied):
        entries.set_cell_text(world["boss"], world["boss"].person, MON, "08:00-12:00")


def test_a_day_change_is_recorded_once_with_the_text_before(world):
    entries.set_cell_text(world["u_lead"], world["nina"], MON, "08:00-12:00")
    entries.set_cell_text(world["u_lead"], world["nina"], MON, "09:00-13:00")
    change = DayChange.objects.get(person=world["nina"], day=MON)
    assert change.before == "no shift"


def test_each_cell_write_audits_one_row_with_the_day_in_the_note(world):
    entries.set_cell_text(world["u_lead"], world["nina"], MON, "08:00-12:00")
    row = AuditEntry.objects.get(model="shifts.entry", object_id=world["nina"].pk, field="cell")
    assert (row.before, row.after) == ("no shift", "08:00-12:00")
    assert row.note == "Mon 1 Mar 2027 · Nina Patel" and row.actor == world["u_lead"]


def test_rewriting_a_cell_keeps_the_appearance_of_items_still_there(world):
    entries.set_cell(world["u_lead"], world["nina"], MON,
                     [{"kind": "shift", "start": "08:00", "finish": "12:00", "appearance": {"bg": "#FFEEAA"}}])
    rows = entries.set_cell_text(world["u_lead"], world["nina"], MON, "09:00-13:00")
    assert rows[0].appearance == {"bg": "#FFEEAA"}


def test_set_cell_refuses_what_cannot_be_stored(world):
    with pytest.raises(ValueError):
        entries.set_cell(world["u_lead"], world["nina"], MON, [{"kind": "shift", "start": "08:00"}])
    with pytest.raises(ValueError):
        entries.set_cell(world["u_lead"], world["nina"], MON, [{"kind": "shift", "start": "08:00", "finish": "12:00", "department": 999}])
    with pytest.raises(ValueError):
        entries.set_cell(world["u_lead"], world["nina"], MON, [{"kind": "comment", "text": "x", "appearance": {"bg": "red"}}])
    with pytest.raises(ValueError):
        entries.set_cell(world["u_lead"], world["nina"], MON, [{"kind": "shift", "start": "08:00", "finish": "12:00", "break_minutes": 20}])


def test_patch_changes_fields_and_audits_appearance_separately(world):
    e = make_entry(world["nina"], MON)
    entries.patch(world["u_lead"], e, overtime="toil", wfh=True)
    entries.patch(world["u_lead"], e, appearance={"bold": True, "size": "lg"})
    e.refresh_from_db()
    assert e.overtime == "toil" and e.wfh and e.appearance == {"bold": True, "size": "lg"}
    fields = list(AuditEntry.objects.filter(model="shifts.entry").order_by("pk").values_list("field", flat=True))
    assert fields == ["cell", "appearance"]
    with pytest.raises(ValueError):
        entries.patch(world["u_lead"], e, overtime="double")


def test_clear_empties_cells_and_records_each_day(world):
    make_entry(world["nina"], MON)
    make_entry(world["nina"], TUE)
    changed = entries.clear(world["u_lead"], [(world["nina"].pk, MON), (world["nina"].pk, TUE)])
    assert Entry.objects.count() == 0
    assert changed.cells == {world["nina"].pk: {MON: [], TUE: []}}
    assert DayChange.objects.filter(person=world["nina"]).count() == 2


def test_move_shifts_a_block_by_days_and_rows_and_copy_keeps_the_source(world):
    boss = world["boss"]
    nina, nurse = world["nina"], world["nurse"]
    make_entry(nina, MON, text="A")
    order = [nina.pk, nurse.pk]
    changed = entries.move(boss, [(nina.pk, MON)], days=1, rows=1, copy=False, row_order=order)
    assert _lines(nina, MON) == [] and _lines(nurse, TUE)[0].text == "A"
    assert set(changed.cells[nina.pk]) == {MON} and set(changed.cells[nurse.pk]) == {TUE}
    entries.move(boss, [(nurse.pk, TUE)], days=0, rows=-1, copy=True, row_order=order)
    assert _lines(nurse, TUE)[0].text == "A" and _lines(nina, TUE)[0].text == "A"


def test_move_onto_a_row_the_viewer_cannot_edit_is_refused_whole(world):
    make_entry(world["nina"], MON)
    with pytest.raises(PermissionDenied):
        entries.move(world["u_lead"], [(world["nina"].pk, MON)], days=0, rows=1, copy=False,
                     row_order=[world["nina"].pk, world["nurse"].pk])
    assert _lines(world["nina"], MON)


def test_paste_writes_a_block_at_the_anchor_replacing_or_adding(world):
    boss, nina, nurse = world["boss"], world["nina"], world["nurse"]
    make_entry(nina, MON, text="old")
    block = {"days": 2, "rows": [
        [[{"kind": "shift", "start": "08:00", "finish": "12:00"}], [{"kind": "comment", "text": "off"}]],
        [[], [{"kind": "shift", "start": "13:00", "finish": "17:00", "department": world["pmc"].pk}]],
    ]}
    order = [nina.pk, nurse.pk]
    changed = entries.paste(boss, (nina.pk, MON), block, "replace", order)
    assert [e.start for e in _lines(nina, MON)] == [time(8)]
    assert _lines(nina, TUE)[0].text == "off" and _lines(nurse, TUE)[0].department == world["pmc"]
    assert _lines(nurse, MON) == [] and changed.skipped == 0
    entries.paste(boss, (nina.pk, MON), block, "add", order)
    assert len(_lines(nina, MON)) == 2


def test_paste_leaves_a_null_cell_alone_but_an_empty_one_clears(world):
    nina = world["nina"]
    make_entry(nina, MON, text="keep")
    make_entry(nina, TUE, text="clear")
    block = {"days": 2, "rows": [[None, []]]}
    entries.paste(world["boss"], (nina.pk, MON), block, "replace", [nina.pk])
    assert [e.text for e in _lines(nina, MON)] == ["keep"]
    assert _lines(nina, TUE) == []


def test_paste_skips_rows_beyond_the_grid_or_outside_the_viewers_teams(world):
    nina, nurse = world["nina"], world["nurse"]
    block = {"days": 1, "rows": [[[{"kind": "comment", "text": "a"}]], [[{"kind": "comment", "text": "b"}]],
                                 [[{"kind": "comment", "text": "c"}]]]}
    changed = entries.paste(world["u_lead"], (nina.pk, MON), block, "replace", [nina.pk, nurse.pk])
    assert _lines(nina, MON)[0].text == "a" and _lines(nurse, MON) == []
    assert changed.skipped == 2


def test_replace_rewrites_matching_lines_and_reparses_them(world):
    nina = world["nina"]
    e = make_entry(nina, MON, department=world["pmc"])
    make_entry(nina, TUE, kind="comment", text="pmc cover")
    changed = entries.replace(world["u_lead"], [(nina.pk, MON), (nina.pk, TUE)], "Reception PMC", "Floating", match_case=False)
    assert _lines(nina, MON)[0].department is None and _lines(nina, MON)[0].text == "Floating"
    assert _lines(nina, TUE)[0].text == "pmc cover"
    assert set(changed.cells[nina.pk]) == {MON}
    assert not Entry.objects.filter(pk=e.pk).exists(), "a changed line is a new item"


def test_reorder_sets_display_order_in_tens_and_audits(world):
    from people.services import profiles
    nina, nurse = world["nina"], world["nurse"]
    profiles.reorder(world["boss"], [nurse.pk, nina.pk])
    nina.refresh_from_db(), nurse.refresh_from_db()
    assert (nurse.display_order, nina.display_order) == (10, 20)
    assert AuditEntry.objects.filter(model="people.person", field="display_order").count() == 2


def test_replace_with_a_department_name_retags_the_shift(world):
    nina = world["nina"]
    make_entry(nina, MON, department=world["pmc"])
    entries.replace(world["u_lead"], [(nina.pk, MON)], "Reception PMC", "Nursing", match_case=False)
    assert _lines(nina, MON)[0].department.name == "Nursing"


def test_replace_inserts_the_replacement_verbatim(world):
    nina = world["nina"]
    make_entry(nina, MON, kind="comment", text="cover")
    entries.replace(world["u_lead"], [(nina.pk, MON)], "cover", r"C:\temp \1", match_case=True)
    assert _lines(nina, MON)[0].text == r"C:\temp \1"


def test_clearing_an_empty_cell_records_nothing(world):
    entries.clear(world["u_lead"], [(world["nina"].pk, MON)])
    assert not DayChange.objects.exists() and not AuditEntry.objects.filter(model="shifts.entry").exists()


def test_retyping_identical_text_keeps_the_entries(world):
    first = entries.set_cell_text(world["u_lead"], world["nina"], MON, "08:00-12:00")
    again = entries.set_cell_text(world["u_lead"], world["nina"], MON, "08:00-12:00")
    assert [e.pk for e in again] == [e.pk for e in first]
    assert AuditEntry.objects.filter(model="shifts.entry").count() == 1


def test_moving_an_empty_cell_writes_nothing_for_the_target(world):
    nina, nurse = world["nina"], world["nurse"]
    entries.move(world["boss"], [(nina.pk, MON)], days=1, rows=1, copy=True, row_order=[nina.pk, nurse.pk])
    assert not DayChange.objects.exists() and not AuditEntry.objects.filter(model="shifts.entry").exists()


def test_reorder_is_for_managers_only(world):
    from people.services import profiles
    staff = make_user_for(make_person(first_name="Staff", team=world["reception"]))
    with pytest.raises(PermissionDenied):
        profiles.reorder(staff, [world["nurse"].pk, world["nina"].pk])
    world["nina"].refresh_from_db()
    assert world["nina"].display_order != 20


def test_reorder_takes_ids_as_strings(world):
    from people.services import profiles
    nina, nurse = world["nina"], world["nurse"]
    profiles.reorder(world["boss"], [str(nurse.pk), str(nina.pk)])
    nina.refresh_from_db(), nurse.refresh_from_db()
    assert (nurse.display_order, nina.display_order) == (10, 20)


def test_reorder_skips_people_the_manager_does_not_manage_including_themselves(world):
    from people.services import profiles
    lead, nina, nurse = world["lead"], world["nina"], world["nurse"]
    tom = make_person(first_name="Tom", team=world["reception"])
    before = {p.pk: p.display_order for p in (lead, nurse)}
    profiles.reorder(world["u_lead"], [nurse.pk, tom.pk, lead.pk, nina.pk])
    for p in (lead, nina, nurse, tom):
        p.refresh_from_db()
    assert (tom.display_order, nina.display_order) == (10, 20)
    assert {p.pk: p.display_order for p in (lead, nurse)} == before
    assert not AuditEntry.objects.filter(model="people.person", object_id__in=[lead.pk, nurse.pk]).exists()


def test_paste_parses_a_text_cell_on_the_server(world):
    nina = world["nina"]
    old = make_department("Old Annex", archived=True)
    block = {"days": 2, "rows": [["08:00-12:00 Reception PMC\n13:00-17:00 30m Old Annex", "---"]]}
    entries.paste(world["u_lead"], (nina.pk, MON), block, "replace", [nina.pk])
    first, second = _lines(nina, MON)
    assert (first.start, first.finish, first.department, first.text) == (time(8), time(12), world["pmc"], "")
    assert (second.break_minutes, second.department, second.text) == (30, None, "Old Annex"), \
        "an archived department is not offered to the server's parser"
    assert old.pk and [e.kind for e in _lines(nina, TUE)] == ["separator"]


def test_paste_of_an_empty_text_cell_clears_and_a_bad_cell_is_refused(world):
    nina = world["nina"]
    make_entry(nina, MON, text="gone")
    entries.paste(world["u_lead"], (nina.pk, MON), {"days": 1, "rows": [[""]]}, "replace", [nina.pk])
    assert _lines(nina, MON) == []
    with pytest.raises(ValueError):
        entries.paste(world["u_lead"], (nina.pk, MON), {"days": 1, "rows": [[{"kind": "comment"}]]}, "replace", [nina.pk])
