# AMG Shift Central: leave — design

**Date:** 2026-10-31
**Status:** approved in conversation; spec for review
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
them, and 2027 for England and Wales (1 Jan, 2 Apr, 5 Apr, 3 May, 31 May,
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
- Repeating time off (FMS "Repeat" column shows "—").
- Maximum off at once, notice periods, multi-level approval, delegation,
  automatic approval.
- Importing FindMyShift bookings or balances.

## Revisit

- Match GPs in the rota app by HR employee id once the rota holds one (as
  the sessions feed).
- A GP who left within the sessions feed's eight-week window loses recent
  sessions on the next replace (grid spec's note); leave costing for GPs
  reads sessions, so a leaver's past GP leave costs stay as booked
  (BookingDay rows are not re-costed for GPs).
- Q-01 to Q-03 (the adviser's questions) may change rounding or carry-over
  rules; both live in one function each.
