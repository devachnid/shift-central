# The Practice HR feed

**Where:** the Health card at the top of the Staff page (managers); `deploy/manage
hr_sync` on the server; `shift-central-hr-sync.timer`. The GP rota app's sessions
are read in the same way, and are [further down](#gp-sessions-from-the-rota-app). The
other direction, GP leave served to the rota app, is
[at the end of this page](#the-gp-rota-app-reads-gp-leave-from-here).

## The mental model

**Shift Central does not hold people of its own; it keeps a copy of Practice HR's,
refreshed every fifteen minutes.** HR is the master for who works at the practice,
their name, email, team, start and finish dates and whether they are a GP. This
app adds what HR does not hold (see [People](people.md)). That way a leaving date is
entered once, in one place, and a wrong leave figure cannot come from the two systems
disagreeing about it.

**The sync can add and overwrite, and nothing else.** It never deletes a person,
never touches a field typed here, and never writes anything back to Practice HR.

## What one sync does

One request goes to `PRACTICE_HR_URL` + `/api/v1/people` with the bearer token
`HR_API_TOKEN` (ten seconds at most; a redirect is refused; over anything but
`https` the token is not even sent). Then, in a single database transaction:

- Each record in the feed is matched to a person by **Practice HR's employee id**.
  A new id creates a person; a known one has its HR fields overwritten: first and
  last name, full name, email, team, start date, finish date and GP.
- A **team name not seen before creates a team**. A person whose team changed is
  moved to the new one. A record with no position keeps the team the person
  already has: HR's feed gives today's positions, so someone between posts has
  none. **A starter appears without a team** until HR holds their position (a
  January starter has none in December); they are on the Staff list's *Starting*
  view for an all-teams manager, who can set up their hours and allowances
  meanwhile. Their team arrives with the first sync after their position starts.
- A person **in the database but missing from the feed is not deleted**. Their
  *last seen* time simply stops advancing, and the Health card lists them once a
  good run has left them out and they have been missing for over a day.
- Every field the sync actually changes writes an entry to the
  [Activity log](access.md#the-two-logs) with the actor `practice-hr` and the reason
  "from Practice HR", so you can see when a finish date arrived. A run that changes
  nothing writes nothing.
- The run is recorded: when it started and finished, whether it worked, how many
  people the feed held, and, if it failed, a message.

**Never fetched:** date of birth, gender, phone numbers, address, NI number, pay,
patterns, contracts and absences. HR holds them; this app does not need them.

New people arrive with the defaults: no hours, no allowances, navy name colour,
display order 100, and the three display switches ticked.

## When the sync fails

A failed sync **keeps the last good data exactly as it was**: the changes are made
in one transaction and rolled back together, so a feed that breaks on the 40th
person does not leave 39 changed. The failure is shown on the Health card in red
with its message; it never shows an error page to anyone. The messages never contain
a person's details.

| Message | Meaning, and the fix |
|---|---|
| `Practice HR returned 401 for people` | The token is missing from, or wrong for, Practice HR. Check `HR_API_TOKEN` here is one of the values in `HR_API_TOKENS` in `/etc/practice-hr.env`, with nothing added or missing, and that Practice HR was restarted after the token was added. |
| `Practice HR returned 429 for people` | Practice HR's rate limit for the feed was hit. Normally one request every fifteen minutes does not; look for something else polling hard from this address. |
| `Practice HR returned 403 ...` or `404 ...` | `PRACTICE_HR_URL` points at the wrong place. It must be Practice HR's own address with no path. |
| `Practice HR unreachable` | A network failure, a wrong hostname, or Practice HR down. Open Practice HR's address in a browser; its tunnel hostname and its service must both be up. |
| `PRACTICE_HR_URL is not https; the token was not sent` | The URL says `http://`. The token goes only over `https`, so use the public tunnel hostname, not `http://127.0.0.1:8322`. |
| `Practice HR returned a non-JSON body for people` or `... has no 'people' list` | The address answers, but it is not the feed: a login page, a Cloudflare challenge, or the wrong site. |
| `record N in the feed: missing or bad <field>` | The Nth person in Practice HR's feed lacks something this app requires, most often a **start date** (an employee with no employment start). Fix the record in Practice HR; until then **no one** is updated. It names the place and the field, never the value. |
| `unexpected error; see the journal` | Something not foreseen. `journalctl -u shift-central-hr-sync` (or `-u shift-central` for Sync now) has the traceback. |

The timer keeps trying every fifteen minutes, so a fault fixed in Practice HR clears
itself on the next run; the card goes back to green and shows the new count.

## The Health card

Managers see it at the top of the Staff page. It is built from the people the
viewer manages, so a team manager's card is about their team. Its boxes are described
below: Practice HR, Needs hours and allowances, Not in Practice HR's feed, Leaving in the next
30 days and the three leave boxes (Requests waiting, Leave costs to check, Negative leave
balances). The GP rota's two are
[under the GP sessions](#the-health-lines).

**Practice HR** is the last run: "*N* people, 29 Oct 14:30" in the normal colour
when it worked; "failed 29 Oct 14:30" and the message in red when it did not;
"never read" in red on a new install. Beside it is **Sync now**.

- *What to do:* if it is red, read the message against the table above. If the
  time is old but the box is not red (an hour or more), the timer is not running:
  `systemctl list-timers shift-central-hr-sync.timer` on the server.

**Needs hours and allowances** is a count and the first five names, each a link
that opens the profile. It counts current and starting people, **who are not GPs**,
with **weekly hours or days per week still blank**, or with **no allowance for
either the current leave year or the next**. A GP is never counted, as they have
no hours here.

- *What to do:* open each name and fill in Pay & time off: the hours, the days and
  at least one of the two leave years' allowances. A person drops off the list once
  all three are there; a person's Pay & time off tab shows a dash for any year not
  entered, so check the other year there.
- Wrong: ignoring it. A person with no hours is costed at nothing on a day with no rota,
  and a person with no allowance shows "not set" and cannot request leave.

**Not in Practice HR's feed for a day** lists people the last good run left out
and who have not been in the feed for over a day. It is measured against the last
run that worked, not the clock, so failed runs do not make everyone look missing;
with no good run in the last day it lists nobody, and the Practice HR box is red
instead. Only current and starting people are listed (someone who left and whom HR
has dropped is not news).

- *What to do:* if it is one or two names, they have been removed or deleted in
  Practice HR, or never should have been there: confirm with the practice manager
  and, if they should not be here, it is the superuser's decision whether to delete
  them (see [Removing someone](people.md#removing-someone)). If it is **everyone**,
  Practice HR's feed itself came back short (a good run that held almost no one);
  check the count in the Practice HR box and the employees in Practice HR.

**Leaving in the next 30 days** lists current people whose finish date falls
between today and thirty days away, with the date.

- *What to do:* nothing except to know they are going: their leave allowance is cut at
  that date automatically. A later release raises the leaver flags (final pay, leave
  owed). A date that looks wrong is wrong in Practice HR; fix it there.

**Requests waiting** is the number of leave requests and cancellation requests waiting for a
decision from the people the viewer manages, the viewer's own not counted (another manager
decides those), with the age of the oldest and a **Decide** link to
[Waiting for approval](leave.md#approving).

- *What to do:* decide them. A request the managers have not answered for the number of
  working days set on Leave settings (3 to begin with) also emails them a reminder, once.

**Leave costs to check** is the number of approved leave days that were costed on an *average
day* because the person's rota for that week was not written yet, with the first five as links to
their booking.

- *What to do:* set the shift behind each day: right-click the day on the rota grid › **Shift
  behind the leave…** (or **Add › Shift…** on that cell), enter the shift the person would have
  worked and save. The shift stays hidden under the leave, the day is re-costed from it, the
  managers are emailed and the line goes. Writing the person's other days does not do it. If the
  average day is right, there is nothing to do; or type the figure into the booking's **Allowance
  used** box (Edit). See [what a day costs](leave.md#what-a-day-costs).

**Negative leave balances** lists the first five people whose annual leave remaining (bank holidays
included) is below zero in their current or next leave year, each a link to their statement. A year with
no allowance entered is *Needs hours and allowances*, not a deficit. GPs are never listed here, whatever
their balance.

- *What to do:* it is allowed (a manager can book past the balance, and an hours change can
  leave one negative), so decide whether to correct it with an adjustment, in which case the line
  goes, or to leave it. See [the statement](leave.md#the-statement-and-how-to-read-it).

## Sync now

A button on the Health card, and in the pop-up *Add staff +* opens. Any manager can
press it. It runs exactly the same read as the timer, at once, for **everyone** (not
only the viewer's team), then returns to the Staff page with one message: "*N* people
read from Practice HR." or "Practice HR could not be read: *message*."

Use it after adding a starter or correcting a date in Practice HR so as not to wait
fifteen minutes. It is safe to press twice; a second run that finds nothing new changes
nothing.

## Running it by hand

On the server, as root:

    deploy/manage hr_sync

It prints "*N* people read from Practice HR" and exits cleanly, or exits with an
error and says why. It refuses to start, naming the setting, if `PRACTICE_HR_URL` or
`HR_API_TOKEN` is unset. Run it by hand once after first install (before enabling
the timer) and after any change to the token or URL: the message appears on your
screen instead of in a journal.

`shift-central-hr-sync.service` is the unit the timer starts. It fails (shown in
`systemctl status shift-central-hr-sync`) when a run fails, which is the second
place to look beside the Health card.

## GP sessions from the rota app

**Where:** the Health card's *GP rota* box and *GPs in the rota app not matched
here*; `deploy/manage gp_sync` on the server; `shift-central-gp-sync.timer`.

**The GP rota app (`devachnid/rota`) owns the GPs' sessions; this app only shows
them.** Every fifteen minutes Shift Central asks it for the sessions in a window,
**from eight weeks before today to fifty-two weeks after**, with `ROTA_URL` +
`/api/v1/sessions` and the bearer token `ROTA_API_TOKEN` (one of the rota app's
`ROTA_API_TOKENS`). Then, in one transaction:

- Each session's **email** is matched, ignoring capitals, to a person here who is
  **marked a GP** and is current or starting; a leaver (finish date passed) is never
  matched. If two people here share the email (a GP who left and came back), the
  one current today gets the sessions. Matched sessions replace the whole
  window's sessions here; a session the rota app has dropped disappears here at the
  next run.
- A session for the same GP, day and part (AM or PM) twice in the feed is kept once,
  and a session outside the window is ignored. Both are counted in the run's message.
- Sessions that match nobody are not stored, and the addresses are listed on the
  Health card.
- Nothing is ever written back to the rota app, and a session cannot be edited here:
  the rota draws them as read-only tiles and the hours report counts each as 4 h 10 min.

The timer is `shift-central-gp-sync.timer`, `OnCalendar=*:7/15:00`: at seven past,
twenty-two past, thirty-seven past and fifty-two past the hour, so that it never
runs at the same moment as the HR timer. Like the HR sync, **a failed run keeps the
last good sessions** exactly as they were, and shows on the Health card; it never
shows an error page.

### The Health lines

**GP rota** is the last run: "*N* GPs, 29 Oct 14:32" when it worked (the count is the
GPs who had a session in the window); "failed 29 Oct 14:32" in red with the message
when it did not; "never read" before the first run; "not configured" when `ROTA_URL`
or `ROTA_API_TOKEN` is unset, which is right for a site that has no GP rota app and is
not a fault. A run that worked can still carry a note in grey under the figure, such as
"3 emails unmatched; 1 clinician without an email; 2 duplicate sessions"; the words are
counts only.

**GPs in the rota app not matched here** appears when the last good run held sessions
for email addresses that belong to no GP here, with the count. **All-teams managers
also see the addresses**; team managers see the count only.

- *What to do:* find each address. The usual cause is that the GP's work email in the
  GP rota app differs from the one in Practice HR (a different spelling, an old
  address, a personal one). Correct whichever is wrong, in that system, and the next
  run (within fifteen minutes) picks the sessions up. Another cause is that the person
  is not marked as a GP in Practice HR (their contract unit must be *sessions*): then the
  address is unmatched and the fault is in HR.
- The note "*N* clinicians without an email" is the other direction: the rota app holds
  sessions for a clinician who has no email there at all, so there is nothing to match.
  Give them one in the rota app.

### When the GP sync fails

| Message | Meaning, and the fix |
|---|---|
| `GP rota returned 401 for sessions` | `ROTA_API_TOKEN` is not one of the values in `ROTA_API_TOKENS` in the rota app's `/etc/rota.env`, or the rota app has not been restarted since the token was added. |
| `GP rota returned 400 ...` | The rota app refused the range. Its limit is a `to` date at most 500 days after `from`; the window is far inside that, so look at whether the rota app is the version with the feed. |
| `GP rota returned 404 ...` or `403 ...` | `ROTA_URL` is wrong, or the rota app does not have the feed yet. It must be the rota app's address with no path. |
| `GP rota returned 429 ...` | The rate limit for the feed was hit: something else is polling hard from this address. |
| `GP rota unreachable` | A network failure, a wrong hostname, or the rota app down. |
| `ROTA_URL is not https; the token was not sent` | Use the public `https` hostname, not `http://127.0.0.1:8321`. |
| `GP rota returned a non-JSON body for sessions` or `... has no 'sessions' list` | The address answers, but it is not the feed. |
| `session N in the feed: missing or bad email, day or part` | The Nth session lacks something this app requires. Until the rota app is fixed no sessions are updated. It never names the value. |
| `unexpected error; see the journal` | `journalctl -u shift-central-gp-sync` has the traceback. |

### Running it by hand

On the server, as root:

    deploy/manage gp_sync

It prints "sessions for *N* GPs read from the GP rota", with any note in brackets, or
exits with an error and says why. It refuses to start, naming the settings, if
`ROTA_URL` or `ROTA_API_TOKEN` is unset. Run it by hand once after setting those two
and before enabling the timer, and after any change to either. There is no Sync now
button for it: the timer is fifteen minutes, and the hand run is for urgent cases.

`shift-central-gp-sync.service` is the unit the timer starts. It fails when a run fails,
which shows in `systemctl status shift-central-gp-sync`.

### To revisit

**Link GPs by Practice HR's employee id once the rota app holds one.** Today a GP is
found by work email, so a changed address silently drops their sessions until someone
corrects it; the Health line is the safety net. Once the rota app records the employee
id, matching on it removes that failure. The practice manager's answer to the
requirements' amendment 2 (GP sessions shown read-only) also decides whether this stays
as it is: if the answer is no, this section is what changes.

## The GP rota app reads GP leave from here

**Where:** `GET /api/v1/leave`; `LEAVE_API_TOKENS` in `/etc/shift-central.env`; on the rota app's side,
`SHIFT_CENTRAL_URL` and `SHIFT_CENTRAL_TOKEN` and its own guide (`docs/admin/shift-central.md` in that repository).

**Shift Central owns every GP's leave; the GP rota app only shows it.** GPs request and are approved here
like everyone else ([Leave](leave.md#gps)). The rota app calls this address every fifteen minutes
(its `rota-shift-central.timer`, a year back to two years ahead) so its grid shows who is off and assisted
fill never assigns them. It replaces the FindMyShift reader the rota app had, which never went live, so
nothing was migrated. Nothing is ever written to or by this feed in the other direction.

    GET https://<this site>/api/v1/leave?from=2027-03-01&to=2027-03-31
    Authorization: Bearer <token>

- **The token** is one of `LEAVE_API_TOKENS`, comma-separated, each made with `openssl rand -hex 32`.
  The rota app has one of them as `SHIFT_CENTRAL_TOKEN`. To change it, add the new one, restart Shift Central,
  point the rota app at it, then remove the old and restart. Unset, every call is a 401. Keep it out of files,
  chat and tickets.
- **The range** is `from` and `to`, dates, `to` no earlier than `from` and at most 1,100 days after it.
- **What is sent**: the approved bookings, and those with a cancellation waiting for a decision, of people
  marked GP who have an email, whose days overlap the range, as an email, a first and last day, a part
  (`whole`, `am` or `pm`) and the leave type's name. A booking by the hour is `am` when it ends by 13:00,
  `pm` when it starts at 13:00 or later, and `whole` if it straddles midday. A leaver's finish date is not
  looked at; the rota app's own active flag decides.
- **What is never sent**: the description, any note or reason, the pay, hours or cost, the person's name, an id,
  waiting, declined or cancelled bookings, or anyone who is not a GP. The response body is never logged.
- **The match is by work email**, ignoring capitals, as for the sessions. An address that matches no clinician in the rota
  app is listed on its status page; the fix is to make the two systems' emails agree.
- **The type's name is the rota app's key.** It turns each name (Holiday, Sick leave…) into its own category
  with a mapping page; a leave type you add here shows there as its default category until a row is added.
  Renaming a type here therefore changes what the rota app sees.

| The rota app sees | Meaning |
|---|---|
| 401 | The token is missing, wrong, or not in `LEAVE_API_TOKENS` (restart Shift Central after changing it). |
| 400 | `from` or `to` is missing, not a date, in the wrong order, or the range is over 1,100 days. |
| 405 | Anything but GET. |
| 429 | The rate limit: `API_RATE_LIMIT_PER_MINUTE` (600) calls a minute from one address, **counted per gunicorn worker**, and counting calls with a wrong token. `0` turns it off. |

**The rate limit counts the caller's address.** Behind the Cloudflare tunnel that is the real address only if the proxy is in
`TRUSTED_PROXY_IPS`; if it is not, every caller shares one address and one allowance (README, the settings table).

Shift Central keeps no record of whether the rota app has read the feed: the proof is the rota app's
Time off from Shift Central status page, or `curl` with the token against the URL above, which
returns the JSON. Nothing about the feed is on the Health card. Run it by hand with a token from
`LEAVE_API_TOKENS` in place of `<token>` and never paste a real one into a ticket.
