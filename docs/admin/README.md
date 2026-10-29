# Admin guide

Reference for everything a manager or the superuser can set in AMG Shift
Central. One page per area, every field explained: what it does, what depends
on it, and what goes wrong if it is set incorrectly.

The `README.md` in the project root has the *sequence* for installing the app
and the commands. [Setting up](setup.md) is the go-live order for the practice.
This is the *reference* for what each setting means once you are in there.

| Page | Covers |
|---|---|
| [People](people.md) | Teams, who a person is and what Practice HR owns of them, the fields typed here, the profile pop-up's tabs and who sees each, hours and the two leave allowances, notes, the Staff list and its download |
| [Departments](departments.md) | The list of departments, colours, order, archiving instead of deleting |
| [Access](access.md) | The three roles, where each is set, what each can see and do, the Permissions link, sessions and signing out, the two logs |
| [The Practice HR feed](sync.md) | What the fifteen-minute sync changes and never changes, the Health card's four figures and what to do about each, Sync now, running it by hand |
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

**Every change to a person is written down.** Each field changed on a profile,
each allowance, each manager grant, each department edit and each change the
feed makes writes an entry that says who, when, from what and to what, and these
entries cannot be edited. See [the Activity log](access.md#the-two-logs).

**Roles are decided when you ask, not stored.** Whether someone is a manager is
looked up from Practice HR's *Admin of shift-central* box or from a grant on
their profile every time they open a page, so taking access away takes effect at
once (or, for the Practice HR box, at the person's next sign-in).

**Nobody manages themselves.** A manager opens their own profile read-only. Their
hours and allowances are set by another manager.

**The Django admin (`/admin/`) is for the superuser, for setup and repair only.**
Every day-to-day screen is the app's own. The one thing the admin is needed for
in normal running is [team order and active](people.md#teams).
