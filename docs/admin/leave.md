# Leave

**Where:** sidebar › Time off (`/time-off/`), with Requests (the list), My leave, Year
planner and, for managers, Waiting for approval, Bank holidays and Blackouts under it. Reports › Leave.
Settings › Leave types and Leave settings (managers). A person's statement is on their
profile, Pay & time off tab. Everyone uses Time off; the approving, booking and
settings are for managers.

## The mental model

**Everything is in hours and minutes, for everyone.** Allowances, costs and balances
are shown as "7 h 30 min", never as days, so a part-time nurse and a full-time receptionist
are counted the same way. A day off costs what the person was due to work that day. A
GP's day costs their sessions at 4 h 10 min each, plus any shift typed into their cell.

**The rota decides what a day costs.** Book a Holiday on a day on which someone is
rostered 08:00 to 16:15 with a lunch break and it costs those worked hours. A day with
no shift costs nothing. Nobody types a figure unless the rota is wrong or missing.
See [what a day costs](#what-a-day-costs).

**Balances are worked out every time, never typed.** What a person has left is their
pro-rated allowance plus any adjustments, less the days approved, and the
[statement](#the-statement-and-how-to-read-it) lists every line of that sum. So a
leaving date arriving from Practice HR, a changed rota or a corrected allowance changes the
answer everywhere without anything being re-posted.

**An approved booking covers the grid; it does not delete it.** The person's shifts for
those days leave the grid, the hours report and the notify emails, and come back if the
leave is cancelled. A booking by the hour shortens the shift it falls in and puts the
original times back on cancelling.

**Nobody decides their own leave.** Another manager approves a manager's request. The
one exception is a flag the practice manager's own profile can carry,
[Own leave needs no approval](access.md#the-permissions-link).

**Every change is written down.** Booking, approving, declining, cancelling, editing,
overriding a cost, adjusting a balance, changing hours and every edit on the bank
holiday, blackout, leave type and leave settings pages writes a line in the
[Activity log](access.md#the-two-logs), with who, when and the figures before and
after. A person's History link (managers) shows their booking and adjustment lines beside
their field changes.

**Leave can be booked in a person's current leave year and the next**, and no further. A
leave year is a person's own: it starts on the month and day on their profile, 1 January
for nearly everyone.

## Allowances and hours changes

**Where:** profile › Pay & time off. The fields are in [People](people.md#typed-here-the-pay--time-off-tab).
Allowances are typed in **hours**, for each of the two leave years, one pair (annual
leave and bank holiday) per year.

**The year's figure is pro-rated by the weeks the person is employed in it.** The rules
a manager needs, all worked out for them:

- The weeks are counted from the person's start date, or the year's start if they were
  already here, to their finish date, or the year's end. **A part week counts as a whole
  week.**
- The share is the full-year figure divided by 52, times the weeks.
- The total is rounded **once**, to the nearest half hour (a quarter of an hour rounds up), and
  never exceeds the full-year figure. That second rule is why a person who is here for
  the whole of a 53-week year still gets exactly their allowance.
- Example: 225 h a year for someone who starts on 1 July. The year has 184 days left, so
  27 weeks, and 27/52 of 225 h is 116.83 h, shown as 117 h.
- The annual leave allowance and the bank holiday allowance are each worked out this way.
- A year with no allowance typed has none, and the statement says "not set". The person
  is also on the Health card's *Needs hours and allowances* list.

**A change of hours part-way through a year** is entered with **Add hours change…**,
under the statement on the Pay & time off tab (managers; not for yourself):

| Field | What it does |
|---|---|
| **From** | The first day of the new arrangement. It must be after the year's first day (the first row is the profile's own allowances) and not the day of an earlier change. |
| **Weekly hours**, **Days per week** | The new contract. They become the person's hours on that day. |
| **New annual leave allowance**, **New bank holiday allowance** | The **full-year** figures for the new hours, in hours. The system works the year out week by week from both rows. |
| **Reason** | Required. It is recorded with the change. |

- The year's first allowance must already be entered; the dialog says so if not.
- **The week of the change counts on both sides.** The practice chose this: the week in
  which the change falls is counted at the old figure and again at the new one, and the
  total is then capped at the larger of the two full-year figures, so it can never be more
  than a full year of the better terms.
- A change dated today or earlier copies the new weekly hours and days onto the profile
  at once. A change dated in the future is copied by the Practice HR sync (every fifteen
  minutes) once the day has come, so nobody has to remember to visit the profile. It is
  copied once: a manager's later edit to the profile is not overwritten by the next sync.
- If the change leaves the person's annual leave **below zero**, the managers are emailed
  and the person is on the Health card's *Negative leave balances* list. Nothing is blocked.
- For a GP the new weekly hours are not copied onto the profile; their sessions, not hours,
  cost their leave, so the allowances are what the change is for.

**Changing when a person's leave year starts** (a profile field, `MM-DD`) is refused once
they have an allowance or a booking, because those are filed under the years the old
date made. Set it before anything else is entered.

## What a day costs

Each day of a booking is costed when the booking is made (a request is costed when it is
approved), and shown in the dialog before you save.

| Booking | The cost of a day | Shown as |
|---|---|---|
| Whole day, the week has a rota | The shifts on the rota that day, after breaks. Overtime-marked shifts do not count. A day with no shift costs 0 | the rota, or "no shift" |
| Whole day, the **whole week** has no rota | The person's **average day**: weekly hours divided by days per week | "average day — no rota yet", flagged |
| Morning or afternoon | Half of the figure above | |
| Times (a start and a finish) | Finish less start | |
| A GP, whole day | Their sessions that day at 4 h 10 min each, plus any shift typed into their cell; neither, no cost | |

**The week rule.** A day counts as "rota not set" only when the person's whole Monday to
Sunday week has nothing on it: no entry of any kind (a comment counts as one) and no session. A blank Wednesday in a week that has shifts is
a day off, and costs nothing. The average day comes from the allowance row in force that
day (so a change of hours is honoured), else from the profile; with neither, the cost is 0
and the dialog says the weekly hours are not set.

**Costs to check.** A day costed on the average day is a placeholder. It is **re-costed
from the rota when a manager sets the shift behind the leave**: right-click the day on the
grid and choose **Shift behind the leave…** (or **Add › Shift…** on that cell), enter the shift the
person would have worked and save it. The shift stays hidden under the leave, the day's cost
becomes that shift's hours, and the managers are emailed ("Leave cost to check for [Name]").
Writing the person's other days does not change it. Until it is set, the Health card's *Leave
costs to check* lists the days, each linking to its booking. The other way to settle it is to
type the figure into the booking's **Allowance used** box (Edit). A day a manager has typed a
figure for is never re-costed, and the shift dialog on a half-day or timed booking changes
no cost.

**Which allowance a day draws on.** The leave type decides: Holiday takes annual leave,
TOIL takes the TOIL balance, Bank holiday takes the bank holiday allowance, and the others
(Sick leave, Training, Maternity and so on) take **nothing**: they record the hours for
the record and, later, the payroll report, but touch no balance. **A Holiday day that is a
listed bank holiday** takes the bank holiday allowance instead of annual leave, whatever
the rota says (the bank holidays page, [below](#bank-holidays)).

**Overriding a day.** In the Add or Edit time off dialog, each day has its own
**Allowance used** box holding the computed figure. Type a different one (`7:30` or `7.5`)
and that day is fixed at it, marked "set by a manager", with the note "set when booked" or
"set when edited". It is the way to put right a day the rota got wrong, or to give a bank holiday
its hours. The Activity log keeps the old and new figure. A pending request's dialog has no
boxes, since its days do not exist until it is approved.

## The Time off list

**Where:** Time off › Requests (`/time-off/`). Every approved and waiting booking in the
practice, newest first, for the current leave year and the next to begin with.

| Column | What it shows |
|---|---|
| **Staff**, **First day off**, **Last day off**, **Days** | Who, the dates, and the calendar days in the booking (weekends included). |
| **Type**, **Display** | The type's name, and the coloured label as the grid shows it. |
| **Pay**, **Allowance used** | Paid or unpaid, and the hours the days took. |
| **Status** | Waiting for approval, Approved or Cancellation requested. |

**What each person sees.** Everyone sees who is off and the type; **the description, pay and cost are
shown only to the person and to their managers.** Filters above the table: **From**, **To**, **Type**,
**Team** and **Status**. Declined and cancelled bookings are left out unless you choose them under Status,
and then only the person's own and their managers' show. Managers get **Download**, the same rows as CSV,
and **Edit** and **Cancel** links on their people's rows. Staff get **Request time off +**; managers
**Add time off +**.

## Requesting leave (staff)

**Where:** Time off › My leave, or the **Request time off +** button on the Time off page
(`/time-off/request/`). A page rather than a pop-up, so it works on a phone.

The page opens with the person's balance (annual leave remaining, how much is available
to request once other requests are counted, and TOIL). Then:

1. Choose the **type**. Only the types a manager has marked requestable are offered
   (Holiday, TOIL, Training, Compassionate, Authorised absence and Unpaid leave to begin with).
   Sickness, family leave and the rest are recorded by a manager.
2. Optionally overtype **Display**, the label shown on the grid for this booking only.
3. Choose the first and last day, **Days to include** (whole days, morning, afternoon or
   times; the last three are one day only) and write a note for the manager.
4. The page shows each day's cost and the balance before and after. **Send request** appears
   when the request passes its checks.

A request is refused, with the reason where the **Send request** button would be, when:
the dates are outside this leave year and the next; any day is in a [blackout](#blackouts)
for the person's team; it overlaps leave they already have, waiting or approved; or its
cost is more than they have **available**. Where it shows depends on the check: a message at
the top of the page for the dates, an overlap (it names the booking already there) or a
blackout (it does not name the day); and, for too little available, there is no Send button
and the balance line shows the figure available.

Sending emails the managers who can manage the person. A waiting request is shown on the
rota grid hatched, with the type and "requested", so colleagues can see who has asked; it
covers no shifts and costs nothing until it is approved. Everyone else sees the type only,
never the description, the pay or the cost.

**My leave** (`/time-off/mine/`) lists the person's own time off, with the statement above
it, and **Request cancellation** against approved leave whose last day is today or later.
Past leave is cancelled by a manager. A person cannot withdraw a *waiting* request
themselves; a manager can decline or cancel it.

## Booking leave (managers)

A manager records leave directly, without a request: **Add time off +** on the Time off
page, **Rota › Time off…** in the sidebar, or right-click a cell on the [rota](rota.md#time-off-on-the-grid)
and choose **Time off…** (the person and day are filled in).

The dialog is the staff page's with a **Staff member** (the people you manage) and the
costs editable: **Type of time off**, **Display**, **First day off**, **Last day off**, **Days to include**, the
per-day **Allowance used** table with its total and the balance before and after, and under
**Advanced** a **Paid or unpaid** box and **Manager notes**. The paid box shows for every
type but counts only for a type where the manager chooses; for the others it is ignored.
It redraws as you change a field. The button is **Add time off**.

- The booking is **approved at once**, the shifts are covered, and the person is told by
  [Notify staff](rota.md#notify-staff) like any other rota change. They are not sent a
  separate email.
- A manager's booking has **no blackout check and no balance check**: it can take someone
  below zero (the Health card then lists them). It still refuses a booking that overlaps
  their other leave, or falls outside this leave year and the next.
- Every type can be booked, including Sick leave, Maternity and KIT days.
- **A timed booking** (say 14:00 to 15:30) shortens the shift it falls inside: at the start
  of the shift the shift begins later, at the end it finishes earlier, in the middle it
  finishes where the leave starts (the rest of that day leaves the grid; add a second shift
  if both halves should show). If the day has no shift containing the time, the booking
  is kept and costs its hours with nothing to shorten.
- **Booking your own leave** when you do not have *Own leave needs no approval*: the dialog
  says it will wait for another manager, and sends it as a request (so the staff rules,
  blackouts and balance included, apply to it, and only requestable types can be used).

## Approving

**Where:** Time off › Waiting for approval (`/time-off/approve/`), and the Health card's
*Requests waiting* box (which counts the requests of the people you manage, not your own).

The list is oldest first, for the people you manage: who, team, what and when, how long it
has waited, the cost and the person's note. Requests and **cancellation requests** (shown
as "asked to cancel") are both here. **Decide** opens the request: its days with their
costs, the balance before and after, who else in the team is off on those days, and a note
box. Then:

- **Approve** applies the booking (covers shifts, writes the costs) and emails the person.
  It checks again that nothing else has been booked over the same days meanwhile. It does
  not check the balance: you saw it in the dialog, and a manager can approve into the red.
- **Decline** records your note and emails the person. A declined request keeps no days.
- For a cancellation request, **Approve cancellation** undoes the leave and **Refuse
  cancellation** leaves it as it was.

The note you write goes into the email to the person, so write it for them to read.

**The reminder.** A request that has waited longer than the number of working days on
[Leave settings](#emails-and-the-reminder) reminds the managers, once. Working days are Monday
to Friday less bank holidays.

## Cancelling, editing

**Cancelling.** A manager cancels any approved or waiting booking, **past days included**:
the Time off list's **Cancel** link, or **Cancel time off** on the rota menu. The shifts come back, the
costs go, and the person is emailed. For a person's own request, see above.

**Editing.** **Edit**, on the list or in the booking's View dialog, changes the type, the
dates, the part, the display text and the paid flag of an approved or waiting booking.
Changing the dates, part or type is done by undoing the leave and applying it again
inside one transaction, so the costs are worked out afresh; any figure a manager typed
for a day that is still in the booking is kept, and a figure you type now becomes an
override. Changing only the display text or paid flag re-costs nothing. Manager notes are not
editable in the dialog. Staff cannot edit: they cancel and request again.

## Adjustments

**Where:** the statement on the profile's Pay & time off tab, **Adjust…**.

An adjustment adds or takes away hours from a balance, and carries the reason, who and when.

| Field | What it does |
|---|---|
| **Leave year** | The year's first day: one of the person's two. |
| **Account** | Annual leave, Bank holiday allowance or TOIL. |
| **Hours** | `15:00` or `7.5` adds; a minus sign (`-4:00`) takes away. |
| **Reason** | Required. |

It shows on the statement as a line and in the Activity log.

**2026 carry-over** (migration, MIG-04): in January 2027 the managers type each person's
carry-over from FindMyShift as an adjustment to annual leave in the 2027 year, with the reason
"carried over from FindMyShift 2026". Nothing is imported from FindMyShift; the figures
are typed from its balances. TOIL is a running balance that never resets, and TOIL
adjustments belong to the person rather than to a year.

## Bank holidays

**Where:** Time off › Bank holidays (`/time-off/bank-holidays/`, managers).

The list for a year, with the days seeded for England and Wales for 2026 and 2027. **The
practice adds a day by hand, such as a one-off, with the form below the list** (day and name),
and **Delete** takes one off. Nothing is automatic: a year that is not listed has none,
so add 2028's before leave is requested for it.

Two things depend on the list: a Holiday day that falls on a listed day draws on the bank
holiday allowance, and working-day counting skips them (the reminder).

**Booking one for everyone.** Each row has **Add for everyone**, which lists the people you
manage:

- Each has a tick box and their hours, the suggestion being the shift they most often
  worked on that weekday in the four weeks before the bank holiday (the largest on a tie; 0 if
  none). Change any figure and untick anyone it does not apply to.
- **GPs are listed at 0 and unticked**: the practice is closed but their sessions are the
  GP rota app's.
- **Add bank holiday for everyone ticked** books a whole-day Bank holiday for each, with
  the typed hours as the cost. Anyone already booked that day is skipped and counted, as is
  anyone whose leave year does not yet allow it.
- You are not on the list: a manager's own bank holiday is booked by another manager.

The bank holiday allowance the person has left, positive or negative, **moves into annual leave**: the
statement shows "Bank holiday allowance less bank holidays taken (moves into annual leave)", and
annual leave remaining includes it. So working a bank holiday gives that time back as
leave, and a bank holiday allowance that is smaller than the bank holidays taken takes the
difference out of annual leave.

## Blackouts

**Where:** Time off › Blackouts (`/time-off/blackouts/`, managers).

A blackout is a range of days staff **cannot request** leave for, for chosen teams or for
everyone (no team ticked). Add one with **Add blackout +**: first day, last day, the teams and a
note. A request touching a blacked-out day is refused and names the day. **Managers can still
book** it. A blackout does not affect leave already approved.

## Leave types

**Where:** Settings › Leave types (`/settings/leave-types/`, managers).

Fifteen types are there from the start, in the order the requirements list them. You edit
what a type is called, its colour (the tile and the planner), its place in the lists, whether
staff can request it, and whether the manager chooses paid or unpaid; you can archive it, or
**add your own**.

| Column | Meaning |
|---|---|
| **Takes its days from** | Annual leave, the bank holiday allowance, TOIL or nothing. It decides the arithmetic. |
| **Staff can request** | Whether it appears on the request page. |
| **Paid or unpaid** | "Manager chooses", or fixed paid, or unpaid. |
| **On the payroll report** | Always, if unpaid, for leavers, or never: for the payroll report that comes in a later release. |

- What a type **takes its days from**, and how it reaches payroll, are **fixed on the fifteen
  standard types** and, on one you add, can be chosen once and are then locked as soon as it
  has any booking. This is so that no edit changes the arithmetic of leave already booked.
- **Renaming is safe**: the system finds the bank holiday and unpaid types by what they are, not
  their names.
- **Archive** instead of deleting. An archived type is not offered, but its bookings stand,
  and the bank holiday type has to be in use for "Add for everyone" to work.
- The type's **name** is the label on the tile, and it is what the GP rota app is sent for a GP's leave
  (see [GPs](#gps)). A custom type's name therefore reaches that app.

## The statement and how to read it

**Where:** the profile's Pay & time off tab for managers; the same figures in My leave for
the person. A **Leave year** box switches between the person's two years. The summary is
at the top: annual leave allowance (pro-rated), bank holiday allowance, adjustments, what is
taken, the bank holiday balance, **annual leave remaining** (bold), what is available to request,
and TOIL. **How it is worked out** under it lists every line, in order:

| Line | What it is |
|---|---|
| Annual leave allowance and Bank holiday allowance, one line per allowance row | The dates, "27 weeks of 52 at 225.00 h", and the share. If the figure was rounded or capped, a further line says "rounded to the half hour" or "…and capped at the full-year figure". "not set" when none. |
| An adjustment | Its reason and account, with the hours. |
| A booking day | "Mon 8 Mar: Holiday (annual leave, rota)", its cost taken off. The source after the comma says where the figure came from: rota, average day, half day, times, set by a manager or no shift. |
| *Requested: …* | A waiting request and its cost. **Not taken off** the remaining figure, but off *available*. |
| Bank holiday allowance less bank holidays taken | Positive: a credit that adds to annual leave. Negative: a deficit that comes off it. |
| **Annual leave remaining, bank holidays included** | Allowance + adjustments − days taken + the line above. |
| Annual leave available to request | Remaining less the requests waiting. What a staff request is tested against. |
| TOIL adjustment / TOIL day / *Requested* | TOIL's own lines, of **every year** (it never resets). |
| TOIL earned, TOIL remaining, TOIL available | Hours of shifts marked **TOIL** in the rota, up to **today**, plus adjustments, less TOIL taken; available is less any waiting. |

An approved TOIL booking dated in the future already reduces the remaining figure, as an
approved holiday does. Hours worked and marked TOIL for a day not yet reached do not count until
that day.

Remaining goes **negative** when a manager books or approves more than is left, or after an
hours change. That is allowed; it shows in red on the Health card.

## The year planner and the leave report

**Year planner** (Time off › Year planner, `/time-off/planner/`). Everyone sees it. Months
are rows, days run across aligned by weekday (so a column is always the same weekday),
weekends are shaded and bank holidays tinted. Each approved booking is a coloured cell with the
person's initials, a hatched one is still waiting. Choose the year, a type and a team. Hover for
the name and the type. It shows the type only, never the reason.

**Leave report** (Reports › Leave, `/reports/leave/`). A table by team with a total for each,
for a range (the viewer's current leave year to begin with; **Refresh** applies a new one).
Managers see the people they manage and themselves; staff see only their own row.

| Column | Meaning |
|---|---|
| **Allowance** | Annual plus bank holiday, pro-rated. "not set" if none. |
| **Adjustments** | Annual and bank holiday adjustments for the year. |
| **Days** | The calendar days booked in the range, approved bookings only. |
| **Deducted** | The hours those days took from annual leave and the bank holiday allowance. |
| **Remaining** | Annual leave remaining, as on the statement, for the leave year the range starts in. |
| **TOIL** | TOIL remaining. |

**Download** gives the same as CSV. A range that crosses a New Year shows the first year's
remaining figure, so keep the range inside one leave year for the figures to mean anything.
The report's *Instances* column (sickness) arrives with sickness.

## Emails and the reminder

Plain-text emails, sent through the same mail relay as Notify staff. If mail is not set up, nothing
is sent, each is recorded as "mail not configured" and every screen still works. A failed
send never stops a booking.

| When | To | Subject |
|---|---|---|
| A request or a cancellation request is made | Every manager who can manage the person, once each, never the person | "[Name] has requested time off" or "… has asked to cancel time off" |
| A request is approved or declined; a cancellation is approved or refused | The person | "Your time off has been approved", "…declined", "…cancelled" or "…kept" |
| A booking with average-day (placeholder) days is made; or a manager sets the shift behind a placeholder day, or a rota write changes an approved whole day's cost | The managers | "Leave cost to check for [Name]" |
| An hours change leaves annual leave below zero | The managers | "[Name]'s leave balance is negative" |
| A request (or a cancellation request) is still waiting after the number of working days set below | The managers, once per request | "Time off request still waiting" |

Subjects name the person and say what happened, never the reason or the note. A decision
email to the person carries the manager's note.

**The reminder** is `deploy/manage leave_reminders`, started by
`shift-central-leave-reminders.timer` at 08:20 each weekday (a few minutes' random delay, and it
catches up after downtime). It prints how many reminders it sent. Settings › Leave settings
(`/settings/leave/`) holds the one setting, **Remind the managers when a request has waited this
many working days** (3 to start; 1 to 30).

## GPs

GPs are booked, requested and approved exactly like anyone else, with these differences.

- **Sessions come from the GP rota app.** A GP's day costs their sessions that day, 4 h 10 min each, plus any shift
  typed into their cell; a day with neither costs nothing. A GP never has an average day.
- **Leave does not remove a session from the grid.** The session is the rota app's. The leave tile shows above
  it, and the rota app flags the clash (see `docs/admin/shift-central.md` in that app's repository).
- **The GP rota app reads approved GP leave from here**, every fifteen minutes, so
  the GP rota shows who is off and assisted fill never assigns them. It replaces FindMyShift as that app's source. The
  [feed](sync.md#the-gp-rota-app-reads-gp-leave-from-here) carries only the email, dates, part and the type's
  name. Request or approve a GP's leave here, not in the rota app.
- A GP's email must match the one the rota app holds, or their leave is not shown there.
  That app's status page lists the addresses it could not match.
- A GP is on the Staff list with **no weekly hours**; allowances are typed in the same way
  as for anyone else.

## What is not here yet

Left for later releases, so do not look for them:

- Sickness records (instances, triggers, the return-to-work flag, long sickness, the
  join-on warning) and the past-schedule section. Sick leave can be booked as time off, and
  nothing more happens.
- Converting annual leave into sickness, and the long-absence rules.
- The year-end carry-over flag, leaver flags and the payroll report, and the one-page
  summaries.
- Push notifications to the phone app, messages and the notice board.
- Repeating time off, a limit on how many can be off at once, notice periods, a second level of
  approval, delegating approval and automatic approval.
- Importing FindMyShift bookings or balances. They are typed in as adjustments, as above.

The Django admin (`/admin/leave/`) shows the bookings, days, adjustments and blackouts
read-only (the superuser can delete a booking there), and lets the superuser repair a leave type, a bank holiday or the setting. It is
for repair, not for booking.
