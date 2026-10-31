# AMG Shift Central: absence and payroll — design

**Date:** 2026-10-31
**Status:** approved in conversation; not yet built
**Requirements:** `docs/requirements/` as amended by
`docs/requirements/2026-10-29-proposed-amendments.md`. This spec covers
LEAVE-14, 21, 22, 24 (the year-end half), 28, 29, 30 (the payroll half)
and 40 to 44; LEAVE-27's payroll half; PAY-01 to 03; REP-04, REP-05, REP-09 and the Instances column
of REP-02; NOTIF-05, 06, 07, 08 and 12 (by email; push is spec 5's);
ACC-06's sickness and past-schedule rows; MIG-05; FMS item 38 (the
Bradford Factor replaced) and the Instances / trigger columns of the time
off report; D-18, D-20, D-28; Q-11 answered. It builds on the Foundation,
rota grid and leave specs (`2026-10-29-foundation-design.md`,
`2026-10-29-rota-grid-design.md`, `2026-10-31-leave-design.md`), whose
constraints, shell, people, access rules, audit, grid, entries service,
leave services, messaging and API conventions it reuses unchanged unless
this spec says so.

Absence and payroll is the fourth of five releases: sickness instances and
triggers, the join-on warning, long sickness and the return flag, the past
schedule section for 2026 sickness, converting annual leave to sickness,
the leaver flags, the year-end carry-over flag, the monthly payroll report
the bureau is sent (with its corrections), and the sickness and leave
one-pagers. After it, the only manual spreadsheet left is the one the
bureau keeps.

## Decisions made in conversation

| Decision | Rationale |
|---|---|
| **Everything the Foundation listed for spec 4 is built now**, the one-pagers and the year-end flag included, though the approved amendments allowed them to follow in February and autumn 2027. | The year-end flag is small once Adjustments exist, the one-pagers share the report code, and every worked example left open by spec 3 (SICK-01 to 04, KIT-01, LV-07b, LV-15a, LV-15b, LV-16) closes in one release. |
| **A booking is the instance.** An approved booking of a leave type flagged "counts as sickness" is one instance of absence, its first and last day as LEAVE-40 defines them. Triggers, the join-on warning, long sickness and the one-pager are computed over those bookings; nothing is stored twice. | Spec 3 already books Sick leave for everyone, covers the rota and costs the day for the payroll report. A second Sickness record would need a rule keeping two rows in step on every edit and cancel, and sickness kept outside leave would vanish from the grid, planner, Time off list and GP feed. |
| **The past schedule section records 2026 sickness as bookings flagged "dates only"**: approved, no costed days, covering nothing, never on payroll. | MIG-05 asks for start and end dates only, counting towards triggers from day one and touching neither balances nor payroll; one flag on the existing record does that. |
| **No sickness reason is recorded** (Q-11). The manager note, visible to managers only, stays the place for anything a manager wants to keep. | Reasons are health data the pack never asked for; the practice manager is told in the postscript. |
| **GPs appear on the payroll report**, with their sessions counted as hours worked at 4 h 10 min, and their leave and sickness like everyone else's. | The practice manager's choice: the bureau sees every person and every absence in one file. |
| **"Sent to the bureau" is a manager's action**, a button that stores a snapshot of the figures; every later report recomputes each sent month of the last twelve and lists the differences as corrections (PAY-02). Downloads before the mark are drafts. | A download is not a send: a manager checks the figures more than once. Storing nothing would leave corrections to be found by hand. |
| **Excel by openpyxl, PDF by reportlab**, two pure-Python dependencies with wheels. | REP-04 and REP-05 want PDF or Excel chosen at download; a print-styled page would make "PDF" depend on each machine's browser, and WeasyPrint needs system packages on the VPS. |
| **One daily command, `daily_flags`, at 08:25 every day**, carries the one-week leaver reminder, the return flag and the year-end flag. The leave reminder's weekday timer is unchanged. | Returns and year starts fall on any day of the week; one timer is easier to run and check than three. |
| **Email only; push waits for spec 5.** | As spec 3. |

## Global constraints

Inherited from the Foundation, grid and leave specs. In addition:

- Every write goes through a service; views never touch models. Audit rows
  under `leave.booking`, `leave.adjustment`, `leave.yearend` and
  `payroll.payrollrun`.
- Log lines, `Outbox.error`, `SyncRun.message` and the GP leave feed never
  carry a description, a note, a reason or a figure. The feed is unchanged
  by this spec (a dates-only booking has first and last days and is
  served like any other).
- Figures are never stored except as the payroll snapshot, which exists
  only so that what was sent can be compared with what is true now. Every
  other screen reads `leave.services.balances` and
  `leave.services.sickness`.
