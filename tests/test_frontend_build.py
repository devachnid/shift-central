"""The committed build is what the page loads; CI rebuilds and compares.
These pin what the templates rely on."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_built_files_exist_and_register_the_colour_picker_and_the_rota_grid():
    js = (ROOT / "static/dist/main.js").read_text()
    assert "colour-picker" in js and "data-component" in js
    assert "rota-grid" in js
    assert (ROOT / "static/dist/main.css").exists()


def test_the_build_output_has_stable_names():
    names = sorted(p.name for p in (ROOT / "static/dist").iterdir())
    assert names == ["main.css", "main.js"], "no hashed names: templates reference these directly"


def test_the_lockfile_is_committed():
    assert (ROOT / "frontend/package-lock.json").exists()


def test_the_colour_picker_is_a_labelled_group_of_toggle_buttons():
    """A listbox owes arrow-key navigation; plain buttons that say whether
    they are pressed do not. The group takes its name from the field's label."""
    js = (ROOT / "static/dist/main.js").read_text()
    assert "aria-pressed" in js and "aria-labelledby" in js
    # The rota grid's cells use aria-selected, so that half is read from the
    # picker's own source; the built bundle must not carry a listbox at all.
    picker = (ROOT / "frontend/src/colour-picker.tsx").read_text()
    assert "listbox" not in js and "aria-selected" not in picker and 'role="listbox"' not in picker


def test_both_colour_fields_name_their_label_for_the_picker(db):
    from django.test import Client

    from tests.factories import make_person, make_user_for
    c = Client()
    c.force_login(make_user_for(make_person(first_name="Boss"), is_all_teams_manager=True))
    person = make_person(first_name="Nina")
    for url, label in ((f"/staff/{person.pk}/profile/?tab=display", "name_colour-label"),
                       ("/departments/add/", "colour-label")):
        body = c.get(url).content.decode()
        assert f'<label id="{label}">' in body and f'data-label="{label}"' in body
