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

3. **Migrate**: `deploy/manage migrate`. This creates the database in
   `/var/lib/shift-central` and puts the seventeen
   [departments](departments.md) in. Run `deploy/manage collectstatic --noinput`
   before the first start, and enable the service and the two housekeeping timers
   as the README shows. The units for both feeds are copied then too; their timers
   are enabled in step 5.

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
   allowances are in **hours**. Then Display for job titles and name colours. The
   managers of each team do their own team; an all-teams manager does the managers
   themselves, since nobody sets their own. Allowances can be entered without a
   reason the first time, but a reason is demanded for every later change, so
   check them as you enter them.

10. **Set the departments' colours** on the Departments page so that each is
    distinct (see [Departments](departments.md)), and archive any the practice
    will not use.

When the Health card shows the feed green, no one needing hours, and nobody in "not
in the feed", the foundation is ready for the rota grid. Then lay the rotas out
(see [the rota](rota.md)), and press **Notify staff** when each team's is ready.

## Upgrading a box that runs the Foundation

A server already running Shift Central from before the rota grid takes the
release like any other pull, plus the new settings and the GP feed's units. In
`/srv/shift-central`, as root:

1. `git pull`.
2. `.venv/bin/pip install -r requirements.txt`. Only that file: `requirements-dev.txt`
   is the browser test's (Playwright), and the server never needs it.
3. `deploy/manage migrate` (the `shifts` and `messaging` tables, and the seventeen
   departments if they are not there yet).
4. `deploy/manage collectstatic --noinput`, then `deploy/manage check --deploy`.
5. **Add the new variables** to `/etc/shift-central.env`: `ROTA_URL` and
   `ROTA_API_TOKEN` (go-live step 1 makes the token), and the `EMAIL_*` values
   (go-live step 2). Either can wait; see step 2 for what works without them.
6. **Copy the GP sync's units**: `cp deploy/shift-central-gp-sync.* /etc/systemd/system/`,
   and `cp deploy/gunicorn.service /etc/systemd/system/shift-central.service` if
   it changed.
7. `systemctl daemon-reload`, then `systemctl restart shift-central`.
8. **Enable the GP timer only once `ROTA_URL` and `ROTA_API_TOKEN` are set**: run
   `deploy/manage gp_sync` once and check it says how many GPs it read, then
   `systemctl enable --now shift-central-gp-sync.timer`. Enabled without them, the
   timer fails every fifteen minutes and fills the journal with it.

## Backups

A copy of the database is made every night at 02:30 into
`/var/lib/shift-central/backups/`, kept 30 days and readable only by the app's own
user; if the off-site push is set up (README, "Off-site backup"), it is sent encrypted
to the Proxmox Backup Server straight afterwards. Both are timer-driven and silent
when they work.

**Check them after the first night, and after any change to the units**:

    ls -l /var/lib/shift-central/backups
    systemctl status shift-central-backup.service shift-central-pbs.service
    journalctl -u shift-central-pbs -n 20 --no-pager

A failed push appears nowhere else. Test the PBS copy by restoring it on another
machine with only the key and opening it (README, step 5 of the off-site setup); a
backup never restored is not yet a backup.

What a copy holds: people's names and emails, hours, allowances, managers' notes, the
audit entries, and session keys that work as login cookies. Treat any copy, wherever
it is, as the live database.

## Restore

Decide what went wrong first. A bad change to a few people's hours is better put
right by retyping it (the History link has the old values) than by a restore, which
loses everything typed since the copy. Restore for a corrupt or lost database, or a
migration that went wrong.

From the box's own copy:

    systemctl stop shift-central shift-central-hr-sync.timer shift-central-gp-sync.timer
    ls -l /var/lib/shift-central/backups
    cp -p /var/lib/shift-central/db.sqlite3 /root/db-before-restore.sqlite3
    install -o shift-central -g shift-central -m 600 /var/lib/shift-central/backups/db-<date>.sqlite3 /var/lib/shift-central/db.sqlite3
    rm -f /var/lib/shift-central/db.sqlite3-wal /var/lib/shift-central/db.sqlite3-shm
    deploy/manage migrate
    systemctl start shift-central shift-central-hr-sync.timer shift-central-gp-sync.timer

Stop first, and remove the old `-wal` and `-shm` files: otherwise SQLite replays a
stale log into the restored file. `migrate` brings an older copy up to the current
code. The next sync (within fifteen minutes, or *Sync now*) brings the people
up to date from Practice HR, so **Practice HR does not need restoring with it**; the
next GP sync does the same for the GP sessions. What is lost is what was typed here
after the copy was made: hours, allowances, notes, departments, manager grants and
their entries in the Activity log, **and any rota changes**: shifts, templates and
the list of changes not yet notified. Check those against the History links, and
look over the rota for the weeks that were being laid out, and re-enter what is missing.

From the Proxmox Backup Server, when the machine is gone: build a fresh server as
in the README, put the same units in place, restore the snapshot with the key you
kept off the machine (README, off-site backup, step 5), put the `db-<date>.sqlite3`
at `/var/lib/shift-central/db.sqlite3` owned by `shift-central` with mode 600, and
continue from `deploy/manage migrate`. `/etc/shift-central.env` is not in the backup
(it holds the secrets) and is written again from step 2; a new `SECRET_KEY` just
signs everyone out, and the client id and secret are those Practice HR printed in
step 1, or run `register_oidc_client` again with `--rotate` for new ones.
