# The Practice HR feed

**Where:** the Health card at the top of the Staff page (managers); `deploy/manage
hr_sync` on the server; `shift-central-hr-sync.timer`.

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
  moved to the new one. A person HR gives no position becomes teamless.
- A person **in the database but missing from the feed is not deleted**. Their
  *last seen* time simply stops advancing, and the Health card lists them after a
  day.
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
viewer manages, so a team manager's card is about their team. There are four boxes.

**Practice HR** is the last run: "*N* people, 29 Oct 14:30" in the normal colour
when it worked; "failed 29 Oct 14:30" and the message in red when it did not;
"never read" in red on a new install. Beside it is **Sync now**.

- *What to do:* if it is red, read the message against the table above. If the
  time is old but the box is not red (an hour or more), the timer is not running:
  `systemctl list-timers shift-central-hr-sync.timer` on the server.

**Needs hours and allowances** is a count and the first five names, each a link
that opens the profile. It counts current and starting people, **who are not GPs**,
with **weekly hours or days per week still blank**. A GP is never counted, as they
have neither.

- *What to do:* open each name and fill in Pay & time off, then the two leave
  years' allowances. Note that the count goes by hours and days: someone with hours
  but no allowances **drops off the list**, so keep your own check for the
  allowances; a person's Pay & time off tab shows a dash for any year not entered.
- Wrong: ignoring it. A person with no hours cannot be costed for leave once leave
  arrives.

**Not in Practice HR's feed for a day** lists people whose last sighting is more
than a day old. Only current and starting people are listed (someone who left and
whom HR has dropped is not news).

- *What to do:* if it is one or two names, they have been removed or deleted in
  Practice HR, or never should have been there: confirm with the practice manager
  and, if they should not be here, it is the superuser's decision whether to delete
  them (see [Removing someone](people.md#removing-someone)). If it is **everyone**, the
  sync has been failing for a day; fix that first.

**Leaving in the next 30 days** lists current people whose finish date falls
between today and thirty days away, with the date.

- *What to do:* nothing in this release except to know they are going. A later
  release raises the leaver flags (final pay, leave owed) from this date. A date
  that looks wrong is wrong in Practice HR; fix it there.

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
