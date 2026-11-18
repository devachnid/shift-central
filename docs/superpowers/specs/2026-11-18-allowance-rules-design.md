# AMG Shift Central and Practice HR: allowances worked out from contracts — design

**Date:** 2026-11-18
**Status:** approved in conversation, section by section; written spec awaiting review
**Repositories:** `devachnid/practice-hr` (part A) and `devachnid/shift-central` (part B). This file is the one copy of the design; each repository gets its own plan.
**Requirements:** `docs/requirements/` as amended. This spec changes LEAVE-01, LEAVE-10 to 12 (for GPs only), PAT-06 and PAT-07 (section 12) on the practice manager's written answers of November 2026 to "Hours and leave allowances: questions for the practice manager". It builds on the Foundation and leave specs (`2026-10-29-foundation-design.md`, `2026-10-31-leave-design.md`) and on Practice HR's foundation spec, whose constraints, access rules, audit and conventions it reuses unchanged unless this spec says so.

Today a manager types every person's two full-year allowances into Shift Central, each year, and types them again when hours change. Contracted hours are typed twice, once in each app. After this spec the contract is entered once, in Practice HR, with its leave terms; Shift Central reads it and works the allowances out, for this leave year and the next, and keeps them in step when the contract changes. A manager checks the figures instead of calculating them.

## 1. The practice manager's answers this is built on

| # | Answer | Where it lands |
|---|---|---|
| 1, 2 | Hours typed in Practice HR only, once it is live with real contracts; it holds only dummy data today. | Sections 3, 5, 11 |
| 3, 5 | Annual leave terms differ by contract and are entered by hand on each record. | Section 4 |
| 4 | A day is a fifth of weekly hours; part-time is pro rata. | Section 6 |
| 6 | Service counts from the start date only; continuous service is not recognised. | Section 6 |
| 7 | A step up in entitlement applies from the next leave year. | Section 6 |
| 8 | Bank holidays: one day each, including any additional bank holiday. | Section 6 |
| 9 | Partners 8 weeks, salaried GPs 6 weeks, each with the bank holidays at 2 sessions each, pro rata on a full-time week of 8 sessions; leave year 1 January; GP trainees' allowances come from NWSSP and stay typed. | Sections 4, 6 |
| 10 | Show a worked-out figure for a manager to accept for the first year, then apply automatically. | Section 7 |
| 11 | Next year's entitlement exists from the start of this year, so leave can be booked ahead at any time. | Section 7 |
| 12 | A change of hours starts a new entitlement from the date of the change. | Section 7 |
| 13 | Round to the nearest half hour. | Section 6 |
| 14 | Compare the figures typed in December with the rule and list the differences. | Section 8 |

## 2. Decisions made in conversation

| Decision | Rationale |
|---|---|
| **The rule is held per contract, in days** (weeks for GPs), with service steps; Shift Central turns it into hours. | The manager's answers 3 and 5: terms differ by contract. Days are what a contract says. |
| **Contracted hours, sessions and leave terms live in Practice HR, on the contract.** Shift Central reads them. | Practice HR goes live first and is where a contract is entered; one place to type. |
| **Shift Central does all leave arithmetic.** Practice HR holds terms and never works out an hours figure. | One implementation of each rule; Practice HR's own leave is switched off (`SHIFT_CENTRAL_URL`). |
| **A contract takes its terms from its contract type unless it has its own**, or is marked not worked out. Nothing is pre-filled. | Most contracts of a type share terms; some differ; GP trainees are told theirs by NWSSP. |
| **A worked-out figure counts straight away**, is marked "not yet checked" and is listed for a manager until confirmed or changed. | Staff can book at once; a manager still sees every figure in the first year (answer 10). |
| **A typed figure is kept**, and listed while it differs from the contract. | A manager's decision is never silently overwritten; the list is also answer 14's comparison. |
| **GP figures are whole sessions, not rounded to the half hour**, full-year and part-year alike. | A session is 4 h 10 min. Rounding 64 sessions (266 h 40 min) to 266 h 30 min would leave a partner ten minutes short of the last one. The practice manager confirmed whole sessions for a GP who starts or leaves in the year (18 November 2026). |
| **Days per week stays typed in Shift Central.** | It is used only for the leave placeholder (PAT-05); deriving it from Practice HR's working patterns is a larger change no one asked for. |
| **No email about figures to check.** The Health card carries them. | It is setup work a manager does when they choose, as "needs hours and allowances" is today. |

