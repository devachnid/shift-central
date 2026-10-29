# AMG Shift Central: rota grid — design

**Date:** 2026-10-29
**Status:** approved in conversation; spec for review
**Requirements:** `docs/requirements/` as amended by
`docs/requirements/2026-10-29-proposed-amendments.md`. This spec covers
ROTA-01, 03 to 09, 12, 13, ROTA-GP-01 and 02 (as amended: sessions shown,
not edited), FMS-00 for the grid screens, FMS items 1 to 11, 13, 14, 54
and 62, PAT-02 and 08, NOTIF-02, REP-01, ACC-03 and the grid side of
ACC-06, and INT-02's read half. It builds on the Foundation spec
(`2026-10-29-foundation-design.md`), whose constraints, shell, people,
departments, access rules and audit it reuses unchanged.

The grid is the second of five releases: shifts, the grid and all its
editing, overtime marks, notify staff, the hours report, and GP sessions
shown from the GP rota app. It is what managers lay the 2027 rotas out
with from early December.

## Decisions made in conversation

| Decision | Rationale |
|---|---|
| **One release**, the whole editing surface of FMS items 1 to 14 and 62. | Copy and paste of week blocks and templates are the stated way of laying out the year (ROTA-07, 08); appearance and find-and-replace are small once the cell model exists. |
| **Email ships here**, not in spec 3: `messaging.send()` over SMTP from the environment, an `Outbox` row per message. | "Notify staff" (ROTA-09) is the first thing that needs mail. Specs 3 and 5 reuse the sender; spec 5's Outbox page reads the table. |
| **GP sessions come from the rota app now**, by a new read endpoint there, matched to people **by email**. | Both apps already hold HR's work email; nothing else links them. Revisit: link clinicians by HR employee id once the rota app holds it. The practice manager's answer to amendment 2 is pending; the direction is agreed and two-way sync is off the table either way. |
| **Free-typed tiles are parsed on save; what does not parse is kept as a comment.** | FindMyShift's feel (FMS item 3) with ROTA-01's structure underneath, so the hours report and spec 3's costing work on fields, not text. Nothing typed is ever lost. |
| **A thin Preact island over JSON; every window is a server-rendered dialog.** | The grid needs a real frontend for selection, drag, paste and menus; the dialogs do not, and the Foundation's modal contract, CSP and templates carry them. One island, one API. |
| **One ordered item table per cell** (`shifts.Entry` with a kind), rather than a shifts table and a notes table. | A FindMyShift cell holds shifts, comments and separators in order; ROTA-06 needs two shifts on one day; copy, paste and rendering stay trivial. Spec 3 adds a kind for time off. |
| **"Message [name]" from the grid is greyed with "coming later".** | Messages are spec 5's; the menu item is kept so the menu matches FindMyShift's (FMS-00). |
| **"Who's in today" ships here with working and WFH; "off" is people with no shift until spec 3.** | A read of shifts; the real off list needs time off. |

## Global constraints

The Foundation's, plus:

- **All writes to `shifts` go through `shifts/services/`**; views and the
  API call services, never models. Every change writes `AuditEntry` rows
  through `people.services.audit.record`.
- **The server parses.** The island's parser is a live preview; what is
  stored is what `shifts/services/parse.py` read from the text sent.
- **The API never redirects.** A signed-out or forbidden call answers
  JSON with 401 or 403; the island shows the message, the page stays.
- **No record's values in a log line or a `SyncRun.message`**, as for the
  HR sync; the GP feed is logged by counts.
- Times are shown `08:00–16:15` (24-hour, en dash) and durations as
  `7 h 15 min` (LEAVE-04). The week starts on Monday.

## 1. Architecture

