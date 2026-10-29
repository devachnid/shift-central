# 00 — Overview

**System name: AMG Shift Central**

*Requirements specification for the practice's staff management system. Written from an interview with the practice manager (29 October 2026). It says **what** the practice needs and **why**, not how to build it.*

## The practice in a page

- A UK GP practice with **two sites**: **AG** (main site) and **PMC** (branch site). Both open **08:00–18:30, Monday to Friday**. Occasional Saturday flu/COVID clinics, staffed by a mix of teams, sometimes at PMC.
- About **59 people**:

| Team | Headcount | Notes |
|---|---|---|
| GPs | 15 | 7 partners, 6 salaried, 2 trainees (registrars), no regular locums |
| Reception | 12 | Some do 1–2 days a week of admin (prescriptions, enhanced services admin) under the same contract |
| Admin / secretaries | 11 | |
| Nursing | 11 | Practice nurses, HCAs, phlebotomists |
| Pharmacy | 5 | Clinical pharmacists, pharmacy technicians |
| Management | 4 | Practice manager + 3 assistant managers |
| Cleaning | 1 | Employed cleaner at PMC |

- Everyone except the GP partners is employed by the practice. No PCN-employed, agency, bank, casual or zero-hours staff. Everyone has fixed contracted weekly hours.

## The goal

1. **Rotas for every team, GPs included**, in one grid whose **visuals and functionality are very close to FindMyShift** (see `03`, FMS-00), using the **AMG Shift Central** name and logo rather than FindMyShift's branding.
2. **Leave calculated correctly in hours** for everyone, using the practice's agreed formulas. This is the reason the project exists: FindMyShift's leave calculations are wrong, so FindMyShift is being retired.
3. **Automate manual work** — the hours report, payroll figures and sickness tracking are currently done by hand across several spreadsheets.
4. **One account per person** across everything, using the existing Practice HR sign-in.

## Who the users are

| User | What they do |
|---|---|
| Staff member (everyone, ~59) | Sees all rotas, their own shifts and balances; requests leave; claims open shifts — mostly on their own phone |
| Team manager (lead nurse for nursing; head pharmacist for pharmacy) | Builds and edits their team's rota; approves their team's leave |
| All-teams manager (practice manager and 3 assistant managers) | Everything, for every team, including GPs |

## Scope

**In scope:** rota grid for all teams and GPs; staff profiles; leave allowances and calculations; leave requests and approvals; sickness recording and absence triggers; TOIL and overtime; open shifts; notifications (email and push); reports including payroll; two-way sync with the GP rota app; one sign-in through Practice HR.

**Out of scope (for now):** pay calculation (the payroll bureau does this); wage costs and budgets (kept as a future "could have"); clock in/out; staff availability; swap requests; minimum staffing and skill checks; links to the clinical system, NHSmail/Outlook calendars or Teams; importing data from FindMyShift or Breathe.

## Key dates

- **As soon as possible, early December 2026 at the latest:** ready for managers to start setting up staff, allowances and the 2027 rota.
- **Before Christmas 2026:** staff can request 2027 leave in the app.
- **1 January 2027:** full launch. Rotas and allowances start (start of the leave year). Everything in place.

## Relationship with the existing systems

- **Practice HR** stays the sign-in for all apps. The new system is the **master** for weekly hours, days per week and leave. Practice HR's own leave design (built, not live) is **not** used.
- **GP rota app** stays. GP rotas are also built in the new grid. The two stay in sync both ways; clashes are flagged to managers.

## Glossary (the practice's own terms)

| Term | Meaning here |
|---|---|
| **AG** | The main site |
| **PMC** | The branch site |
| **Manager access** | Permission to build and edit a team's rota, approve its leave and change allowances. Decides who approves leave (not the line manager in Practice HR) |
| **Department** | A tag on a shift from one combined list: teams, roles and tasks together (e.g. Reception AG, Prescriptions, HCA, Salaried GP) |
| **Shift** | Clock times on a day, with an optional unpaid break and department tag |
| **Session** | A GP half-day (AM or PM). Counts as **4 h 10 min** for leave |
| **Scheduled hours** | A shift's length minus unpaid breaks, excluding overtime shifts |
| **Annual leave allowance** | Full-year hours, typed in by a manager |
| **Bank holiday allowance** | Separate full-year hours for bank holidays, typed in by a manager; any deficit or credit moves into annual leave |
| **TOIL** | Time off in lieu — hours from shifts marked "overtime – TOIL", kept in a separate balance |
| **Instance of absence** | One sickness entry (start date to end date) |
| **Trigger 1 / 2 / 3+** | 3 / 4 / 5 or more instances of absence in a rolling 6 months |
| **Long sickness** | One instance lasting longer than 4 calendar weeks (29+ days) |
| **Authorised absence** | Time off agreed by a manager, e.g. appointments (including medical appointments) |
| **SDL** | Example overtyped description for GP study leave ("Training – SDL") |
| **KIT day** | Keeping-in-touch day during maternity/adoption leave |
| **WFH** | Working from home, shown on the rota |
| **Notify staff** | The manager action that sends the saved rota changes to affected staff |
| **Placeholder** | Average-day cost used for leave booked before the rota is set |
| **ARRS** | Additional Roles Reimbursement Scheme (PCN-funded roles) — **none at this practice** |

## Name and logo

- The system is called **AMG Shift Central**.
- **Chosen logo: the dark version** — on a navy background, a white rounded square holding a 3 × 3 grid of navy rota tiles (some faded, like days off), with the **centre tile in amber** ("Central"); next to it "AMG" in heavy white type above "Shift Central" in pale grey-blue (#DDE7EE).
- **Where it's used:** the dark logo is the main logo and sits naturally at the top of the dark navy side panel. The light and stacked versions on the canvas are alternatives for white backgrounds (e.g. printed reports and PDFs); the square **app icon / favicon** (the mark on its own) is used for the phone app and browser tab.
- **Colours:** navy **#143D5C**, amber accent **#F2A33A**, white. **Typeface:** Manrope (fallbacks Segoe UI, Arial). The navy sits naturally with the FindMyShift-style dark navy side panel.
- The logo design canvas is shared separately; the developer exports the files from it.

## How to read this specification

- Each requirement has an ID (e.g. `LEAVE-12`) and a short "why".
- Anything not yet confirmed is marked **[UNCONFIRMED]**.
- Every leave rule in `05` points to worked examples in `06`; each worked example should become an automated test.
- Each document ends with "Not needed, on purpose".
- Where the practice's choice differs from the Practice HR leave design, it says so.

## Not needed, on purpose

- FindMyShift's name, logo or branding (the look and way of working are copied closely; see `03`).
- Statutory pay calculations (SSP, SMP etc.).
- Staff training (the system must be simple enough to pick up without it).