## 3. Architecture

```
Practice HR                                   Shift Central
-----------                                   -------------
ContractType: usual leave terms               people.Contract (a copy of the feed)
Contract: weekly amount, dates, terms   -->   entitlement service: full-year figures per period
GET /api/v1/people (adds "contracts")         Allowance rows: worked out / typed / copied, checked or not
                                              existing pro-rata (GPs to whole sessions), statements, bookings
```

- **Practice HR** owns: who is employed, each contract's dates, weekly hours or sessions, its type's full-time week, and its leave terms.
- **Shift Central** owns: days per week, the bank holiday list, every allowance figure, pro-rata (LEAVE-10 to 13), bookings, balances and year end.
- The feed only gains a field. A Shift Central that does not know it ignores it; a Practice HR that does not send it leaves Shift Central exactly as it is today.

## 4. Part A: Practice HR, leave terms on the contract

### 4.1 Models

`people.ContractType` gains:

- `leave_base`: decimal, 5 digits, 2 places, blank allowed. The usual full-year annual leave for a contract of this type, in **days** for an hours type and **weeks** for a sessions type. Blank means the type has no usual terms.
- `ContractTypeLeaveStep(contract_type, after_years, total)`: "after `after_years` complete years the total becomes `total`", in the same unit. One row per `after_years` per type.

`people.Contract` gains:

- `leave_terms`: `usual` (default, "Usual for the contract type"), `own` ("Own terms") or `none` ("Not worked out").
- `leave_base`: as on the type; required when `leave_terms` is `own`, cleared otherwise.
- `ContractLeaveStep(contract, after_years, total)`: as on the type; allowed only with `own`.

Bank holidays are not a term: the rule is the same for everyone of a unit (section 6).

### 4.2 Rules, in `people/services/leave_terms.py`

- `resolved(contract)` returns the terms in force for a contract, `{"base", "steps"}`, or `None`: the contract's own for `own`; the type's for `usual` when the type has a base; `None` for `none` and for `usual` on a type with no base.
- A base is greater than 0 and at most 99. `after_years` is 1 or more. Totals rise with the years and the first is greater than the base. Steps need a base. A contract that is not `own` holds no base and no steps of its own.
- Terms are not dated. A change of terms from a date is a new contract from that date, which is how any contractual change is already recorded; editing the terms of an existing contract corrects them for the whole contract.
- Every change is audited through `people.services.audit`, as contract changes are.

### 4.3 Screens (the admin)

- **Contract type** page: "Usual annual leave" (labelled days or weeks by the type's unit) and a steps table, "After (complete years)" and "Total becomes". Help text: used by AMG Shift Central to work out allowances; leave blank for a type whose allowances are typed there.
- **Contract** (the inline on an employment): a read-only "Leave terms" line, for example "Usual for Reception: 22 days; 23 after 1 year; 25 after 5 years", "Own: 25 days" or "Not worked out", with a "Change leave terms" link. The choice itself is not in the inline: existing contracts there can only be ended, never edited.
- **Contract's own page** (new, reached from the inline, as a working pattern's page is): the choice, the base and the steps table. HR admins only, as contracts are.
- Nothing is added to what staff see. The leave screens switched off by `SHIFT_CENTRAL_URL` are not touched, and Practice HR's own leave policies ignore these terms whether or not that setting is on.

