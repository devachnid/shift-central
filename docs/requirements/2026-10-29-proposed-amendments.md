# Proposed amendments to the requirements

**From:** the developers
**To:** the practice manager
**Date:** 29 October 2026
**Status:** proposed; awaiting the practice manager's decision

We have read the whole pack and can build it. Three things need your
agreement before we start, because each changes something you approved.

## 1. Staff details come from Practice HR, not typed in twice

**What the pack says (PAT-07, INT-01):** managers type names, emails, start
and leaving dates and teams into AMG Shift Central, and the two systems are
not linked apart from sign-in.

**What we propose:** Practice HR already holds everyone's name, work email,
team, start date and leaving date, and already publishes them for the GP
rota app to read. AMG Shift Central reads the same feed, so those details
appear automatically and stay in step. Managers type in Shift Central only
what Practice HR does not hold: weekly hours, days per week, the two leave
allowances, colours, job title shown on the rota, mobile number.

**Why:** a leaving date entered in one system but not the other is exactly
the kind of wrong leave figure the project exists to remove. It also saves
re-typing 59 people in December.

**What you would notice:** a new starter is added in Practice HR first and
then appears in Shift Central a few minutes later, ready for hours and
allowances to be set. A leaving date is entered in Practice HR and Shift
Central picks it up and raises its leaver flags (LEAVE-14).

## 2. GP sessions stay in the GP rota app; GP leave lives in Shift Central

**What the pack says (ROTA-GP-01, 03, 04):** GP rotas are built in Shift
Central as well as in the GP rota app, the two update each other both ways,
and clashes are flagged.

**What we propose:** one home for each thing.

- The **GP rota app keeps building GP sessions** (it fills them against the
  coverage rules, handles swaps, trainees and locums). Shift Central
  **shows** every GP's sessions in its grid as 4 h 10 min tiles, kept up to
  date automatically, but they are not edited there.
- **Shift Central holds every GP's leave**, with the same allowances,
  requests and approvals as everyone else. The GP rota app **reads GP leave
  from Shift Central** instead of from FindMyShift (this also answers Q-10).

**Why:** two editable copies of the same rota means endless clashes to sort
out, and a large amount of work to build and keep working in nine weeks.
Your stated reason for wanting GPs in the grid — leave, hours and training
entitlements and deductions in one place — is met in full by this, and
nothing is lost except the ability to type a GP's session into the Shift
Central grid, which the GP rota app already does better.

**What you would notice:** GPs appear in the Shift Central grid with their
sessions, their hours count in the hours report, and their leave is booked
and approved in Shift Central. To change a GP's sessions you open the GP
rota app, as now.

## 3. What is in place on 1 January, and what follows

Everything in the pack is marked Must for 1 January. There are about five
weeks until managers need to start data set-up and nine until launch. We
will build in the order you gave (staff and allowances, then the rota grid,
then leave, then the rest) so set-up can start as early as possible.

**In place for data set-up (early December):** sign-in, staff profiles,
departments, allowances, manager access, the rota grid with all its editing.

**In place for staff to request 2027 leave (before Christmas):** leave
requests, approvals, balances, every leave calculation, email
notifications.

**In place for 1 January:** sickness and triggers (with the past-schedule
section), TOIL, open shifts, leaver flags, hours report, leave report, year
planner, activity log, log-in logs, the phone layout.

**Shortly after launch:**

| Item | Needed by | Proposed |
|---|---|---|
| Payroll report (Excel) | First report ~24 January | Mid-January |
| Push notifications to the phone app | — | January; email notifications from day one |
| Sickness and leave one-pagers (PDF/Excel) | — | February |
| Messages, notice board, uploads, outbox | — | February |
| Dashboard, shifts and staff-by-hour reports | — | February |
| Year-end carry-over flag | December 2027 | Autumn 2027 |
| Pay rates and budget report | Could have | Not scheduled |

This is also our answer to **Q-04** (the fallback if set-up cannot start in
early December): the set-up features come first and on their own, so a
delay elsewhere does not hold them up.

## Two smaller points

- **Hours change in the middle of a year (LEAVE-12).** Counting the week of
  the change on both sides can give slightly *more* than either full-year
  allowance when the change is small (37.5 h to 37 h gives 174.6 h, against
  full-year figures of 172.5 h and 170.2 h). We propose capping the total at
  the larger of the two full-year allowances, so LEAVE-13 ("never more than
  the full allowance") always holds. Please confirm.
- **Half-minutes (Q-08).** We propose showing a half-minute as "½" after the
  minutes (2 h 37½ min), and only ever on a half-day of an odd-minute shift,
  which is rare. Please confirm.

## What we need from you

1. Yes or no to each of 1, 2 and 3 (and any changes to the dates in 3).
2. Your answers to the two smaller points.
3. The redacted FindMyShift screenshots, when ready.

## Postscript, 29 October 2026 (developers)

Built as proposed in 2: GP sessions appear in the Shift Central grid as
read-only tiles, read from the GP rota app every fifteen minutes and matched
to each GP by their work email. If a GP's email differs between the two
systems their sessions do not show and the Staff page's Health card lists
the address. We will revisit the link (by Practice HR's employee id) once
the GP rota app holds one. Your yes or no to 1, 2 and 3 is still needed.
