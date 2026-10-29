# 02 — Team rotas

All teams (reception, admin/secretarial, nursing, pharmacy, management, cleaner) work **the same way**. GPs are covered at the end.

## Common to all teams

**ROTA-01** — A rota entry is a **shift**: start and finish clock times, an optional **unpaid break** (15, 30, 45 or 60 minutes — length only, not the time it is taken), an optional **department tag**, and optional comment text.
*Why:* this is how FindMyShift is used today (e.g. "07:30–13:30, PMC", "08:00–16:15, 1 hour break").

**ROTA-02** — Departments are **one combined list** of teams, roles and tasks. Initial list: Reception AG, Reception PMC, Cleaning PMC, Prescriptions, Private Income, Workflow, VAS/Enhanced, Scanning, Pharmacy, Secretarial, Management, Salaried GP, Nursing, HCA, Phlebotomist, Pharmacist, Pharmacy Technician. Managers can add more and set colours.
*Why:* the practice chose one list rather than separating "who someone is" from "what they're doing".

**ROTA-03** — Breaks are always unpaid and are deducted from worked hours (08:00–16:15 with a 1 h break = 7 h 15 min).
*Why:* matches the hours report the practice relies on.

**ROTA-04** — A shift can be shown as **WFH** (working from home).

**ROTA-04a** — **All rota grid colours are set by managers when building the rota**: each person's name colour, each department's colour, and the background and text colour of any individual tile (overriding the department colour). Nothing is fixed by the system.
*Why:* the practice uses colour to make the rota readable at a glance and wants full control of it, as in FindMyShift.

**ROTA-05** — Shifts can be placed on **any day**, including Saturdays and Sundays.
*Why:* managers add occasional Saturday clinics by hand.

**ROTA-06** — A manager can **mark a shift as overtime**, either "overtime – paid" or "overtime – TOIL", by right-click. Extra hours on the same day as a normal shift are entered as a **separate overtime shift**.
*Why:* overtime hours must be excluded from leave costs (see `05`) and TOIL must build a balance.

**ROTA-07** — Managers can lay out rotas **manually for the whole year or beyond**, mainly by **copying and pasting blocks of weeks** (one person, several people or the whole team), then making ad hoc changes.
*Why:* the practice wants to plan the year ahead. Today rotas are finalised only 1–2 weeks ahead. The current reception rotation will be redesigned, so the system must not assume any fixed rotation.

**ROTA-08** — **Templates**: save a set of shifts and reuse them. "Common" and "recent" shifts can be picked from the right-click menu.

**ROTA-09** — Changes are **saved quietly**. Affected staff are told only when a manager presses **"notify staff"** — each affected person then gets **one email and push notification summarising their changes**.
*Why:* building a year ahead means hundreds of edits; staff must not be flooded, but must always hear about changes.

**ROTA-10** — When time off is added for a whole day, the person's shift is **removed** (the original shift is kept on record so its hours can be used to cost the leave and restored if the leave is cancelled). For part-day leave the shift is **shortened**.
*Why:* the practice does not want shifts and time off overlapping.

**ROTA-11** — **Open shifts**: a manager posts an unfilled shift and **chooses who is notified** (one team, several teams or everyone). Staff claim it; **a manager approves** the claim; the shift then goes on the claimant's rota and they are notified.

**ROTA-12** — **"Who's in today"** view for managers (PC and phone): everyone across all teams and GPs, by site (AG / PMC), showing who is working, who is WFH and who is off.

**ROTA-13** — Swaps are agreed between staff and **a manager makes the change** on the rota.

## Cover

- Gaps are covered by a manager asking someone directly, or by posting an open shift (ROTA-11).
- The person working extra chooses **overtime pay or TOIL** (ROTA-06).

## GPs

**ROTA-GP-01** — GP rotas are **built in the new grid** as well, in the same way as other staff.
*Why:* the practice manager needs GPs there for leave, hours and training entitlements and deductions.

**ROTA-GP-02** — Every GP session counts as **4 h 10 min** for leave and hours (two sessions = 8 h 20 min).

**ROTA-GP-03** — The new system and the existing GP rota app **stay in sync both ways**. Either can be edited and each updates the other automatically.

**ROTA-GP-04** — If a change in one app clashes with a change in the other (e.g. leave approved in the new app for Dr A on Tue 10 March while, in the GP rota app, Dr A takes a swap into Dr B's Tuesday afternoon session), **both changes are allowed and managers are flagged** to sort it out.

**ROTA-GP-05** — The GP rota app must take GP time off from the new system instead of FindMyShift (its current stop-gap). **[Developer to confirm]**

## Not needed, on purpose

- Minimum staffing rules and skill/competency checks, for any team.
- Break times (only lengths).
- Special features for Saturday flu/COVID clinics.
- Separate "team" and "task" lists.
- Matching the clinical system's appointment book (EMIS/SystmOne).
- Any link between other teams' rotas and which GPs are in.
- Rooms and clinic types as separate fields (use department tags or comments).
- A wall display.
