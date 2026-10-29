# 05 — Leave policy

These rules apply to **everyone**: all staff groups and all GPs (partners, salaried, trainees). Each rule points to worked examples in `06`.

## Allowances

**LEAVE-01** — Each person has two allowances, both **full-year figures in hours, typed in by a manager** from their contract: an **annual leave allowance** and a **bank holiday allowance**. The system does not work them out from service, role or contract.
*Why:* entitlements vary by individual contract (e.g. 23 days for one person, 285 h for another).
*Tests:* LV-01, LV-02, LV-03. *HR design:* **differs** — the HR design calculates entitlement as weeks × weekly hours with service steps.

**LEAVE-02** — The unit is **hours for everyone, GPs included**. A GP session counts as 4 h 10 min.
*Tests:* LV-19. *HR design:* **differs** — the HR design uses sessions for GPs.

**LEAVE-03** — The leave year runs **1 January – 31 December**, with a per-person override.
*HR design:* **matches** (fixed leave year option).

**LEAVE-04** — Hours are **shown as hours and minutes** everywhere (e.g. 8 h 20 min); calculations are kept exact underneath.
*Tests:* LV-19, LV-04b.

## What leave costs

**LEAVE-05** — A day of leave costs the person's **scheduled hours on the rota for that day**: shift length minus unpaid breaks, **excluding overtime shifts**. A day with no shift costs nothing. For GPs, 4 h 10 min per rota'd session.
*Why:* deductions must reflect individual working patterns.
*Tests:* LV-01, LV-03, LV-12, LV-19, LV-23. *HR design:* **differs** — the HR design uses the dated weekly pattern.

**LEAVE-06** — If leave is booked on a day the rota has not yet been set, it costs the **average day** (weekly hours ÷ days per week) as a **placeholder**, is **recalculated automatically** when the rota is set, and **managers are flagged** to check.
*Tests:* LV-22.

**LEAVE-07** — Anyone with manager access can **override the hours deducted** for any day. Overrides are logged (LEAVE-31).

**LEAVE-08** — A **half day** costs **exactly half the scheduled hours** for that day, with **no rounding**. Breaks make no difference.
*Tests:* LV-04a, LV-04b.

**LEAVE-09** — Leave can be booked as **any number of hours**: start and end times are entered, it costs exactly those hours, and the shift is **shortened** to match.
*Tests:* LV-05. *HR design:* **matches** (partial days in hours).

## Starters, leavers and hours changes

**LEAVE-10** — For starters and leavers, each allowance = **full-year allowance ÷ 52 × weeks on contract in the leave year**. **A part week counts as a whole week.** The result is **rounded once, to the nearest 0.5 h**.
*Why:* the practice's chosen rule; FindMyShift's day-based figure is what is wrong. A monthly rule was considered and rejected.
*Tests:* LV-06a, LV-06b, LV-07a, LV-20. *HR design:* **differs** — the HR design accrues day by day.

**LEAVE-11** — The **bank holiday allowance is pro-rated the same way** (LEAVE-10). Bank holidays falling in the person's period are then deducted as usual, and the deficit or credit moves into annual leave.
*Tests:* LV-11a, LV-07b.

**LEAVE-12** — When contracted hours change mid-year, each side of the change is pro-rated by LEAVE-10 using the old and new full-year allowances, **counting part weeks as whole on both sides** (so the week of the change is counted twice — a deliberate choice), and the **total is rounded once** to the nearest 0.5 h. Leave already booked after the change costs whatever the rota shows on the day.
*Tests:* LV-08a, LV-08b.

**LEAVE-13** — Someone employed for the whole leave year gets **exactly** the full allowance, never more.

**LEAVE-14** — For a leaver, the **hours over or remaining** are shown on their record and on the payroll changes report. Managers are **flagged as soon as the leaving date is entered and again 1 week before** the last day, so untaken leave can be booked. The system does not calculate pay.
*Tests:* LV-07b. *HR design:* **matches** (no pay calculation).

