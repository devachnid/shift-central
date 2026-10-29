# 09 — Reports, integrations and payroll

## Payroll

Today, payroll figures are tracked by hand across several spreadsheets and the bureau is sent the final hours. The system replaces this. **It does no pay calculation** — the bureau does that.

**PAY-01** — A **monthly payroll report** per person for the **calendar month**, showing:
- total hours to pay (hours worked plus paid leave)
- paid overtime, shown separately (TOIL goes to the TOIL balance, not payroll)
- unpaid leave (any entry marked unpaid)
- sickness
- TOIL taken
- actual days of leave taken
- KIT days
- starters and leavers, with leavers' hours over or remaining (LEAVE-14)

**PAY-02** — The report must be ready to send **no later than 7 days before the last day of the month**. It covers the **whole calendar month, using the rota for the remaining days**. Anything that changes after it is sent appears as a **correction on the next month's report**.

**PAY-03** — Format: an **Excel file** a manager downloads.

## Reports

| ID | Report | Contents | Audience | Format |
|---|---|---|---|---|
| REP-01 | **Hours report** | Rota hours minus breaks, per person per week; date range | Managers; staff see their own | Screen + download |
| REP-02 | **Leave report** | Allowance (annual + bank holiday combined), instances, days, deducted, remaining, TOIL; any date range | Managers; staff see their own | Screen + download |
| REP-03 | **Year planner** | All leave for all staff for a year, filtered by type | Everyone (types only — ACC-05) | Screen |
| REP-04 | **Sickness one-pager** | Whole-practice totals, totals by team, then per person: instances in the rolling 6 months, total time off sick, trigger level; chosen date range | Managers | **PDF or Excel**, chosen at download |
| REP-05 | **Leave one-pager** | Leave taken and remaining: practice totals, team totals, then per person | Managers | PDF or Excel |
| REP-06 | **Log-in logs** | Every log-in with date and time | All-teams managers | Screen |
| REP-07 | Dashboard, shifts, staff-by-hour reports | As FindMyShift today | Managers | Screen + download |
| REP-08 | **Budget** (could have, future) | Needs pay rates (FMS item 19) | All-teams managers | — |
| REP-09 | Payroll report | PAY-01 | Managers → bureau | Excel |

**REP-10** — Every figure on a leave report must be explainable from the bookings and logged changes behind it (LEAVE-31).
*Why:* one of the stated failure measures is leave figures not matching the agreed formulas.

## Integrations

**INT-01** — **Practice HR**: sign-in only (one account). No exchange of contract, pattern or leave data.

**INT-02** — **GP rota app**: two-way sync of GP rotas and leave; clashes flagged (ROTA-GP-03, 04).

## Not needed, on purpose

- Statutory pay calculations; wage costs at launch.
- Hours worked vs contracted report.
- Links to the clinical system (EMIS/SystmOne), NHSmail or Outlook calendars, Microsoft Teams, PCN or ICB systems.
- CQC evidence exports.
- A payroll period other than the calendar month.
