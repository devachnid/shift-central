# 04 — Contracts and working patterns

**PAT-01** — Each non-GP person has **contracted weekly hours** and **days worked per week** on their profile, typed in by a manager. (amended November 2026: see LEAVE-01 and D-34)
*Why:* only the weekly total is fixed; days and hours are set by the rota. Days per week is needed for the leave placeholder (PAT-05).

**PAT-02** — There is **no fixed weekly pattern**. Which days someone works and how long each day is comes from **the rota**.
*Why:* the practice decides days week to week. **Differs from the Practice HR design**, which uses a dated weekly pattern with AM/PM amounts.

**PAT-03** — Each person has **one contract** with one weekly total.
*Why:* nobody has overlapping contracts.

**PAT-04** — GPs work in sessions; **each session counts as 4 h 10 min** for leave and hours, with no exceptions (e.g. 6 sessions = 25 h a week).

**PAT-05** — **Average day** = weekly hours ÷ days worked per week (e.g. 30 h over 5 days = 6 h). It is used only as a **placeholder** for leave booked on a day the rota has not yet been set (see LEAVE-06).

**PAT-06** — A change of hours is entered as a **new contract in Practice HR from its date**; AMG Shift Central works out the new allowances from that date. Where allowances are typed, the manager adds the hours change as before. The leave effect is in LEAVE-12. *(Amended November 2026.)*

**PAT-07** — **Practice HR is the master for contracts, weekly hours or sessions, and leave terms. AMG Shift Central is the master for days per week, allowances, leave and balances.** Practice HR's built-in leave design is not used. *(Amended November 2026.)*
*Why:* a contract is entered once, where it is kept; the practice manager's written answers of November 2026.

**PAT-08** — Staff can work at **either site**; the site is shown by the department tag on each shift (e.g. Reception AG / Reception PMC).

## Not needed, on purpose

- Fixed or dated weekly working patterns.
- Alternating-week, rotating or seasonal patterns as contract types (worked example 17 not applicable).
- Annualised hours, term-time, zero-hours, bank or irregular-hours contracts (worked example 18 not applicable).
- Overlapping contracts, secondments, acting-up (worked example 9 not applicable).
- Backdated hours changes.
- Different session lengths for different GPs or session types.
- Staff working for more than one employer.
- Automatic syncing of contract details with Practice HR.