**LEAVE-15** — If an hours change leaves someone already over their new total, the balance shows as negative and **managers are flagged**; nothing is blocked.

## Bank holidays

**LEAVE-16** — The practice is closed on bank holidays. A manager **adds bank holiday leave with the hours to deduct**, prompted by a suggestion: "*[person]* usually works X hours on this day", where X is the **most common scheduled hours on that weekday over the previous 4 weeks**. The manager can accept or change it. This can be done **for everyone at once** (list of all staff with suggestions to check, then confirm) **or one person at a time**.
*Tests:* LV-02, LV-13.

**LEAVE-17** — Bank holidays are deducted from the **bank holiday allowance**. The difference at the end (deficit or credit) **moves into annual leave**. The two allowances are shown **combined** on the leave report.
*Tests:* LV-02, LV-03, LV-13, LV-21. *HR design:* **matches** the "separate pro-rata bank holiday allowance" option.

**LEAVE-18** — A leave booking that includes a bank holiday takes the bank holiday from the bank holiday allowance and the other days from annual leave.
*Tests:* LV-12.

**LEAVE-19** — **Extra one-off bank holidays** have no automatic handling; managers adjust allowances mid-year when one happens.
*Tests:* LV-14.

## Balances and carry-over

**LEAVE-20** — Staff **cannot request more than their remaining balance**. **Managers can override** and book it; the balance then shows as **negative**.
*Tests:* LV-24.

**LEAVE-21** — At the start of each leave year, **managers are flagged** about everyone with **annual leave or TOIL left over**. For each person the manager chooses **carry it all, lose it, or carry part** (typing the amount). The chosen amount is added to the new year automatically.
*Tests:* LV-15a, LV-15b, LV-16.

**LEAVE-22** — There is **no maximum and no deadline** on carried-over leave; it can be used at any time in the new year. Each year starts from the contractual allowance; the year-end flag offers **whatever is left**, wherever it came from, and the manager decides.
*Tests:* LV-15a. *HR design:* **differs** — the HR design has a maximum and optional expiry.

## TOIL and overtime

**LEAVE-23** — Shifts marked **"overtime – TOIL"** add their hours to a **separate TOIL balance**. People book time off against it. Shifts marked **"overtime – paid"** go on the payroll report. Overtime hours never count towards the cost of a day's leave.
*Tests:* LV-16, LV-23.

**LEAVE-24** — TOIL does **not** expire by itself; it is included in the year-end carry-over flag (LEAVE-21).
*Tests:* LV-16.

## Leave types

**LEAVE-25** — Leave types (managers can edit the list):

| Type | Comes out of | Needs approval? | Paid/unpaid choice? | On payroll report? |
|---|---|---|---|---|
| Holiday (annual leave) | Annual leave | Yes | No (paid) | Only for leavers |
| Bank holiday | Bank holiday allowance | No (manager adds) | No (paid) | No |
| TOIL | TOIL balance | Yes | No | No |
| Sick leave | Nothing | No (manager records) | No | Yes |
| Training (incl. study, e.g. "Training – SDL") | Nothing | Yes | No | No |
| Maternity | Nothing | No (manager records) | No | Yes |
| Paternity | Nothing | No (manager records) | No | Yes |
| Adoption / shared parental | Nothing | No (manager records) | No | Yes |
| KIT day | Nothing | No (manager records) | No | Yes |
| Dependants' leave | Nothing | No (manager records) | **Yes** | If unpaid |
| Compassionate | Nothing | Yes | **Yes** | If unpaid |
| Authorised absence (incl. medical and other appointments) | Nothing | Yes | **Yes** | If unpaid |
| Unpaid leave | Nothing | Yes | Unpaid | Yes |
| Unauthorised absence | Nothing | No (manager records) | No | Yes |
| Jury service | Nothing | No (manager records) | No | Yes |

**LEAVE-26** — When booking, the leave type is picked and the **description can be overtyped for that occasion only** (e.g. type Training, shown as "Training – SDL"). The type still decides how it is counted and reported.

