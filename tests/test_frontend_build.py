"""The committed build is what the page loads; CI rebuilds and compares.
These pin what the templates rely on."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_built_files_exist_and_register_the_colour_picker():
    js = (ROOT / "static/dist/main.js").read_text()
    assert "colour-picker" in js and "data-component" in js
    assert (ROOT / "static/dist/main.css").exists()


def test_the_build_output_has_stable_names():
    names = sorted(p.name for p in (ROOT / "static/dist").iterdir())
    assert names == ["main.css", "main.js"], "no hashed names: templates reference these directly"


def test_the_lockfile_is_committed():
    assert (ROOT / "frontend/package-lock.json").exists()