### 4.4 The feed

Each record of `GET /api/v1/people` gains `contracts`: every contract of the employment the record already describes, oldest first.

```json
"contracts": [
  {"id": 41, "contract_type": "Reception", "unit": "hours",
   "from": "2025-06-01", "to": null,
   "weekly_amount": "22.50", "full_time_weekly": "37.50",
   "leave": {"base": "22.00", "steps": [{"after_years": 1, "total": "23.00"}]}}
]
```

`leave` is `null` when `resolved()` is `None`. `base` and `total` are days when `unit` is `hours` and weeks when it is `sessions`. The existing fields (`contract_type`, `unit`, `employment`, `positions`) are unchanged. `docs/admin/api.md` documents the field.

### 4.5 The GP full-time week

The practice's full-time GP week is 8 sessions, not 9. A data migration changes `full_time_weekly` from 9 to 8 on Partner, Salaried GP and GP trainee where it is still 9; the demo seed, the field's help text and `docs/admin/people.md` follow. FTE shown for GPs changes with it.

## 5. Part B: Shift Central, what is stored

### 5.1 `people.Contract`, a copy of the feed

`person`, `hr_id` (unique), `type_name`, `unit`, `from_day`, `to_day`, `weekly_amount`, `full_time_weekly`, `leave_base` (null when there are no terms), `leave_steps` (a list of `[after_years, total]`). The sync replaces a person's rows with what the feed sends, in the sync's transaction. Rows are not audited here: Practice HR audits the contract, and Shift Central audits every allowance figure that results.

- A feed record with no `contracts` key leaves the person's copy alone (an older Practice HR).
- A record with an empty list empties it.
- A contract that is malformed (a missing or unreadable date, amount or step) fails the record as any bad field does today: the run fails with "record N in the feed: missing or bad contracts", and the previous data stands.
- A contract that is well formed but cannot be worked out is copied as sent. Two cases: steps that do not rise, which Practice HR refuses to save, so this is a guard and not a path anyone should reach; and a weekly amount of 0, which Practice HR allows (a bank contract with no fixed hours). Either way the year is not worked out. Only the first is listed (section 8); a bank worker's allowance is simply typed.

### 5.2 `people.Allowance` gains

- `source`: `typed` (default; every existing row), `worked_out` or `copied`.
- `checked_at`, `checked_by` (both null until a manager confirms; `checked_by` null with `checked_at` set means the app confirmed it itself, section 7.6).
- `annual_hours` and `bank_holiday_hours` widen from 2 to 4 decimal places, so a whole number of GP sessions is exact to the second (64 sessions is 266.6667 h, which is 960 000 s). Typed figures stay at 2 places.

A row **needs checking** when its source is `worked_out` or `copied` and `checked_at` is null.

### 5.3 `leave.LeaveSetting` gains

`allowances_need_checking`, on by default.

### 5.4 Weekly hours

For a person whose hours contracts in force today (on the start date for a starter) add up to more than 0, `Person.weekly_hours` is an HR field: the sync sets it to that sum, audited "from Practice HR", and nothing else writes it. The profile shows it read-only with "from Practice HR". `apply_due_hours_changes` copies only days per week for such a person. A GP's weekly hours stay empty, as now. A person with no copied contract, or whose only contracts in force are for 0 hours (bank staff), is typed exactly as today.

## 6. The arithmetic (`leave/services/entitlement.py`)

Pure functions over a person's copied contracts, their start date and the bank holiday list. All figures are **full-year**; pro-rata for starters, leavers and changes stays in `prorata.py`, with the one change in section 6.1.

**Service.** Complete years from the person's start date to the first day of the leave year (a year the person starts in has none). The annual leave figure is the base, or the total of the highest step whose `after_years` is not more than the service. It is fixed for the whole leave year, so a step always starts with a leave year (answer 7).

**An hours contract**