**LEAVE-27** — For any type where it could go either way, the manager marks **each entry paid or unpaid**. This is **shown on the rota** (to managers — see ACC-05) and unpaid entries go on the payroll report.
*Tests:* LV-25.

**LEAVE-28** — **Sick during annual leave:** a manager can convert booked annual leave days to sickness; the hours are given back to annual leave and a sickness instance is recorded. **[Adviser to check]**
*Tests:* SICK-03.

**LEAVE-29** — **Long absence:** the allowance is not reduced by sickness or family leave (it is a full-year figure). When someone returns from **long sickness** (LEAVE-44) or maternity, adoption or similar leave, **managers are flagged with their remaining leave**, and they are **marked in the year-end carry-over flag**. **[Adviser to check]**
*Tests:* SICK-02.

**LEAVE-30** — **KIT days** are recorded and go on the payroll report; they do not affect leave balances.
*Tests:* KIT-01.

**LEAVE-31** — Every **manual change** to an allowance, balance or deduction is **logged** with date, who made it, old and new figures, and a typed reason. The log is visible to **managers only**.
*Tests:* LV-14, LV-15b. *HR design:* **matches in spirit** (every figure can be explained).

## Sickness and instances of absence

**LEAVE-40** — **One sickness entry = one instance of absence**, defined by its start and end dates (e.g. 1–13 January = 1 instance). Managers record sickness and can **always edit the dates** to extend or shorten it.

**LEAVE-41** — If a new sickness entry **joins on** to an existing one, the system **warns the manager and offers to extend the existing entry** instead. "Joins on" includes gaps made up **only of days the person does not work**. If the manager goes ahead, it counts as 2 instances.
*Tests:* SICK-04.

**LEAVE-42** — Instances are counted over a **rolling 6 months**. An entry counts if **any of its days** fall within the period.
*Tests:* SICK-01.

**LEAVE-43** — **Triggers:** 3 instances = **Trigger 1**; 4 = **Trigger 2**; 5 or more = **Trigger 3+**. The level shows on the sickness report and profile, and **managers are emailed** when someone reaches a new trigger. (Replaces FindMyShift's Bradford Factor.)
*Tests:* SICK-01.

**LEAVE-44** — **Long sickness** = one instance lasting **longer than 4 calendar weeks**, i.e. 29 days or more counting the first and last day.
*Tests:* SICK-02.

## For the practice's HR / legal adviser to check

- Rounding to the nearest 0.5 h sometimes rounds **down** (165.58 → 165.5). Is that acceptable for the statutory minimum?
- Statutory carry-over rights when leave could not be taken because of sickness or family leave (LEAVE-21/22 leave it to the manager).
- Sickness during annual leave (LEAVE-28).
- Leave during long absence and on return (LEAVE-29).

## Summary of differences from the Practice HR leave design

| HR design decision | Practice's choice |
|---|---|
| Unit per contract type: sessions for GPs | Hours for everyone; session = 4 h 10 min |
| Entitlement = weeks × weekly hours; service steps | Full-year hours typed in by manager; no service steps |
| Accrues day by day | Weeks on contract ÷ 52, part week = whole week, round to 0.5 h |
| Booking costs the dated weekly pattern | Costs scheduled rota hours that day |
| Bank holiday: three options | Separate pro-rata allowance (matches one option) |
| Carry-over maximum and optional expiry; TOIL can expire | No maximum, no deadline; manager decides at year end for leave and TOIL |
| Line managers approve | Anyone with manager access for the team approves |
| Leave held in Practice HR | Leave held in the new system |

## Not needed, on purpose

- Service-related increases.
- Buying and selling leave.
- Carry-over limits and deadlines.
- Automatic handling of extra bank holidays.
- Rules for irregular-hours, bank or term-time workers.
- A monthly pro-rata rule (considered and rejected) and FindMyShift's daily rule.
- Sick allowance and Bradford Factor.
- Return-to-work interview records (kept elsewhere).
