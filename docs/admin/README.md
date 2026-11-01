# Admin guide

Reference for everything a manager or the superuser can set in AMG Shift
Central. One page per area, every field explained: what it does, what depends
on it, and what goes wrong if it is set incorrectly.

The `README.md` in the project root has the *sequence* for installing the app
and the commands. [Setting up](setup.md) is the go-live order for the practice.
This is the *reference* for what each setting means once you are in there.

| Page | Covers |
|---|---|
| [People](people.md) | Teams, who a person is and what Practice HR owns of them, the fields typed here, the profile pop-up's tabs and who sees each, hours, the leave year and the two leave allowances, the leave statement, the own-leave permission, notes, the Staff list and its download |
| [Departments](departments.md) | The list of departments, colours, order, archiving instead of deleting |
| [Access](access.md) | The three roles, where each is set, what each can see and do (leave included), the Permissions link and its own-leave tick, sessions and signing out, the two logs |
| [The rota](rota.md) | The grid, typing a shift and what the parser reads, the right-click menu, copying weeks, templates, overtime, notify staff, options and filters, time off on the grid, the hours report, who's in today, the phone view, GP sessions |
| [Leave](leave.md) | Allowances and hours changes, what a day costs, requesting and booking, approving, cancelling and editing, adjustments, bank holidays, blackouts, leave types, the statement and how to read it, the year planner and the leave report, the emails and the reminder, GPs, and what is not built yet (push, repeating time off, the approval variants, imports) |
| [Absence and payroll](absence.md) | Recording sickness and the join-on warning, instances and triggers, converting holiday to sickness, the past schedule section for 2026, the sickness and leave summaries (PDF or Excel), the leaver, return and year-end flags, the payroll report (each column, Mark as sent, corrections), the emails and the daily command |
| [The Practice HR and GP feeds](sync.md) | Practice HR: what the fifteen-minute sync changes and never changes, the Health card's figures (people and leave) and what to do about each, Sync now, running it by hand. The GP rota app: sessions read every fifteen minutes, the unmatched list; and GP leave served to the rota app, with its token |
| [Setting up](setup.md) | The go-live order, then backups and restore |

## The mental model

**Practice HR owns the person; Shift Central owns how they are scheduled.**
Names, emails, teams, start and finish dates and whether someone is a GP arrive
from Practice HR every fifteen minutes and cannot be edited here. Job title,
colour, hours, days per week, leave allowances and notes are typed here and are
never touched by the feed. A mistake in the first group is put right in
Practice HR; a mistake in the second, on the profile.

**Nothing is deleted.** There is no delete button on any page. A leaver stays
on the Staff list under *Left*; a department is archived; a manager's access is
revoked, and the record that it was granted stays in the Activity log.

**Leave is counted in hours, and worked out, not typed.** A person's allowance is pro-rated for
the weeks they are employed; a day off costs what the rota says they were due to work; what is left
is the allowance plus adjustments less the days approved, and the statement lists every line. Nobody
types a balance. See [Leave](leave.md).

**Every change to a person is written down.** Each field changed on a profile,
each allowance, each booking, approval and adjustment of leave, each manager grant, each department
edit and each change the feed makes writes an entry that says who, when, from what and to what, and these
entries cannot be edited. See [the Activity log](access.md#the-two-logs).

**Roles are decided when you ask, not stored.** Whether someone is a manager is
looked up from Practice HR's *Admin of shift-central* box or from a grant on
their profile every time they open a page, so taking access away takes effect at
once (or, for the Practice HR box, at the person's next sign-in).

**Nobody manages themselves.** A manager opens their own profile read-only. Their
hours and allowances are set by another manager, and so is their leave approved by another
manager (the practice manager's own leave can be switched to need no approval, on their
Permissions link, by another all-teams manager).

**The Django admin (`/admin/`) is for the superuser, for setup and repair only.**
Every day-to-day screen is the app's own. The one thing the admin is needed for
in normal running is [team order and active](people.md#teams).
