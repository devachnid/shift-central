"""The one writer of cells (spec, section 4). Every function here checks
access.can_manage for each person touched before any write, records a
DayChange before a day's first unnotified change, applies the change and
audits one row per cell, all in one transaction. Partial writes never
happen: a refusal raises before the transaction opens."""

import re
from dataclasses import dataclass, field
from datetime import date, time, timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction

from people.models import Department, Person
from people.services import access, audit
from shifts.models import DayChange, Entry
from shifts.services import parse, render

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
APPEARANCE_BOOLS = ("bold", "italic", "underline", "strike", "wrap")
SIZES = ("sm", "md", "lg")


@dataclass
class Changed:
    cells: dict = field(default_factory=dict)   # {person_id: {date: [Entry]}}
    skipped: int = 0

    def add(self, person, day, rows):
        self.cells.setdefault(person.pk, {})[day] = rows


# --- input -----------------------------------------------------------------

def clean_appearance(raw):
    if not isinstance(raw, dict):
        raise ValueError("appearance must be an object")
    out = {}
    for key in ("bg", "fg"):
        if raw.get(key):
            if not isinstance(raw[key], str) or not HEX.match(raw[key]):
                raise ValueError(f"{key} must be a hex colour")
            out[key] = raw[key].upper()
    for key in APPEARANCE_BOOLS:
        if raw.get(key):
            out[key] = True
    if raw.get("size"):
        if raw["size"] not in SIZES:
            raise ValueError("size must be sm, md or lg")
        if raw["size"] != "md":
            out["size"] = raw["size"]
    return out


def _hm(value, name):
    try:
        return time.fromisoformat(value) if isinstance(value, str) else value
    except ValueError:
        raise ValueError(f"{name} is not a time") from None


def _clean_item(raw, departments):
    """A JSON-shaped item as the fields an Entry takes."""
    kind = raw.get("kind", "shift")
    if kind not in Entry.Kind.values:
        raise ValueError("unknown item kind")
    item = {"kind": kind, "appearance": clean_appearance(raw.get("appearance") or {})}
    if kind == Entry.Kind.SEPARATOR:
        return item
    item["text"] = str(raw.get("text") or "")[:200]
    if kind == Entry.Kind.COMMENT:
        return item
    start, finish = _hm(raw.get("start"), "start"), _hm(raw.get("finish"), "finish")
    if not isinstance(start, time) or not isinstance(finish, time) or finish <= start:
        raise ValueError("a shift needs a start and a later finish")
    item.update(start=start, finish=finish)
    item["break_minutes"] = int(raw.get("break_minutes") or 0)
    if item["break_minutes"] not in Entry.BREAKS:
        raise ValueError("the break must be 15, 30, 45 or 60 minutes")
    dept = raw.get("department")
    if dept not in (None, ""):
        dept = departments.get(int(dept)) if str(dept).isdigit() else None
        if dept is None:
            raise ValueError("unknown department")
    item["department"] = dept or None
    item["overtime"] = raw.get("overtime") or ""
    if item["overtime"] not in Entry.Overtime.values:
        raise ValueError("overtime must be paid or TOIL")
    item["wfh"] = bool(raw.get("wfh"))
    return item


def _from_parsed(parsed):
    """parse.cell's dicts as _clean_item's output (same keys, Department
    objects already resolved)."""
    item = dict(parsed)
    item.setdefault("appearance", {})
    item.setdefault("text", "")
    return item


def _departments():
    return {d.pk: d for d in Department.objects.all()}


# --- access and bookkeeping -----------------------------------------------

def _people(user, ids):
    """The people for these ids, each one the user may manage, else refuse."""
    people = {p.pk: p for p in Person.objects.filter(pk__in=set(ids))}
    for pk in set(ids):
        person = people.get(pk)
        if person is None or not access.can_manage(user, person):
            raise PermissionDenied("you can't edit this person's rota")
    return people


def _check(user, person):
    if not access.can_manage(user, person):
        raise PermissionDenied("you can't edit this person's rota")


def _touch(person, day):
    DayChange.objects.get_or_create(person=person, day=day,
                                    defaults={"before": render.day_text(person, day)})


