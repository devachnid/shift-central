# AMG Shift Central: leave — design

**Date:** 2026-10-31
**Status:** approved in conversation; built and reviewed, with the deviations (the final review's under their own heading) recorded at the end
**Requirements:** `docs/requirements/` as amended by
`docs/requirements/2026-10-29-proposed-amendments.md`, all three amendments
and the two smaller points approved by the practice manager on 31 October
2026. This spec covers LEAVE-01 to 27 and 30, 31; REQ-01 to 14 (REQ-12 to
14 by email; push is spec 5's); NOTIF-01 (email half), NOTIF-09, NOTIF-11;
PAT-01, 03 to 06; PEOPLE-05, 07; ROTA-10; REP-02, REP-03, REP-10; ACC-05,
ACC-06's leave rows; FMS-00 for the time-off screens and FMS items 21, 22,
31 to 35, 37, 41, 42, 47; INT-02's leave half (as amended: the rota app
reads GP leave from here); MIG-03, MIG-04. It builds on the Foundation and
rota grid specs (`2026-10-29-foundation-design.md`,
`2026-10-29-rota-grid-design.md`), whose constraints, shell, people, access
rules, audit, grid, entries service, messaging and API conventions it
reuses unchanged unless this spec says so.

Leave is the third of five releases, and the reason the project exists:
allowances in use, costing from the rota, the pro-rata rules, bank
holidays, requests and approvals, balances and their statements, the year
planner and the leave report, every worked example in `06` as a test,
email notifications, and the GP leave feed the GP rota app reads instead
of FindMyShift. It is what staff use to request 2027 leave before
Christmas.

## Decisions made in conversation

| Decision | Rationale |
|---|---|
| **All fifteen leave types are bookable in this release.** Sickness, family leave, KIT days, jury service and unauthorised absence are recorded by managers now; instances, triggers, the join-on warning, long sickness and the TOIL year-end follow in spec 4 over data that already exists. | A sick day in early January needs somewhere to go; the booking machinery is the same for every type. |
| **Leave is its own app that covers grid days; balances are computed, never stored.** A booking's days mark the day's entries as covered (they stay in the table, leave the grid, the hours report and notify) or shorten the one entry a timed booking overlaps. Remaining = pro-rated allowance + adjustments − approved costs, and a statement lists the lines. | One answer to "is this person off on Tuesday" (the rota repo's own rule); REP-10 wants every figure explainable, and a leaving date from HR or a rota set on a placeholder day changes the answer without anything to re-post. Leave as a grid entry kind, and a posted ledger, were considered and rejected. |
| **The rota app's FindMyShift time-off reader is replaced by a Shift Central reader**, in the same PR that adds the feed here; FindMyShift's client, sync, settings and admin are removed. | Amendment 2 is approved and the FindMyShift feed never went live, so there is nothing to migrate and no reason to keep two readers. |
| **The practice manager's own leave is a per-person permission**, "own leave needs no approval", set on the Permissions page by an all-teams manager. | PEOPLE-07 names a role the system does not otherwise distinguish from the assistant managers; a flag is explicit and auditable. |
| **Bank holidays are an editable list under Settings**, seeded with England and Wales 2026 and 2027. | LEAVE-19 wants no automatic handling; a typed list the manager can see beats a feed nobody checks. |
| **A day with no rota is a placeholder only when the person's whole week has no rota.** | LEAVE-06 says "a day the rota has not yet been set"; a blank day in a week that has shifts is a day off and costs nothing (LV-03's Wednesday). The rule is explainable on the statement. |
| **Minutes and seconds internally, hours and minutes on screen, "½" for a half-minute.** | LEAVE-04 and Q-08 as proposed; costs are stored in seconds so a half day of an odd-minute shift (LV-04b) is exact. |
| **The LEAVE-12 total is capped at the larger full-year allowance.** | The approved smaller point; it also makes LEAVE-13 hold for the 53-week whole year without a special case. |
| **Email only; push waits for spec 5.** | NOTIF-01 wants both; the phone app is spec 5's and the sender exists now. |

## Global constraints

Inherited from the Foundation and grid specs. In addition:

- Every write goes through `leave/services/`; views never touch models.
  Every service writes audit rows through `audit.record_as` under
  `leave.booking`, `leave.adjustment` or `people.allowance`, with the
  person's pk as `object_id`, so the Activity log's person filter finds
  them.
- Secrets from the environment only. Log lines, `Outbox.error`,
  `SyncRun.message` and the GP leave feed never carry a description, a
  note or a reason. The feed carries emails because that is the match key,
  as the sessions feed does.
- Balances are never stored. Any screen that shows a figure gets it from
  `leave/services/balances.py`, and the statement explains it.
- Times and dates are Europe/London; "today" is `timezone.localdate()`.

## 1. Architecture

A new app, `leave`, beside `people`, `shifts` and `messaging`:

```
leave/
  models/        types.py booking.py adjustment.py blackout.py bank_holiday.py setting.py
  services/      hours.py (display) years.py prorata.py costing.py balances.py
                 bookings.py cancel.py adjustments.py bank_holidays.py blackouts.py
                 types.py settings.py notify.py reminders.py feed.py common.py
  views/         list.py request.py approve.py statement.py planner.py report.py
                 bank_holidays.py blackouts.py settings.py api.py
  forms.py admin.py urls.py
  management/commands/leave_reminders.py
templates/leave/ ...
```

`shifts` gains `Entry.covered_by`, a `leave` block in the window payload,
the "Time off…" menu items in the island and a leave tile; `people` gains
`Allowance.from_day`, `Allowance.weekly_hours`, `Allowance.days_per_week`,
`Person.leave_year_start`, `Person.own_leave_without_approval` and the
Permissions tick box. The island's change is small: draw the tile, treat
the cell as read-only, add two menu items.

`shifts.services.entries` calls into `leave.services.costing` on a write to
a covered day (section 4). `leave` imports from `shifts` for entries and GP
sessions. No other cross-app import.

## 2. Data model

**`LeaveType`** — `name` (unique), `colour`, `draws_from` (`annual`,
`bank_holiday`, `toil`, `none`), `requestable`, `paid_choice`,
`default_paid` (true unless the type is Unpaid leave), `on_payroll`
(`always`, `if_unpaid`, `leavers`, `never`), `display_order`, `archived`.
Seeded by migration with the fifteen rows of LEAVE-25 in its order:

| Name | draws_from | requestable | paid_choice | on_payroll |
|---|---|---|---|---|
| Holiday | annual | yes | no | leavers |
| Bank holiday | bank_holiday | no | no | never |
| TOIL | toil | yes | no | never |
| Sick leave | none | no | no | always |
| Training | none | yes | no | never |
| Maternity | none | no | no | always |
| Paternity | none | no | no | always |
| Adoption / shared parental | none | no | no | always |
| KIT day | none | no | no | always |
| Dependants' leave | none | no | yes | if_unpaid |
| Compassionate | none | yes | yes | if_unpaid |
| Authorised absence | none | yes | yes | if_unpaid |
| Unpaid leave | none | yes | no (always unpaid) | always |
| Unauthorised absence | none | no | no | always |
| Jury service | none | no | no | always |

Managers edit names, colours, order and the requestable and paid-choice
flags, and archive types; `draws_from` and `on_payroll` are fixed on the
seeded rows (they decide the arithmetic and spec 4's report) and chosen
once when a manager adds a type. An archived type is not offered but its
bookings stand.

**`Booking`** — `person`, `type`, `description` (blank means the type's
name; LEAVE-26), `first_day`, `last_day`, `part` (`whole`, `am`, `pm`,
`times`), `start`, `finish` (times only), `paid` (null when the type has no
choice), `status` (`pending`, `approved`, `declined`, `cancel_requested`,
`cancelled`), `requested_by`, `requested_at`, `decided_by`, `decided_at`,
`cancel_requested_at`, `cancel_decided_by`, `cancel_decided_at`,
`staff_note`, `manager_note`, `reminded_at`. Constraints: `first_day <=
last_day`; `part != whole` only when `first_day == last_day`; `times` has
`start < finish`, the others have neither. Index on `(person, first_day)`.

**`BookingDay`** — `booking`, `day` (unique together), `cost_seconds`,
`source` (`rota`, `placeholder`, `half`, `times`, `override`, `none`),
`account` (`annual`, `bank_holiday`, `toil`, `none`), `placeholder` (true
until re-costed from a rota), `override_by`, `override_note`,
`shortened_entry` (nullable FK to `shifts.Entry`), `original_start`,
`original_finish`. Rows exist only while the booking is approved or
cancel-requested; declined and cancelled bookings keep no days.

**`shifts.Entry.covered_by`** — nullable FK to `BookingDay`,
`on_delete=SET_NULL`, indexed. Covered entries are excluded by the window
payload, the hours report, notify's `day_text`, the download, who's in
today and the phone list; the admin shows them. A timed booking's shortened
entry is not covered: it stays on the grid with its new times.

**`Adjustment`** — `person`, `leave_year` (its first day), `account`
(`annual`, `bank_holiday`, `toil`), `seconds` (signed), `reason`
(required), `actor`, `at`. LEAVE-31's manual ledger; MIG-04's carry-over
from FindMyShift is one of these with the reason the pack prescribes.

**`Blackout`** — `first_day`, `last_day`, `teams` (many to many; none means
everyone), `note`. Staff cannot request leave on a day inside a blackout
that names their team or names none; managers book regardless.

**`BankHoliday`** — `day` (unique), `name`. Seeded: 2026 as `06` lists
them, and 2027 for England and Wales (1 Jan, 26 Mar, 29 Mar, 3 May, 31 May,
30 Aug, 27 Dec, 28 Dec). The list is a Settings page; a manager adds the
occasional extra day by hand (LEAVE-19).

**`LeaveSetting`** — one row: `reminder_working_days` (3). Read through
`settings.get()`, created on first read.

**`people.Allowance`** gains `from_day` (default the leave year's first
day), `weekly_hours` and `days_per_week` (nullable; null means the person's
current figures), and its unique constraint becomes `(person, leave_year,
from_day)`. The first row of a year is the contract at the year's start; a
later row is a dated hours change (PAT-06, LEAVE-12) carrying the new
full-year allowances and the new weekly hours and days. `profiles.
set_allowance` keeps its signature for the first row; a new
`profiles.add_hours_change(actor, person, from_day, weekly_hours,
days_per_week, annual_hours, bank_holiday_hours, note)` writes the later
row and, when `from_day` is today or past, copies the hours onto the
person. The HR sync run, which already runs every fifteen minutes, copies
a row's hours onto the person once its `from_day` has arrived, so a change
entered for a future date takes effect without a manager's visit.

**`people.Person`** gains `leave_year_start` (`CharField(5)`, `MM-DD`,
default `01-01`) and `own_leave_without_approval` (bool, default false).

Migrations: `leave/0001`, `people/0005` (allowance and person fields; a
data step sets `from_day` on existing rows), `shifts/0002`
(`covered_by`). All additive; existing data is untouched.

## 3. The arithmetic

`leave/services/hours.py`: `fmt(seconds)` renders "7 h 30 min", "0 min",
"2 h 37½ min" (a half-minute only ever arises from a half day of an
odd-minute shift), negative as "−1 h 30 min". Nothing on screen shows
decimals except the allowance boxes managers type (hours to two places, as
the Foundation has them).

### Leave years (`years.py`)

`year_of(person, day)` → the first day of the person's leave year
containing `day`, from `leave_year_start`. `years_for(person, today)` → the
current and next years, as the profile already offers. `Allowance.
leave_year` is that first day. Changing `leave_year_start` is refused while
the person has bookings or allowances in a year it would move; the form
says so.

### Pro-rata (`prorata.py`) — LEAVE-10 to 13

```
allowance(person, year, account) -> ProRata(total_seconds, lines, capped)
```

For each Allowance row of the year in `from_day` order, its period runs
from `from_day` to the day before the next row's `from_day` or the year's
last day, cut to `[person.start_date, person.end_date]` and to the year.
`weeks = ceil(days / 7)` (a part week counts whole, on both sides of a
change — the week of the change counts twice, the practice's deliberate
choice). `share = full ÷ 52 × weeks` as a Decimal with no intermediate
rounding. The total of the shares is rounded **once** to the nearest 0.5 h,
ties upward, then capped at the largest full-year figure among the rows
(the approved smaller point; it also gives LEAVE-13 exactly for the
53-week whole year). An empty period contributes nothing; a person with no
Allowance row for the year has no allowance and the statement says
"allowance not set". The same function serves `annual` and `bank_holiday`.
`lines` are the statement's per-row explanation: dates, weeks, figure,
share.

### Costing a day (`costing.py`) — LEAVE-05 to 09, 16, 23

```
rota_seconds(person, day) -> int   # shift entries not marked overtime, not already covered by another booking,
                                   # plus GpSession.HOURS per session that day
is_placeholder(person, day) -> bool   # the Monday-to-Sunday week holds no entry and no session for the person
placeholder_seconds(person, day) -> int   # weekly_hours ÷ days_per_week from the Allowance row in force that day,
                                          # else the person's; 0 with a "no hours set" flag when neither is set
cost(booking, day) -> (seconds, source, placeholder)
```

| part | cost | source |
|---|---|---|
| whole, week has a rota | `rota_seconds` (0 when the day has none — a day off) | `rota` or `none` |
| whole, week has no rota | `placeholder_seconds` | `placeholder`, flagged |
| am / pm | half of the whole-day figure above, exact | `half` (flagged if from a placeholder) |
| times | `finish − start` | `times` |

A GP's day is their sessions at 4 h 10 min each (LV-19); GPs have no
placeholder (their sessions come from the rota app) and a GP day with no
session costs nothing. Overtime entries never count (LV-23). A manager's
override replaces the figure and sets `source = override` with the note;
an overridden day is never re-costed.

**Account.** A day draws on the type's `draws_from`, except that a day
listed in `BankHoliday` inside a Holiday booking draws on `bank_holiday`
(LEAVE-18, LV-12). A Bank holiday booking is a manager's whole-day booking
of the Bank holiday type with the hours typed, so its day's `source` is
`override` with the note "bank holiday"; the suggestion offered is the most
common `rota_seconds` on that weekday over the previous four weeks (ties:
the largest), "0" when none (LV-13).

### Balances (`balances.py`) — LEAVE-17, 20 to 24

```
statement(person, year) -> Statement
```

with, all in seconds:

- `annual_allowance`, `bank_holiday_allowance` — pro-rata.
- `adjustments` by account.
- `taken` by account — the sum of `cost_seconds` of BookingDay rows whose
  booking is approved or cancel-requested, by `account`.
- `pending` by account — the costs a pending request would have, computed
  on the fly from its days (a pending booking has no BookingDay rows).
- `bank_holiday_balance = bank_holiday_allowance + adjustments[bh] −
  taken[bh]` — the deficit or credit that moves into annual leave.
- `annual_remaining = annual_allowance + adjustments[annual] −
  taken[annual] + bank_holiday_balance` — the combined figure (LEAVE-17).
- `annual_available = annual_remaining − pending[annual] − pending[bh]`.
- `toil_earned` — hours of entries marked overtime-TOIL dated up to today
  (whatever the year; TOIL does not reset), `toil_remaining = toil_earned +
  adjustments[toil] − taken[toil]`, `toil_available` likewise.
- `lines` — the ordered explanation the statement page prints.

A staff request is refused when its cost exceeds `available` on its
account; a manager's booking is not, and the remaining figure goes
negative (LV-24). Types drawing on `none` cost their hours for the record
and the payroll report (spec 4) but touch no balance (LV-25).

### Re-costing — LEAVE-06

`costing.recost(booking_day)` recomputes a whole-day booking's day from the
current entries when its `source` is `rota`, `placeholder` or `none` (never
`half`, `times`, `override`), updates `cost_seconds`, `source` and
`placeholder`, covers the day's entries, and returns whether the figure
changed. It is called from `entries._write` after any write to a day that
has a BookingDay (section 4) and from `bookings.approve`. A change on a
day that was a placeholder, or any change to an approved day's cost,
raises the NOTIF-09 email and a Health card line.

## 4. The booking lifecycle

All in `leave/services/bookings.py` and `cancel.py`, each in one
transaction, each audited with `record_as(actor, "leave.booking",
person.pk, {...})`.

**Permissions.** `may_request(user, person)`: the user is the person.
`may_book(user, person)`: `access.can_manage(user, person)`, or the user
is the person and has `own_leave_without_approval`. `may_decide(user,
booking)`: `access.can_manage(user, booking.person)` — never self,
whatever the flag. `may_view(user, booking)`: anyone signed in sees type,
dates and part of an approved or pending booking; description, paid flag,
notes and costs are the person's own and their managers' (ACC-05).

**`request(user, person, type, first, last, part, start, finish,
description, paid, note)`** — staff. Checks: type is requestable and not
archived; dates within the current or next leave year; no overlap with the
person's approved, pending or cancel-requested bookings on any day; no day
inside a blackout for the person's team; cost (computed by section 3 for
each day) within `available` for the type's account. A failed check raises
`LeaveError(code, message)` the form shows; nothing is written. Writes the
`pending` booking and emails every manager who can manage the person
(REQ-12). Pending requests cover nothing and cost nothing until approved.

**`book(user, person, ...)`** — manager (or own-leave flag). Same shape,
no blackout or balance check, overlap still refused. Writes the booking as
`approved` with `decided_by = user` and applies it (below).

**`approve(user, booking, note)`** / **`decline(user, booking, note)`** —
`may_decide`; the booking must be pending. Approve re-runs the overlap
check (another booking may have landed), applies, emails the person
(REQ-14). Decline sets the status and emails the person. Both set
`decided_by`, `decided_at`, `manager_note`.

**Applying** an approval: for each day from `first_day` to `last_day`,
`cost()` → a `BookingDay`; then, for a whole or half day, every entry of
that day gets `covered_by` = the row; for `times`, the one shift entry
whose span contains `[start, finish]` is shortened: when the leave starts
at the shift's start the entry's `start` becomes `finish`, when it ends at
the shift's end the entry's `finish` becomes `start`, and when it falls in
the middle the entry keeps its start and its `finish` becomes the leave's
`start` (the remainder of the day is lost to the grid; a manager who wants
both halves shown adds the second shift); the original times go on the
day. A timed booking on a day with no containing shift is still booked and
costs its hours, with nothing to shorten. A `DayChange` is written for
each day whose text changes, so notify tells the person (ROTA-09). The
days' placeholder flags raise the NOTIF-09 email.

**`request_cancel(user, booking, note)`** — the person, on an approved
booking whose `last_day` is today or later; sets `cancel_requested` and
emails the managers. **`decide_cancel(user, booking, approve, note)`** —
`may_decide`; on approve, undo: entries uncovered, the shortened entry's
times restored, BookingDay rows deleted, DayChange rows written, status
`cancelled`; on refuse, back to `approved`. The person is emailed either
way (REQ-10). **`cancel(user, booking, note)`** — a manager cancels an
approved or pending booking directly, with the same undo; past days
included.

**`edit(user, booking, ...)`** — a manager changes dates, part, type,
description or paid flag of an approved booking: implemented as undo then
re-apply inside one transaction, so costs are recomputed and the audit row
shows before and after. Staff cannot edit; they cancel and request again.

**Overrides (`override_day`)** — a manager sets a day's `cost_seconds`
with a required note (LEAVE-07, 31); `source = override`.

**Adjustments (`adjustments.add`)** — a manager writes an `Adjustment`
with a required reason; shown on the statement and in the Activity log.

**Hours changes and balances (NOTIF-11, LEAVE-15).** `profiles.
add_hours_change` recomputes the person's statement afterwards and, when
`annual_remaining` is negative, emails the managers and adds a Health card
line. Nothing is blocked.

**Overlap with the entries service.** `entries._write(user, person, day,
items)` on a day that has a BookingDay: writes as now, then calls
`costing.recost`, which re-costs a whole day by section 3's rule, leaves a
half-day, timed or overridden day's cost alone, and covers the new entries
either way. `move` and `paste` skip a target day that has a
BookingDay and count it in `skipped`, as they skip unmanaged people. The
shift dialog on a covered day shows the leave and a link to it instead of
the form.

## 5. The grid and the island

**Window payload** gains, per row, `leave: {day: LeaveJson}` where
`LeaveJson = {id, type, colour, part, label}` and, when the viewer is the
person or a manager, `description`, `paid`, `cost` (seconds) and `status`
(`approved` or `pending`). Pending requests are shown hatched with the type
name so colleagues can see who has asked (ACC-06's "approved and pending
time off" row). Cancel-requested shows as approved. `visible_people` is
unchanged.

**Island.** A cell with `leave` draws a leave tile (type colour, label,
"½ am" / "½ pm" / "14:00–15:30" marker; description beneath for those who
may see it) above any remaining entries (a timed booking's shortened shift
stays). Such a cell is excluded from selection for paste, drag and typing
(the same `editable` filter as read-only rows, so the invariant "the
selection never holds a non-editable cell" stands); it can still be
focused and right-clicked. The right-click menu gains "Time off…" on any
editable cell (opens the Add time off dialog with person and day filled)
and, on a leave tile, "View time off" and, for managers, "Cancel time off"
(both server dialogs). The phone list and Who's in today show the type;
Who's in today's "off" list is now people with approved leave that day.

**Download and print** of the grid render the tile's label in the cell.

## 6. The screens

Server-rendered Django, through `modal.js` for pop-ups, phone-usable, in
the FindMyShift shapes of `03`. URLs under `/time-off/`, `/reports/leave/`
and `/settings/`.

**Navigation** (`ui/context_processors.py`): **Time off** after Rota with
children Requests (`/time-off/`), Year planner (`/time-off/planner/`) for
everyone, and Waiting for approval (`/time-off/approve/`), Bank holidays,
Blackouts for managers; **Reports** gains Leave; **Settings** appears for
managers with Leave types and Leave settings. The Rota flyout gains "Time
off…" for managers. The top bar's orange **Add** on the Time off page opens
Add time off (managers) or Request time off (staff).

**Time off list** (`/time-off/`): columns Staff, First day off, Last day
off, Days (calendar days in the booking), Type, Display (the coloured
label), Pay, Allowance used (sum of costs, managers and self only), Status;
edit / view / delete icons for managers, view for others. Default range:
the current leave year; filters by person, team, type, status and range;
CSV download for managers (through `csv_safe`). Staff see every approved
and pending booking with type only, and their own in full (ACC-05).

**Add time off** (manager pop-up, `/time-off/add/`): General: Staff member
(the manager's people), Type, Display (colour swatch and the overtypeable
description), First day off, Last day off, Whole day / Half day (am, pm) /
Times (start, finish). Advanced: Allowance used — one line per day with
the computed cost, editable (an edit becomes an override with a note
field), Paid / Unpaid where the type allows, Manager notes. The dialog
re-renders on change through `data-submit-on-change` with a `preview=1`
POST, showing each day's cost, the balance before and after, and warnings
(placeholder days, blackout, overlap, over balance). Button "Add
[type]". A manager booking for themselves without the own-leave flag is
told their request will wait for another manager, and the booking is made
pending.

**Request time off** (`/time-off/request/`, staff, a page not a pop-up so
it works on a phone): Type (requestable only), description, dates, part,
note; balance before and after; each day's cost; a request that fails a
check shows the reason in place of the Send button (REQ-02, 05, 08). "My
leave" (`/time-off/mine/`): the person's bookings and statement, with
"Request cancellation" on approved future bookings.

**Waiting for approval** (`/time-off/approve/`): pending requests and
cancellation requests for the manager's people, oldest first, with how
long they have waited; each opens a decision pop-up listing the days with
costs, the person's balance before and after, who else in the team is off
on those days, a note box, Approve and Decline.

**Statement** (profile → Pay & time off for managers; My leave for the
person): per leave year, the pro-rata lines, adjustments, each approved
booking with its days and costs, bank holiday allowance against bank
holidays taken and the resulting deficit or credit, TOIL earned, taken and
remaining, and the remaining figures; "Adjust…" (managers) opens the
Adjustment pop-up; "Add hours change…" (managers) opens the dated change
form (new weekly hours, days, both allowances, from date, reason).

**Year planner** (`/time-off/planner/`): months as rows, days across
aligned by weekday, weekends shaded, bank holidays marked, each approved
booking a coloured cell with the person's initials; filters by year, type
and team; pending hatched. Everyone, types only.

**Leave report** (`/reports/leave/`): per person for a range (default the
leave year): Allowance (annual plus bank holiday, pro-rated), Adjustments,
Days (calendar days booked in the range), Deducted, Remaining, TOIL
remaining; subtotal rows per team; CSV. Managers
see their people, staff their own row. The Instances column is spec 4's.

**Bank holidays** (`/time-off/bank-holidays/`): the list by year with add
and delete; "Add for everyone" for a chosen day lists every current
non-GP person with the suggested hours (section 3), each editable, with a
tick box, then "Add bank holiday for N people" books a Bank holiday day
for each ticked person (skipping anyone already booked that day, counted).
GPs are listed with 0 and unticked: the practice is closed and their
sessions are the rota app's.

**Blackouts** (`/time-off/blackouts/`), **Leave types**
(`/settings/leave-types/`) and **Leave settings** (`/settings/leave/`):
lists with add, edit and archive or delete pop-ups.

**Health card** gains, for the manager's people: requests waiting (with
the oldest's age), placeholder days to check, negative balances, and
people whose allowance for the current or next year is not set (already
there as "needs hours and allowances").

## 7. Notifications

Through `messaging.send(person, subject, body)`, plain text, one Outbox
row each, with an absolute link built from the request as notify does;
failures are recorded on the row and never fail the booking.

| When | To | Subject |
|---|---|---|
| Request or cancellation request made | every manager with `can_manage` over the person (deduplicated by user) | "[Name] has requested time off" / "…asked to cancel time off" |
| Approved / declined / cancellation decided | the person | "Your time off has been approved" etc. |
| A booking with placeholder days approved; a placeholder or approved day re-costed | the managers | "Leave cost to check for [Name]" |
| An hours change leaves a balance negative | the managers | "[Name]'s leave balance is negative" |
| Pending longer than `reminder_working_days` working days (Mon–Fri, bank holidays excluded) | the managers, once per request (`reminded_at`) | "Time off request still waiting" |

The reminder is `manage.py leave_reminders`, run by
`shift-central-leave-reminders.timer` each weekday at 08:20, like the
other timers. Mail not configured (`EMAIL_HOST` empty) records the Outbox
row as failed with "mail not configured" and the screens still work.

## 8. The GP leave feed and the rota app

**Shift Central serves** `GET /api/v1/leave?from=YYYY-MM-DD&to=YYYY-MM-DD`
in `leave/views/api.py`, behind `Authorization: Bearer <token>` against
`LEAVE_API_TOKENS` (comma-separated, from the environment), the rota app's
`api/auth.py` copied as the sessions feed copied it, with its rate limit;
`to` at most 1,100 days after `from`. The answer:

```json
{"from": "...", "to": "...", "generated_at": "...",
 "leave": [{"email": "a.gp@practice.nhs.uk", "first_day": "2027-03-10", "last_day": "2027-03-12",
            "part": "whole" | "am" | "pm", "type": "Holiday"}]}
```

Approved (and cancel-requested) bookings of people with `is_gp`, whose
days overlap the range; a `times` booking is reported as `am` when it ends
by 13:00, `pm` when it starts at or after 13:00, else `whole`. No
description, note, pk or cost. The response is never logged.

**The rota app** (`devachnid/rota`, one PR): `rota/services/shift_central/
{client,sync}.py` replace `rota/services/findmyshift/`, reading the feed
from `SHIFT_CENTRAL_URL` with `SHIFT_CENTRAL_TOKEN`, window a year back to
two years ahead, matching each record to a clinician by lowercased email
(unmatched counted, listed on the status page by email as the Health card
does here), writing `TimeOff` rows (unchanged model) with `reason` the
type name and `source_ids` the feed's `first_day`, replace-in-full as
today. `TimeOffMapping` keeps its shape; the help text and seeds name
Shift Central types (default → OTH; Holiday, Bank holiday → AL; Sick leave
→ SICK; a row each for TOIL and Training → OTH). `TimeOffSyncRun`'s
FindMyShift counters (`n_teams`, `n_approved`, `n_deduped`, `n_unlinked`)
become `n_records`, `n_matched`, `n_unmatched`, `n_outside`. Removed: the FindMyShift client, sync, `spans.py` (its
`Span` moves to `rota/services/time_off.py`), the `findmyshift_sync`
command and timer, the `FINDMYSHIFT_*` settings and the `rota.E007` check,
the inspect command, `docs/admin/findmyshift.md` (replaced by
`docs/admin/shift-central.md`), and the "from FindMyShift" wording in
tooltips and headers ("from Shift Central"). The sidebar entry becomes
"Time off from Shift Central". Timer `rota-shift-central.timer` at
`*:11/15:00`, offset from both apps' other timers.

## 9. Audit and activity

Every service writes `record_as(actor, "leave.booking", person.pk,
{"booking": (before, after)}, note)` where before and after are the
booking's one-line summary ("Holiday 10–12 Mar 2027, whole days, 22 h 30
min, approved"), and `leave.adjustment`, `people.allowance` for
adjustments and hours changes with the figures and the typed reason. The
Activity log's model list gains these labels; a person's history dialog
shows them. Overrides record the day, before and after seconds and the
note. The log is managers-only as the Activity log already is (LEAVE-31).

## 10. Errors

- A `LeaveError` from a service renders in the form it came from, next to
  the field where there is one; the request page shows it in place of the
  Send button.
- Overlap, blackout and balance refusals name the day or the figure.
- A booking on a person the user cannot manage is a 403; on a person who
  does not exist a 404; malformed dates a 400 on the API and a form error
  in dialogs.
- The feed answers 401 for a bad token, 400 for a bad range, as the
  sessions feed does.
- Mail failures never fail a booking; the Outbox row carries the class
  name only.
- `recost` on a day whose booking was cancelled between the read and the
  write does nothing (the FK is gone).

## 11. Testing

`tests/test_leave_*.py`, pytest with the existing factories plus
`make_booking`, `make_type`, `make_bank_holiday`.

- **Worked examples**: one test each, named `test_lv_01_full_time_whole_year`
  and so on, for LV-01, 02, 03, 04a, 04b, 05, 06a, 06b, 07a, 07b, 08a,
  08b, 11a, 12, 13, 14, 15a (the carry-over typed as an Adjustment, the
  flag itself being spec 4's), 15b (likewise), 16 (balance after each
  event; the year-end flag spec 4's), 19, 20, 21 (as written, unconfirmed:
  the test fixes a rota giving 65 h), 22, 23, 24, 25, KIT-01. Each asserts
  the exact seconds and the displayed string.
- **Pro-rata**: part weeks, the 53-week cap, no row, a row with a future
  `from_day`, start and end both inside the year, leave year override.
- **Costing**: each `part` × rota / no rota in a week with rota / empty
  week / GP sessions / overtime excluded / already-covered entries not
  double counted; the bank holiday account rule; suggestions.
- **Lifecycle**: every transition and refusal in section 4, covering and
  uncovering, shortening in each of the three positions and restoring,
  edit as undo and re-apply, recost from `entries._write`, move and paste
  skipping covered days, DayChange rows written, own-leave flag, a manager
  never approving their own.
- **Balances**: pending reduces available; manager overrides go negative;
  types drawing on nothing; TOIL earned up to today.
- **Views**: each screen per role (staff, team manager, all-teams), ACC-05
  on the list, planner and payload; CSV safety; the Permissions tick box
  all-teams-only.
- **Notifications**: each row of section 7, deduplicated recipients, the
  reminder command's working-day arithmetic and once-only.
- **Feed**: token, range cap, GP filter, parts, no description in the
  body.
- **Island**: vitest for the leave tile's label and the read-only cell;
  one e2e: book from the grid menu, see the tile, cancel, see the shift
  back.
- **Rota app**: the sync against a fixture (match, unmatched, replace in
  full, parts), the removed settings gone, `check --deploy` clean.

## 12. Deploy, operations and documentation

- `requirements.txt` unchanged. Migrations as section 2. `LEAVE_API_TOKENS`
  in `/etc/shift-central.env`; `SHIFT_CENTRAL_URL` and
  `SHIFT_CENTRAL_TOKEN` in `/etc/rota.env`, `FINDMYSHIFT_*` removed.
- Timers: `shift-central-leave-reminders.{service,timer}`; in the rota,
  `rota-shift-central.{service,timer}` replacing `rota-findmyshift.*`.
- `docs/admin/setup.md` upgrade checklist extended; `docs/admin/leave.md`
  (the manager's guide: booking, approving, bank holidays, hours changes,
  adjustments, reading a statement); `docs/admin/people.md` for the new
  profile and permission fields; the README's feature list; the rota's
  `docs/admin/shift-central.md`.
- `docs/requirements/2026-10-29-proposed-amendments.md` status line set to
  "approved by the practice manager, 31 October 2026"; `12`'s Q-08 and the
  LEAVE-12 point answered in a postscript.

## Not done, on purpose

- Sickness instances, triggers, the join-on warning, long sickness, the
  return flag and the past-schedule section (spec 4).
- Converting annual leave to sickness (LEAVE-28) and the long-absence rules
  (LEAVE-29): spec 4, with the adviser's answers.
- Year-end carry-over flag, leaver flags, the payroll report and
  one-pagers (spec 4). MIG-04's typed carry-over is an Adjustment here.
- Push notifications; the leave one-pager; messages (spec 5).
- Repeating time off (the Time off list has no Repeat column).
- Maximum off at once, notice periods, multi-level approval, delegation,
  automatic approval.
- Importing FindMyShift bookings or balances.

## Revisit

- Match GPs in the rota app by HR employee id once the rota holds one (as
  the sessions feed).
- A GP who left within the sessions feed's eight-week window loses recent
  sessions on the next replace (grid spec's note); leave costing for GPs
  reads sessions, so a leaver's past GP leave costs stay as booked. A GP's day is re-costed only when a
  rota write touches it, as when a manager sets the shift behind the leave; a change to the GP's sessions
  alone does not re-cost it.
- Q-01 to Q-03 (the adviser's questions) may change rounding or carry-over
  rules; both live in one function each.
- GP sessions are not covered by leave. They are the rota app's, so on Who's in today a GP on leave still
  appears at their session's site as well as under "off"; to settle with the rota app in spec 4.
- Approved bookings that run past a person's HR finish date still count in their balance and, for a GP,
  stay in the feed. Whether to flag or cancel them belongs with the leaver's window in spec 4.
- Sync run rows are never pruned. The rota app writes one for every fifteen-minute read of the feed (about
  35,000 a year), each holding the addresses it could not match, and this app's own sync runs are kept
  the same way.

## Deviations recorded during the build

**31 October 2026.** Where the build departed from, or settled something this spec left open, it is
recorded here, grouped by the task in which it was decided, so that the spec and the code can be read
together. Where this section and the sections above disagree, this section describes what was built.
Where a ruling was later refined, the final behaviour is given with the refinement. Tasks 11 and 12 were
built in the GP rota app's repository (`devachnid/rota`). The review of the whole branch, last, made the
decisions under "Final review". The manager's guide (`docs/admin/leave.md`)
describes the finished behaviour.

### Before the build (the plan's pre-flight)

1. **The bank holiday suggestion looks at the holiday's own previous four weeks, not at today.** The spec
   said "the previous four weeks"; the plan fixed it as the four weeks before the bank holiday itself, so
   `costing.suggestion` takes a person and a day and no "today". A figure a manager types for a bank
   holiday is always stored as an override, even when it equals what the rota would give.
2. **A leave type's `archived` flag is among the fields a manager can edit,** so a type can be archived and
   restored from the same dialog.
3. **Date boxes are drawn and read as `YYYY-MM-DD`.** With the en-gb locale a date input otherwise shows
   day-first text the browser's date control rejects, so every date widget carries an explicit format.
4. **The Add time off preview helper takes an optional person,** because the staff request form has no
   person field and reuses it.
5. **The plan's test details were corrected before any code was written:** the suggestion tests lay out the
   rota one to four weeks before the bank holiday (the May 2027 bank holiday test too); the half day of an
   odd-minute shift in LV-04b is pinned at 9,450 s; the balance test's −225 h adjustment leaves 7.5 h
   available and `describe()` is checked for its format; the list tests look for table-cell markers rather than
   words that filters also print; the request page's Send button carries a marker the test looks for; and the
   rota app's sync fixture counts six records, two matched clinicians (one twice), one unmatched and one
   outside the window, giving three time-off rows.

### Task 1: the models, seeds, allowance periods and covered entries

6. **2027's Good Friday and Easter Monday are 26 and 29 March,** not 2 and 5 April as first written (Easter
   Sunday is 28 March 2027). The spec, plan, seed data and test were corrected; the dates are public.
7. **The seed data is its own migration.** The spec named three migrations (`leave/0001`, `people/0005`,
   `shifts/0002`); there are four for this task, because the fifteen leave types and the bank holidays are
   seeded by `leave/0002_seed`, and `LeaveType` carries a `seeded` flag marking the fifteen standard rows
   (the spec's "fixed on the seeded rows" needed something to ask). `Allowance.from_day` is not an editable
   form field; it is filled in when the row is saved.
8. **Two details of the plan's test file changed:** two unused imports were dropped, and each deliberate
   database error in the booking-constraint test is wrapped in its own transaction so the second can run.

### Task 2: pro-rata and dated hours changes

9. **The pro-rata total is summed exactly and rounded once.** Each row's share is worked out as an exact
   fraction (full year ÷ 52 × weeks), the shares are added, and only that total is rounded to the nearest
   half hour, ties upward. The two-decimal share shown on a statement line is for display; it is never
   added up. The function returns `seconds`, `lines`, `capped` and a `missing` flag for a year with no row.
10. **The HR sync applies due hours changes after the run is recorded as good,** in its own `try` inside a
    transaction. A failure is logged and added to the run's message but does not turn the run red, because
    the people feed itself worked.
11. **`add_hours_change` runs in one transaction,** and a test covers the sync hook.
12. **A dated change's hours are copied onto the person once.** `Allowance` gained `hours_applied`
    (migration `people/0006`; existing rows without hours are marked applied), set when
    `add_hours_change` copies the hours at once or when the sync copies them on the day. Only unapplied
    rows are considered, so a manager's later edit to the profile stands and is not re-asserted by the
    next sync. This is an extra column the spec did not list.
13. **A test needed a first-row allowance:** the "future change waits for its day" test sets a first row for
    the change's own year, because `add_hours_change` refuses a year with no first row.

### Task 3: costing and balances

14. **The plan's TOIL-earned tests use dates before today,** since TOIL earned counts shifts up to today and
    a shift in 2027 earned nothing on the day the test was written. Task 4's LV-16 example, which carries the
    same TOIL arithmetic, was moved to dates before today too (10 and 20 February 2026 instead of November 2026).
15. **TOIL is a running balance across leave years (LEAVE-24).** TOIL earned, TOIL adjustments and TOIL days
    taken are all counted over every year in the statement, not scoped to the year shown; annual leave and
    bank holiday taken and adjustments stay scoped to the year.
16. **The statement's lines gained two kinds the spec did not list:** one "Requested" line per waiting booking
    (its cost, shown but not subtracted from the remaining figure) and "available to request" lines for annual
    leave and for TOIL.
17. **Waiting TOIL is summed over every year** (`toil_pending`), and TOIL available is TOIL remaining less
    that, so the running figure and what is waiting are itemised on the same footing.
18. **An approved TOIL booking dated in the future reduces TOIL remaining now,** exactly as approved holiday
    reduces annual leave remaining. Item 17 is about TOIL still waiting for approval; this is TOIL already
    approved.

### Task 4: the booking lifecycle

19. **The decision email to the person carries the manager's note.** The spec forbids notes only in logs,
    outbox error text and the feed; the person is the one the note was written for. Subjects never carry it.
20. **Status and overlap checks run inside the transaction.** `approve`, `decline`, `request_cancel`,
    `decide_cancel`, `cancel` and `edit` re-read the booking inside their transaction and test its status there,
    so two managers deciding the same request cannot both succeed; `request`, `book` and `edit` check overlap
    inside it as well. In `request` the overlap error therefore comes after the blackout and balance errors.
21. **Every email from the booking services is sent after the transaction commits** (`transaction.on_commit`),
    never while the write lock is held and never for a write that rolls back.
22. **A grid rewrite re-links a timed day.** The entries service deletes and recreates a day's rows when
    written, which would orphan a timed booking's shortened or covered shift; `after_rota_write` finds the
    shift again (the uncovered one whose span equals the original less the leave, or the shift the leave filled)
    and re-links it. Re-costing also covers entries on an overridden whole day.
23. **`edit` carries overrides across and does less when it can.** For days that stay in the booking, a
    manager's typed figure, its note and who set it are kept; a change of only the display text or the paid
    flag does not undo and re-apply anything.
24. **`book` takes typed costs only from someone who can manage the person.** A manager booking their own leave
    under the own-leave flag is costed from the rota.
25. **`override_day` re-reads the day and its booking inside its transaction** and refuses a booking that is no
    longer live, so a stale object cannot resurrect a day of a cancelled booking.
26. **Test and example fixes in the plan:** the part-of-day text is built lazily; the examples' rota helper lays
    out the four weeks before 1 January so a suggestion for 1 January has data; and the past-cancel test uses a
    date the booking checks accept.

### Task 5: leave in the grid's server side

27. **Clear and move skip a source day that has leave, as well as a target day.** The spec said move and paste
    skip a *target* day with a booking. The build also skips a *source* day for clear and for cut or copy, and
    counts it in `skipped`, so the shifts hidden under leave are never deleted or carried away, and a cancelled
    booking restores them. Copy and cut snapshots leave out covered entries for the same reason.
28. **A blank write to a day of leave does nothing.** `entries._write` with no items on a covered day returns
    without change, so a blank typed cell cannot delete the hidden shift. Writing at least one item still replaces
    the hidden shift and re-costs the leave, as the spec says.
29. **Two Task 4 tests lost their "before" assertions** because the entries service now links timed days itself
    on every write; their final-state assertions stand.

### Task 6: the grid's island

30. **The approved-leave guard sits in `startEdit`** rather than only on double-click, so Add › Comment on a
    covered cell, and any other route to the editor, is also blocked. (The plan put it on double-click.)
31. **The right-click menu on a day of leave, final behaviour.** The menu opens for a viewer who can edit when
    the cell is selectable or holds leave. On a cell holding leave that is not selectable (approved leave, or
    any leave on a row the viewer cannot edit), the menu holds only the leave items: **View time off**, and
    **Cancel time off** where the row is editable, and on approved leave of an editable row the shift item
    that item 70 describes. Pending leave on an editable row keeps the normal items with
    the leave items first. A viewer who cannot edit gets no menu. The plan assumed the context-menu handler did
    not consult selectability; it did, and the first fix (leave items only on approved leave) was then refined
    to cover a row the viewer cannot edit. The leave items come from a pure `leaveMenuItems` function with its
    own unit test. Right-clicking such a cell also empties the selection (item 82).

### Task 7: the Time off screens

32. **The list defaults to the current leave year and the next,** not only the current one, because both can be
    booked. Row actions are text links (View, Edit, Cancel), not icons.
33. **The Edit dialog's preview costs the booking with its own covered shifts included** and credits what the
    booking already spends, so editing does not count it twice against the balance.
34. **The Edit dialog has no Manager notes box,** because `edit` does not save them. Add keeps it.
35. **Costs typed in Edit become overrides.** `bookings.edit` gained `costs`: after the booking is re-applied a
    typed figure wins over a kept override; on a change of label or paid flag only, typed figures become
    overrides on the existing days, and the audit shows "cost <day>: rota → override" even when the figure is
    unchanged. A stored override shows as the day's default in the preview ("set by a manager"), with the bank
    holiday allowance named first for a bank holiday day. A waiting request's Edit dialog shows no cost boxes,
    since its days do not exist until it is approved. Item 76 gives how Edit opens.
36. **Typed costs are gated by `may_decide`,** which is `can_manage` by definition, so no extra check was added.
37. **The list and CSV show no "Allowance used" for a waiting booking** (blank, not "0 min").
38. **Declined and cancelled bookings are listed when named in the Status filter,** only where the viewer has
    detail on the booking (their own, or their people's); colleagues never see them (ACC-06 lists approved and
    waiting leave only). Item 73 gives the rest of what a colleague sees.
39. **Smaller mechanics settled in the build:** the Add time off dialog redraws as a field changes, and its Save
    button saves rather than previews; My leave shows the statement on the page; and a manager booking their own
    leave without the flag sees "Your own leave will wait for another manager to approve it".

### Task 8: the statement, Adjust and Add hours change

40. **The statement shows the current leave year, or the next when only it has an allowance,** unless a year is
    chosen. A year picker works inside a pop-up through a new `data-dialog-get` handler in `modal.js`.
41. **Small additions:** `years.label` names a leave year for the picker; the Adjust form checks that its leave
    year is one of the person's two; the leave year start on the hours form is optional.
42. **A leave year that does not start on 1 January is handled in the profile.** The allowance boxes are keyed
    by `years_for(person)` (so a 1 April person files "from 1 Apr 2027"), a start change is applied first in the
    same save, and `profiles.leave_years()` was deleted. The Health card's "needs hours and allowances" test
    became "an allowance row whose year falls within a year either side of today", which does not depend on the
    start day.
43. **The negative-balance email on an hours change is sent by the Add hours change dialog,** after the change
    is saved, not by `add_hours_change` as the spec put it. It is tested to fire when the figure is negative, not
    when positive, and not when the change is refused.

### Task 9: the remaining screens

44. **The leave report's default range is the viewer's current leave year,** not the calendar year. One function
    builds the rows for the page and the CSV, and shows "not set" rather than 0 where a person has no allowance.
    Its Remaining is the statement figure for the leave year the range starts in.
45. **The planner hatches waiting requests,** as the spec says, rather than fading them, and its type filter
    includes archived types.
46. **The Health card's counts, as built.** *Requests waiting* does not count the viewing manager's own
    requests (another manager decides those) and measures the oldest wait from the cancellation request's time
    when there is one. *Leave costs to check* shows the real count beside the first five days, then "and N more".
    *Negative leave balances* looks at the current and the next leave year (a manager may overbook the next year),
    skipping a year with no allowance, and never lists a GP, whatever their balance (a GP has no hours here, and
    *Needs hours and allowances* leaves GPs out for the same reason); it filters to people with leave taken or
    hours taken away before the slow statement is worked out.
47. **A date outside the supported calendar (2000 to 2100) no longer errors in the report or the list.** The
    view treats it as not given and falls back to the default range: the report's is the viewer's current
    leave year, the list's is the current leave year and the next.
48. **A type with no paid/unpaid choice records itself as unpaid only when its default is unpaid;** otherwise it has
    no paid flag. The rule is keyed to the flag, not to the name "Unpaid leave", so renaming the type is safe.
49. **The Bank holiday type is found by what it is** (the seeded row that draws on the bank holiday account), not
    by name, so a manager can rename it.
50. **A type's source and payroll treatment lock once it has bookings.** What a type takes its days from and how
    it reaches payroll are chosen once and then fixed as soon as any booking (waiting ones included) uses it, in
    the service as well as the form, which is wider than the spec's "fixed on the seeded rows".
51. **Practice-wide leave writes appear in the Activity log:** bank holidays, blackouts, leave types and the leave
    setting are audited and listed as departments are. This adds to section 9.
52. **The settings pages need a manager,** as the spec says; a team manager can change them, as for departments.
53. **Blackout dialogs answer with a redirect, and a "refresh" on a page that is not the grid reloads the page.**
    The blackout dialog is on a list page where nothing listens for the grid's refresh event, so it redirects. For
    the Adjust and Add hours change dialogs, `modal.js` turns a refresh request into a page reload when there is
    no rota grid, and a `data-dialog-refresh` marker reloads when the dialog is closed (by a fresh visit to the
    address: item 90).
54. **"Add for everyone" is hardened.** An unknown or malformed day is a 404; a figure that is not hours or is
    over 24 h is an error on its row; a day that falls outside a person's two leave years, or an archived Bank
    holiday type, is reported by name; a duplicate bank holiday day is a form error; deleting a bank holiday is a
    POST; an inactive team stays ticked when a blackout is edited.
55. **The reminder setting is 1 to 30 working days,** and saving it is audited.
56. **The team-manager report scope** (their people and themselves) and the CSV are tested.
57. **Smaller decisions about addresses and pages:** the fixed addresses (planner, approve, bank holidays) are
    matched before the ones that take a booking's number; pages carry no inline script, as the
    Content-Security-Policy requires; and no log line carries a record's values.
58. **The Health test pins today's date** so "this leave year" does not depend on the clock.

### Task 10: the GP leave feed

59. **The feed names the type of every approved booking,** as section 8 requires; the rota app maps names to its
    own categories. A per-type "do not export" flag is a policy question left to spec 4.
60. **Leavers are not filtered by finish date in the feed;** the rota app's own active flag decides, until spec 4
    settles how a GP leaver's window is treated.
61. **The README's `TRUSTED_PROXY_IPS` row says the rate limit is per client address,** so if the proxy's address
    is not trusted every caller shares one bucket. The limit is counted per gunicorn worker (the default cache is
    per process), so with two workers the effective limit can be up to twice `API_RATE_LIMIT_PER_MINUTE`; the
    README says so.
62. **Twelve more tests than the plan** pin the range limits, the timed-booking parts, the five fields only,
    GP-only, status filtering, the 405 and 401 cases, the rate limit and the logs. The README's feed section sits
    before "The tunnel", because there is no earlier GP-feed section on the serving side. Only GET is accepted;
    HEAD and OPTIONS answer 405.

### Tasks 11 and 12: the GP rota app (repository `devachnid/rota`)

63. **"Without a login email" means an active, non-locum clinician with no login.** A login's email is required and
    unique in the rota app, so the count, the lists and the link on the admin dashboard agree; a login created
    outside the app with a blank email would be treated as linked (and could not be matched).
64. **A token with a space or line break is treated as not set,** and a malformed token in the client gives a
    fixed message with no token text; the dashboard and the status page read "configured" from the same function; and
    the status page's *Refresh now* message pluralises its counts.
65. **Advisory findings from the rota pull request's automated review** (a development-key helper, an unbounded
    read, replace-in-full deletion, coupling) were answered and not acted on: they match the sessions client or
    were pre-existing.
66. **The first rota task left a few things for the second,** as the plan allowed: temporary "unlinked" helpers
    (moved to `links.py`), eighteen tests that still used FindMyShift wording (reworked or deleted), and an admin
    status page reading removed counters (rewritten). Three operations-hardening tests were rewritten for the
    Shift Central settings, the deploy unit list was reordered, and the rota guide gained a "Moving from
    FindMyShift" note for a box that ran the old reader.

### Task 13: the manager's guide and its review

67. **The Add time off dialog's layout.** The per-day *Allowance used* table sits in the main part of the dialog
    under the dates, not under Advanced; Advanced holds *Paid or unpaid* (where the type allows it) and *Manager
    notes*; the button reads "Add time off", not "Add [type]".
68. **The navigation and the Health card.** Under Time off the children are Requests, **My leave** and Year planner
    for everyone, and Waiting for approval, Bank holidays and Blackouts for managers (the spec did not list My
    leave in the menu). The Health card's lines are named *Requests waiting*, *Leave costs to check* (the spec's
    "placeholder days to check") and *Negative leave balances*.
69. **A person cannot withdraw a waiting request.** Only approved leave can be cancelled by the person (as a
    cancellation request); a manager declines or cancels a waiting one.

70. **LEAVE-06 is reachable through the shift dialog and a leave-cell menu item.** The spec re-costs a
    placeholder-costed day when the rota for that day is written, but as first built nothing in the interface could
    write to a day of approved leave (the cell is read-only, paste, move and clear skip it, and the shift dialog
    showed only "is off" with a link), so a placeholder cost and its Health line could clear only through the
    booking's Edit override. Two things were added.
    - The shift dialog on a day of approved whole-day or half-day leave shows the normal shift form, prefilled from
      the first shift the leave covers (otherwise empty), under a note that the person is off. On a whole day that
      has not been overridden the note says the shift set here is what they would have worked, sets the leave's
      cost and stays hidden on the grid; saving goes through the ordinary entries path, so the new shift is covered
      and the day is re-costed (source `rota`, no longer a placeholder). The "Leave cost to check" email goes to the
      managers whenever the day was a placeholder or its figure changed, so also when the shift confirms the same
      figure the average day gave. On a half day or an overridden day the note says the shift stays hidden and
      the cost is not changed; a half day's placeholder therefore clears only by typing the figure in Edit.
    - On a day of leave by the hour the shift is not hidden but shortened, so the dialog edits that shortened
      shift instead (item 75).
    - The grid menu on a cell of approved leave, on a row the viewer may edit, offers **Shift behind the leave…**
      (whole and half days) or **Edit the day's shift…** (leave by the hour), both opening the shift dialog, after
      View time off and Cancel time off (section 5 listed only the first two); pending leave is unchanged.
    Writing the person's other days of the week does not re-cost the day.

### Final review

These were decided when the whole branch was read against this spec, the requirements and the guides.

71. **The balance check pools annual leave with bank holidays and goes a leave year at a time.** The spec checked
    each account on its own against the first day's leave year. A bank holiday's allowance moves into annual
    leave, so a request that drew on both could pass each check and still take more than the one figure the
    statement shows. Now annual leave and bank holidays are added together and compared once against annual leave
    available, for each leave year the request touches, so a request over the end of a leave year is checked a year
    at a time (a year with no allowance has none). TOIL never resets and is one pool whatever the year. The refusal
    reads "This would take 37 h 30 min of annual leave (bank holidays included) and 25 h is available", naming
    the year when the request touches two. The previews on Add, Edit, Request and Decide show a balance line for
    each year, and a manager's own request is refused by the same check whatever the preview shows.
72. **Typed hours are strict and bounded.** Every box that takes hours (a day's *Allowance used*, Adjust, Add for
    everyone) accepts `7:30` (up to three digits of hours, minutes 00 to 59) or decimal hours with an optional
    "h" (`7.5`, `7.5 h`). Anything else, such as `7h30`, `1e3` or `7,5`, is a form error and is never guessed at.
    A day's figure is at most 24 hours, an adjustment at most 2,000 hours either way, and a figure too large to
    read is a form error rather than a server error.
73. **The Time off list, its CSV and the View dialog show colleagues only what the grid would.** The spec had every
    member of staff see every approved and waiting booking by type. Now a person sees colleagues' rows only for the
    people the grid shows them (*Show to other staff*, *Can see other staff*), managers see everyone on the rota
    with their own people in full and the others by type, and the CSV carries the same rows as the screen. The
    View dialog answers "not found" to a colleague for a declined or cancelled booking and for a person the grid
    hides, never shows a colleague who decided, and shows a cancellation request as Approved, as the list and the
    CSV do (section 5). Filtering by Cancellation requested shows a colleague only their own rows and their
    people's. This extends item 38.
74. **Nobody can tick *Own leave needs no approval* on themselves.** The spec left it to an all-teams manager,
    which allowed the practice manager to tick it on their own profile and so approve their own leave. The
    service now refuses it, and one's own Permissions dialog shows the value and says another all-teams manager
    sets it.
75. **A shift set on a day of timed leave is cut around the leave, and the shift dialog edits it.** When a shift is
    written on a day that already has timed leave (in a week with no shifts, or through the dialog), it is cut
    around the leave as booking the leave would have cut it: shortened with its original times remembered, or
    hidden when the leave is the whole of it. The dialog on such a day edits the visible shortened shift ("Update
    shift") under a note giving the leave's times, so saving 09:00 to 17:00 around leave from 14:00 to 15:30 leaves
    09:00 to 14:00 showing and 09:00 to 17:00 remembered for when the leave is cancelled. Where the leave is the
    whole of a shift nothing is showing, so the dialog says "Add shift", and a shift added there stays visible. The
    grid menu words it **Edit the day's shift…**. This refines item 70 and replaces the note "stays hidden on the
    grid" for leave by the hour.
76. **Edit opens with the costs, works the paid flag out again when the type changes, and can edit an archived
    type's booking.** Items 34 and 35 left Edit's cost boxes empty until a change was made. Now Edit opens bound
    to the booking: each day's cost, a figure a manager typed earlier in its box (as hours and minutes), and the
    balance line. A waiting request's Edit shows its costs without boxes and says "Costs can be set once the
    request is approved". Changing the type works the paid flag out as booking would (the manager's choice or
    the type's default where the type offers one, otherwise the type's own setting; "—" means the type's
    default), where it had been kept or cleared. A booking whose type has since been archived keeps that type on
    offer in Edit, though Add does not offer it. Add shows no cost boxes when the staff member is the manager
    themselves, since their own leave is costed from the rota (item 24).
77. **Leave that draws on no allowance has its own table on the statement.** Sick leave, Training and the other
    types that take their days from nothing had appeared among the annual leave deductions and the "Requested"
    lines. They now appear in a second table headed "Leave that draws on no allowance", approved and requested,
    in no figure.
78. **Who is emailed, and the links.** The managers emailed are those who can manage the person, can sign in and
    have not left; a manager who has not started or has no login gets nothing. A link in an email sent from a
    rota write is a full address, from the first trusted origin when no page made the request. A cancellation
    request on a booking that was already reminded is reminded in its own right.
79. **Hours changes start within the person's two leave years, and a back-dated change does not undo a later one.**
    As an adjustment must, an hours change must start in the person's current or next leave year ("An hours change
    can start in this leave year or the next"). A change already due is copied onto the person only when no later
    change is already in force; otherwise it is recorded, works out its own days, and is marked copied so the sync
    never copies it. Posting the same change twice says "There is already a change from that day" and is not a
    server error. This refines items 12 and 43.
80. **The leave admin is read-only, and a booking cannot be deleted there.** Leave types, bank holidays and the
    leave setting join the bookings, days, adjustments and blackouts as view-only in the Django admin, because an
    edit there skipped the audit and the lock on a type's account. A booking cannot be deleted there, as that
    skipped the undo and the audit and never put back a shift the leave had shortened; it is cancelled on the
    Time off pages.
81. **Find and Replace skips a day of leave, and a paste counts leave days apart from rows.** Find and Replace
    leaves a day of approved leave alone, as Clear and Move do (item 27). A paste or a template reports
    "1 row and 2 leave days couldn't be pasted onto.": rows the manager may not edit and days of approved leave
    are counted separately, and the answer to a paste carries the leave days as part of its skipped total.
82. **On the grid, right-click on leave empties the selection, and leave tiles are coloured for contrast.**
    Right-clicking a day of approved leave empties the selection and moves focus there, as a left click does, so
    that Delete or Cut afterwards cannot act on an earlier selection. Approved leave is filled in the type's colour
    with white or dark text, whichever contrasts more; waiting leave is outlined with a thick edge in the type's
    colour and dark text; and today's column keeps its highlight.
83. **A typed figure's audit line says where the old figure came from.** It reads "7 h 30 min (average day)" to
    "7 h 30 min (override)", for example, where it had always said "(rota)".
84. **Where a refusal shows, and what the blackout message says.** Section 6 put every refusal in place of the
    Send button, and section 10 had the overlap, blackout and balance refusals name the day or the figure. As built,
    dates, an overlap (which names the booking already there) and a blackout show a red message at the top of
    the request page; only too little available shows where the button would be, with the balance line giving
    the figure. The blackout message, "Leave cannot be requested on one of these days (a blackout period)",
    names no day (a request that reached the service some other way is refused naming the day). A refusal from
    a service in any dialog is shown at the top of the dialog, never beside a field.
85. **The practice-wide settings are open to any manager.** Item 52 is read in full: a team manager can add a
    blackout for any team or for everyone, add and delete a bank holiday, and edit leave types and the leave
    setting, and each holds for the whole practice. "Add for everyone" lists only the people the manager can
    manage.
86. **The person reads adjustment reasons and override notes.** The statement shows an adjustment's reason, and
    the View dialog and My leave show an override's note and the Manager notes, to the person they are about.
    The requirements mark the balance-change log as hidden from the person (ACC-06), but the statement is the
    person's own record (REP-10). The guide warns managers to write them for the person to read.
87. **Approving a cancellation undoes the whole booking.** The spec's cancellation approval, like a manager's
    cancel, undoes every day, those already taken included, and the build keeps that. To end a booking early
    a manager refuses the cancellation request and Edits the booking so that it ends on the last day taken; the
    guide says so.
88. **Small differences between the build and the spec's wording.** (a) There is no `cancel.py`: cancelling,
    the decision on a cancellation and editing are in `bookings.py`. (b) `people` and `shifts` read from `leave`
    in more places than section 1 allows (the profile's allowance years and its statement, the rule on moving a
    leave year, the Health card, the grid's window, Who's in today and the shift dialog). (c) Changing a leave
    year's start is refused once the person has any allowance or any waiting or approved booking, not only in a
    year it would move. (d) Add for everyone has the button "Add bank holiday for everyone ticked". (e) The grid's
    download writes a leave tile as the type's name with its part, and "(requested)" for waiting leave, not the
    tile's label. (f) Edit works on a waiting booking as well as an approved one. (g) TOIL earned leaves out a TOIL
    shift hidden under leave. (h) LV-15a and LV-15b share one test, the carry-over being a typed adjustment.
89. **Tests do not depend on today's date.** In the tests the clock is pinned to Monday 2 November 2026 at 09:00
    (Europe/London) and runs on from there. A test written on the 2026 to 2027 calendar, such as the worked
    examples and every 2027 booking, says so with a marker that sets the day it was written for, so moving
    the pinned day does not break them. The whole suite was run with the pin moved to June 2027 and to January
    2028, and passed each time.
90. **A page that a dialog refreshes is reloaded by visiting its address again.** A page that was itself the
    answer to a form post no longer makes the browser ask to resend the form when a dialog refreshes it. This
    refines item 53.
91. **The rota app's setup order, and the checks it keeps.** In the rota app's repository, the guide gives the
    order token, environment, the timer's units installed, migrate then restart, logins, the type mapping, the
    first sync, the timer; it names the real leave types (Holiday, Sick leave, TOIL, Training); and its README's
    move of an install that runs as root copies the timer too. The old FindMyShift design is marked superseded.
    `rota.E007` stays, as the check that the Shift Central address is https (section 8 listed it as removed
    with the FindMyShift settings). More tests pin the client's refusals (plain http with debug off, a
    redirect, a body that is not JSON, a body with no list) and that a login with a blank email matches
    no record.