**Apps added.** `shifts` (entries, templates, the grid, its API and
services, the hours report, who's in today, the GP feed) and `messaging`
(`Outbox`, `send()`). `people` gains a `source` on `SyncRun`. `ui` gains
the Rota and Reports items.

**Repository layout, additions.**

    shifts/
      models/            entry.py template.py day_change.py gp_session.py grid_options.py
      services/          entries.py parse.py render.py clipboard.py templates.py
                         common.py notify.py gp_client.py gp_sync.py hours.py today.py
      views/             grid.py api.py dialogs.py reports.py today.py
      management/commands/gp_sync.py
      urls.py admin.py forms.py
    messaging/           models.py services.py
    frontend/src/rota-grid/
      index.tsx grid.tsx cell.tsx menu.tsx selection.ts clipboard.ts
      parser.ts api.ts keys.ts types.ts
    frontend/src/rota-grid.css
    templates/shifts/    grid.html _grid_phone.html shift_dialog.html options_dialog.html
                         filters_dialog.html templates_dialog.html notify_dialog.html
                         hours.html today.html
    tests/test_shifts_*.py tests/test_messaging.py tests/e2e/test_grid.py
    deploy/shift-central-gp-sync.{service,timer}
    docs/admin/rota.md

**Data flow.**

- Browser ↔ Shift Central: one `GET /rota/api/window/` per window shown;
  one JSON POST per edit; dialogs fetched into `#dialog` as before.
- GP rota app → Shift Central, every 15 minutes: `GET /api/v1/sessions`
  (section 9).
- Shift Central → staff: one email per person per "Notify staff" through
  SMTP (section 8).

## 2. Data model

**`shifts.Entry`** — one row per item in a cell. A cell is one person on
one day.

| Field | Type | Notes |
|---|---|---|
| person | FK `people.Person`, PROTECT | |
| day | date | |
| position | small int | Order within the cell, from 0 |
| kind | `shift` / `comment` / `separator` | |
| start, finish | time, null | Shift only; finish after start, same day |
| break_minutes | small int | 0, 15, 30, 45, 60 (ROTA-01); shift only |
| department | FK `people.Department`, null, PROTECT | Archived departments stay on old entries |
| text | char 200 | The comment, or a shift's comment line |
| overtime | `""` / `paid` / `toil` | ROTA-06; shift only |
| wfh | bool | ROTA-04 |
| appearance | JSON | Keys `bg`, `fg` (hex), `bold`, `italic`, `underline`, `strike`, `wrap` (bool), `size` (`sm`/`md`/`lg`); `{}` means the department's colour and the defaults (ROTA-04a) |
| created_by | FK user, null, SET_NULL | Feeds "Recent" |
| created_at, updated_at | | |

Constraints: a check that `kind = "shift"` has both times and the others
have neither; unique `(person, day, position)`; index `(person, day)`.
`Entry.hours` is a `timedelta`: finish − start − break for a shift, zero
otherwise. Overtime is not subtracted here; readers that must exclude it
(spec 3's costing, the hours report's scheduled column) filter on the
mark. Overlapping shifts in one cell are allowed.

**`shifts.Template`** — `name` (unique), `created_by`, `created_at`,
`block` JSON: the clipboard block (section 5), rows of relative day
offsets with their items. Shared by all managers.

**`shifts.DayChange`** — `person`, `day`, `before` (text), `at`; unique
`(person, day)`. Written by the service before the first unnotified change
to a day, holding the day's rendering at that moment (section 5,
`render.day_text`); deleted by notify. A day whose rendering now equals
`before` is a change undone and sends nothing.

