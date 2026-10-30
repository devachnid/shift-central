"""Free-typed cell text into items (spec, section 5). A line with a time
range is a shift; from the rest a break, WFH, an overtime word and a
department name are pulled out, and what remains is the comment. A line
without a range is a comment; three or more hyphens alone, a separator.
Never raises: whatever cannot be read is kept as text, so nothing typed is
lost. frontend/src/rota-grid/parser.ts mirrors this for the live preview;
parser.cases.json is the shared table both are tested against. Digits are
[0-9], not \\d: Python's \\d is any Unicode digit and JavaScript's is
ASCII, and the two parsers must agree."""

import re
from datetime import time

from shifts.models import Entry

_SIDE = r"(?P<{p}h>[0-9]{{1,2}})(?:[:.]?(?P<{p}m>[0-9]{{2}}))?\s*(?P<{p}ap>(?:am|pm)(?!\w))?"
RANGE = re.compile(
    r"(?<![0-9:.])" + _SIDE.format(p="a") + r"\s*(?:-|–|—|to|until)\s*" + _SIDE.format(p="b") + r"(?![0-9])(?![:.][0-9])",
    re.IGNORECASE)
SEPARATOR = re.compile(r"^\s*-{3,}\s*$")
# The word 'break' is required on the hour and minute forms, so '1 hour
# training' stays a comment; the bare 'N m' / 'Nm' shorthand needs none.
BREAK = re.compile(
    r"(?<!\w)(?:(?P<h>[0-9]+)\s*(?:hours?|hrs?|h)\s+break"
    r"|(?P<m>[0-9]+)\s*(?:minutes?|mins?)\s+break"
    r"|break\s+(?P<n>[0-9]+)"
    r"|(?P<s>[0-9]+)\s*m)(?!\w)",
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
    start before 13:00 is read as pm (8-4 is 08:00–16:00, 12:30-1 is
    12:30–13:00); a start at or after 13:00 is 24-hour, so 16:00-08:00 is
    not a shift. A start with no marker, before noon, under a pm finish is
    read as pm too when that still ends before the finish (1-5pm is
    13:00–17:00; 8-4pm stays 08:00–16:00). If the finish still is not after
    the start, it is not a shift either."""
    start = _time(match["ah"], match["am"], match["aap"])
    finish = _time(match["bh"], match["bm"], match["bap"])
    if start is None or finish is None:
        return None
    if not match["bap"] and start.hour < 13 and finish <= start and finish.hour < 12:
        finish = time(finish.hour + 12, finish.minute)
    if match["bap"] and not match["aap"] and start.hour < 12:
        pm_start = time(start.hour + 12, start.minute)
        if pm_start < finish:
            start = pm_start
    if finish <= start:
        return None
    return start, finish


def _first_range(text):
    """The first range in the text that reads as a shift, with its times,
    or None. Ranges that do not read are left in the text as comment."""
    for m in RANGE.finditer(text):
        times = _range(m)
        if times is not None:
            return m, times
    return None


def _break(rest):
    """The break in minutes and the text without it, or 0 and the text
    unchanged when the length is not one ROTA-01 allows (a '20 min break'
    stays in the comment for a manager to see)."""
    for m in BREAK.finditer(rest):
        groups = m.groupdict()
        if groups["h"]:
            minutes = int(groups["h"]) * 60
        else:
            minutes = int(groups["m"] or groups["n"] or groups["s"])
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
    """Whitespace collapsed and cut at 200 characters: a comment line as
    typed."""
    return " ".join(text.split())[:200]


def _leftover(text):
    """What is left of a shift line once its parts are taken out, with the
    punctuation left at either end of it (from '9-5.' or '9-5, wfh')
    dropped. Only a shift's leftover is tidied: a pure comment such as
    'OFF.' or '...' keeps what was typed."""
    return _comment(text).strip(" ,.:;")


def line(text, departments):
    """One line of cell text as an item dict. Runs of whitespace are
    collapsed first: what is stored is collapsed anyway, and the range
    pattern's optional spaces would otherwise backtrack on a long run."""
    text = " ".join(text.split())
    if SEPARATOR.match(text):
        return {"kind": "separator"}
    found = _first_range(text)
    if found is None:
        return {"kind": "comment", "text": _comment(text)}
    m, times = found
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
            "department": department, "text": _leftover(rest), "wfh": wfh, "overtime": overtime}


def cell(text, departments):
    """Every non-blank line of a cell's text, in order."""
    departments = list(departments)
    return [line(raw, departments) for raw in text.splitlines() if raw.strip()]