- Annual leave = days × weekly hours ÷ 5.
- Bank holidays = the number of bank holidays in the leave year × weekly hours ÷ 5. The count is `BankHoliday` rows from the year's first day to its last, so an added bank holiday is included.
- Each of the two is rounded to the nearest half hour, a quarter hour rounding up.

**A sessions contract**

- Annual leave = weeks × sessions per week, in sessions.
- Bank holidays = bank holidays in the year × 2 × sessions per week ÷ the type's full-time week, in sessions.
- Each is rounded to the nearest whole session, a half rounding up (whole weeks and whole sessions need no rounding), then held as sessions × 4 h 10 min.

**Several contracts in force together** are each worked out and rounded, then added. Practice HR does not allow contracts of different units to overlap.

**Worked examples**, with 8 bank holidays in the year. These are the unit tests, figure for figure.

| Person | Terms | Annual leave | Bank holidays |
|---|---|---|---|
| 37.5 h, 1 complete year | 22 days; 23 after 1 year | 172 h 30 min | 60 h |
| 22.5 h, under 1 year | 22 days; 23 after 1 year | 99 h | 36 h |
| 18.75 h, 1 complete year | 22 days; 23 after 1 year | 86 h 15 min, rounded to 86 h 30 min | 30 h |
| Partner, 6 sessions | 8 weeks | 48 sessions, 200 h | 12 sessions, 50 h |
| Salaried GP, 8 sessions | 6 weeks | 48 sessions, 200 h | 16 sessions, 66 h 40 min |
| Salaried GP, 5 sessions, 9 bank holidays | 6 weeks | 30 sessions, 125 h | 11.25, rounded to 11 sessions, 45 h 50 min |

Service: a start date of 1 June 2025 is 1 complete year on 1 January 2027, so 2027 is at the 1-year step all year; 3 years are reached on 1 June 2028 and a 3-year step applies from 1 January 2029.

### 6.1 Part-year figures for a GP

LEAVE-10 to 12 round a pro-rated allowance once, to the nearest half hour. For a GP (`Person.is_gp`) `prorata.allowance` rounds it once to the nearest **whole session** instead (4 h 10 min, a half session rounding up), for both allowances and whether the full-year figure was worked out or typed. Everything else in the rule is as it is: part weeks count whole, the week of a change counts on both sides, and the total is capped at the largest full-year figure, so a GP employed all year still gets exactly the full allowance.

A salaried GP on 8 sessions (200 h and 66 h 40 min) who starts on 1 July 2027 is on contract for 27 weeks:

| Allowance | 27 ÷ 52 of the full year | Today | After this spec |
|---|---|---|---|
| Annual leave | 103 h 51 min, 24.92 sessions | 104 h | 25 sessions, 104 h 10 min |
| Bank holidays | 34 h 37 min, 8.31 sessions | 34 h 30 min | 8 sessions, 33 h 20 min |

Staff on hours contracts are not affected.

**The working.** Each figure comes with a line of text, for example "23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min" or "8 bank holidays × 2 sessions × 6 ÷ 8 = 12 sessions = 50 h". It is shown beside the figure and is the note on the audit entry when the figure is written.

**Periods.** `periods(person, year)` returns the year as a list of `(from_day, annual, bank_holiday, weekly_hours)`: the first from the contracts in force on the year's first day (the start date, for someone who starts in the year), then one from each later day in the year on which the contracts in force change (a contract starts, or the day after one ends), up to the person's end date. A period whose figures and weekly hours equal the one before is dropped. A day with no contract in force while the person is still employed starts no period: the earlier figures carry on and the person is listed (section 8). A contract's dates are read within the person's start and end dates: Practice HR does not guarantee a contract sits inside its employment, so one that starts before the start date counts from the start date.

**Not worked out.** `periods` returns nothing, with a reason, when: the person has no copied contract; a contract in force in the year has no terms, a weekly amount of 0, or steps that do not rise (5.1); or the year holds both an hours and a sessions contract.