**`shifts.GpSession`** — `person`, `day`, `part` (`AM`/`PM`), `label`
(the session type's name, char 60), `site` (char 60), `note` (char 200),
`synced_at`; unique `(person, day, part)`. Replaced in full for the window
fetched on each sync. Counts 4 h 10 min (ROTA-GP-02); `GpSession.HOURS =
timedelta(hours=4, minutes=10)`.

**`shifts.GridOptions`** — one per user (`user` OneToOne), `data` JSON with
the Options panel's keys and defaults: `staff_colours` (true),
`job_titles` (false), `department_colours` (true), `float_headers`
(true), `my_shifts_on_top` (false), `only_my_shifts` (false),
`hide_no_shifts` (false), `font_size` (`md`), `spacing` (`normal`),
`days` (`[0..6]`, weekday numbers shown), `paste` (`replace` / `add`).
Unknown keys are dropped on save.

**`people.SyncRun.source`** — char 20, default `practice-hr`; the GP sync
writes `gp-rota`. `hr_sync.last_run()` and `not_seen_recently()` filter
on their source.

**`messaging.Outbox`** — `to_person` (FK, null, SET_NULL), `to_email`,
`subject`, `body`, `queued_at`, `sent_at` (null), `error` (char 300,
blank). One row per message, written before the send is attempted and
updated after.

Not stored here: time off (spec 3 adds a kind and the ROTA-10 rules),
open shifts (spec 5), break times, pay.

## 3. The grid page and the island

**URL and side panel.** `/rota/?from=YYYY-MM-DD&weeks=N` (`from` any
day, snapped back to its Monday; `weeks` 1 to 20, default 1; default
`from` is this week). Filters (section 6) live in the same query string.
The Rota item is first in the side panel, its flyout: Rota, Who's in
today (managers), Templates (managers). Reports follows Departments with
one child, Hours. The order matches FindMyShift's: Rota, Staff,
Departments, Reports, Activity logs.

**Top bar**, as FindMyShift's: ‹ › arrows (a window back or forward),
Today, "Show [weeks] from [date]" (a select and a date field that submit
on change), Options, Filters, Download, Templates; for managers, "Notify
staff (N)" in amber, N the people with unnotified changes among those they
manage, hidden when zero.

**The mount point.** The page's content is a single element with
`data-component="rota-grid"`, `data-from`, `data-weeks`, `data-filters`
(the query string), `data-api="/rota/api/"`, `data-role` and `data-me`
(the viewer's person id, or empty). The page also includes
`_grid_phone.html` (section 7); CSS shows one or the other by width, and
the island mounts only while `matchMedia("(min-width: 768px)")` matches,
mounting on a resize that crosses it.

**Window payload.** `GET /rota/api/window/?from=&weeks=&…filters` →

    {
      "days": [{"date": "2026-10-26", "label": "Mon. Oct. 26", "today": false, "weekend": false}, …],
      "rows": [{"person": 12, "name": "Nina Patel", "colour": "#C0392B", "job_title": "Receptionist",
                "team": "Reception", "is_gp": false, "editable": true,
                "cells": {"2026-10-26": [ {entry}, … ], …},
                "sessions": {"2026-10-26": [ {"part": "AM", "label": "Surgery", "site": "AG", "note": ""} ]}}, …],
      "departments": [{"id": 3, "name": "Reception PMC", "colour": "#F2A33A"}, …],
      "common": [ {shape}, … ], "recent": [ {shape}, … ],
      "options": {…}, "unnotified": 4, "can_edit": true
    }

An `{entry}` is the model's fields plus `id`, `hours` in minutes and
`line` (its rendering); a `{shape}` is `start`, `finish`, `break_minutes`,
`department` and a `label`. Cells with nothing are omitted. One request
per window; the island re-fetches after a dialog closes having saved
(the dialog's JSON answer is `{"refresh": true}` instead of a redirect,
which `modal.js` learns to honour by dispatching `shift-central:refresh`).

**Drawing.** A table with a sticky name column and sticky day header
(`position: sticky`, the Options' "float headers" switches it off);
today's column shaded `--today`; weekends' headers in `--muted`; thin
`--hairline` gridlines; rows 44 px tall at normal spacing, taller when a
cell holds more. A name cell is a chip in the person's colour with white
bold text (or plain text when "show staff colours" is off), the job title
beneath it when asked for; clicking it opens the profile pop-up through
`data-dialog` as the Staff page does. A shift tile shows three lines
centred in small type: `08:00–16:15`, `1 hour break` (omitted when none),
then the department name or the comment; a fourth line `WFH`, `OT paid`
or `TOIL` when set, overtime tiles with a thin amber left border. The
background is the tile's own `bg` if set, else the department's colour
when "use department colours" is on, else white; text `fg` or
`--ink`. A comment tile is the text in italics with a dotted top border
so it reads as uncosted; a separator a hairline across the cell. A GP
session tile is pale grey-blue, `AM · Surgery · AG`, with the rota app's
name as its title, drawn before the cell's own items, never selectable.

**Interaction** (viewers who may edit at least one row):

- Click selects a cell; Shift-click extends to a block; Ctrl-click adds
  a cell; drag over cells selects a block. Clicking a day header selects
  the column, a name the row (the menu's Select ▸ offers Row, Column,
  Week, All). Selection is a set of (person, day); cells the viewer may
  not edit are never in it.
- Double-click, Enter or typing a printable character on a single
  selected cell opens in-place editing: a textarea over the cell holding
  the cell's text (one item per line, section 5), the typed character
  already in it. Enter saves, Shift-Enter adds a line, Escape cancels,
  blur saves. Saving posts `cell/`.
- Delete or Backspace clears the selection (`clear/`).
- Ctrl-X / Ctrl-C copy the selection as a block to the island's
  clipboard and the system clipboard (section 5); Ctrl-V pastes at the
  selection's top-left (`paste/`). Cut is copy then clear.
- Ctrl-Z undoes the viewer's last change in this page load: the island
  keeps a stack of the cell states each of its own posts replaced (up to
  50) and writes them back through `cell/`. Redo is not offered.
- Dragging a selection moves it (`move/`), Ctrl-drag copies; a drop on a
  row the viewer may not edit is refused before any request.
- Right-click opens the context menu at the pointer (also Shift-F10 and
  the Menu key on the focused cell): a navy panel, white text, icons,
  submenus to the right, closing on Escape, click-away or an action. Its
  items, in FindMyShift's order:
  Add ▸ Shift…, Comment, Separator, Department ▸ (names with swatches,
  "More departments…" opens the Departments page), Break ▸ (None, 15,
  30, 45 minutes, 1 hour), Common ▸, Recent ▸, Overtime ▸ (None, Paid,
  TOIL), WFH;
  Appearance ▸ Background ▸ (swatches), Text colour ▸ (swatches), Bold,
  Underline, Italic, Strikethrough, Wrap text, Font size ▸ (Small,
  Normal, Large), Reset appearance;
  Find & Replace…; Cut; Copy; Paste; Delete; Select ▸; Save selection as
  template…; Print; Message [name] (greyed, "coming later").
  Add ▸ Shift… opens the server-rendered shift dialog for the cell
  (section 4); Add ▸ Comment starts in-place editing of a new line in the
  cell; Separator appends one through `cell/items/`; Common and Recent
  add a shift of that shape through `cell/items/`; a department, break,
  overtime or WFH applies to the selection's shifts through
  `entries/<id>/`. Appearance items patch every entry in the selection.
  Menu items that open a dialog are `data-dialog` anchors, so `modal.js`
  handles them exactly as it does elsewhere.
- Arrow keys move the selection; Tab moves right; Home/End to the
  window's first and last day. The grid is a `role="grid"` with
  `aria-selected` cells and a visible focus ring; each tile's text is
  its accessible name.

Viewers with nothing to edit get the same drawing, hover titles and the
profile links, and no selection, menu or typing.

## 4. The API and the services

All under `/rota/api/`, JSON in and out, `X-CSRFToken` on POST, a
decorator `api_login_required` that answers `{"error": "signed out"}`
with 401 instead of redirecting, and `PermissionDenied` rendered as 403
JSON. Each mutation returns `{"cells": {"<person>": {"<day>": [entries]}},
"unnotified": N}` for every cell it touched, and the island patches them in.

| Endpoint | Body | Service |
|---|---|---|
| `GET window/` | query as above | `entries.window(user, from, weeks, filters)` |
| `POST cell/` | `{person, day, text}` | `entries.set_cell_text(user, person, day, text)` — parses, replaces the cell's items |
| `POST cell/items/` | `{person, day, items: [{kind, …}]}` | `entries.set_cell(user, person, day, items)` — the structured form (undo, Common/Recent, the shift dialog) |
| `POST entries/<id>/` | any of `department`, `break_minutes`, `overtime`, `wfh`, `appearance`, `text` | `entries.patch(user, entry, fields)` |
| `POST move/` | `{cells: [[person, day]…], days: ±n, rows: ±n, copy: bool, row_order: [person…]}` | `entries.move(user, cells, days, rows, copy)` — rows counted over the window's row order sent as `row_order: [person…]` |
| `POST paste/` | `{anchor: [person, day], block, mode}` | `entries.paste(user, anchor, block, mode)` — `mode` replace or add |
| `POST clear/` | `{cells}` | `entries.clear(user, cells)` |
| `POST replace/` | `{cells or "window", find, replace, match_case}` | `entries.replace(user, scope, find, replace, match_case)` — over each item's text line; a changed line is re-parsed |
| `POST order/` | `{people: [id…]}` | `people.services.profiles.reorder(user, ids)` — managers only; `display_order` set to 10, 20, 30… for the ids sent, audited |

**The one writer** is `shifts/services/entries.py`. Every mutation:

1. Resolves every person touched and checks `access.can_manage(user,
   person)` for each; any refusal raises `PermissionDenied` before a
   write (the whole request fails, nothing partial).
2. In one `transaction.atomic()`: for each day touched, `DayChange` is
   created if absent with `before = render.day_text(person, day)`; the
   change is applied; `audit.record` writes one `AuditEntry` per cell
   with `model="shifts.entry"`, `object_id=person.pk`, `field="cell"`,
   `before`/`after` the day's text and `note` = `"{day:%a %-d %b %Y} ·
   {person.name}"`. Appearance-only changes audit as field
   `"appearance"` with the entry's line in the note, so the Activity log
   is not flooded with colour changes that read like shift changes.
3. Returns the cells' new entries.

`set_cell_text` parses with `parse.cell(text, departments)` (section 5)
and keeps the existing items' appearance where a parsed item matches an
old one by position and kind. `paste` writes each block cell at `anchor +
offset`, skipping offsets that land on a row the viewer may not edit
(reported in the answer as `skipped: n`) and days outside the window;
`replace` mode clears the target first, `add` appends. `move` is copy
then clear of the source, in that order, inside the transaction.

**Dialogs**, server-rendered under `/rota/…/` and fetched into `#dialog`:

- `shift/<person>/<day>/` (and `shift/<person>/<day>/<entry>/` to edit):
  start, finish (time fields), break (select), department (select with
  swatches), comment, WFH, overtime (radio: none, paid, TOIL). Saves
  through `set_cell` and answers `{"refresh": true}`.
- `options/`: the Options panel as a form of tick boxes and selects, with
  "Sort staff…" switching the grid into reorder mode on close.
- `filters/`: name contains, team (multi), department (multi); submits
  as the grid's query string.
- `templates/`: list with Apply (to the selected cell: the island sends
  the selection in the dialog URL), Rename, Delete; and
  `templates/save/` from the menu, named by the manager, storing the
  selection's block.
- `replace/`: Find, Replace with, Match case, scope (selection or whole
  window), Replace all.
- `notify/`: section 8.

## 5. Editing: parser, rendering, clipboard, Common and Recent

**Cell text.** One item per line. A shift renders as its canonical line:
`08:00-16:15`, then `1 hour break` / `30 min break` when set, then the
department's name, then `WFH`, then `OT paid` / `TOIL`, then the
comment, separated by single spaces; a comment is its text; a separator
is `---`. `render.day_text(person, day)` is the cell's lines joined by
` / `, or `no shift` when empty; it is what `DayChange.before` and the
audit hold and what the notify email prints.

**Parser** (`shifts/services/parse.py`, mirrored in `parser.ts` for the
live preview; the server's reading is what is stored). For each line:

1. `---` (three or more hyphens alone) → separator.
2. A time range makes a shift. Each side is `H`, `HH`, `H:MM`, `HH:MM`,
   `H.MM`, `HHMM`, with an optional `am`/`pm` (case-insensitive, optional
   space); the sides joined by `-`, `–`, `—`, `to` or `until`. A side
   with `pm` and an hour under 12 adds 12; `12am` is 00:00. When neither
   side has a marker and the finish is not after the start, the finish is
   read as pm (`8-4` → 08:00–16:00); when it still is not after the
   start, the line is a comment. Minutes over 59 or hours over 23 → the
   line is a comment.
3. From the rest of a shift line, in this order, each removed when found:
   a break — `N hour(s) break`, `N h break`, `N min(s) break`, `N minute
   break`, `break N`, `N m` where N is 15, 30, 45, 60 or `1 hour`;
   `wfh` as a word; `toil` as a word → overtime TOIL; `ot paid`,
   `overtime paid`, `paid overtime`, `ot` as a word → overtime paid; the
   longest unarchived department name that matches as a whole phrase,
   case-insensitively. What remains, trimmed and with runs of spaces
   collapsed, is the comment (up to 200 characters; longer is cut).
4. A line with no time range is a comment.

The parser never raises. A comment that contains a department name or
"wfh" re-parses as that when edited again, which is FindMyShift's
behaviour too; the shift dialog is the exact way.

**Clipboard block.** `{"rows": [[{item}…]…], "days": n}` as cells
relative to the block's top-left: `rows[r][d]` is the item list at row
offset `r`, day offset `d` (a column index within the selected days, so
a copied Monday-to-Friday block pastes onto the next Monday). Items carry
kind, times, break, department id and name, text, overtime, wfh and
appearance. Held in the island, saved to `localStorage`
(`shift-central.clipboard`) so it survives a reload, and written to the
system clipboard as tab-separated text (cells joined by ` / `) so a block
can be pasted into Excel. A paste whose system clipboard text differs
from the island's last copy is treated as plain text: each line goes to
the anchor cell through `cell/`; tab-separated text fills cells rightward
and lines downward.

**Templates** store the same block. Apply is `paste/` with the stored
block at the selected cell with the viewer's paste mode.

**Common and Recent** (`services/common.py`): a shape is `(start,
finish, break_minutes, department_id)`. Common is the ten most frequent
shapes among shifts in the viewer's managed teams in the last twelve
weeks; Recent the viewer's own ten most recently created distinct shapes.
Both are computed in the window request; picking one adds a shift of
that shape to every selected cell through `cell/items/`.

**Undo** is the island's, for this page load only (section 3). The
Activity log and `DayChange` are the record.

## 6. Who sees what; filters

**Rows.** People current on at least one day of the window (`start_date
<= last day` and `end_date` null or `>= first day`) with `display_on_rota`
on. A staff viewer also needs `show_to_other_staff` on each row, and a
viewer with `can_see_other_staff` off sees only their own row. GPs are
rows like anyone else. A leaver's row disappears from windows after their
end date; their past cells stay for the hours report. The row order is
team order, then `display_order`, then name; "my shifts on top" lifts the
viewer's row to the top.

**Editing.** A row is `editable` when `access.can_manage(user, person)`
holds: team managers for their teams' people, all-teams managers for
everyone, nobody for themselves (the Foundation's rule, which spec 3
relies on). The practice manager's own shifts are entered by another
manager, as their leave is approved by one. The island never offers an
edit on a non-editable row, and the service refuses one regardless.

**GP rows.** Sessions are the rota app's and are never edited here. A
GP's cell can still take the cell's own items (a comment, an overtime
shift) from a manager; the hours report adds sessions and shifts.

**Filters** (FMS item 2): `name` (contains, case-insensitive), `team`
(ids, repeatable), `dept` (department ids, repeatable: keeps rows with at
least one shift so tagged in the window). Kept in the URL so a filtered
rota can be bookmarked; the Filters dialog edits them; "hide staff with
no shifts" from Options drops rows with no shift and no session in the
window.

## 7. Overtime, the hours report, who's in today, the phone

**Overtime (ROTA-06).** The menu's Overtime ▸ marks the selected shifts
`paid` or `toil`; the tile gains the fourth line and the amber border.
Hours of a marked shift are excluded from the "scheduled" figure
everywhere (LEAVE-05, 23) and shown in their own column. The marks are
what spec 4 reads for the TOIL balance and the payroll report.

**Hours report (REP-01, FMS 54)** at `/reports/hours/?from=&to=`, default
this week, any range up to a year. Managers see the people they manage
plus themselves; staff see themselves. One block per person headed
"Nina Patel — 5 shifts / 37 h 30 min", a table of Day, Date, Start,
Finish, Break, Hours, Overtime, with a subtotal row per week when the
range spans more than one and a total per person. A GP session is a row
with its part and label, Start and Finish blank, Hours 4 h 10 min. A
comment is not a row. Download is CSV with the same columns plus Name.
`services/hours.py` returns the figures; the view only renders.

**Who's in today (ROTA-12)** at `/rota/today/?day=`, managers only, with
‹ › and Today. By site, then by team: AG, PMC, Either, from the shift's
department name containing "AG" or "PMC" as a word (so "Reception AG",
"Cleaning PMC" sort themselves) else Either. Each person with their
times, WFH listed in its own section, then "Off": people current today
with no shift and no session. Spec 3 replaces Off with time off and adds
leave to the Rota's tiles. Phone-friendly: one column, large rows.

**The phone layout.** Under 768 px `/rota/` renders `_grid_phone.html`:
the week's seven days as cards, each listing the viewer's own tiles
first (or "No shift") and, behind a "Whole team" toggle, everyone else's
in row order with name chips; ‹ › and Today in the top bar; no editing.
Managers who must edit on a phone turn it sideways, where the width
passes 768 px on most phones and the grid mounts, as FindMyShift's does.

## 8. Notify staff and messaging

**`messaging.send(person, subject, body)`** writes an `Outbox` row, sends
with Django's SMTP backend (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`, already in
settings; the console backend when `EMAIL_HOST` is empty, `locmem` in
tests), and records `sent_at` or `error` (the exception's class and a
short message, never the body). It never raises; it returns the row.
Plain text only; no attachments; one recipient per message.

**The dialog** (`/rota/notify/`, managers): the people with `DayChange`
rows among those the viewer manages, each with a tick box (ticked), their
changed days as "Tue 3 Mar, Sat 7 Mar", and a note where sending is
impossible: "no email" (greyed, unticked) or "changes cancel out"
(greyed; the rows go when Send runs, the dialog itself writes nothing).
Send posts the ticked ids to `services/notify.py`:

For each person, in one transaction per person: build the lines for
their `DayChange` rows in date order, deleting unmailed any row whose
`before` equals the day's current text (a change undone), as

    Tue 3 Mar 2027: 08:00–16:15 1 hour break Reception PMC (was 09:00–17:00 Reception PMC)
    Sat 7 Mar 2027: no shift (was 08:00–13:00 Reception AG)

under "Your rota has changed. Here is what is different:" and above
"See your rota: https://<host>/rota/?from=<first changed week>", subject
"Your rota has changed"; `messaging.send()`; if it reports `sent_at`,
delete the rows and `audit.record` one entry (`model="shifts.entry"`,
`field="notified"`, `after` = the count of days, note the person's name);
if not, leave the rows for next time. The dialog re-renders with what
went out and what failed, by name.

The **Health card** gains "Unnotified rota changes over a week old: N",
counting `DayChange` rows older than seven days among the viewer's
managed people, linking to the notify dialog.

## 9. GP sessions from the rota app

**The rota app's feed** (a PR on `devachnid/rota`, its own tests):
`GET /api/v1/sessions?from=YYYY-MM-DD&to=YYYY-MM-DD` with
`Authorization: Bearer <token>`, the token one of `ROTA_API_TOKENS` in
`/etc/rota.env` (comma-separated, compared in constant time, in HR's
`api/auth.py` pattern, with the same per-address rate limit), CSRF-exempt,
no session. 400 for a missing or unordered range or one over 500 days;
401 without a valid token. Answers

    {"from": "…", "to": "…",
     "sessions": [{"email": "a.gp@practice.nhs.uk", "day": "2027-01-04", "part": "AM",
                   "type": "Surgery", "site": "AG", "note": ""}, …],
     "without_email": 1}

from published `RotaEntry` rows whose clinician has a user with an email,
ordered by day, part, clinician; `without_email` counts the clinicians
with entries in the range but no email, so the other side can report
them. Nothing else in the rota app changes; a README line documents the
variable and the endpoint.

**Shift Central's side.** `ROTA_URL` and `ROTA_API_TOKEN` in the
environment (both empty means "no GP feed", which the Health card says).
`services/gp_client.py` is `hr_client.py`'s shape: https only outside
DEBUG, refuses redirects, ten-second timeout, `GpError` on anything but a
200 with the expected keys. `services/gp_sync.py`: `sync(client=None,
now=None)` fetches from eight weeks before today to fifty-two after,
matches each email to a `Person` with `is_gp` (case-insensitive,
current or future), replaces the window's `GpSession` rows in one
transaction (delete the window, bulk-create the new), writes a `SyncRun`
with `source="gp-rota"`, `people_seen` = matched clinicians, and a
`message` naming counts only ("3 emails unmatched"); never raises;
`last_run()` and `unmatched()` for the Health card. `manage.py gp_sync`
runs it; `deploy/shift-central-gp-sync.{service,timer}` every fifteen
minutes, offset from the HR timer.

**Shown.** The Health card: "GP rota — 9 GPs, 14:32" (or failed / never
read / not configured) and "GPs in the rota app not matched here: 2",
with the emails shown only to all-teams managers. The grid draws sessions
as section 3 says; the hours report counts them at 4 h 10 min.

**Revisit (recorded in `docs/admin/sync.md`):** link clinicians by HR
employee id once the rota app holds one, so a changed email cannot drop a
GP's sessions; the Health line is the safety net until then.

## 10. Options, download, print

**Options** saves `GridOptions` and answers `{"refresh": true}`; the
island re-renders from the new payload. "Sort staff…" puts the grid into
reorder mode: the name column grows drag handles, dropping posts
`order/`, Done leaves the mode. Managers only; staff do not see the
item. "Days to display" hides the unticked weekdays' columns (the data
still exists; a paste never lands on a hidden day).

**Download** (FMS 13) offers CSV of the window: a row per person (Name,
Team, then one column per day, a cell's items joined by ` / `), through
`/rota/download/?…` with the window's query string, and "Printable page".

**Print** (FMS 11): `@media print` on the grid page hides the side panel
and top bar, lays the table out landscape at a smaller type size,
repeats the header row on each page (`thead { display: table-header-group
}`), keeps tile colours (`print-color-adjust: exact`) and prints the
window's title and range. The menu's Print calls `window.print()`.

## 11. Audit

Every change in section 4 writes `AuditEntry` rows through
`people.services.audit.record` as described there: model `shifts.entry`,
`object_id` the person, field `cell` (or `appearance`, `notified`), the
day and name in the note. The Activity log's person filter therefore
shows a person's rota history in order, and its field filter separates
rota edits from profile edits. Template saves and deletes audit on
`shifts.template`; order changes on `people.person` field
`display_order` as the Foundation's services do; the GP sync writes no
audit rows (its data is the rota app's, replaced wholesale), only its
`SyncRun`.

## 12. Errors

- A window request that fails (network, 5xx) leaves the last grid on
  screen and shows a red bar under the top bar: "The rota couldn't be
  loaded. Check your connection and try again." with a Retry link.
- A mutation that fails puts the cells back as they were before the
  optimistic update and shows the bar: "That change wasn't saved: …" with
  the server's message for 400/403, "Your session ended" with a sign-in
  link carrying `next` for 401, the connection message for a network
  failure. Never a browser alert.
- The parser never rejects; the service refuses only what cannot be
  stored (an unknown department id, a person outside the viewer's
  teams, a day outside 2000–2100), each with a sentence the bar shows.
- Two shifts overlapping in one cell draw a small warning marker with
  the title "These shifts overlap"; nothing is blocked.
- The GP sync's failures are the `SyncRun` row and a Health line, as
  the HR sync's; a feed that stops never removes sessions already held.
- `messaging.send()` failures are the `Outbox` row's `error`; notify
  leaves the person's rows for the next attempt.

## 13. Testing

Python (pytest, the Foundation's fixtures and factories, plus
`make_entry(person, day, **kw)`, `make_gp_session(...)`):

- `test_shifts_parse.py`: a table of every form in section 5 (both
  12- and 24-hour, every break spelling, department match, WFH and
  overtime words, the pm inference, junk lines, over-long comments) and
  the round trip of `render` → `parse` for a generated set of shifts.
- `test_shifts_entries.py`: each service with a team manager, an
  all-teams manager, a staff user and the person themselves; refusal
  before any write; `DayChange` created once per day and not again;
  audit rows' shape; paste modes, skipped rows, moves off the window.
- `test_shifts_api.py`: every endpoint's status for signed-out (401),
  staff (403 on every mutation, 200 on the window), manager; the window
  payload's row visibility under the three Display switches and the
  filters.
- `test_shifts_notify.py`: lines built, undone changes skipped, no-email
  people listed, a failed send keeps the rows, the audit row, the
  Health count.
- `test_shifts_gp_sync.py`: against `tests/fixtures/gp_sessions.json`,
  matching, replacement of the window only, unmatched counts, a failing
  client leaving data untouched, the `SyncRun` source.
- `test_shifts_hours.py`: breaks subtracted, overtime in its column,
  sessions at 4 h 10 min, weekly subtotals, who sees whom, CSV.
- `test_shifts_today.py`, `test_shifts_views.py` (dialogs, options,
  download, print page, phone layout), `test_messaging.py` (Outbox row,
  console backend, an exception recorded, nothing raised).
- `tests/e2e/test_grid.py`: Playwright over Django's live server
  (`pytest-playwright`), skipped unless `E2E=1`: sign in with a
  password as a manager the test creates (HR is not configured in tests,
  so the password form is open), type a shift, see the tile, drag it,
  copy and paste a block, open the context menu and mark overtime, undo.
  CI runs
  it in the `tests` job after `playwright install --with-deps chromium`.

TypeScript (`vitest`, added to `frontend/package.json`; `npm test` in
CI's `frontend` job): `parser.ts` against the same table as the Python
test (the cases live in `frontend/src/rota-grid/parser.cases.json`,
which the Python test also reads, so the two parsers cannot drift),
`clipboard.ts` serialisation both ways, `selection.ts` block maths.

The rota app's feed has its own tests in that repository: token
required, range validation, published-only, emails, `without_email`.

## 14. Deploy, operations and CI

- `/etc/shift-central.env` gains `ROTA_URL`, `ROTA_API_TOKEN` and the
  `EMAIL_*` values (documented in `docs/admin/setup.md`); the rota's
  `/etc/rota.env` gains `ROTA_API_TOKENS`.
- `deploy/shift-central-gp-sync.{service,timer}` in the HR sync's shape,
  `OnCalendar=*:07/15` so it does not coincide with the HR timer.
- CI: the `tests` job installs Playwright's Chromium and runs the e2e
  test with `E2E=1`; the `frontend` job runs `npm test` before the
  build check. `requirements.txt` gains `pytest-playwright`.
- The admin (superuser) lists `Entry`, `Template`, `DayChange`,
  `GpSession`, `GridOptions`, `Outbox` read-only; `Entry` and `Template`
  deletable for repair.

## Documentation

`docs/admin/rota.md` for managers: the grid, typing a shift, the menu,
copying weeks, templates, overtime, notify staff, the hours report,
who's in today, printing. `docs/admin/sync.md` gains the GP feed, the
Health lines and the revisit. `docs/admin/setup.md` gains the new
variables and the rota-side token. `README.md`'s overview mentions the
grid. `docs/requirements/2026-10-29-proposed-amendments.md` gains a
dated postscript: GP sessions shown read-only, matched by email, with the
revisit.

## Not done, on purpose

- Time off tiles, ROTA-10's removal and restoring of shifts, blackout
  periods (spec 3).
- TOIL balances, the payroll report, sickness (spec 4).
- Open shifts, messages from the grid, push notifications, the
  installable app, the Outbox page (spec 5).
- Writing anything to the GP rota app; GP sessions edited here.
- Break times (only lengths), minimum staffing, skills, rooms.
- Importing FindMyShift's rotas.
- Redo; undo across page loads.

## Revisit

- Link GP rota clinicians by HR employee id, not email (section 9).
- The practice manager's answer to amendment 2 (GP sessions read-only);
  if it changes, this spec's section 9 is what changes.
