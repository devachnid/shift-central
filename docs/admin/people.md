# People

**Where:** sidebar › Staff (`/staff/`), then a name for the profile pop-up. Teams
are in the Django admin (`/admin/people/team/`, superuser only).

## The mental model

**A person is one row per Practice HR employee**, created by the sync the first
time HR's feed includes them and never deleted by it. Two kinds of field hang
off the row: those **from Practice HR**, overwritten by every sync and read-only
here, and those **typed here**, on the profile, which the sync never touches.
The profile tells you which is which: the General tab is the first kind, the
others the second.

**People are added and removed in Practice HR, not here.** *Add staff +* on the
Staff list says so and links to HR. A starter appears here within fifteen
minutes of being entered there, with no hours and no allowances, and is listed
on the [Health card](sync.md#the-health-card) until a manager fills the profile in.

## Teams

`/admin/people/team/` (superuser). A team is created by the sync when a team name
arrives that has not been seen before; it is never created or removed by hand.

| Field | What it does |
|---|---|
| **Name** | Practice HR's team name, taken from the person's *first* position. **Do not edit it here.** The sync finds teams by exact name, so a renamed team is simply a new name. See below. |
| **Display order** | Teams are listed by this number, lowest first, then by name. It sets the order of the Staff list (team, then each person's own display order) and of the Team filter and the Permissions list. New teams start at 100, after any you have numbered lower. |
| **Active** | Untick it for a team nobody should be filtered by or granted any more. An inactive team drops out of the Staff list's Team filter and the Permissions list (except, marked "(inactive)", for someone who still holds it). It does **not** hide its people or remove grants already given; the people keep their team and appear in *All teams*. |

**Renaming a team in Practice HR** creates a new team here and moves everyone
in it across on the next sync. The old team stays, empty, with any manager
grants still attached to it, and the people who were granted it now manage
nobody. Untick **Active** on the old team and grant the new team from the
Permissions link under each manager's profile. A person with **no team** (HR
gives none) can be managed only by an all-teams manager.

## From Practice HR

Shown on the General tab and in the Staff list. None can be changed here; if one
is wrong, change it in Practice HR and it arrives within fifteen minutes (or press
*Sync now*).

| Field | Where it comes from, and what depends on it |
|---|---|
| **Name** | Practice HR's full name for the person. Shown everywhere; the initials in the profile's avatar come from first and last name. |
| **Email** | HR's work email for the employee record. Shown to the person's managers. It is *not* what signing in uses; sign-in binds on HR's employee id (see [Access](access.md#how-a-sign-in-becomes-a-person)), so an email difference never moves anyone into someone else's account. |
| **Team** | The team of the person's first position in HR. Decides which managers manage them. A person who changes team is moved at the next sync; a team manager's own grant does not move with them. HR sends only today's positions, so **a starter appears without a team until HR holds their position**; meanwhile an all-teams manager finds them under *Starting* on the Staff list and sets them up. A person between posts keeps the team they had. |
| **Start date** | HR's employment start. Required: a record in the feed with no start date makes the whole sync fail (see [sync](sync.md#when-the-sync-fails)). Someone whose start date is in the future is *Starting*, not *Current*. |
| **Finish date** | HR's employment end; blank while employed. After it passes, the person leaves the *Current* list and appears under *Left*. They stay on record. The Health card lists leavers in the next 30 days. |
| **GP** | True when HR's contract unit for the person is *sessions*. A GP has no weekly hours or days per week here (their sessions come from the GP rota app, [read-only on the rota](rota.md#gps)). If a GP shows as an ordinary member of staff, or the reverse, the fault is the contract in HR. |

## Typed here: the Display tab

Editable by the managers of the person's team. Everyone can read their own.

| Field | What it does, and what goes wrong |
|---|---|
| **Job title** | Up to 80 characters; may be blank. Shown on the Staff list and under the name on the profile. Practice HR's position title is not copied; this is what the rota will show. |
| **Name colour** | The colour of the person's name chip on the Staff list (and, later, on the rota). Pick from the swatches or type a hex value. Exactly `#rrggbb` is accepted; anything else is refused with "Choose a colour." Default is navy. A very pale colour makes the white name text unreadable. |
| **Display order** | A whole number, 0 or more, default 100. People in the same team are listed by it, lowest first, then by last name, then first. Equal numbers (everyone starts at 100) therefore fall back to alphabetical. |
| **Display on rota** | Whether the person appears on the [rota](rota.md) grid (and Who's in today). Untick for someone who should not be on it; their shifts and the hours report are unaffected. |
| **Show to other staff** | Whether other *staff* see this person on the Staff list. Untick for someone who should not be listed to colleagues. Managers always see everyone; the person always sees themselves. |
| **Can see other staff** | Whether the person may see colleagues on the [rota](rota.md). The requirement is that everyone sees every rota, so leave it ticked unless a manager has a reason to restrict someone: with it off they see only their own row. |

## Typed here: the Pay & time off tab

Editable by the managers of the person's team. A person reads their own.

| Field | What it does, and what goes wrong |
|---|---|
| **Weekly hours** | Contracted hours a week, to two decimal places, 0 to 999.99. Not shown for a GP, who shows "Sessions, from the GP rota". Leave blank and the person stays on the Health card's *Needs hours and allowances* list. |
| **Days per week** | Whole number, 1 to 7. With weekly hours it gives the **average day** (weekly hours divided by days, to two places), shown beneath the field. This is the day length leave is costed in for a week whose rota has not been written yet, so a wrong figure here becomes a wrong leave cost (the Health card lists those days as *Leave costs to check*). |
| **Leave year starts (MM-DD)** | The month and day the person's leave year begins, `01-01` for nearly everyone. It can only be changed **before any allowance or booking exists** for the person, because those are filed under the years it makes; after that the form refuses and says so. Someone whose year starts on 1 April shows their allowances as "from 1 Apr 2027". |
| **Annual leave allowance (hours)** and **Bank holiday allowance (hours)** | The full-year figures in hours, to two places, for **each of two leave years: the current one and the next**. They are what the person's leave is worked out from: the system pro-rates them by the weeks the person is employed in the year (starters, leavers; [Leave](leave.md#allowances-and-hours-changes) explains the rules), and a change of hours part-way through the year is added with **Add hours change…** under the statement, not here. With neither year entered, the person stays on the Health card's *Needs hours and allowances* list. |
| **Reason for the change** | Up to 300 characters. **Required to change an allowance that is already set**, and recorded with the change. Not needed the first time a year's allowances are entered, or when only hours and days change. |

Things that surprise people:

- Give **both** allowances for a year or **neither**. One without the other is refused.
- You cannot clear an allowance by blanking it: empty boxes mean "no change". To correct a figure, type the right one and give a reason.
- The tab saves as a whole. If the allowance change is refused (no reason), the hours and days typed with it are **not** saved either.
- The two years roll over on the first day of the person's leave year (1 January for most): from then, the tab shows the new current year and the one after; the earlier year's figures are still on record but no longer on the tab.
- A GP's allowances are entered here the same way, even though their hours are not.

**Below the form is the person's leave statement**, which the person sees too: the pro-rated allowances, adjustments, each
booking's days with their costs, the bank holiday balance, what is remaining and what is available, and TOIL, with a
**Leave year** box to switch between their two years. Managers also get **Adjust…** and
**Add hours change…** there. How to read it is in [Leave](leave.md#the-statement-and-how-to-read-it).

## Typed here: the Notes tab

Free text for the managers of the person's team. **The person never sees it**, and
neither do other staff or managers of other teams; the tab does not appear for them.
Every save is recorded in the history and the Activity log as `notes` changed,
with who and when, but never the text: a manager can see the Activity log for
their own team, themselves included, and must not read notes written about them
there. Keep it to what a manager needs.

## The profile pop-up

Opened by a name on the Staff list. The title is "Your profile" for your own and
"[Name]'s profile" for anyone else's. Under the form, **Update profile** saves the
tab you are on. Below are two links for managers: **Permissions** (all-teams
managers only; see [Access](access.md#the-permissions-link)) and **History**
(every change to that person's fields and allowances, newest first, the latest 200).

| Tab | The person themselves | Managers of the person's team | Everyone else |
|---|---|---|---|
| General: name, email, team, start and finish dates | Reads | Reads | Cannot open the profile |
| Display | Reads | Edits | Cannot open |
| Pay & time off | Reads their own hours, allowances and statement | Edits the form; Adjust and Add hours change | Cannot open |
| Notes | Tab not shown | Edits | Cannot open |

A manager does not manage themselves, so a manager opens their own profile
read-only and without Notes; another manager with access to them sets their hours.
For a practice manager, that means another all-teams manager.

**Permissions** (all-teams managers) holds two things: the team ticks, and **Own leave needs no
approval**. The tick is for the practice manager, whose own leave is then recorded as soon as
they add it instead of waiting for another manager; it is off for everyone else. It changes
nothing else: nobody can approve their own request on the Waiting for approval page, flag or not.
The grant and its removal are recorded in the Activity log like any other change. See
[Access](access.md#the-permissions-link).

Saving shows "Saved." in the pop-up. A pop-up left open past the ten-minute
session says "Your session ended. Sign in again." rather than losing the edit
silently; sign in and retype it.

## The Staff list

`/staff/`. A white table; each name is a coloured chip, and is a link to the
profile if it is yours or one you manage.

| Column | Who sees it |
|---|---|
| Name, Job title, Team | Everyone |
| Email, Start date, Finish date | Managers, for the people they manage; blank for other teams' people |

What each role sees:

- **Staff** see the *current* people who have **Show to other staff** ticked, plus
  themselves. There are no filters beyond Team.
- **Managers** also get the **Show** filter: *Current* (started, not yet finished;
  someone finishing today is still current), *Starting* (start date in the future)
  and *Left* (finish date passed). Managers see every person in those views,
  whatever their Show to other staff setting.
- **Team** filters to one active team.

**Download** (top bar, managers only) gives `staff.csv` of exactly the rows the
filters show: Name, Job title, Team, Email, Start date, Finish date. Email and
dates are filled in only for the people the downloader manages, as on screen.
The file holds personal data; treat it as you would the screen.

**Add staff +** (managers) opens a pop-up pointing to Practice HR's Add employee page,
with a **Sync now** button for when the new person has been entered there.

Above the table, managers see the Health card; see [the sync](sync.md).

## Removing someone

You cannot, and are not meant to. A leaver is finished in Practice HR and stays
here under *Left*. The only deletion is the superuser's, in the admin
(`/admin/people/person/`), for a person who has gone from HR's feed for good: it
deletes their allowances and manager grants with them, and their history entries
stay. If that person is still in HR's feed, the next sync recreates them as a
brand-new person with none of the typed fields, so do it only for someone really
removed from Practice HR.
