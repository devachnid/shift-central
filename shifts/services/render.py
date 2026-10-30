"""Items and cells as text: the canonical line parse.py reads back, the
day's text DayChange and the audit hold, and durations as LEAVE-04 shows
them."""

from shifts.models import Entry

_OVERTIME = {"paid": "OT paid", "toil": "TOIL"}


def time_hm(t):
    return t.strftime("%H:%M")


def _get(item, key, default=None):
    return item.get(key, default) if isinstance(item, dict) else getattr(item, key, default)


def line(item):
    """A shift as '08:00-16:15 1 hour break Reception PMC WFH TOIL comment';
    a comment as its text; a separator as '---'. Hyphen, not en dash, so
    the line re-parses; the island shows the dash."""
    kind = _get(item, "kind")
    if kind == "separator":
        return "---"
    if kind == "comment":
        return _get(item, "text", "")
    parts = [f"{time_hm(_get(item, 'start'))}-{time_hm(_get(item, 'finish'))}"]
    minutes = _get(item, "break_minutes", 0)
    if minutes == 60:
        parts.append("1 hour break")
    elif minutes:
        parts.append(f"{minutes} min break")
    dept = _get(item, "department")
    if dept is not None:
        parts.append(dept.name)
    if _get(item, "wfh"):
        parts.append("WFH")
    if _get(item, "overtime"):
        parts.append(_OVERTIME[_get(item, "overtime")])
    if _get(item, "text"):
        parts.append(_get(item, "text"))
    return " ".join(parts)


def cell_text(entries):
    return "\n".join(line(e) for e in entries)


def day_text(person, day):
    rows = Entry.objects.filter(person=person, day=day).select_related("department").order_by("position")
    return " / ".join(line(e) for e in rows) or "no shift"


def duration(td):
    minutes = int(td.total_seconds() // 60)
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h} h {m} min"
    if h:
        return f"{h} h"
    return f"{m} min"


def audit_note(person, day):
    return f"{day:%a} {day.day} {day:%b %Y} · {person.name}"