- Spreadsheet and PDF cells are written as text, never as formulas: a
  name or description starting with `=`, `+`, `-`, `@` is cleaned as
  `csv_safe.cell` cleans it, and openpyxl cells are given the string type
  explicitly.
- Times and dates are Europe/London; "today" is `timezone.localdate()`;
  tests run under the pinned clock (`tests/clock.py`).

## 1. Architecture

Two new apps beside `people`, `shifts`, `leave` and `messaging`, a shared
export package, and additions to `leave` and `people`:

```
absence/                       sickness screens: no models of its own
  services/    convert.py (LEAVE-28)  onepager.py (REP-04)
  views/       past.py convert.py onepager.py
  forms.py urls.py
templates/absence/ ...

payroll/
  models.py    PayrollRun
  services/    report.py (rows, corrections)  runs.py (mark sent)  xlsx.py
  views.py urls.py
templates/payroll/ ...

exports/                       not an app: writers both one-pagers and payroll share
  xlsx.py (openpyxl workbook with text cells)  pdf.py (reportlab A4 landscape, logo, tables)

leave/ gains
  models/      types.py (two flags)  booking.py (two fields)  yearend.py (YearEnd)
  services/    sickness.py (window, instances, level, is_long, joins_on; the trigger check)
               leavers.py returns.py yearend.py summary.py (REP-05)  sessions.py
               notify.py gains trigger_reached, leaving, leaving_soon, returned, year_end
  views/       yearend.py summary.py
  management/commands/daily_flags.py
people/ gains  Person.leaver_flagged_for, Person.leaver_week_flagged_for
shifts/        today.board uses leave.services.sessions; the shift dialog unchanged
```