def _write(user, person, day, items, keep_appearance=True):
    """Replace the cell's items. The appearance of an item in the same slot
    with the same kind survives a rewrite (a retyped time keeps its colour).
    Audits the cell as one row. Call inside a transaction, after _check."""
    old = list(Entry.objects.filter(person=person, day=day).select_related("department").order_by("position"))
    planned = []
    for position, item in enumerate(items):
        fields = dict(item)
        if keep_appearance and not fields.get("appearance") and position < len(old) \
                and old[position].kind == fields["kind"]:
            fields["appearance"] = old[position].appearance
        planned.append(fields)
    if [(f["kind"], render.line(f), f.get("appearance") or {}) for f in planned] \
            == [(e.kind, render.line(e), e.appearance or {}) for e in old]:
        return old   # nothing changes: no DayChange, no new rows, no audit
    before = " / ".join(render.line(e) for e in old) or "no shift"
    _touch(person, day)
    Entry.objects.filter(person=person, day=day).delete()
    rows = [Entry(person=person, day=day, position=position, created_by=user, **fields)
            for position, fields in enumerate(planned)]
    Entry.objects.bulk_create(rows)
    rows = list(Entry.objects.filter(person=person, day=day).select_related("department").order_by("position"))
    after = " / ".join(render.line(e) for e in rows) or "no shift"
    audit.record_as(user, "shifts.entry", person.pk, {"cell": (before, after)}, note=render.audit_note(person, day))
    return rows


# --- the API's verbs --------------------------------------------------------

def set_cell_text(user, person, day, text):
    _check(user, person)
    offered = Department.objects.filter(archived=False)
    items = [_from_parsed(p) for p in parse.cell(text, offered)]
    with transaction.atomic():
        return _write(user, person, day, items)


def set_cell(user, person, day, items):
    _check(user, person)
    departments = _departments()
    cleaned = [_clean_item(raw, departments) for raw in items]
    with transaction.atomic():
        return _write(user, person, day, cleaned, keep_appearance=False)


PATCHABLE = ("department", "break_minutes", "overtime", "wfh", "appearance", "text")


def patch(user, entry, **fields):
    unknown = set(fields) - set(PATCHABLE)
    if unknown:
        raise ValueError(f"not patchable: {sorted(unknown)}")
    _check(user, entry.person)
    if "appearance" in fields:
        fields["appearance"] = clean_appearance(fields["appearance"] or {})
    if "department" in fields:
        dept = fields["department"]
        fields["department"] = None if dept in (None, "") else Department.objects.filter(pk=dept).first()
        if dept not in (None, "") and fields["department"] is None:
            raise ValueError("unknown department")
    if "break_minutes" in fields and int(fields["break_minutes"]) not in Entry.BREAKS:
        raise ValueError("the break must be 15, 30, 45 or 60 minutes")
    if "overtime" in fields and (fields["overtime"] or "") not in Entry.Overtime.values:
        raise ValueError("overtime must be paid or TOIL")
    if entry.kind != Entry.Kind.SHIFT and set(fields) & {"department", "break_minutes", "overtime", "wfh"}:
        raise ValueError("only a shift takes a department, break, overtime or WFH")
    with transaction.atomic():
        before_line = render.line(entry)
        if set(fields) == {"appearance"}:
            entry.appearance = fields["appearance"]
            entry.save(update_fields=["appearance", "updated_at"])
            audit.record_as(user, "shifts.entry", entry.person.pk, {"appearance": ("", str(entry.appearance))},
                            note=f"{render.audit_note(entry.person, entry.day)} · {before_line}")
            return entry
        before = render.day_text(entry.person, entry.day)
        _touch(entry.person, entry.day)
        for name, value in fields.items():
            setattr(entry, name, value if name != "text" else str(value or "")[:200])
        entry.save()
        audit.record_as(user, "shifts.entry", entry.person.pk, {"cell": (before, render.day_text(entry.person, entry.day))},
                        note=render.audit_note(entry.person, entry.day))
        return entry


def _cells(cells):
    return [(int(p), d if isinstance(d, date) else date.fromisoformat(d)) for p, d in cells]


def clear(user, cells):
    cells = _cells(cells)
    people = _people(user, [p for p, _ in cells])
    changed = Changed()
    with transaction.atomic():
        for pk, day in cells:
            changed.add(people[pk], day, _write(user, people[pk], day, []))
    return changed