## 7. How figures are created and kept in step

`entitlement.refresh()` runs after each good read of Practice HR, before `apply_due_hours_changes`, in its own transaction. A failure adds "allowances failed; see the journal" to the run's message, as the other steps do, and changes nothing.

### 7.1 Which years

For each current person and starter: their current leave year and the next (`years.years_for`), leaving out a year that ended before launch (`yearend.LAUNCH`, so 2026 is never worked out). Next year's rows therefore exist from the first day of this year (answer 11).

### 7.2 A person whose year is worked out

Each period is matched to the Allowance row with the same `from_day`:

| Row | What refresh does |
|---|---|
| None | Creates it, `worked_out`. A period after the first carries the new weekly hours and the days per week then in force. |
| `worked_out`, same figures | Nothing. |
| `copied`, same figures | Sets `worked_out`; its check is left as it is. |
| `worked_out` or `copied`, different figures | Writes the new figures, sets `worked_out`, clears `checked_at` and `checked_by`. |
| `typed`, same figures | Sets `worked_out`, checked. It follows the contract from now on. |
| `typed`, different figures | Nothing. It is listed (section 8). |

A `worked_out` row after the year's first whose day is no longer the start of a period (the contract's date was corrected) is deleted. A typed row is never deleted or changed.

Every write is audited with no actor and the note "from Practice HR" followed by the working.

### 7.3 Changes during the year

A new contract or a change of weekly hours or sessions is a new period from the contract's start date (answer 12), which refresh adds as a dated row: what a manager does by hand today with "Add hours change". Pro-rata does the rest, part weeks whole on both sides. For a person whose year is worked out, "Add hours change" is not offered (the statement says "Hours changes come from Practice HR.") and the service refuses it with "Enter the new contract in Practice HR".

A change to the terms alone alters the figures of every period in each year refresh covers, and they go back to "not yet checked".

### 7.4 Finished years

Refresh never writes to a leave year that has ended. A contract change dated inside the previous leave year is listed (section 8) for a manager to put right with an adjustment, as last year's statement is corrected today.

### 7.5 A person whose year is not worked out

- If this year has allowance rows and next year has none, next year's first row is created with the full-year figures of this year's last row, `copied`. It needs checking. Nothing is copied forward until at least one person has a copied contract, so an app that Practice HR sends no contracts to behaves exactly as today.
- Nothing else is written. A change of contract inside the year is listed, for a manager to add the hours change by hand.
- GP trainees, anyone whose contract is "Not worked out", and anyone not yet in Practice HR with a contract are all this case.

### 7.6 The setting

