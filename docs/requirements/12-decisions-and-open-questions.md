# 12 — Decisions and open questions

All decisions were made by the practice manager during the interview on **29 October 2026**.

## Decisions

| # | Decision | Reason | Ref |
|---|---|---|---|
| D-01 | Leave approval and rota editing follow **manager access**, not the Practice HR line manager | Simpler; access is shared | PEOPLE-05 |
| D-02 | Practice manager and assistant managers have manager access to **all teams**; lead nurse and head pharmacist to their own | Cover and oversight | PEOPLE-04 |
| D-03 | Practice manager's own leave is recorded without approval | Stated preference | PEOPLE-07 |
| D-04 | One combined department list (teams, roles and tasks) | Matches current use | ROTA-02 |
| D-05 | Rotas laid out by hand for a year or more by copy and paste; current rotation not recorded | Practice will redesign the rotation | ROTA-07 |
| D-06 | No minimum staffing or skill checks | Managers judge it themselves | `02` |
| D-07 | GP rotas built in the new grid; two-way sync with the GP rota app; clashes flagged | Need GPs for leave, hours, training | ROTA-GP-01–04 |
| D-08 | Rota changes saved quietly; staff told on "notify staff" | Avoid flooding staff while planning ahead | ROTA-09 |
| D-09 | Adding time off removes (or shortens) the shift | No overlap of shifts and leave | ROTA-10 |
| D-10 | Staff details typed into the new system; new system is master for hours and leave; Practice HR leave design not used | Practice manager's preference | PAT-07 |
| D-11 | Leave in **hours** for everyone; GP session = 4 h 10 min | One unit for all | LEAVE-02 |
| D-12 | Allowances typed in by managers as full-year hours (annual + separate bank holiday) | Entitlements vary by contract | LEAVE-01 |
| D-13 | A day costs **scheduled rota hours**, excluding overtime; average day only as placeholder | Reflects individual working patterns | LEAVE-05, 06 |
| D-14 | Starter/leaver: **weeks ÷ 52, part week = whole week, round once to 0.5 h**. Monthly rule and FindMyShift's daily rule rejected | Practice's chosen formula | LEAVE-10 |
| D-15 | Hours change: part weeks whole on both sides (53 weeks counted) | Consistent with starter rule | LEAVE-12 |
| D-16 | Half day = exactly half the scheduled hours, no rounding | Simple and fair | LEAVE-08 |
| D-17 | Bank holiday allowance pro-rated like annual leave; deficit/credit into annual leave | Matches practice's existing method (Staff E email) | LEAVE-11, 17 |
| D-18 | Carry-over (leave and TOIL) entirely the manager's decision at year end; no limits | Flexibility | LEAVE-21, 22 |
| D-19 | Bradford Factor replaced by instances of absence, triggers 3/4/5+ in rolling 6 months | Current practice policy | LEAVE-40–44 |
| D-20 | Long sickness = longer than 4 calendar weeks | Easier than calendar months | LEAVE-44 |
| D-21 | Staff can't exceed balance; managers can override | Control | LEAVE-20 |
| D-22 | Blackout periods only; no maximum-off or notice periods | Only restriction needed | REQ-08 |
| D-23 | Cancelling approved leave needs approval; shift restored | Control | REQ-10 |
| D-24 | No swap request feature; managers edit the rota | Swaps agreed between staff | REQ-15 |
| D-25 | Colleagues see leave type only | Privacy | ACC-05 |
| D-26 | Auto log-out after 10 minutes | Shared PCs | ACC-09 |
| D-27 | Email **and** push notifications | Staff use phones | NOTIF-01 |
| D-28 | Payroll report for the calendar month, due 7 days before month end; later changes as corrections | Bureau deadline | PAY-02 |
| D-29 | No data import; launch 1 Jan 2027; 2026 carry-over and sickness entered by hand | Clean start at leave-year start | MIG-01–05 |
| D-30 | No parallel running; no training | FindMyShift not in use; simplicity | MIG-06, 07 |
| D-31 | Visuals and functionality very close to FindMyShift, screen by screen; AMG Shift Central name and logo | Staff know it; no training; stated failure measure | FMS-00 |
| D-33 | System named **AMG Shift Central**; the **dark logo** chosen as the main logo (described in `00`) | Practice manager's choice | `00` |
| D-32 | All documents and worked examples (incl. LV-22 to LV-25) approved by the practice manager | Review complete | All |

## Open questions

| # | Question | Who can answer | Blocks |
|---|---|---|---|
| Q-01 | Is rounding to the nearest 0.5 h acceptable when it rounds **down** (e.g. 165.58 → 165.5)? | Practice's HR / legal adviser | LEAVE-10, 11, 12 |
| Q-02 | Statutory carry-over rights after sickness or family leave — does manager discretion meet them? | HR / legal adviser | LEAVE-21, 22 |
| Q-03 | Sickness during annual leave, and leave during long absence — do the rules meet the law? | HR / legal adviser | LEAVE-28, 29 |
| Q-04 | What is the fallback if the system isn't ready for set-up by early December 2026? | Practice manager and developer | MIG-02 |
| Q-05 | Staff E: confirm the 17 h bank holiday deficit against their rota hours | Practice manager | LV-21 |
| Q-06 | Placeholder leave: anything special if the recalculated cost is very different? | Practice manager | LEAVE-06 |
| Q-07 | Who, if anyone, should be told about the practice manager's own leave? | Practice manager | PEOPLE-07 |
| Q-08 | How to display half-minutes (e.g. 2 h 37½ min) | Developer (check with practice manager) | LEAVE-04 |
| Q-09 | Confirm Practice HR's built-in leave design stays switched off | Developer | PAT-07 |
| Q-10 | Confirm the GP rota app stops reading time off from FindMyShift and uses the new system | Developer | ROTA-GP-05 |
| Q-11 | Should a sickness *reason* be recorded at all, and if so who sees it? (Not discussed) | Practice manager | ACC-10 |
| Q-12 | The rota relies heavily on colour; no accessibility needs are known today | Practice manager (if needs arise) | FMS items 7, 10 |

## Action

- The FindMyShift screenshots document contains real staff names and one person's personal contact details and date of birth. **Redact it before sharing with the developer.**
