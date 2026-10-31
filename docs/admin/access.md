# Access

**Where:** Practice HR (Login accounts › Apps › *Admin of shift-central*) for
all-teams managers; the **Permissions** link under a profile in Shift Central for
team managers; sidebar › Activity logs for the two logs.

## The mental model

**There are three roles, and nobody is given one by hand here except team
managers.** Staff member is everyone who can sign in. All-teams manager is decided by
Practice HR. Team manager is decided by a grant on the person's profile. The role is
worked out every time a page is opened, from those two sources; there is no stored
"role" field to get out of step with them.

| Role | Who | How it is set |
|---|---|---|
| Staff member | Everyone signed in | Having a login account in Practice HR that is linked to an employee |
| Team manager | The lead nurse, the head pharmacist | A grant for a team on their profile (the Permissions link) |
| All-teams manager | The practice manager and the three assistant managers | Practice HR: tick **Admin of shift-central** on their login account (Login accounts › Apps) |

## How a sign-in becomes a person

Nobody has a password here except the superuser. Everyone clicks *Sign in with the
practice account* and is sent to Practice HR, which tells Shift Central three
things: their **email**, their **employee id**, and whether they are an **admin** of
this app.

- The **employee id** decides which person they are. At every sign-in the person
  with that Practice HR employee id is linked to the login, and unlinked from any
  other login. (The email is only used the very first time, to find a login that was
  made before it had a Practice HR id; after that the login is found by Practice HR's
  own id, so an edited email cannot hand over someone else's account.)
- The **admin** claim sets whether they are an all-teams manager, at each sign-in,
  both ways: ticking the box makes them one at their next sign-in, and unticking it
  removes it at their next sign-in. Only a plain "true" counts.
- **No employee id, or one that matches nobody here yet**, still signs in, and lands
  on a page titled "You're not yet on the rota" saying who to ask. This usually
  resolves itself: the person has been entered in Practice HR but not yet read in
  (wait fifteen minutes or press *Sync now*), or their Practice HR login is not
  linked to their employee record, which only Practice HR can fix. The employee id
  is kept with the login, so once the sync has read the person in, the next page
  they load (reloading the holding page will do) takes them in without signing in
  again. Until it resolves, they reach nothing else but sign-out.

## What each role can see and do

Rows are the ones this release has data for; later releases add the rest of the
requirements' table.

| | Staff member | Team manager (their team) | All-teams manager |
|---|---|---|---|
| Staff list: names, job titles, teams | Current people who share themselves, and themselves | Everyone, in every view | Everyone, in every view |
| Staff list: emails and dates; Download | No | Their team's people | Everyone |
| Staff list filters Show (Current, Starting, Left) | No | Yes | Yes |
| Own profile: General, Display, Pay & time off | Reads | Reads | Reads |
| Another person's profile | No | Their team's people | Everyone |
| Edit Display, Pay & time off, hours, allowances | No | Their team's people | Everyone but themselves |
| Notes | No, not even their own | Their team's people | Everyone but themselves |
| Permissions link | No | No | Yes |
| History link | No | Their team's people | Everyone but themselves |
| Health card and Sync now | No | Yes, limited to their team | Yes |
| Departments | No | Yes | Yes |
| Activity log | No | Entries about their team's people (rota and leave changes included), and all department and template entries | Everything |
| Time off list, year planner, requesting own leave | Yes (colleagues' leave by type only) | Yes | Yes |
| Another person's leave description, pay and cost | No | Their team's people | Everyone |
| Book, edit, approve, decline or cancel leave; Adjust; Add hours change | No | Their team's people | Everyone but themselves |
| Bank holidays, Blackouts, Leave types, Leave settings | No | Yes | Yes |
| Leave report | Their own row | Their team's people and themselves | Everyone |
| Log in logs | No | No | Yes |

The one case where "their team's people" and "themselves" differ: a team manager
sees their own team's list in full including themselves, but opens **their own**
profile read-only, since nobody manages themselves. A manager's own hours and
allowances are set by an all-teams manager.

A page someone may not open answers "You can't open that"; the menu does not
offer them the item in the first place.

## The Permissions link

Under a profile (in the pop-up, beside History), **all-teams managers only**. It
opens "Permissions: [name]" with a tick for each **active** team and the button
**Update permissions**. Tick a team to make that person a **team manager** of it.
Untick to take it away. Saving shows "Saved."

- Grants are by *team*, not by job: the lead nurse is granted Nursing, the head
  pharmacist Pharmacy. A person can manage several teams.
- A team manager manages **the people whose team is theirs**. If Practice HR moves
  someone to another team, they pass to that team's managers at the next sync.
- A grant given before the person has ever signed in is fine; it takes effect from
  their first sign-in, when they are linked to their person.
- Revoking takes effect on the person's next request, with no sign-out needed. The
  grant is removed, but the record that it existed and was removed stays in the
  Activity log (field `manager_of`, with the team's name before and after).
- For someone who is an all-teams manager the dialog reads "all teams, set in
  Practice HR" and has no ticks, and a save writes nothing. Their access is not
  editable here; remove their *Admin of shift-central* box in Practice HR.
- An inactive team is listed only for someone who still holds it, marked
  "(inactive)", so saving the dialog keeps the grant unless you untick it; untick
  it to revoke it. Left alone it is harmless once the team has no one in it.
- Manager access is what lets someone build the team's rota and approve and book its
  leave, as well as seeing the profile, the Staff list's extra columns and the Activity log.
- Below the team ticks is **Own leave needs no approval**, for the practice manager. With
  it ticked the person's own leave is recorded as soon as they add it; without it (everyone
  else) it waits for another manager. It is ticked and unticked here by an all-teams manager
  and recorded in the Activity log. Nobody can approve their own request.

## Sessions and signing out

A session lasts **ten minutes from the last request**, and every request restarts
the ten minutes, because the app is used on shared reception PCs. A form left open
longer than that does not save; a pop-up says "Your session ended. Sign in again."
and the sign-in brings the person back to the page.

**Log out** is the bottom item of the side panel. It signs out of Shift Central and
then of Practice HR too, so that on a shared PC the next person is asked who they
are instead of being signed in as the last. A session that simply timed out has not
signed out of Practice HR, so every sign-in also asks Practice HR to check who is
there (`prompt=login`): Practice HR shows its log-in page even to a browser it
already knows, and the person types their own password or uses their passkey.
Signed-in pages are marked not to be kept by the browser, and signing out clears
what it kept.

The superuser is the exception, as it must be when Practice HR is down: it signs in
with a password at `/admin/` (the login page offers only the practice account while
Practice HR is configured). The superuser is not a manager unless Practice HR's
box is also ticked, though it can open every page without being linked to a person.

## The two logs

**Activity log** (sidebar › Activity logs › Activity log, `/activity/`) is every
recorded change to the people a manager manages, newest first, the latest 500: the
time, who made the change (a person's email, or `practice-hr` for the sync),
which record, the field, the old and new value and the reason. It shows changes to
profiles (display fields, hours, and that the notes changed, never their text), to allowances, to manager grants
(`manager_of`), to what the feed changed (including `created` for a new person and a
new finish date arriving), to departments, to the rota and to templates. An
allowance's row names the person it belongs to, and so does a rota change (field
`cell` for what the day said before and after, `appearance` for a colour or style,
`notified` when the person was emailed); a template's row reads `template`. Filter by **Person**, by **Field** (the field's name as shown, such as
`weekly_hours` or `end_date`; type it exactly) and by **From** and **To** dates (both
included; either may be left blank).
It is the answer to "who changed this, and when did I see that date arrive?".

**Log in logs** (sidebar › Activity logs › Log in logs, `/activity/logins/`,
all-teams managers only) has one row per sign-in: when, who, the address (the real
one from Cloudflare, not the tunnel's) and the browser, newest first, the latest
1,000. Filter by **Person** (the login's email) and by **From** and **To** dates. If every address reads `127.0.0.1`, the tunnel's address header is not
arriving and the address column is meaningless; see `TRUSTED_PROXY_IPS` in the
README.

Neither log can be edited or cleared.