While `allowances_need_checking` is on, a row refresh creates or changes needs checking. Once it is off, such rows are written already checked (`checked_at` set, `checked_by` null) and rows waiting are left for a manager to confirm. A dated row (a period after the year's first) that refresh creates or changes needs checking whatever the setting: the contract cannot give its days per week, so a person must look. The year's first row follows the setting. Typed figures that differ are listed either way. All-teams managers change the setting, on the Leave settings page; other managers see it.

### 7.7 What a manager does to a row (`people/services/profiles.py`)

Whoever can manage the person (`access.can_manage`; no one manages themselves):

- **Confirm**: sets `checked_at` and `checked_by`. Audited.
- **Change**: types both figures with a reason, as an allowance change needs today. The row becomes `typed`. On a dated row, Change also takes days per week, at any time; changing only the days per week leaves the figures, the source and the check as they are.
- **Use the worked-out figure**, on a typed row that differs: writes the worked-out figures, `worked_out`, checked by that manager. On a typed dated row the contracts have no change for, it removes the row.
- **Days per week** can also be corrected as a dated row is confirmed.

## 8. The lists, and the Health card

`entitlement.review(user)` builds them from the rows and the copied contracts of the people the user manages, on demand; nothing extra is stored. The Health card gains four lines, each with its count and a link to `/staff/allowances/`.

| Line | Who is on it |
|---|---|
| **Allowances to check** | Rows that need checking. Also a not-worked-out person with a contract change in the year and no row from that day ("hours changed on 1 June; add the hours change"). |
| **Allowances that differ from the contract** | Typed rows in a worked-out year whose figures are not the rule's, both shown; a typed dated row on a day the contracts do not change; a finished previous year whose rows are not what the contracts now give. |
| **Bank holidays not entered** | A leave year refresh covers with no bank holiday in the list. Empty, like the fourth list, until at least one person has a copied contract. |
| **Contracts to look at in Practice HR** | A current person or starter with no copied contract in force today, or none from a day in the year ("no contract from 1 July"); a person whose contract has steps that do not rise (5.1). Not shown until at least one person has a copied contract, so it stays empty before Practice HR sends any. |

**The page** `/staff/allowances/` (managers) has the four lists, a Team box (the report filters' partial), and for each row: the person, year, from-day, the two figures, the working, and the buttons of section 7.7. "Confirm all shown" confirms every row on the "to check" list as filtered. It posts each row's id and figures; a row whose figures have changed since the page was drawn is skipped and the page says how many.

**The December figures.** Managers type 2027 in December for anyone whose contract and terms are not yet in Practice HR. When they arrive, a typed figure equal to the rule becomes worked out, and one that differs appears in the second list. That list is the comparison of answer 14.

**The profile**, Pay & time off: each year's figures show "worked out, not yet checked", "worked out, checked by … on …", "typed" or "copied from last year, not yet checked", with the working and the buttons. Weekly hours are read-only "from Practice HR" when section 5.4 applies. The statement's allowance lines gain the working for managers.

**Staff** see their figures as now, with no state and no working. A figure that needs checking counts in full.

## 9. When things go wrong

| Situation | What happens |
|---|---|
| Practice HR cannot be reached, or the feed is bad | The run fails as today; figures and the copy of contracts stay as they were. |
| Practice HR does not send `contracts` | Everything is typed, as today. |
| A year has no bank holidays entered | The bank holiday figure is 0, and nothing is deducted either; the Health card says so. Entering them changes the figure at the next read, and a confirmed row goes back to "not yet checked". |
| A figure drops below what is booked | Nothing is cancelled. The person, a GP included, is on the Health card's existing "below zero" line (*Negative leave balances*). |
| A contract ends with nothing after it, the person still employed | The earlier figures carry on; the person is on "Contracts to look at in Practice HR". |
| Steps that do not rise reach Shift Central | That person's year is not worked out and their rows are left alone; they are on "Contracts to look at in Practice HR". |
| A contract with a weekly amount of 0 (bank staff) | That person's year is not worked out; their allowance is typed, and they are not listed. |
| A person moves between hours and sessions inside a year | That year is not worked out; its rows stay as they are and are typed. |
| Refresh fails for one person | That person is logged by id and skipped; the rest are done; the run's message says "allowances failed; see the journal". |

Log lines carry ids and counts, never names, figures or terms.

## 10. Testing

- **Arithmetic**: the table in section 6, the service example, rounding at the quarter hour, a fractional session count, the GP part-year table in 6.1 (and an hours person's part-year figure unchanged), two contracts in force together, and each "not worked out" reason.
- **The feed**: both repositories hold the same file, `tests/data/people_feed.json`. Practice HR tests that a fixed set of people produces it exactly; Shift Central tests that it reads it. A change to the feed changes the file in both.
- **Refresh**: each row of the table in 7.2; a mid-year contract; a corrected contract date; terms changed; the setting off; a finished year untouched; copy-forward; pinned clocks across 1 January for both years.
- **Practice HR**: the validation rules of 4.2, `resolved()` for each choice, the admin pages, the 9 to 8 migration, audit entries.
- **Screens**: the Health card counts, the page's permissions (a team manager sees only their teams; no one confirms their own), "Confirm all shown" skipping a changed row, and one browser test that confirms a figure.
- **Unchanged behaviour**: with no copied contracts every existing test passes untouched, except any that pins a GP's part-year figure to the half hour.

## 11. Order of work

1. **Practice HR** (one pull request): section 4. It can go in before go-live, so staff are loaded with their terms from the start.
2. **Shift Central** (one pull request): sections 5 to 9, the guide (`docs/admin/leave.md`, the staff page of the admin guide) and section 12's requirement changes.
3. **The go-live checklist** gains a line in stage 3: set each contract type's usual leave terms before loading staff, and leave GP trainee blank.

Nothing needs switching on. Shift Central starts working figures out for a person at the first read after their contract and terms are in Practice HR.

**Before part B is deployed to production**, Practice HR must hold the practice's real contracts and none of its dummy data. From the first read, anyone with a copied contract has their weekly hours set from it (5.4), so a dummy contract would overwrite hours a manager typed.

## 12. Requirement changes

- **LEAVE-01** becomes: each person has two full-year allowances in hours. They are worked out from the person's contract and its leave terms, held in Practice HR, and a manager checks them; where a contract has no terms a manager types them.
- **LEAVE-10, 11 and 12** gain: for a GP the single rounding is to the nearest whole session (4 h 10 min), not the nearest half hour.
- **PAT-06** becomes: a change of hours is entered as a new contract in Practice HR from its date; Shift Central works out the new allowances from that date. Where allowances are typed, the manager adds the hours change as now.
- **PAT-07** becomes: Practice HR is the master for contracts, weekly hours or sessions, and leave terms. Shift Central is the master for days per week, allowances, leave and balances. Practice HR's built-in leave design is not used.
- **New decisions** D-34 to D-39 in `12-decisions-and-open-questions.md`: terms per contract in days or weeks with service steps from the start date; a step applies from the next leave year; bank holidays one day each, 2 sessions for a GP on a full-time week of 8; a worked-out figure counts at once and is checked by a manager, automatic later by a setting; next year's allowance exists from the start of this year; a GP's allowances are whole sessions, part-year included.
- A postscript in `2026-10-29-proposed-amendments.md` records the change for the practice manager.

## 13. A question for the practice manager, not blocking

**A GP bank holiday figure that is not a whole number of sessions** (a 5-session GP in a year with 9 bank holidays, 11.25) is rounded to the nearest whole session here, as a part-year figure is (6.1). Say if it should always round up.

## 14. Not in this spec

- Deriving days per week from Practice HR's working patterns.
- Any change to pro-rata beyond 6.1, or to costing, carry-over or year end.
- Recognising continuous service, or a service date other than the start date.
- Practice HR's own leave policies, pots and ledger: left as they are, switched off.
- Matching GPs between the apps by employee id instead of email.

## 15. As built (Shift Central, part B)

Built as designed, with these choices where the text above left room or met the code.

- **The year's first figures are always dated the leave year's first day** (6, Periods), for someone who starts later in the year too: the year's first Allowance row always is, and pro-rata cuts it to the start date. When no contract is in force on that first day (the start date, for a starter) the year is not worked out and the person is listed with "no contract from …".
- **A GP whose weekly shares already reach the largest full-year figure gets exactly that figure** (6.1). Without it a typed figure that is not a whole number of sessions (55 h is 13.2 sessions) would round down for someone employed all year, against LEAVE-13. A GP's stored figure is also read to the whole second before it is shared out, so 58.3333 h is the 14 sessions it stands for and half a session is a true tie.
- **A dated row made by refresh is marked as already applied** (5.4, 7.2): its weekly hours are Practice HR's and its days per week are a copy, so `apply_due_hours_changes` has nothing to copy from it. Days corrected on a dated row, beside Confirm or with Change, go onto the person at once if the row's day has come and no later change is in force, and on the day otherwise. Only a dated row that carries weekly hours takes days per week: costing reads its average day from such a row.
- **A removed dated row is audited against the person**, as "allowance from 1 Jun 2027", so the line stays in their History.
- **Weekly hours are typed whenever no hours contract is in force** (5.4), not only for bank staff: someone between contracts keeps the box too, and the sync leaves their hours alone until a contract for more than 0 hours is in force again.
- **"Add hours change" is hidden by the leave year the statement is showing** (7.3): where that year is worked out the statement says "Hours changes come from Practice HR."; on a year that is not (a year typed before the contract arrived) the link is still offered, and the service refuses a day in a worked-out year whichever way it is reached.
- **The profile's year boxes show the year's first row.** They used to start from the year's last row while saving to its first, which a refresh-made dated row would have tripped over. A stored four-place figure is shown to two places in the boxes, and saving it back untouched is no change.
- **The setting is a choice, not a tick box** (7.6), so a post that does not carry it leaves it alone.
- **A finished year is compared, never written** (7.4): the previous leave year is listed when its rows are not the periods the contracts now give, and a row of it still waiting can still be confirmed. "Use the worked-out figure" is refused for a year that has ended.
- **Order of tasks**: models before the GP rounding (its tests need 66.6667 stored), and the Health card's lines with the page they link to.
- **"Use the worked-out figure" is offered on any typed row that differs** from what the contracts give, the year's first or a dated one, on the page and on the profile.
- **The page lists the viewer's own rows without buttons** (8), for another manager to act on; nobody confirms or changes their own.
- **`sound()` also rejects a base of 0 or less and a sessions full-time week of 0** (5.1), besides steps that do not rise: either would divide by nothing or give nothing.
- **A person whose leave year does not start on 1 January has their 2026/27 year worked out**, because it ends after launch (7.1): only a year that ended before 1 January 2027 is left out.

After the whole-branch review (November 2026):

- **A GP below zero is on *Negative leave balances*** (9). GPs' figures are worked out unattended now, so a GP in deficit must show; *Needs hours and allowances* still leaves GPs out.
- **`hr_sync --dry-run`** (`hr_sync.preview()`): the feed is applied to people, contracts and weekly hours and the allowances refreshed, inside one transaction that is always rolled back, with no leaver flag, email, push or SyncRun. It prints counts only, read from the audit entries the transaction wrote: people in the feed, weekly hours set from a contract, allowance rows created, changed, taken over from typed and removed, and whether refresh failed for anyone. The setup guide's first-run procedure uses it, with a backup and a back-out.
- **A dated row refresh makes or rewrites always waits for a manager** (7.6), and a placeholder day on a dated row with weekly hours but no days per week uses the person's days per week, instead of costing nothing.
- **A typed row is compared with the rule at two decimal places** (7.2, 8), as a manager types it. Equal there, it is adopted as before and takes the rule's exact four-place figures: a GP's 66.67 becomes 66.6667, 16 whole sessions. Every other row is compared exactly.
- **Change refuses new figures for a leave year that has ended** ("That leave year has ended; correct it with an adjustment") and is not offered there; days per week alone, and Confirm, still work.
- **The lists and copy-forward are gated on anything having come from Practice HR**: a copied contract, or a row worked out from one. Emptying every contract after figures were worked out leaves the lists on, with the people under *Contracts to look at*. With nothing ever copied or worked out, everything is as before.
- **A worked-out row in a year the contracts no longer give a figure for** is left as it is, its check included, and the person is listed under *Contracts to look at* ("the 2027 allowance was worked out, but the contracts no longer give a figure (…)"). Change with the same figures and a reason takes it over as typed; anywhere else the same figures are no change.
- **The Health card counts only rows the viewer can act on** for *Allowances to check* and *Allowances that differ*; the page still lists the viewer's own rows without buttons.
