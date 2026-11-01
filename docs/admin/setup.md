# Setting up

**Where:** Practice HR, the server, then the app. The commands for the server are in
the project README (Deploy); this page is the order they are done in for the
practice's go-live, and why.

## The mental model

**Each step needs the one before it.** Practice HR must know about the app before
anyone can sign in; the app must have read the people before a manager can be
recognised; a manager must exist before they can grant another. Do them out of order
and the symptom is a sign-in that lands on the "not yet on the rota" page, which
looks like a fault and is only the sequence.

**Practice HR has to be live first**, with everyone's employee record and position
entered. That is Practice HR's own go-live, and managers start data set-up here in
early December 2026, so it is the dependency with a date.

## The go-live order

1. **Register Shift Central in Practice HR.** On the server, in `/srv/practice-hr`,
   `deploy/manage register_oidc_client --name shift-central --redirect-uri
   https://<host>/oidc/callback/`. It prints the client id and secret **once**;
   keep them. The `<host>` must be the hostname the tunnel will serve, exactly, and
   `https`. A wrong redirect URI shows as Practice HR refusing the sign-in later.
   Also make an API token (`openssl rand -hex 32`), add it to `HR_API_TOKENS` in
   `/etc/practice-hr.env` beside the others, and restart Practice HR. Without the
   token, step 5 fails with "returned 401".

   For the GP sessions, do the same in the GP rota app (`/srv/rota`): make another
   token (`openssl rand -hex 32`), add it to the comma-separated `ROTA_API_TOKENS`
   in `/etc/rota.env`, and restart the rota app. The rota app must be the version
   with the sessions feed (`/api/v1/sessions`); without it, or without the token,
   the [GP sync](sync.md#when-the-gp-sync-fails) fails with "returned 404" or "401".
   This can wait until the GP sessions are wanted: the rest of the go-live does not
   depend on it, and the Health card says "not configured" meanwhile.

2. **Write the environment file**, `/etc/shift-central.env`, root-only: the
   secret key, `DB_PATH`, the host and origin, `PRACTICE_HR_URL`, `HR_API_TOKEN`,
   and the client id and secret from step 1. Add `ROTA_URL` (the GP rota app's
   address, `https`, no path) and `ROTA_API_TOKEN` (the rota-side token from step 1)
   for the GP sessions, and the `EMAIL_*` variables for **Notify staff**:
   `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
   `EMAIL_USE_TLS` and `DEFAULT_FROM_EMAIL` (the address staff see the email come
   from). Every variable is explained in the README's table. A missing one is usually
   loud (the app will not start); a wrong `PRACTICE_HR_URL` is not, and shows in
   step 5. Without `EMAIL_HOST` the app works, the grid included, and Notify staff
   sends nothing: nothing is tried, each send is recorded as "mail not configured",
   and the changes are kept for when mail is set up. There is no "print the email
   to the log" fallback.
   Without `ROTA_URL` or `ROTA_API_TOKEN` the grid has no GP tiles and the Health card
   says "GP rota: not configured".
   Add `LEAVE_API_TOKENS` too if the GP rota app is to read GP leave from here: one or
   more tokens, comma-separated, made with `openssl rand -hex 32`; the rota app gets one
   of them (see [the GP leave feed](sync.md#the-gp-rota-app-reads-gp-leave-from-here)).
   Without it the feed answers 401 to everyone, and nothing else is affected.

3. **Migrate**: `deploy/manage migrate`. This creates the database in
   `/var/lib/shift-central` and puts in the seventeen [departments](departments.md),
   the fifteen [leave types](leave.md#leave-types) and the England and Wales bank
   holidays for 2026 and 2027. Run `deploy/manage collectstatic --noinput`
   before the first start, and enable the service and the two housekeeping timers
   as the README shows. The units for both feeds, the leave reminders and the daily flags are
   copied then too; the feeds' timers are enabled in step 5, and the reminders' and the
   daily flags' once mail works (step 11).

4. **Create the superuser**: `deploy/manage createsuperuser`, with a long password.
   It is the break-glass account: it signs in at `/admin/` with a password even
   when Practice HR is down, and it is the only account that can edit
   [teams](people.md#teams). It is not a manager and needs no person record.

5. **Read the people in**: `deploy/manage hr_sync`, then enable
   `shift-central-hr-sync.timer`. Expect "*N* people read from Practice HR". If it
   fails, [the table](sync.md#when-the-sync-fails) has the message; fix that
   before going on. Once `ROTA_URL` and `ROTA_API_TOKEN` are set, run `deploy/manage
   gp_sync` the same way and enable `shift-central-gp-sync.timer` (every fifteen
   minutes, seven past the quarter hour so it never meets the HR timer). The
   GPs must be marked as GPs in Practice HR first, or their sessions will be listed
   as unmatched. Afterwards, open `/admin/people/team/` and set each team's
   **Display order** so the Staff list is in the order the practice expects
   (GPs, Reception, Admin/Secretarial, Nursing, Pharmacy, Management,
   Cleaning, or whatever HR calls them), and untick **Active** on any team
   that should not be offered.

6. **Tick *Admin of shift-central* in Practice HR** for the practice manager and the
   three assistant managers: Login accounts › the account › Apps. The box exists
   only after step 1. Nothing here changes until each of them signs in (step 7).

7. **Each of the four signs in** to Shift Central through the practice account. This is what
   links their login to their person and makes them an all-teams manager. If one
   lands on "You're not yet on the rota", check that their Practice HR login is
   linked to their employee record, and that step 5 included them. Check the
   [Log in logs](access.md#the-two-logs) afterwards: four rows.

8. **Grant the lead nurse Nursing and the head pharmacist Pharmacy.** An all-teams
   manager opens the lead nurse from the Staff list, **Permissions**, ticks
   *Nursing*, **Update permissions**; the same for the head pharmacist and *Pharmacy*.
   (Both must be on the Staff list, so step 5 must have included them; they do not
   need to have signed in yet.) Team managers then see only their team's people,
   emails and dates, and Activity log entries. See [Access](access.md).

9. **Fill in hours, days per week and leave allowances** for everyone, starting
   with whoever the Health card's *Needs hours and allowances* box lists. For each
   person: profile › Pay & time off. Do the two leave years, and remember that
   allowances are in **hours**; the pro-rating for starters and leavers is done
   for you ([Leave](leave.md#allowances-and-hours-changes)). Then Display for job titles and name colours. The
   managers of each team do their own team; an all-teams manager does the managers
   themselves, since nobody sets their own. Allowances can be entered without a
   reason the first time, but a reason is demanded for every later change, so
   check them as you enter them.

10. **Set the departments' colours** on the Departments page so that each is
    distinct (see [Departments](departments.md)), and archive any the practice
    will not use.

11. **Switch the leave reminders on**: with `EMAIL_HOST` set, run
    `deploy/manage leave_reminders` once (it prints how many reminders it sent) and
    enable `shift-central-leave-reminders.timer`. Then, for the practice manager only,
    tick *Own leave needs no approval* under their Permissions link, and look over
    Settings › Leave types, Bank holidays and Leave settings; see [Leave](leave.md).
    Then run `deploy/manage daily_flags` once (it prints three counts) and enable
    `shift-central-daily-flags.timer`, which sends the leaver, return and year-end emails
    at 08:25 every day; see [Absence and payroll](absence.md#the-daily-command).

When the Health card shows the feed green, no one needing hours, and nobody in "not
in the feed", the foundation is ready for the rota grid. Then lay the rotas out
(see [the rota](rota.md)), and press **Notify staff** when each team's is ready.

## Demo data for a staging box

**Only on a staging box, never on the practice's own.** `seed_demo` fills a staging Shift
Central with fictional working data, so the rota, the leave pages and the Health card have
something in them to look at. It makes no people: they come from Practice HR, as everywhere
else. The three apps share one fictional cast of nineteen, and the Practice HR and rota
seeds give each person an address built from one base: for the base `tom@example.org`,
Morgan Ellis is `tom+morgan.ellis@example.org` (lower-case `first.last`, tagged on with a
`+`). `seed_demo` finds the cast by those addresses, so give it the base the Practice HR
seed was given. The base must have exactly one `@` and no `+`.

**The order**, each step needing the one before:

1. The tunnel, and the environment file (go-live steps 1 and 2).
2. The superusers (step 4).
3. The Practice HR seed, then the rota app's seed, in their own repositories.
4. `deploy/manage hr_sync`: reads the nineteen in (step 5).
5. `deploy/manage gp_sync`, once the rota app is up: reads the GPs' sessions.
6. This command:

       deploy/manage seed_demo --email-base tom@example.org --yes-this-is-staging

**What it refuses.** Without `--yes-this-is-staging`; with fewer than the nineteen in the
database (it says how many are missing and "run hr_sync first"); and with any person in the
database who is not one of the nineteen. Each refusal changes nothing, and none names anyone.

**What it creates**, all through the same services the screens use, so every change is in the
[Activity log](access.md#the-two-logs), made by an inactive login called
`seed-demo@shift-central.invalid` that nobody can sign in as:

- **Hours, days per week and two leave years of allowances** for everyone but the GPs, so the
  Health card's *Needs hours and allowances* box is empty afterwards. Allowances are five
  weeks' hours of annual leave and 1.6 weeks' of bank holiday leave, in hours, for the
  current and the next leave year.
- **Job titles and name colours**, where a person has none. Nothing a manager has typed is
  overwritten.
- **Team grants**: the lead nurse manages Nursing and the head pharmacist Pharmacy, as in
  go-live step 8.
- **The four all-teams managers are not made here.** That is Practice HR's *Admin of
  shift-central* box (go-live step 6), applied when each of them signs in (step 7); the command
  does nothing for them and says so when it finishes.
- **A rota** for Reception, Admin/Secretarial, Nursing, Pharmacy and Cleaning staff: this week
  and the next four, each person on their own days only, weekends empty and nobody on a bank
  holiday (Reception 08:00 to 16:15 and 10:15 to 18:30, early and late; Nursing 08:30 to 17:00). The
  weeks the leave below falls in are written too, so every booked day is costed from a rota and none is
  left as an "average day" to check. GPs' sessions and the managers' rows are left alone.
- **Nine leave records**: a Holiday week for each of two receptionists next month, a Holiday day for
  a nurse, a half day for a secretary, a request by a receptionist that is approved, one by a pharmacy
  technician left **waiting for a manager's decision**, a Sick leave booking last month, a dates-only
  past sickness record, and one Holiday booking that was cancelled. Nobody goes over their allowance.

**It sends nothing.** Leave bookings normally email the managers or the person after they are
saved. Here no message is composed at all, whatever the `EMAIL_*` settings are, and the Outbox is
left empty (not filled with "mail not configured" rows that read as failures). The seeded rota is
also taken as the starting point, so the grid's **Notify staff** has nothing waiting. The cast's plus-addresses
all land in the base address's one real inbox, which is why this matters on a box that has a relay.

**Running it again** is safe: it fills what is missing and changes nothing else, so a second run on the same
day does nothing. On a later day it adds the rota weeks that have come into range, and
not a second set of leave records.

**Clearing it.** There is no undo: delete the staging database (and run `migrate`, `hr_sync` and
the rest again). **Never run it on production**: it writes people's hours, allowances and leave, and
the flag is there so that it cannot be run by accident.

## Upgrading a box that runs an earlier release

The engagement release (open shifts, messages, uploads, phone notifications) has its own short
checklist in the README, "Upgrading to the engagement release". The list below carries a box
from earlier releases up to absence and payroll.

A server already running Shift Central takes the release like any other pull, plus the
new settings and units. This is the checklist for the absence and payroll release, and it also
carries a box from the Foundation, the rota grid or the leave release through their steps (6 and 8 are the
GP sync's, 9 the leave reminders'). In `/srv/shift-central`, as root:

1. `git pull`.
2. `.venv/bin/pip install -r requirements.txt`. Only that file: `requirements-dev.txt`
   is the browser test's (Playwright), and the server never needs it. The absence and payroll
   release adds `openpyxl` (the Excel files) and `reportlab` (the PDFs): both pure Python, so
   nothing is compiled and no system package is needed.
3. `deploy/manage migrate`. For leave it creates the `leave` tables and fills them: the
   fifteen leave types and the bank holidays for 2026 and 2027. It also adds the allowance
   periods (each existing allowance row gains the first day of its year as its start, and
   a place for weekly hours, days per week and "hours already copied", so every figure
   already typed stands as it was) and the column that lets a rota entry be covered by
   leave. A box from before the rota grid also gets the `shifts` and `messaging` tables and
   the seventeen departments. For absence and payroll it adds the two leave type flags (Sick
   leave counts as sickness; Maternity and Adoption flag the return), dates-only bookings, the
   year-end table, the leaver flag dates on each person and the payroll run table. Nothing existing
   changes.
4. `deploy/manage collectstatic --noinput` (it copies the PDF's logo), then `deploy/manage check --deploy`.
5. **Add the new variables** to `/etc/shift-central.env`: `LEAVE_API_TOKENS` (a token for
   the GP rota app, made with `openssl rand -hex 32`; see go-live step 2), `ROTA_URL` and
   `ROTA_API_TOKEN` and the `EMAIL_*` values if they are not there yet (go-live steps 1
   and 2). `API_RATE_LIMIT_PER_MINUTE` is optional. Any can wait; see step 2 for what
   works without them.
6. **Copy the units**: `cp deploy/shift-central-gp-sync.* deploy/shift-central-leave-reminders.*
   deploy/shift-central-daily-flags.* /etc/systemd/system/`, and `cp deploy/gunicorn.service /etc/systemd/system/shift-central.service`
   if it changed.
7. `systemctl daemon-reload`, then `systemctl restart shift-central`.
8. **Enable the GP timer only once `ROTA_URL` and `ROTA_API_TOKEN` are set**: run
   `deploy/manage gp_sync` once and check it says how many GPs it read, then
   `systemctl enable --now shift-central-gp-sync.timer`. Enabled without them, the
   timer fails every fifteen minutes and fills the journal with it.
9. **Enable the leave reminders timer once mail works** (`EMAIL_HOST` set and a test message
   delivered): run `deploy/manage leave_reminders` once, which prints "0 reminders sent" on a new
   install, then `systemctl enable --now shift-central-leave-reminders.timer`. It runs at 08:20 on
   weekdays. Enabled earlier, each reminder is recorded as "mail not configured" and not sent,
   and the request counts as reminded, so it is not reminded again. With `EMAIL_*` unset, every
   other leave email is recorded the same way.
10. **Enable the daily flags timer once mail works**: run `deploy/manage daily_flags` once (it prints
    three counts: leaver reminders, return flags and year-end flags) then
    `systemctl enable --now shift-central-daily-flags.timer`. It runs at 08:25 every day. Enabled
    before mail works, each leaver, return and year-end email is recorded as "mail not configured"
    and counts as sent, so it is not sent again later. See [Absence and payroll](absence.md#the-daily-command).
11. **In the GP rota app**, on its own server. A box that ran its old FindMyShift reader first
    has that timer disabled and removed: its guide's "Moving from FindMyShift" gives the commands
    (`rota-findmyshift.timer`). Then, as root in `/srv/rota`, pull the release. Set
    `SHIFT_CENTRAL_URL` (this box's address, `https`) and `SHIFT_CENTRAL_TOKEN` (one of the
    `LEAVE_API_TOKENS` from step 5) in its environment file, so that `check --deploy` can check
    them. Follow the rota README's *Redeploying* section: `.venv/bin/pip install -r requirements.txt`,
    `deploy/manage migrate`, `deploy/manage collectstatic --noinput` (this release changes the
    rota's CSS, so it is not optional) and `deploy/manage check --deploy`. Copy
    `deploy/rota-shift-central.service` and `deploy/rota-shift-central.timer` to
    `/etc/systemd/system/`, run `systemctl daemon-reload`, then `systemctl restart rota`. Then follow its own
    `docs/admin/shift-central.md` for the rest, in its order: give each clinician a login email, map
    the leave types, run the first sync, enable the timer. Until then the rota app has no GP leave
    and nothing here is affected.

Allowances already typed stand as they were. The leave pages start empty; before staff are
asked to request 2027 leave, check that everyone has a 2027 allowance: the Health card's
*Needs hours and allowances* box lists anyone without hours or without an allowance for the
current or the next leave year.

## Backups

A copy of the database is made every night at 02:30 into
`/var/lib/shift-central/backups/`, kept 30 days and readable only by the app's own
user, with a `media-DATE.tar.gz` of the uploaded documents beside each; if the off-site push is set up (README, "Off-site backup"), it is sent encrypted
to the Proxmox Backup Server straight afterwards. Both are timer-driven and silent
when they work.

**Check them after the first night, and after any change to the units**:

    ls -l /var/lib/shift-central/backups
    systemctl status shift-central-backup.service shift-central-pbs.service
    journalctl -u shift-central-pbs -n 20 --no-pager

A failed push appears nowhere else. Test the PBS copy by restoring it on another
machine with only the key and opening it (README, step 5 of the off-site setup); a
backup never restored is not yet a backup.

What a copy holds: people's names and emails, hours, allowances, leave bookings with their
descriptions and notes, managers' notes, the audit entries, and session keys that work as
login cookies. Treat any copy, wherever
it is, as the live database.

## Restore

Decide what went wrong first. A bad change to a few people's hours is better put
right by retyping it (the History link has the old values) than by a restore, which
loses everything typed since the copy. Restore for a corrupt or lost database, or a
migration that went wrong.

From the box's own copy:

    systemctl stop shift-central shift-central-hr-sync.timer shift-central-gp-sync.timer shift-central-leave-reminders.timer shift-central-daily-flags.timer shift-central-push.timer
    ls -l /var/lib/shift-central/backups
    cp -p /var/lib/shift-central/db.sqlite3 /root/db-before-restore.sqlite3
    install -o shift-central -g shift-central -m 600 /var/lib/shift-central/backups/db-<date>.sqlite3 /var/lib/shift-central/db.sqlite3
    rm -f /var/lib/shift-central/db.sqlite3-wal /var/lib/shift-central/db.sqlite3-shm
    deploy/manage migrate
    systemctl start shift-central shift-central-hr-sync.timer

Then start `shift-central-gp-sync.timer`, `shift-central-leave-reminders.timer`,
`shift-central-daily-flags.timer` and `shift-central-push.timer` as well, but only the ones
that were enabled (`systemctl is-enabled shift-central-gp-sync.timer
shift-central-leave-reminders.timer shift-central-daily-flags.timer
shift-central-push.timer` says): a timer started before its settings are in place
fails every fifteen minutes (the GP sync) or marks requests and flags as sent when no mail can go
(the reminders and the daily flags).

Stop first, and remove the old `-wal` and `-shm` files: otherwise SQLite replays a
stale log into the restored file. `migrate` brings an older copy up to the current
code. The next sync (within fifteen minutes, or *Sync now*) brings the people
up to date from Practice HR, so **Practice HR does not need restoring with it**; the
next GP sync does the same for the GP sessions. What is lost is what was typed here
after the copy was made: hours, allowances, notes, departments, manager grants and
their entries in the Activity log, **leave requested, approved or booked since**, and any
adjustments, **and any rota changes**: shifts, templates and the list of changes not yet
notified. Check those against the History links, and
look over the rota for the weeks that were being laid out, and re-enter what is missing.

From the Proxmox Backup Server, when the machine is gone: build a fresh server as
in the README, put the same units in place, restore the snapshot with the key you
kept off the machine (README, off-site backup, step 5), put the `db-<date>.sqlite3`
at `/var/lib/shift-central/db.sqlite3` owned by `shift-central` with mode 600, and
continue from `deploy/manage migrate`. `/etc/shift-central.env` is not in the backup
(it holds the secrets) and is written again from step 2; a new `SECRET_KEY` just
signs everyone out, and the client id and secret are those Practice HR printed in
step 1, or run `register_oidc_client` again with `--rotate` for new ones.
