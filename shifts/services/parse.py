"""Free-typed cell text into items (spec, section 5). A line with a time
range is a shift; from the rest a break, WFH, an overtime word and a
department name are pulled out, and what remains is the comment. A line
without a range is a comment; three or more hyphens alone, a separator.
Never raises: whatever cannot be read is kept as text, so nothing typed is
lost. frontend/src/rota-grid/parser.ts mirrors this for the live preview;
parser.cases.json is the shared table both are tested against."""

import re
from datetime import time

from shifts.models import Entry

_SIDE = r"(?P<{p}h>\d{{1,2}})(?:[:.]?(?P<{p}m>\d{{2}}))?\s*(?P<{p}ap>am|pm)?"
RANGE = re.compile(
    r"(?<![\d:.])" + _SIDE.format(p="a") + r"\s*(?:-|–|—|to|until)\s*" + _SIDE.format(p="b") + r"(?![\d:.])",
    re.IGNORECASE)
SEPARATOR = re.compile(r"^\s*-{3,}\s*$")
BREAK = re.compile(
    r"(?<!\w)(?:(?P<h>\d+)\s*(?:hours?|hrs?|h)(?:\s+break)?|(?P<m>\d+)\s*(?:minutes?|mins?|m)(?:\s+break)?|break\s+(?P<n>\d+))(?!\w)",
    re.IGNORECASE)
WFH = re.compile(r"(?<!\w)wfh(?!\w)", re.IGNORECASE)
TOIL = re.compile(r"(?<!\w)toil(?!\w)", re.IGNORECASE)
PAID = re.compile(r"(?<!\w)(?:ot paid|overtime paid|paid overtime|ot)(?!\w)", re.IGNORECASE)


def _time(h, m, ap):
    h, m = int(h), int(m or 0)
    if h > 23 or m > 59:
        return None
    ap = (ap or "").lower()
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    return time(h, m)


def _range(match):
    """The two times, or None. A finish with no am/pm that is not after a
    start of noon or earlier is read as pm (8-4 is 08:00–16:00); a start
    already in the afternoon, such as 16:00-08:00, is 24-hour, so the line
    is not a shift. If it still is not after the start, it is not a shift."""
    start = _time(match["ah"], match["am"], match["aap"])
    finish = _time(match["bh"], match["bm"], match["bap"])
    if start is None or finish is None:
        return None
    if not match["bap"] and start.hour <= 12 and finish <= start and finish.hour < 12:
        finish = time(finish.hour + 12, finish.minute)
    if finish <= start:
        return None
    return start, finish


def _break(rest):
    """The break in minutes and the text without it, or 0 and the text
    unchanged when the length is not one ROTA-01 allows (a '20 min break'
    stays in the comment for a manager to see)."""
    for m in BREAK.finditer(rest):
        minutes = int(m["h"]) * 60 if m["h"] else int(m["m"] or m["n"])
        if minutes in Entry.BREAKS:
            return minutes, rest[:m.start()] + " " + rest[m.end():]
    return 0, rest


def _department(rest, departments):
    """The longest department name present as a whole phrase, and the text
    without it."""
    for dept in sorted(departments, key=lambda d: -len(d.name)):
        m = re.search(r"(?<!\w)" + re.escape(dept.name) + r"(?!\w)", rest, re.IGNORECASE)
        if m:
            return dept, rest[:m.start()] + " " + rest[m.end():]
    return None, rest


def _comment(text):
    return " ".join(text.split())[:200]


def line(text, departments):
    """One line of cell text as an item dict."""
    if SEPARATOR.match(text):
        return {"kind": "separator"}
    m = RANGE.search(text)
    times = _range(m) if m else None
    if times is None:
        return {"kind": "comment", "text": _comment(text)}
    rest = text[:m.start()] + " " + text[m.end():]
    break_minutes, rest = _break(rest)
    wfh = bool(WFH.search(rest))
    rest = WFH.sub(" ", rest)
    overtime = ""
    if TOIL.search(rest):
        overtime, rest = "toil", TOIL.sub(" ", rest, count=1)
    elif PAID.search(rest):
        overtime, rest = "paid", PAID.sub(" ", rest, count=1)
    department, rest = _department(rest, departments)
    return {"kind": "shift", "start": times[0], "finish": times[1], "break_minutes": break_minutes,
            "department": department, "text": _comment(rest), "wfh": wfh, "overtime": overtime}


def cell(text, departments):
    """Every non-blank line of a cell's text, in order."""
    departments = list(departments)
    return [line(raw, departments) for raw in text.splitlines() if raw.strip()]
