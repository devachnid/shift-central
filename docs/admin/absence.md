# Absence and payroll

**Where:** Time off (`/time-off/`) for recording sickness, with Past schedule and Year end under
it (managers); a booking's **Convert days to sickness…** link. Reports › Payroll, Sickness summary and
Leave summary (managers). Settings › Leave types for the two flags that make a type count as sickness or
flag a return. The Health card on the Staff list carries three new lines. Everything here is for
managers, except that a person sees their own sickness line on My leave and their statement.

## The mental model

**A sickness entry is a booking of Sick leave.** There is no separate sickness record. A manager
adds time off, chooses a leave type that *counts as sickness* (Sick leave, as supplied), and that booking is
the entry. It covers the grid, appears on the Time off list and the year planner, costs the days from the
rota and reaches the payroll report like any other leave. Staff cannot request Sick leave; a manager
records it.

**One entry is one instance.** An entry from its first day to its last is one instance of absence,
however many days it lasts. A week off and a single day off are one instance each. The manager decides
what is one entry and what is two, and the [join-on warning](#recording-sickness) helps them.

**Triggers count the last six months.** The system counts a person's instances in the **rolling six
months** to today: from the same day of the month six months back, plus one day, to today. On 1 July
that is 2 January to 1 July. An instance counts if **any** of its days falls inside that window. Three
instances is **Trigger 1**, four **Trigger 2**, five or more **Trigger 3+**. What the practice does at a
trigger is the practice's own business; the system tells the managers and shows the level.

**The system never stores a figure.** The instance count, the trigger level, "long sickness" and every
number on the payroll report and the two summaries are worked out each time from the bookings, so
correcting a date, cancelling an entry or letting the window move changes every answer without anything
being re-posted. The one exception is the snapshot taken when a payroll month is marked as sent, which
exists only so that later changes can be shown as corrections.

**No reason is recorded.** Reasons are health information the practice chose not to keep. The manager
note on a booking (managers see it, staff do not) stays the place for anything a manager wants to write
down.

## Recording sickness

**Where:** Time off › **Add time off +** (managers). Choose the person, **Sick leave**, and the first
and last days. The dialog previews as you type.

- **The days cost what the rota says**, as for any leave ([Leave](leave.md#what-a-day-costs)). A sick day with
  no rota is costed as an average day and the managers get the usual *Leave cost to check* email,
  because that figure reaches the payroll report.
- **The preview** shows the person's instances in the last six months *after* this entry, and the trigger
  it makes: "Instances in the last six months after this entry: 4 (Trigger 2)".
- **The join-on warning.** When the new entry starts or ends close to an earlier sickness entry of the
  same person, the dialog says *This joins on to Sick leave 19 Oct–23 Oct 2026* and offers two choices:
  **Extend that entry to …** (the default; one instance) or **Record as a separate instance**. The rule: the entry joins on
  when every day between the two is a day the person does not work. Dates that touch always join;
  so does a gap made only of a weekend, a part-timer's day off or a week with no rota. **A gap of more
  than seven calendar days never joins on**, whatever the rota says. The warning is advice, never a
  block: *Record as a separate instance* always works.
- **What Extend does.** The button reads **Extend the existing entry** and the existing booking's first
  or last day moves to cover the new days; the result is one entry and one instance. The existing entry keeps
  its own manager note and flags; anything typed for the new entry is not kept. **Extend joins entries of the
  same kind only.** If the earlier entry is a [past schedule](#the-past-schedule-section) one, Extend is not
  offered here: the warning says the entry "is recorded as a separate instance because the other entry is a
  past schedule entry", so the new days keep their hours and reach the payroll report. The past schedule's
  own dialog does the same the other way round ("…because the other entry has hours"), so typed history is
  never costed.
- **Long sickness** is an entry of **29 days or more**, first and last day counted (28 is not long, 29
  is). The dialog shows *This is long sickness (29 days or more): managers are emailed when [Name]
  returns*, the booking's view carries the same note, and see
  [Returning from a long absence](#returning-from-a-long-absence).
- **The trigger email.** When recording, editing or converting an entry makes the person reach a **higher** trigger
  level than before, every manager who can manage them is emailed: *[Name] has reached Trigger 2*,
  listing the instances in the window with their dates, with a link to the profile. It is sent
  after the entry is saved. Cancelling an entry can only lower a level and sends nothing. If a person falls to Trigger 1
  as the window moves and later climbs to Trigger 2 again, that is a new trigger and the managers are
  told again. Entries typed on the [past schedule](#the-past-schedule-section) never send it.
- **Editing the dates** of an entry is the ordinary **Edit** on the Time off list. The trigger check
  runs again. The join-on warning is shown but the choice is not offered, because the manager is already
  editing one entry; two entries that join on stay two instances unless the manager extends one and
  cancels the other.
- **Cancelling** an entry is the ordinary cancel: the record is kept and it stops counting.

**What colleagues see.** Only the type, "Sick leave", on the grid, the planner and Who's in today, as
for any leave. The person sees their own line on My leave and on their statement, *Sickness: 4 instances
in the last six months (Trigger 2)* or *Sickness: none in the last six months*. Managers see it on the
profile's Pay & time off tab, in the leave report's **Instances** and **Trigger** columns (blank for
someone with none; the instances are the rolling six months to the end of the range, or to today if the
range runs into the future), on the past schedule and on the sickness summary.

**Setting up a type.** Settings › Leave types has two ticks: **Counts as sickness (instances, triggers, the
sickness summary)** and **Email the managers when the person returns**. Sick leave has the first;
Maternity and Adoption / shared parental have the second. Any type, including one a manager adds, can
carry either.

## Converting holiday to sickness

A person who falls ill on a booked holiday has the sick days taken out of the holiday and their hours put
back (LEAVE-28).

**Where:** Time off › open the booking (**View**) › **Convert days to sickness…**. The link is offered
to managers on an **approved**, **whole-day** booking of a type that takes annual leave or the bank holiday
allowance (Holiday, Bank holiday). A waiting request, a cancel-requested booking, half days and
timed bookings are not converted, and the link is not offered on them.

The dialog asks for the **First sick day**, **Last sick day** (both start as the whole booking), **Record
as** (a sickness type) and **Manager notes**. Press **Convert to sickness**.

What happens, in one step:

- **The holiday is cut around the sick days.** If they are the whole booking, the holiday is cancelled
  (note "converted to sickness"). If they are at the start or the end, it is shortened. If they are in the
  middle, the holiday keeps its first part and the rest is booked again as a second holiday, with the
  same description and notes and any figures a manager had typed on those days.
- **The hours come back exactly as they were charged.** A Monday to Friday holiday of 37.5 h with
  Wednesday and Thursday converted gives 15 h back to the allowance, and the statement shows it.
- **A sickness booking is made** for the sick days, costed from the rota, with the manager note
  "converted from Holiday 10–14 Mar 2027" ahead of anything typed. It is one new instance, and the
  trigger check runs; the trigger email goes if a level was reached.
- **The person is emailed** "Your time off has been changed", saying which days are now sickness and that the hours have gone back.
  When the whole booking is converted they also get the usual cancellation email.
- **The Activity log** shows each booking touched: the shortened holiday with the note "converted to
  sickness", the others as a manager's booking or cancellation; the sickness booking's manager note says what
  it was converted from.

## The past schedule section

**Where:** Time off › **Past schedule** (`/time-off/past/`), managers.

This is how 2026 sickness gets into the system, so the triggers are right from the first day. Nobody
needs the whole of 2026: type the sickness from **about the six months before the system starts**
(for a start in November 2026, from roughly May 2026), because anything older has left the rolling window
and counts for nothing.

**What to type for 2026.** **Add past sickness +**: choose the staff member, the sickness type, the
**first day** and the **last day**, one dialog per spell. Dates only: no hours, no reason. The dialog shows the instances
and trigger the person will have after the entry, and the join-on choice if the spell joins an earlier
one. The last day must be before today ("The past schedule is for days already gone; book today's sickness as time off").

**Why dates only.** The entry is a Sick leave booking flagged *dates only*: approved, whole days, with
no costed days. So it counts as an instance and towards a trigger, and touches **nothing else**: not the
allowance statement, not the grid's shifts, not the payroll report. It still appears on the Time off
list (its cost reads "dates only"), the planner, and the GP rota app's feed for a GP.

The list shows every past-schedule entry for your people: staff, first and last day, calendar days,
type, *Long sickness*, who recorded it and when, the person's instances now and their trigger.

**To correct an entry**, **Edit** changes its dates or type, in 2027 as in 2026 (the leave-year rule does not apply
to a past schedule entry; its last day must still be before today), and shows no hours. **To remove one**, use **Remove**: it is the
ordinary cancel, the record is kept, and the entry stops counting. Past schedule entries never send the trigger email.

## Triggers and the sickness summary

**Where:** Reports › **Sickness summary** (`/reports/sickness/`), managers, for their people.

| Level | Instances in the rolling six months | Shown as |
|---|---|---|
| 0 | fewer than 3 | blank |
| 1 | 3 | Trigger 1 |
| 2 | 4 | Trigger 2 |
| 3 | 5 or more | Trigger 3+ |

**A worked example.** Today is 1 July 2026, so the window is 2 January to 1 July. Four entries have a day
in it: 15 to 17 January, 9 March, 20 to 24 April and 22 to 24 June. That is four instances: Trigger 2. An
entry from 29 December to 3 January also counts, because 2 and 3 January fall inside the window; one that
ended on 1 January does not. On 1 August the window is 2 February to 1 August: the January entry has left
it and the person falls to three instances, Trigger 1, with no email.

**The summary** opens on the rolling six months to today; change **From** and **To** and press
**Refresh**. It is three tables:

- **Practice**: people, instances, days off sick, hours off sick, and how many people are at Trigger 1,
  2 and 3+.
- **Teams**: the same for each team.
- **People**: each person's instances (the rolling six months as at the range's end, or as at today
  when the range runs into the future), days and hours off sick inside the range, the longest instance
  (marked *long* at 29 days or more) and the trigger.

The practice and team **Instances** are the sickness entries that overlap the range; the person's column is
the rolling six months. The two can differ, which is why the page says so. Past schedule entries count their days and have no
hours.

**Download PDF** gives the A4 one-pager (with the practice logo) and **Download Excel** a workbook of the
same tables; the files are named for the range, `sickness-2026-07-01-2026-12-31.pdf`. In the Excel, hours are
written as "7 h 30 min" text.

## Leavers

When Practice HR gives someone a finish date, the managers are told what to do about their leave
(LEAVE-14). Two emails go to the managers who can manage the person.

| When | Subject |
|---|---|
| The finish date appears or changes in Practice HR's feed (within fifteen minutes) | "[Name] is leaving on 14 Oct 2026" |
| A week before the date, by the [daily command](#the-daily-command) | "[Name] leaves in a week, on 14 Oct 2026" |

If the date is already within a week when it arrives, one email covers both; if it is already past, one
email says "[Name] left on …" and no reminder follows. A date changed later is announced again, one
unchanged is not announced twice, and clearing a date resets it without an email. A person who first appears in Practice HR's feed
already carrying a finish date is not flagged, so the first import does not flood the managers (the Health
card still lists them). If the "is leaving on" email cannot be worked out or sent, the Health card's
Practice HR line says *leaver flag failed; see the journal*, because the next sync sees no change and does not
try again: tell the managers by hand. A failure for one person never stops the week reminders or the return
emails for the others.

**The figure** in the email, and on the profile and the statement ("Leaves on 14 Oct 2026: 18 h 30 min of
annual leave remaining"), is the person's **annual leave as at the leaving date**: their allowance
pro-rated to that day, plus adjustments, less the leave approved. **Remaining** is leave they have not taken; **over** is leave taken beyond their pro-rated share
("11 h 30 min over"). The email adds their TOIL balance. The same figure is the *Leaver's leave
remaining* column on the payroll report in the month they leave (negative means over).

**Bookings after the leaving date are flagged, never cancelled.** The email lists every active booking
with a day after the finish date, "to shorten or cancel". On the Time off list and in the booking's view
they read **after leaving date**. They still count in the person's balance, and for a GP they stay
in the feed to the rota app, until a manager edits or cancels them. A GP's rota-app leave is
changed here, not there.

**The Health card.** *Leaving in the next 30 days* now gives each person's figure and the number of
bookings that run past their date: "[Name] (14 Oct, 18 h 30 min of annual leave remaining, 2 bookings after)".

## Returning from a long absence

The day after a **long sickness** (29 days or more) or a booking of a type ticked *Email the managers when
the person returns* (Maternity and Adoption / shared parental as supplied) ends, the managers are emailed
(LEAVE-29): *[Name] is back after 6 weeks of Sick leave*. The email gives the person's remaining annual
leave for the current leave year and their TOIL, so untaken leave can be planned, and says that **the
allowance was not reduced by the absence** (it is a full-year figure), with a link to the profile.

- It is sent **once per booking**, by the [daily command](#the-daily-command) at 08:25. If a run was
  missed it catches up: a booking that ended up to **14 days ago** and has not been announced is still
  sent. Older history is not announced.
- The weeks are rounded to the nearest week, at least one.
- Past schedule entries and short sickness never send it; nor does it go for someone who has since left.
- LEAVE-29's allowance arithmetic is unchanged: the allowance is a full year's, whatever the
  absence. If the practice's adviser decides otherwise, the rule has one place to change.

## Year end

When a person's leave year ends with annual leave or TOIL left over (or annual leave taken beyond the
allowance), the managers decide what carries into the new year (LEAVE-21, 22, 24).

**When the flag opens.** On the first run of the [daily command](#the-daily-command) after a person's
leave year starts (1 January for nearly everyone) and for up to 31 days after, so a missed run still
catches it. It opens a row for the year that has just ended when that year has an **allowance typed**. A year with
no allowance opens nothing, and **nor does a leave year that ended before the system started (1 January 2027)**,
even if a 2026 allowance was typed for someone: the 2026 carry-over stays a **manual adjustment** typed in January 2027,
with the reason "carried over from FindMyShift 2026", and is never carried a second time. **The first year end the system
handles for a 1 January leave year is the one that ends in December 2027, flagged from 1 January 2028.** A person whose
leave year starts on another day is flagged for the first year of theirs that ends after go-live: a 1 April leave year
ending 31 March 2027 opens in April 2027. A person with nothing left (no annual leave and no TOIL above zero) is closed
straight away and not emailed.

**The email.** Each manager gets one: *Year end: 7 people have leave or TOIL left*, a line per person (annual
leave left or over, the bank holiday balance folded in, and TOIL) and a link to the page.

**The page.** Time off › **Year end** (`/time-off/year-end/`). *Waiting for a decision* lists your people with
year ended, annual leave left (red when over) and TOIL left, a *long absence this year* marker where a long
sickness or a flagged-return booking fell in the year, and **Decide…**. The figures are worked out again each time
the page or the dialog opens, and again when the decision is saved: a correction to last year typed in January,
days converted to sickness or TOIL used since the flag opened all change what *Carry it all* carries and what
*Lose it all* loses, and the decision records the figures it acted on. *Decided* lists the decisions with who made them and a note. The Health card's **Year-end
decisions waiting** counts the open rows.

**The three choices** (the dialog's note is optional):

| For | Choices |
|---|---|
| Annual leave left | **Carry it all** (default), **Lose it all**, **Carry part** with the hours to carry |
| Annual leave over (a deficit) | **Carry the deficit into the new year** (default), **Write it off** |
| TOIL, when above zero | **Keep it all** (default), **Lose it all**, **Keep part** with the hours to keep |

A carry outside "none to all that was left" is refused with the limit, and so is a TOIL keep above what there is.

**What it writes.** Through the ordinary Adjustments, in the new leave year:

- Annual leave carried becomes an **annual** adjustment, positive, with the reason "carried over from
  2027" (or "deficit carried over from 2027"). Leave lost writes nothing; it is simply not carried.
- TOIL lost becomes a negative **TOIL** adjustment, "TOIL lost at year end 2027". TOIL never resets, so keeping it writes
  nothing.

**Where the carry shows afterwards.** On the person's statement, as adjustment lines in the new year, which
the allowance and remaining figures include. Worked examples: a 172.5 h year that starts with 15 h carried is 187.5 h;
with 20 h left and 10 h carried, the year starts at 182.5 h and the 10 h lost is in the decision's record. The
Activity log carries the decision (what was left, carried, lost and any note) and the adjustments.

## The payroll report

**Where:** Reports › **Payroll** (`/reports/payroll/`), managers. All-teams managers see everyone;
team managers see the people they manage.

The report is one calendar **month** at a time: choose it with the arrows or the **Month** box and
**Show**. It opens on this month. The month's figures take the days still to come from the rota as it
stands, so a month in progress is a draft that moves; nothing is final until it is marked sent. The people are everyone who was current on any
day of the month, **GPs included**, one row each, grouped by team with team subtotals and, for all-teams
managers, a practice total.

| Column | Meaning |
|---|---|
| **Worked** | Hours on shifts that were not covered by leave and not marked overtime, after breaks. A GP's sessions count at 4 h 10 min each (a session under a whole-day booking is hidden; under a half-day booking the other half is still shown). A half day's other half counts as worked |
| **Paid leave** | Leave hours on paid types: Holiday, Bank holiday, TOIL, Training, paid Dependants', Compassionate and Authorised absence (the paid/unpaid choice on the booking decides) |
| **Total to pay** | **Worked plus Paid leave**: the hours the bureau pays. Sickness, Unpaid leave and the always-reported types' columns are outside it |
| **Paid overtime** | Shifts marked as overtime to be paid |
| **Unpaid leave** | Leave hours resolving unpaid, including Unpaid leave |
| **Sickness** | Hours of Sick leave days. It is not in Paid leave; sickness pay is the bureau's to work out |
| **Instances** | Sickness entries that overlap the month (past schedule entries excluded) |
| **TOIL taken** | TOIL hours taken, shown on their own as well as being inside Paid leave |
| **Leave days** | Annual leave and bank holiday days taken, a half day or a timed booking as ½ (3½). Only days that cost something count: a weekend or a part-timer's day off inside a booking is not a leave day |
| One column per **always-reported type** | For each of KIT day, Maternity, Paternity, Adoption / shared parental, Unauthorised absence and Jury service that anyone has in the month: "1 day, 6 h", counting only the days that cost something, as Leave days does. KIT days leave the balances untouched |
| **Started / leaves** | Anyone whose start or finish date is in the month; a leaver's line adds their leave remaining or over |

Past schedule (dates only) entries are never on the report. Every figure is the sum of days a manager
can open on the Time off list.

**Starters and leavers** is a table of those who start or leave in the month, with the leaver's annual
leave remaining ("negative = over").

**Download Excel** gives `payroll-2026-10.xlsx`: a **Payroll** sheet (a heading row "October 2026 —
Draft" or "— Sent 30 Oct 2026", then Name, Team, Worked, Paid leave, Total to pay, Paid overtime,
Unpaid leave, Sickness, Sickness instances, TOIL taken, Leave days, a days and an hours column for
each type present, Started, Leaves, Leaver's leave remaining), a **Corrections** sheet and a **Starters
and leavers** sheet. In the Excel, hours are **decimal hours** to two places (7.5, so the bureau can add them
up), days are numbers and names are plain text. It is a draft until marked sent.

**Mark as sent to the bureau** (all-teams managers only; team managers do not see the button, and the
address answers 403) opens a confirm dialog naming the month and the number of people. Marking stores a
snapshot of every figure as it stands and writes a line in the Activity log ("Payroll for October 2026 marked sent, 59 people"). It also records,
for every earlier month whose corrections the report was carrying, those months' figures as they now stand,
because the bureau has now been told them; the Activity log line names those months ("with corrections to
September 2026"). A month can be marked again; the latest mark is what later corrections compare with. The page then reads "Sent to the bureau on 30 Oct
2026 by [Name]". The month must be a real one, from January 2026 to a year ahead.

**How corrections appear.** Each time a report is opened, every earlier month **in the last twelve** that was
marked sent is recomputed from the bookings and the rota as they are now and compared with the snapshot. Any
difference (a booking added late, a sickness date corrected, a cost re-set) is listed under *Corrections to
months already sent* with the month, the person, the figure, what was sent, what it is now and the
difference; a person added or removed since is a line for each non-zero figure. The report for a
month is therefore "this month as it stands, plus every earlier sent month's changes since they were last
sent", which is what the bureau gets in the Excel's Corrections sheet. **A correction is sent once**: marking the
month sent records the corrected months too, so the next month's report lists only what has changed since, and
the bureau can apply each Corrections sheet as it stands. Download the Excel **before** marking the month sent:
afterwards the corrections it carried are part of what was sent and leave the report. A correction older than
twelve months has to be looked for by choosing that month by hand.

**The Health line.** From ten days before a month's last day, until it is marked sent, all-teams managers
see **Payroll for October not yet sent** on the Staff list's Health card, with an *Open* link.

## The leave summary

**Where:** Reports › **Leave summary** (`/reports/leave-summary/`), managers, for their people.

A leave year at a time (the current one to begin with; the arrows change it). Practice, team and person
tables: **Leave year**, **Allowance** (annual plus bank holiday, pro-rated; "not set" if none),
**Adjustments**, **Taken**, **Remaining**, **TOIL remaining** and **Waiting for approval**. A person whose leave year
starts on another day is reported for the year of theirs that holds the chosen year's first day, with a
footnote saying so. **Download PDF** and **Download Excel** give `leave-summary-2027.pdf` and
`.xlsx`. It sits beside the Leave report, which is by range and gives the same figures per team as
CSV.

## Emails

Plain text, through the same mail relay as the rest; if mail is not set up each is recorded as "mail
not configured" and every screen still works. Subjects never carry a reason or a note.

| When | To | Subject |
|---|---|---|
| A sickness entry raises the person's trigger level (recorded, edited or converted) | The managers who can manage the person | "[Name] has reached Trigger 2" |
| Practice HR gives a finish date, or changes it | The managers | "[Name] is leaving on 14 Oct 2026" |
| A week before the finish date (daily) | The managers | "[Name] leaves in a week, on 14 Oct 2026" |
| The day after a long sickness, or a flagged-return booking, ends (daily) | The managers | "[Name] is back after 6 weeks of Sick leave" |
| A leave year ends with leave or TOIL left (daily) | Each manager, for their people, one email | "Year end: 7 people have leave or TOIL left" |
| Annual leave is converted to sickness | The person | "Your time off has been changed" |

The managers emailed are those who can manage the person, have an active login, have started and have
not left; never the person. The join-on warning is on the screen, not an email.

## The daily command

`deploy/manage daily_flags` sends the leaver week reminders, the return emails and the year-end flags.
It is started by `shift-central-daily-flags.timer` at **08:25 every day** (a few minutes' random delay, and it catches up after downtime), and prints
a count for each step:

    N leaver reminders
    N return flags
    N year-end flags

**To check it**, after the first night and when something looks missing:

    systemctl list-timers shift-central-daily-flags.timer
    journalctl -u shift-central-daily-flags -n 30 --no-pager

A normal run says the three counts. A step that failed says so ("return flags failed; see the journal"),
and the traceback is in the journal; **the command still exits cleanly** so the timer does not go red for one
bad person, and the other steps carry on. A person whose year-end statement fails is skipped and tried
again the next day; a year-end row saved but not yet emailed is emailed on the next run. Two runs
at once send one email between them.

Switch the timer on once mail works; see [Setting up](setup.md).

## What is not here yet

Left for later releases, so do not look for them:

- Push notifications to the phone app, and the dashboard, shifts and staff-by-hour reports.
- Pay rates, salary and a budget report. The payroll report is hours; the bureau does the pay, and the
  statutory sick pay is theirs.
- A payroll period other than the calendar month.
- A sickness reason or category, return-to-work interview records, fit notes and phased returns.
- Cancelling or shortening bookings after a leaving date automatically; they are flagged and a manager
  decides.