`absence` and `payroll` import from `leave`, `shifts` and `people`; `leave`
imports from `shifts` as before; nothing imports from `absence` or
`payroll` except `people.services.health` (the card's lines) and
`ui.context_processors` (navigation). The instance arithmetic lives in
`leave` because `bookings.book` and `bookings.edit` run the trigger check,
and `leave` must not import from `absence`. `hr_sync` calls
`leave.services.leavers.flag` when an end date appears or changes.

## 2. Data model

**`leave.LeaveType`** gains `sickness` (bool, default false; seeded true on
Sick leave) and `flag_return` (bool, default false; seeded true on
Maternity and Adoption / shared parental). Both are manager-editable on
the type form ("Counts as sickness: instances, triggers and the sickness
one-pager"; "Email managers when the person returns") and chosen when a
manager adds a type. `draws_from` and `on_payroll` stay fixed on seeded
rows.

**`leave.Booking`** gains `dates_only` (bool, default false): the past
schedule section's record, approved, whole days, with no `BookingDay` rows
written by `_apply` (section 4), so it covers nothing and costs nothing.
Constraint: `dates_only` only with `part = whole`. It gains
`return_flagged_at` (nullable datetime), set when the return email has
gone.

**`leave.YearEnd`** — `person`, `year_ended` (the first day of the leave
year that ended), `notified_at`, `annual_remaining`, `toil_remaining`
(seconds, as the flag found them), `annual_carried`, `annual_lost`,
`toil_lost` (seconds, null until decided), `decided_by`, `decided_at`,
`note`. Unique `(person, year_ended)`. A row exists from the moment the
flag opens; decided rows are the record of the manager's choice.

**`people.Person`** gains `leaver_flagged_for` and `leaver_week_flagged_for`
(nullable dates): the end date each email was sent for, so a changed end
date is announced again and an unchanged one is not.

**`payroll.PayrollRun`** — `month` (the first day), `sent_at`, `sent_by`,
`people` (count), `figures` (JSON: `{"generated_at": ..., "rows":
{"<person pk>": {field: int, ...}}}`, the numeric fields of section 4 in
seconds and counts, plus `started` and `leaves` as ISO dates or null).
Several runs for a month are allowed; the latest is what was sent.

Migrations: `leave/0003` (type flags with a data step setting the seeded
rows, booking fields, `YearEnd`), `people/0007`, `payroll/0001`. All
additive.

## 3. Sickness (`leave/services/sickness.py`)

```
window(today) -> (start, end)      # rolling six months, LEAVE-42
instances(person, today) -> [Booking]
level(count) -> 0 | 1 | 2 | 3      # LEAVE-43; 3 is shown as "Trigger 3+"
is_long(booking) -> bool           # LEAVE-44
joins_on(person, first, last, exclude=None) -> Booking | None   # LEAVE-41
```

- `window`: `end = today`; `start` is the same day of the month six months
  earlier, plus one day; when that month has no such day, the last day of
  that month is used before adding one. SICK-01: today 1 Jul 2026 gives
  2 Jan to 1 Jul.
- `instances`: active bookings (`approved`, `cancel_requested`) of the
  person whose type has `sickness`, with `first_day <= end` and `last_day
  >= start`, dates-only bookings included, ordered by `first_day`. An
  entry counts if any of its days fall within the window (LEAVE-42).
- `level`: fewer than 3 → 0; 3 → 1; 4 → 2; 5 or more → 3.
- `is_long`: `(last_day − first_day).days + 1 >= 29` (SICK-02: 28 days is
  not long, 29 is).
- `joins_on`: among the person's active sickness bookings other than
  `exclude`, the nearest one that ends before `first` or starts after
  `last` where every day strictly between them is a day the person does
  not work: no shift entry (whatever its cover) and no GP session that
  day. Adjacent dates (SICK-04a) have no days between and join. The
  rota decides what "does not work" means, as PAT-02 says it does; a
  weekday with no rota at all counts as not worked, which is what the
  practice means by "joins on" for a receptionist off Friday and Monday.

**Trigger notices (NOTIF-05).** `bookings.book`, `bookings.edit` and
`convert.convert` (section 5), for a sickness type, compute
`level(len(instances(person, today)))` before and after the write inside
the transaction and, when it rose, queue `notify.trigger_reached(person,
level, instances)` to `common.recipients(person)` on commit:
subject "[Name] has reached Trigger 2", body the instances in the window
with their dates and a link to the profile. Cancelling can only lower the
level and sends nothing. Dates-only entries never email: the manager is
entering history and the past schedule page shows the level as they type.
Nothing is stored; a person who drops to Trigger 1 as the window moves
and later returns to Trigger 2 has reached a new trigger and the managers
hear again.

**Long sickness** is a property of one booking, shown as a note on the
booking's view, in the Add dialog's preview once the dates span 29 days,
on the past schedule list and on the sickness one-pager. Its return flag
is section 6's.

**Who sees what (ACC-06).** The instances count and trigger level appear
to the person on My leave and to managers on the profile's Pay & time off
tab, the leave report, the past schedule list and the sickness one-pager. Colleagues see the type only, as now.

## 4. The past schedule section (MIG-05)

`/time-off/past/`, managers, nav item "Past schedule" under Time off. The
list shows every dates-only booking for the manager's people: Staff,
First day, Last day, Days (calendar), Type, Long sickness (yes or blank),
Recorded by and when, and the person's current instances and trigger. Add
opens a pop-up: Staff member (the manager's people), Type (sickness types
only), First day, Last day; the preview shows calendar days, the join-on
warning with Extend / Record separately as the Add dialog does (section
7), and the person's trigger level after the entry. The last day must be
before today. Saving calls `bookings.book(..., dates_only=True)`, which
records the booking approved with no days, audited as any booking with
the note "dates only (past schedule)". Removing an entry is the existing
cancel, which keeps the record. Dates-only bookings appear on the Time
off list (Allowance used reads "dates only"), the year planner and the
grid like any approved booking, and in the GP leave feed for a GP (the
rota app shows 2026 history; nothing there costs).

`_apply` skips a dates-only booking; `_undo` has nothing to undo; `edit`
allows the dates and type to change and refuses `part`, times and costs;
`recost` never sees one (no rows); `balances.statement` reads
`BookingDay` rows and so never counts one; the payroll report (section 8)
excludes them explicitly even though they have no rows to count.

## 5. Converting annual leave to sickness (LEAVE-28)

`absence.services.convert.convert(user, booking, leave_type, first, last,
note="", base_url="") -> Booking` for a manager (`bookings.may_book`) on an
active, whole-day, non-dates-only booking whose type draws from `annual`
or `bank_holiday`, where `first..last` lies inside the booking and
`leave_type.sickness` is true. In one transaction, re-reading the booking
as spec 3's services do:

1. If `first == booking.first_day` and `last == booking.last_day`,
   `bookings.cancel` the booking with the note "converted to sickness".
   Otherwise `bookings.edit` it to the head (`last_day = first − 1`) or,
   when there is no head, to the tail (`first_day = last + 1`); when both a
   head and a tail remain, `bookings.book` the tail as a second approved
   booking with the same type, description, paid flag and notes, and a
   manager's typed figures on the tail's days carried as its overrides. Each
   step restores the removed days' costs through the edit path, so the
   hours come back exactly as they were charged (SICK-03: Mon–Fri 37.5 h,
   Wed–Thu converted, 15 h back).
2. `bookings.book` the sickness booking for `first..last`, approved,
   costed from the rota as any sickness, with the manager note
   "converted from Holiday 10–14 Mar 2027" ahead of anything typed.
3. The trigger check of section 3 runs inside the same transaction.

Audit: one `leave.booking` row per booking touched, each carrying the note
"converted to sickness", plus the new booking's own; the Activity log and
the person's history show them together. Emails: the person is told their
leave was changed ("Your time off has been changed": the existing edit
mail) and nothing else beyond a trigger notice. Refusals name the reason:
not approved, not whole days, not annual leave, days outside the booking,
not a sickness type.

The screen: the booking view gains "Convert days to sickness…" for
managers, a pop-up with First day, Last day (defaulting to the booking's),
Type (sickness types), Note, and a preview of the hours that come back
and the trigger level after.

## 6. The flags

All three email `common.recipients(person)` through `messaging.send`, one
Outbox row each, links built as `notify._link` builds them (the daily
command and the HR sync have no request, so the `CSRF_TRUSTED_ORIGINS`
fallback applies), and each has a Health card line.

### Leaver (LEAVE-14, NOTIF-06) — `leave/services/leavers.py`

```
figure(person) -> (year, statement)      # the leaving year's statement
flag(person) -> bool                     # the "date entered" email
week_flags(today) -> int                 # the one-week reminders
```

`hr_sync._apply`, after saving a person whose `end_date` changed: a new
non-null date calls `flag(person)`; a cleared date resets both flag
fields and sends nothing. `flag` emails "[Name] is leaving on 14 Oct
2026" with the annual leave remaining or over as at the leaving date
(`balances.statement(person, years.year_of(person, end_date))`:
`annual_remaining` positive reads "18 h 30 min remaining", negative
"11 h 30 min over"; LV-07b), the TOIL remaining, and every active booking
of theirs with a day after the end date ("to shorten or cancel": nothing
is cancelled automatically, closing spec 3's revisit item), with a link to
the profile; it sets `leaver_flagged_for = end_date`, and when the end
date is within seven days it sets `leaver_week_flagged_for` too so one
email covers both. `week_flags` (from `daily_flags`) emails "…leaves in a
week, on…" for each current person with `end_date` within the next seven
days whose `leaver_week_flagged_for` is not that date, the same body.

The profile's Pay & time off tab and the statement page show "Leaves on
14 Oct 2026: 18 h 30 min remaining" for anyone with an end date; the Time
off list and booking view mark a booking with days after the end date
"after leaving date". The Health card's "Leaving in the next 30 days"
line gains each person's figure and the count of bookings past their end
date.

### Return from long absence (LEAVE-29, NOTIF-07) — `leave/services/returns.py`

`due(today)` is every active, non-dates-only booking that is either a
long sickness (`sickness.is_long`) or of a `flag_return` type, with
`last_day < today`, `last_day >= today − 14 days` (so a missed day is
caught, and history is not re-announced), and `return_flagged_at` null.
`send(today)` emails "[Name] is back after 6 weeks of Sick leave" with the
remaining annual leave for the current leave year and TOIL (so untaken
leave can be planned), the LEAVE-29 reminder that the allowance was not
reduced by the absence, and a link to the profile; then sets
`return_flagged_at`. The year-end page marks the person "long absence this
year" (section 6, year end) when such a booking overlaps the year ended.
The allowance arithmetic is unchanged: LEAVE-29 says the allowance is a
full-year figure and spec 3 already does that; the adviser's answer to
Q-03 may add a rule, which would live here.

### Year end (LEAVE-21, 22, 24; NOTIF-08) — `leave/services/yearend.py`

```
open_due(today) -> [YearEnd]     # rows opened this run
notify(rows) -> int              # one summary per manager
decide(user, row, annual_carry, toil_keep, note="") -> YearEnd
```

`open_due`: for each current person, `y = years.year_of(person, today)`;
when `y` began within the last 31 days and no `YearEnd` exists for
`(person, years.previous_year(y))`, compute the ended year's statement.
A statement that is `missing` (no allowance for that year, as everyone's
2026) opens nothing: the first flags come on 1 January 2028. Otherwise a
row is created with `annual_remaining` and `toil_remaining` as found;
when `annual_remaining == 0` and `toil_remaining <= 0` it is decided at
once ("nothing left", `decided_by` null) and not emailed. `notify` sends
each manager one email listing the people they manage among the rows
opened: "Year end: 7 people have leave or TOIL left", each line the name,
the annual figure (the bank holiday balance folded in, LV-15a) and the
TOIL figure, with a link to the year-end page.

**The page** `/time-off/year-end/`, managers, nav item "Year end" under
Time off: open rows for the manager's people first (name, team, year
ended, annual remaining or over, TOIL remaining, "long absence this year"
where it applies, Decide…), then decided rows for the chosen year with
their decisions and who made them. Decide… opens a pop-up: Annual leave —
Carry all (default), Lose all, Carry part [hours]; for a deficit, Carry the
deficit (default) or Write it off; TOIL (only when above zero) — Keep all
(default), Lose all, Keep part [hours]; Note. `decide` writes, through
`adjustments.add` in the new leave year: `annual` +carry with the reason
"carried over from 2027" (or "deficit carried over from 2027" when
negative), and `toil` −(remaining − keep) with "TOIL lost at year end
2027" when anything is lost (TOIL never resets, so keeping it writes
nothing; LV-16). It records `annual_carried`, `annual_lost`, `toil_lost`,
`decided_by`, `decided_at`, audits `leave.yearend` with the figures and
the note, and refuses a carry outside `0..remaining` (or
`remaining..0` for a deficit) or a keep outside `0..toil_remaining`. The
statement's adjustment lines then show the carry as they show any
adjustment (LV-15a: 172.5 + 15 = 187.5 h; LV-15b: 182.5 h and 10 h lost,
logged). MIG-04's typed 2026 carry-over stands: the first year end this
page handles is 2027's.

The Health card gains "Year-end decisions waiting: N" and "Payroll for
October not yet sent" (section 8).

## 7. Screens

Server-rendered through `modal.js`, phone-usable, as spec 3.

**Navigation** (`ui/context_processors.py`): Time off gains, for managers,
Past schedule (`/time-off/past/`) and Year end (`/time-off/year-end/`);
Reports gains Payroll (`/reports/payroll/`), Sickness summary
(`/reports/sickness/`) and Leave summary (`/reports/leave-summary/`), the
three for managers only (staff keep Hours and Leave).

**Add time off** (manager pop-up): choosing a sickness type makes the
preview run `sickness.joins_on`; when it finds an entry, the preview
shows "This joins on to [Type] 1–5 Jan 2027. Extend that entry to 13 Jan
instead?" with a radio — Extend the existing entry (default) / Record as
a separate instance — and the button reads "Extend" or "Add Sick leave".
Extend calls `bookings.edit` on the existing booking with the new last (or
first) day; Record separately books as now and the result is two
instances (SICK-04). Dates spanning 29 days or more show "This is long
sickness (29 days or more): managers are emailed when [Name] returns."
The preview also shows "Instances in the last six months after this
entry: 4 (Trigger 2)". Staff never see this dialog for sickness: sickness
is not requestable.

**Edit** (manager): editing a sickness booking's dates re-runs the trigger
check; the join-on warning is shown but the choice is not offered (the
manager is already editing one entry).

**Booking view**: "Convert days to sickness…" (section 5) for managers on
an eligible booking; "Long sickness" and "dates only" notes; "after
leaving date" where it applies.

**Past schedule** (section 4) and **Year end** (section 6).

**Leave report** (`/reports/leave/`): gains Instances (in the rolling six
months as at the range's end) and Trigger columns, blank for people with
none, in the table and the CSV; FMS item 38.

**Profile** Pay & time off tab and **My leave**: a line "Sickness: 4
instances in the last six months (Trigger 2)" or "Sickness: none in the
last six months", and the leaver line (section 6).

**Payroll** (`/reports/payroll/`, section 8), **Sickness summary** and
**Leave summary** (section 9).

**Who's in today**: a GP with an active whole-day booking is listed under
"off" only; with an `am` or `pm` booking the other session still shows
under its site; a `times` booking hides nothing (the rule in
`leave/services/sessions.py`, `visible_sessions(person, day, sessions)`,
shared with the payroll report). Closes spec 3's revisit item without
touching the rota app: sessions stay the rota app's and are shown
unchanged on the grid.

## 8. The payroll report (PAY-01 to 03)

### Figures (`payroll/services/report.py`)

```
month_of(text) -> date                       # "2027-01" -> 1 Jan 2027; bad text -> this month
people_for(user, month) -> [Person]          # managed (all-teams: everyone), current on any day of the month, GPs included
rows(people, month) -> [Row]
corrections(user, month) -> [Correction]
```

A `Row` per person, seconds unless stated, every figure for days inside
the calendar month; the days after today use the rota as it stands
(PAY-02), placeholder costs included as they are:

| Field | Source |
|---|---|
| `worked` | shift entries, not covered, `overtime == ""`, `Entry.hours`; plus the GP's sessions left visible by `sessions.visible_sessions` at 4 h 10 min each |
| `paid_leave` | `BookingDay.cost_seconds` of active, non-dates-only bookings whose type is not `sickness`, whose `on_payroll` is not `always`, and which resolve paid (`paid` true, or null and `type.default_paid`): Holiday, Bank holiday, TOIL, Training, paid Dependants', Compassionate and Authorised absence |
| `total` | `worked + paid_leave` — "total hours to pay" |
| `paid_overtime` | entries with `overtime == "paid"`, not covered |
| `unpaid` | costed days resolving unpaid (`paid` false, or Unpaid leave's `default_paid` false) |
| `sickness`, `sickness_instances` | costed days of sickness types; bookings of sickness types overlapping the month (dates-only excluded from both) |
| `toil_taken` | costed days with `account == "toil"` (also inside `paid_leave`; shown apart as PAY-01 asks) |
| `leave_days` | days with `account` in (`annual`, `bank_holiday`): a whole day 1, a half day or a timed booking ½ (held as half-days, an integer, in the snapshot; shown as 3½) |
| per always-reported type | for each type with `on_payroll == always` other than sickness that has days in the month for anyone: `{"days": n, "seconds": s}` — KIT day, Maternity, Paternity, Adoption / shared parental, Unauthorised absence, Jury service. The sheet gets one column pair per such type present (KIT-01: "KIT day 1 day, 6 h"); Unpaid leave is in `unpaid` |
| `started`, `leaves` | `start_date` or `end_date` inside the month, else null |
| `leaver_balance` | for a leaver, `leavers.figure(person)[1].annual_remaining` (positive remaining, negative over; LV-07b) |

Figures are computed per person from the same tables the statement reads,
so REP-10 holds: every payroll figure is the sum of days a manager can
open.

### Corrections (PAY-02)

`corrections(user, month)`: for each month from `month − 12` to `month −
1` that has a `PayrollRun`, recompute `rows` today for everyone in the
latest run plus anyone now current in that month, and compare field by
field with the run's `figures`; a difference is a `Correction(month,
person, field, sent, now, delta)`, a person absent from the run is one
correction per non-zero field, a person gone from the people set one per
non-zero sent field. Shown to the viewer for their people only. The
report for a month is therefore "this month as it stands, plus every
earlier sent month's changes", which is what the bureau is sent.

### Mark as sent (`payroll/services/runs.py`)

`mark_sent(user, month)` for all-teams managers only (the bureau's record
is the practice's): computes `rows` for everyone current in the month,
stores a `PayrollRun` with the figures, audits `payroll.payrollrun`
(practice-wide, so in the Activity log as leave settings are) and returns
the run. A month may be marked sent again; corrections then compare with
the latest. The Health card shows "Payroll for October not yet sent" from
ten days before the month's last day until a run exists for that month,
for all-teams managers.

### The screen and the file

`/reports/payroll/?month=YYYY-MM`, managers, default this month, month
arrows. A table of the rows for the viewer's people with team subtotals
and a practice total (all-teams), hours as "7 h 30 min"; a Corrections
table beneath when there are any; a Starters and leavers table; "Sent to
the bureau on 23 Jan by [Name]" or "Not yet sent"; buttons Download Excel
and, for all-teams managers, Mark as sent to the bureau (a confirm
pop-up naming the month and the people count). The Excel
(`payroll/services/xlsx.py` on `exports/xlsx.py`), `payroll-2027-01.xlsx`:
sheet **Payroll** — Name, Team, Worked, Paid leave, Total to pay, Paid
overtime, Unpaid leave, Sickness, Sickness instances, TOIL taken, Leave
days, then the type columns present ("KIT day (days)", "KIT day (hours)",
…), Started, Leaves, Leaver's leave remaining (negative = over); hours as
decimal hours to two places (the bureau adds them up), days as numbers;
sheet **Corrections** — Month, Name, Figure, Sent, Now, Difference; sheet
**Starters and leavers** — Name, Team, Started, Leaves, Leave remaining.
Every text cell cleaned and typed as a string. The download is a draft
until marked sent; the sheet's title row says "Draft" or "Sent 23 Jan
2027".

## 9. The one-pagers (REP-04, REP-05)

Both are a screen with a range or year, a table, and Download as PDF /
Download as Excel, managers only, their people, with team and practice
totals; the writers are `exports/pdf.py` (reportlab, A4 landscape, the
logo from a PNG copy of `docs/brand/amg-shift-central-logo-dark.png` added
to `static/img/`, a title, the range, the tables with repeating headers,
page numbers, generated on and by) and `exports/xlsx.py`.

**Sickness summary** (`/reports/sickness/?from&to`,
`absence/services/onepager.py`), default range the rolling six months to
today. Practice totals: people, instances (sickness bookings overlapping
the range, dates-only included), days off sick (calendar days inside the
range), hours off sick (costs inside the range), people at Trigger 1, 2
and 3+ as at `to`. The same per team. Then per person: Team, Instances (in
the rolling six months as at `to`, or as at today when `to` is in the
future, as the leave report's column does), Days in range, Hours in range, Longest
instance (days) and "long" where 29 or more, Trigger. Sorted by team then
name. File names `sickness-2026-07-01-2026-12-31.pdf` / `.xlsx`.

**Leave summary** (`/reports/leave-summary/?year=`,
`leave/services/summary.py`), default the current leave year (people with
a different `leave_year_start` are reported for the year of theirs that
contains the chosen year's first day, noted in a footnote). Per person:
Team, Allowance (annual plus bank holiday, pro-rated), Adjustments, Taken
(annual and bank holiday costs), Remaining, TOIL remaining, Pending; team
totals and a practice total; "not set" for a missing allowance. File
names `leave-summary-2027.pdf` / `.xlsx`.

## 10. Notifications

Through `messaging.send`, plain text, one Outbox row each, failures
recorded on the row and never failing the write.

| When | To | Subject |
|---|---|---|
| A sickness entry raises the person's trigger level (book, edit, convert) | the person's managers | "[Name] has reached Trigger 2" |
| An end date appears or changes in HR's feed | the managers | "[Name] is leaving on 14 Oct 2026" |
| Seven days before the end date (daily) | the managers | "[Name] leaves in a week, on 14 Oct 2026" |
| The day after a long sickness or a flagged-return booking ends (daily) | the managers | "[Name] is back after 6 weeks of Sick leave" |
| A leave year ends with leave or TOIL left (daily, once per manager per run) | each manager, their people | "Year end: 7 people have leave or TOIL left" |
| A sickness entry joins on to another | the manager entering it | on screen, in the preview (NOTIF-12) |
| Annual leave converted to sickness | the person | the existing "Your time off has been changed" |

`manage.py daily_flags` runs `leavers.week_flags`, `returns.send`,
`yearend.open_due` and `yearend.notify`, prints the counts, and is run by
`shift-central-daily-flags.timer` every day at 08:25 (`Persistent=true`,
`RandomizedDelaySec=300`), the service unit a copy of the reminders'.
Each step catches and logs its own failure so one bad person does not
stop the others.

## 11. Audit and activity

- `leave.booking`: convert's steps with the note "converted to sickness";
  dates-only bookings with "dates only (past schedule)"; the trigger
  level reached, when it rose, in the booking's audit note ("Trigger 2
  reached").
- `leave.yearend`: the decision with the figures and the note, `object_id`
  the person's pk.
- `leave.adjustment`: the carry-over and TOIL-lost rows, as any adjustment.
- `payroll.payrollrun`: "Payroll for January 2027 marked sent, 59 people",
  practice-wide; the Activity log's `LEAVE_SETTING_MODELS` list gains
  `payroll.payrollrun` as "Payroll" and `PERSON_MODELS` gains
  `leave.yearend`.
- The leaver and return emails are not audited (nothing changed); the
  Outbox is their record.

## 12. Errors

- `convert` refuses with a `LeaveError` naming the reason; the dialog
  shows it in place of the button.
- `joins_on` is a warning, never a refusal; "Record separately" always
  works.
- A dates-only entry whose last day is today or later is refused ("the
  past schedule is for days already gone; book today's sickness as time
  off").
- `decide` refuses a carry or keep outside the range; the dialog shows
  the limit.
- `mark_sent` by a team manager is a 403; a month more than a year ahead
  or before 2026 a 400 (as the window's `parse_day` bounds); a missing or
  unreadable `month` is a 400 on Mark as sent (never a fallback: marking
  the wrong month sent is a wrong record) and falls back to this month on
  the report page only.
- The flags claim their row before sending (the leaver flag dates, a
  booking's `return_flagged_at`), so two runs alongside each other send one
  email between them; the trigger level is read inside the write's
  transaction.
- A PDF or Excel writer failure is a 500 logged with the class name only;
  the screen table still works.
- `daily_flags` steps never raise out of the command; each logs and
  continues; the command exits 0 so the timer does not go red for one
  bad row.

## 13. Testing

`tests/test_absence_*.py`, `tests/test_payroll_*.py`,
`tests/test_leave_flags.py`, `tests/test_leave_yearend.py`,
`tests/test_exports.py`, under the pinned clock, with the existing
factories plus `make_sick(person, first, last, dates_only=False)`.

- **Worked examples**, one test each: SICK-01 (window 2 Jan to 1 Jul, four
  instances, Trigger 2, the email once), SICK-02 (28 not long, 29 long,
  1 Jun to 1 Jul long; the return email with remaining leave), SICK-03
  (15 h back, one instance Wed–Thu, the head and tail bookings), SICK-04a
  and 04b (the warning, Extend gives one instance, Record separately two),
  KIT-01 (6 h on the payroll sheet as a KIT day column, balances
  untouched), LV-07b (the flag at date entered and a week before, 11.5 h
  over and 18.5 h remaining on the record and the payroll report), LV-15a
  (the flag offers 20 h; carry all gives 187.5), LV-15b (carry 10 gives
  182.5, 10 lost, logged), LV-16 (1 h TOIL offered; lose writes −1 h), LV-25
  (7.5 h unpaid on the payroll sheet).
- **Instances**: window arithmetic at month ends (31 Aug, 29 Feb), an
  entry straddling the window's start, dates-only counted, cancelled not
  counted, `joins_on` across a weekend, across a rota-less weekday, not
  across a worked day, with `exclude`.
- **Convert**: whole booking, head only, tail only, both; refusals; audit
  rows; costs restored to the second; the trigger check inside.
- **Past schedule**: dates-only writes no days and covers nothing; the
  statement and payroll ignore it; the feed serves it; the list and add
  per role; last day today refused.
- **Leavers**: `hr_sync` flags on a new date, re-flags on a change, resets
  on a clear, never twice for the same date; the week reminder; bookings
  past the end date listed; the profile line.
- **Returns**: due set, once per booking, the 14-day catch-up, dates-only
  and short sickness not due, a `flag_return` type due.
- **Year end**: `open_due` at a 1 January and a 1 April leave year start,
  missing statements open nothing, nothing-left rows closed at once, one
  email per manager, `decide` in each branch with the adjustments and
  refusals, the page per role, the long-absence marker.
- **Payroll**: each field from a built month (worked excluding covered and
  overtime, GP sessions and a GP on leave, paid leave by type and paid
  flag, unpaid, sickness, TOIL, leave days with halves, the type columns,
  starters and leavers), the future days from the rota, `mark_sent` and
  the snapshot, corrections after an edit, a person added and removed,
  role filtering, the Excel's sheets and cell types, formula-looking names
  cleaned, the Health line.
- **One-pagers**: the figures per practice, team and person; PDF and Excel
  produced and parseable (openpyxl reads back; the PDF starts with
  `%PDF` and names the range); role filtering.
- **Who's in today**: a GP on whole-day leave listed under off only; am
  leave leaves the pm session.
- **Views**: nav items per role; the leave report's new columns; the Add
  dialog's warning and radio; the booking view's convert item; CSV safety.
- **Deploy**: the timer and service units present and parseable
  (`test_deploy_units.py`), requirements pinned.
- **e2e**: a manager records sickness that joins on, chooses Extend, sees
  one entry; downloads the payroll Excel.

## 14. Deploy, operations and documentation

- `requirements.txt` gains `openpyxl` and `reportlab`, pinned; the
  frontend bundle is unchanged (nothing in the island changes).
- Migrations as section 2. `static/img/` gains the PNG logo for the PDF.
- Timer `shift-central-daily-flags.{service,timer}`; the upgrade checklist
  in `docs/admin/setup.md` adds pip install, migrate, collectstatic, copy
  the two units, `daemon-reload`, enable the timer, `check --deploy`,
  restart.
- `docs/admin/absence.md`, the manager's guide: recording sickness and
  what an instance is, the join-on warning, triggers and the email, long
  sickness and the return email, the past schedule section and how to
  enter 2026, converting holiday to sickness, the leaver flags and what
  to do with bookings after the leaving date, the year-end page and the
  three choices, the payroll report, what each column means, marking it
  sent and how corrections appear, the two one-pagers. `docs/admin/
  leave.md`'s "What is not here yet" shrinks accordingly;
  `docs/admin/people.md` notes the leaver line; `docs/admin/README.md`
  and the README's feature list gain the release.
- `docs/requirements/2026-10-29-proposed-amendments.md` gains a postscript:
  Q-11 answered (no reason recorded), GPs on the payroll report, and the
  one-pagers and year-end flag delivered ahead of the dates in point 3.
- The rota app is untouched by this release.

## Not done, on purpose

- Push notifications; the dashboard, shifts and staff-by-hour reports;
  open shifts; messages (spec 5).
- Pay rates, salary, payroll id and the budget report (FMS item 19,
  REP-08: could have).
- A payroll period other than the calendar month; statutory pay; SSP
  waiting days; the bureau's own format (it receives the sheet).
- A sickness reason or category (Q-11, answered no).
- Return-to-work interview records, fit notes, phased returns.
- Automatic cancelling or shortening of bookings after a leaving date:
  they are flagged and the manager decides.
- Pruning sync run rows (spec 3's revisit item): unchanged, revisited in
  spec 5 with the outbox.
- The adviser's answers to Q-01 to Q-03: the rules are built as the pack
  states them and each lives in one function.

## Revisit

- The join-on rule treats a weekday with no rota as a day not worked;
  if managers find it warns too often for weeks not yet rota'd, the rule
  could fall back to the person's days per week.
- "Leave days" counts a timed booking as half a day; the bureau may want
  the hours instead, which the Paid leave column already gives.
- Corrections look back twelve months; a correction to a month older than
  that would need the month chosen by hand.
- The payroll snapshot stores person pks; a person deleted from the
  database (never done by the app) would appear as "left" in corrections.
- The year-end flag assumes a person's leave year start does not change
  between the year ending and the flag opening; a change in that window
  opens the flag for the year as it then stands.