def _snapshot(entry):
    return {"kind": entry.kind, "start": entry.start, "finish": entry.finish,
            "break_minutes": entry.break_minutes, "department": entry.department,
            "text": entry.text, "wfh": entry.wfh, "overtime": entry.overtime,
            "appearance": dict(entry.appearance)}


def _items_of(person, day):
    return [_snapshot(e) for e in Entry.objects.filter(person=person, day=day)
            .select_related("department").order_by("position")]


def move(user, cells, days, rows, copy, row_order):
    """Translate a selection by (days, rows) over the grid's row order.
    Targets are checked before anything is written; a target off the row
    list or on a row the user may not edit refuses the whole move."""
    cells = _cells(cells)
    row_order = [int(p) for p in row_order]
    targets = []
    for pk, day in cells:
        try:
            idx = row_order.index(pk) + rows
        except ValueError:
            raise ValueError("a moved row is not on the grid") from None
        if idx < 0 or idx >= len(row_order):
            raise ValueError("the move goes off the grid")
        targets.append((row_order[idx], day + timedelta(days=days)))
    people = _people(user, [p for p, _ in cells] + [p for p, _ in targets])
    changed = Changed()
    with transaction.atomic():
        snapshots = {(pk, day): _items_of(people[pk], day) for pk, day in cells}
        if not copy:
            for pk, day in cells:
                changed.add(people[pk], day, _write(user, people[pk], day, []))
        for (pk, day), (tpk, tday) in zip(cells, targets):
            changed.add(people[tpk], tday, _write(user, people[tpk], tday, snapshots[(pk, day)], keep_appearance=False))
    return changed


def paste(user, anchor, block, mode, row_order):
    """Write a clipboard block with its top-left at the anchor. Rows below
    the end of the grid, or the user may not edit, are skipped and counted;
    nothing else about the paste is refused."""
    if mode not in ("replace", "add"):
        raise ValueError("paste mode must be replace or add")
    anchor_pk, anchor_day = _cells([anchor])[0]
    row_order = [int(p) for p in row_order]
    if anchor_pk not in row_order:
        raise ValueError("the anchor is not on the grid")
    rows = block.get("rows") if isinstance(block, dict) else None
    if not isinstance(rows, list):
        raise ValueError("the block has no rows")
    departments = _departments()
    start = row_order.index(anchor_pk)
    planned, skipped = [], 0
    people = {p.pk: p for p in Person.objects.filter(pk__in=row_order[start:start + len(rows)])}
    for r, cells in enumerate(rows):
        if start + r >= len(row_order):
            skipped += 1
            continue
        person = people.get(row_order[start + r])
        if person is None or not access.can_manage(user, person):
            skipped += 1
            continue
        for d, items in enumerate(cells if isinstance(cells, list) else []):
            planned.append((person, anchor_day + timedelta(days=d), [_clean_item(i, departments) for i in items]))
    changed = Changed(skipped=skipped)
    with transaction.atomic():
        for person, day, items in planned:
            if mode == "add":
                items = _items_of(person, day) + items
            changed.add(person, day, _write(user, person, day, items, keep_appearance=False))
    return changed


def replace(user, cells, find, replacement, match_case):
    """Find and replace over each item's canonical line; a changed line is
    re-parsed, so replacing a department name re-tags the shift."""
    if not find:
        raise ValueError("nothing to find")
    cells = _cells(cells)
    people = _people(user, [p for p, _ in cells])
    pattern = re.compile(re.escape(find), 0 if match_case else re.IGNORECASE)
    offered = list(Department.objects.filter(archived=False))
    changed = Changed()
    with transaction.atomic():
        for pk, day in cells:
            person = people[pk]
            old = list(Entry.objects.filter(person=person, day=day).select_related("department").order_by("position"))
            items, touched = [], False
            for e in old:
                line = render.line(e)
                new = pattern.sub(lambda match: replacement, line)
                if new == line:
                    items.append(_snapshot(e))
                    continue
                touched = True
                item = _from_parsed(parse.line(new, offered))
                item["appearance"] = dict(e.appearance)
                items.append(item)
            if touched:
                changed.add(person, day, _write(user, person, day, items, keep_appearance=False))
    return changed
