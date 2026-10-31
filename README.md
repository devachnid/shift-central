# AMG Shift Central

Staff rotas and leave management for the practice: one rota grid for every
team (GPs included), and leave calculated correctly in hours for everyone. It
replaces FindMyShift. It is the third of the practice's apps, beside the GP
rota (`devachnid/rota`) and Practice HR (`devachnid/practice-hr`), and it signs
people in through Practice HR and reads its people from there, so nobody is
typed in twice.

Built so far: the foundation (sign-in, people fed from Practice HR every
fifteen minutes, teams, departments, who may manage whom, staff profiles with
hours and leave allowances, the activity and log-in logs, and the Staff list's
Health card), the rota grid release, leave, and absence and payroll:

- **The rota grid**: a spreadsheet-style grid of days and people that managers
  type shifts into, drag, copy, template, mark as overtime and print, with
  **Notify staff** emailing each person what changed, and a read-only list of
  the week on a phone.
- **Who's in today** and **the hours report** (per person per week, overtime
  apart, downloadable).
- **The GP feed**: GPs' sessions are read from the GP rota app every fifteen
  minutes, matched by work email, and drawn as read-only tiles.
- **Leave**, in hours, for everyone (GPs included): allowances pro-rated by the weeks a
  person is employed, with dated changes of hours; what a day costs read from the rota
  (an average day where the week has no rota); requests, approvals, cancellations and
  manager bookings, whole days, half days or by the hour, for all fifteen leave types;
  bank holidays (one, or booked for everyone), blackouts, TOIL, adjustments and a
  statement that explains every figure; a leave tile on the grid and the shifts it covers
  hidden; the time off list, the year planner and the leave report; and emails to the
  managers and the person, with a reminder for requests left waiting
  (`shift-central-leave-reminders.timer`). Balances are worked out, never stored.
- **The leave feed**: approved GP leave is served to the GP rota app at
  `/api/v1/leave`, behind a bearer token (see "The leave feed" below). The rota app
  reads it every fifteen minutes in place of FindMyShift.
- **Absence and payroll**: sickness as bookings of Sick leave, counted as instances over a
  rolling six months with Trigger 1, 2 and 3+ (and the managers emailed when one is
  reached), the join-on warning, long sickness and the return flag; converting holiday to
  sickness; the past schedule section for 2026 sickness; the leaver, return and year-end
  flags, emailed by `shift-central-daily-flags.timer`; the monthly payroll report with its
  Excel, Mark as sent and the corrections to months already sent; and the sickness and
  leave one-pagers as a page, a PDF or an Excel file.

Push notifications to the phone app, and the dashboard, shifts and staff-by-hour reports,
follow in later specs (push notifications and the reports are spec 5's). Managers' guides:
[docs/admin/absence.md](docs/admin/absence.md), [docs/admin/leave.md](docs/admin/leave.md)
and [docs/admin/rota.md](docs/admin/rota.md).

The practice manager's requirements, approved on 29 October 2026, are in
[docs/requirements/](docs/requirements/README.md): thirteen documents from
`00-overview.md` to `12-decisions-and-open-questions.md`. Start with the
overview, then the leave policy (`05`) and its worked examples (`06`), which
become the leave calculation's tests. The foundation's design is in
[docs/superpowers/specs/2026-10-29-foundation-design.md](docs/superpowers/specs/2026-10-29-foundation-design.md)
and the leave release's, with the deviations recorded while it was built, in
[docs/superpowers/specs/2026-10-31-leave-design.md](docs/superpowers/specs/2026-10-31-leave-design.md);
the absence and payroll release's, with its deviations, in
[docs/superpowers/specs/2026-10-31-absence-payroll-design.md](docs/superpowers/specs/2026-10-31-absence-payroll-design.md);
later specs and the plans go in `docs/superpowers/specs/` and
`docs/superpowers/plans/`, as in the rota and HR repositories.

Logo files and brand colours are in [docs/brand/](docs/brand/) and described in
the requirements README.

## Develop

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    DEBUG=1 python manage.py migrate
    DEBUG=1 python manage.py runserver
    pytest
    cd frontend && npm test

The browser tests (the grid, and booking and cancelling leave from its menu, driven in Chromium) are skipped unless asked for:
`pip install -r requirements-dev.txt` (Playwright and its pytest plugin, kept
out of `requirements.txt` so the VPS never installs them), then
`python -m playwright install chromium`, then `E2E=1 python -m pytest -q tests/e2e`.
Where Chromium is already installed elsewhere, set `E2E_CHROMIUM` to its path.

The payroll and one-pager downloads use two libraries, `openpyxl` (Excel) and `reportlab`
(PDF). Both are pure Python and installed from `requirements.txt`, so a server needs no
system package for them.

`DEBUG=1` is what lets `manage.py` start on a box with no `SECRET_KEY` in the
environment. It then uses a key of this checkout's own, generated once into the
git-ignored `.dev_secret_key`. With debug off, the settings refuse to run
without a real key (see Deploy). The suite needs neither: it detects pytest.
With no `PRACTICE_HR_URL` set, the login page offers the superuser's password
form only (`DEBUG=1 python manage.py createsuperuser` makes one), and `hr_sync`
refuses to run and says so; with no `EMAIL_HOST`, nothing is sent.

The grid and the colour picker are built from `frontend/` with Vite: `cd frontend && npm install && npm run build` writes `static/dist/`, which is committed. Run the build before committing a frontend change; CI fails on a stale bundle. `npm run dev` rebuilds on save.

The built bundle is committed so that the VPS deploys by `git pull` and has no
node on it.

## CI

`.github/workflows/tests.yml` runs on every pull request and every push to
`main`, and nothing in it needs a secret:

- **tests**: `ruff check .` (pyflakes rules only; see `ruff.toml`),
  `makemigrations --check`, the suite, the browser test (`E2E=1 pytest tests/e2e`,
  in Playwright's Chromium), and `collectstatic` + `check --deploy` against a
  throwaway environment.
- **tests-next-python**: the suite on Python 3.14, an early warning for the next
  interpreter. It is not a required check, and it does not run the browser test.
- **frontend**: `npm ci`, the type check, `npm test`, `npm run build`, and `git diff
  --exit-code -- static/dist`, which fails when the committed bundle is not what
  the source produces.

Locally: `pip install ruff==0.16.6 && ruff check .`.

## Admin guide

Everything a manager or the superuser can set is documented in
[docs/admin/](docs/admin/README.md): one page per area, each field explained
with what depends on it and what goes wrong if it is set wrong. The sequence
below gets the app running; that guide is the reference for what the settings
mean, and [its setup page](docs/admin/setup.md) is the go-live order for the
practice.

## First-time setup

In this order; each step needs the one before it. The first four are on the
server, the rest in the app. The details are in Deploy below and in
[docs/admin/setup.md](docs/admin/setup.md).

1. **Register the client in Practice HR**, which prints the client id and secret
   once, and add an API token to HR's `HR_API_TOKENS`: `deploy/manage
   register_oidc_client --name shift-central --redirect-uri
   https://<host>/oidc/callback/`, run in `/srv/practice-hr`.
2. **Write `/etc/shift-central.env`** with the secret key, the host names, and
   the HR address, token, client id and client secret.
3. **Create the database**: `deploy/manage migrate`.
4. **Create the superuser**: `deploy/manage createsuperuser`. It is the
   break-glass account, signed in at `/admin/` with a password.
5. **Read the people in**: `deploy/manage hr_sync` (then the timer does it every
   fifteen minutes).
6. **Tick *Admin of shift-central* in Practice HR** for the practice manager and
   the three assistant managers: Login accounts › Apps.
7. **Each of them signs in** to Shift Central through the practice account.
8. **Grant the lead nurse Nursing and the head pharmacist Pharmacy** from the
   Permissions link under their profiles.
9. **Fill in hours, days per week and leave allowances** for everyone, working
   down the Health card's *Needs hours and allowances* list.
10. **Set the departments' colours** on the Departments page.

## Deploy (VPS + Cloudflare tunnel)

The app runs as its own `shift-central` user, never as root, in three places:

| Where | Owner | What |
|---|---|---|
| `/srv/shift-central` | root, read-only to the app | the code, its `.venv` and `staticfiles/` |
| `/var/lib/shift-central` | `shift-central`, closed to everyone else | the database and its nightly backups |
| `/etc/shift-central.env` | root, mode 600 | the settings and secrets |

So a bug that let a request run code reaches Shift Central's data and nothing
else: not the tunnel's credentials, not the app's own code, not the GP rota's or
Practice HR's data beside it. Every unit in `deploy/` also runs in a systemd
sandbox; `deploy/gunicorn.service` explains each part.

    useradd --system --home-dir /var/lib/shift-central --no-create-home --shell /usr/sbin/nologin shift-central
    install -d -o shift-central -g shift-central -m 700 /var/lib/shift-central
    git clone https://github.com/devachnid/shift-central /srv/shift-central
    cd /srv/shift-central
    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # requirements.txt only: requirements-dev.txt is for the browser test
    chown -R root:root /srv/shift-central
    chmod -R u=rwX,go=rX /srv/shift-central

### Register the app in Practice HR

Practice HR is the identity provider and the source of people, so it is set up
first. In `/srv/practice-hr`, as root:

    deploy/manage register_oidc_client --name shift-central --redirect-uri https://shifts.example.org/oidc/callback/

It prints a `client_id` and a `client_secret` once (the secret is stored hashed
and cannot be shown again; `--rotate` makes a new one). They go into
`OIDC_RP_CLIENT_ID` and `OIDC_RP_CLIENT_SECRET` below. The redirect URI must
match this app's hostname exactly and be `https`. Registering also gives every
login account in Practice HR an **Admin of shift-central** box, under Login
accounts › Apps; that box is what makes someone an all-teams manager here. See
Practice HR's own guide, "Registering a relying party".

Then make a token for the people feed, one of its own so it can be retired
alone:

    openssl rand -hex 32

Add it to the comma-separated `HR_API_TOKENS` in `/etc/practice-hr.env` (beside
the GP rota's), restart Practice HR, and use the same value as `HR_API_TOKEN`
below. Without it Practice HR answers the feed with 401 and `hr_sync` fails.

### The settings

Create the secrets file, root-only, never in the unit file. The subshell keeps
`umask 077` from leaking into later commands, where it would make files the app
has to read unreadable:

    (
    umask 077
    .venv/bin/python -c 'from django.core.management.utils import get_random_secret_key as k; print("SECRET_KEY=" + k())' > /etc/shift-central.env
    cat >> /etc/shift-central.env <<'EOF'
    DEBUG=0
    DB_PATH=/var/lib/shift-central/db.sqlite3
    ALLOWED_HOSTS=shifts.example.org
    CSRF_TRUSTED_ORIGINS=https://shifts.example.org
    PRACTICE_HR_URL=https://hr.example.org
    HR_API_TOKEN=<the token you made above>
    OIDC_RP_CLIENT_ID=<printed by register_oidc_client>
    OIDC_RP_CLIENT_SECRET=<printed by register_oidc_client>
    ROTA_URL=https://rota.example.org
    ROTA_API_TOKEN=<one of ROTA_API_TOKENS in the rota app's /etc/rota.env>
    LEAVE_API_TOKENS=<token the rota app sends>
    EMAIL_HOST=smtp.example.org
    EMAIL_HOST_USER=<relay user>
    EMAIL_HOST_PASSWORD=<relay password>
    DEFAULT_FROM_EMAIL=Shift Central <shift-central@example.org>
    EOF
    )

**Environment variables** (`/etc/shift-central.env`, all read in
`config/settings.py`; a value takes the whole line, since an env file has no
comment syntax after one):

| Variable | Meaning |
|---|---|
| `SECRET_KEY` | Django's signing key. Required with `DEBUG` off. |
| `DEBUG` | `0` in production (the default); `1` only for development. |
| `DB_PATH` | Where the SQLite database lives. Unset, it sits beside `manage.py`, which is what development wants; production points it at `/var/lib/shift-central/db.sqlite3`, out of the read-only code tree, because SQLite needs to write the directory its database is in. |
| `ALLOWED_HOSTS` | Comma-separated hostnames the app answers for. |
| `CSRF_TRUSTED_ORIGINS` | Comma-separated `https://` origins allowed to POST. |
| `PRACTICE_HR_URL` | Practice HR's address, `https://hr.example.org`, with no trailing path. Sign-in and the people feed both use it. It must be `https`: the client refuses to send the token over anything else. Unset, the login page offers only the superuser's password form and `hr_sync` refuses to run. |
| `HR_API_TOKEN` | The bearer token `hr_sync` sends, one of Practice HR's `HR_API_TOKENS`. Unset, `hr_sync` refuses to run and says so. |
| `OIDC_RP_CLIENT_ID`, `OIDC_RP_CLIENT_SECRET` | Printed once by `register_oidc_client` in Practice HR. |
| `ROTA_URL` | The GP rota app's address, `https://rota.example.org`, no trailing path. `gp_sync` reads `/api/v1/sessions` from it. It must be `https`. Unset (with `ROTA_API_TOKEN`), there is no GP feed: the grid has no GP tiles, `gp_sync` refuses to run, and the Health card says "not configured". |
| `ROTA_API_TOKEN` | The bearer token `gp_sync` sends: one of the GP rota app's `ROTA_API_TOKENS` in its `/etc/rota.env` (comma-separated there; make it with `openssl rand -hex 32`, add it, restart the rota app). |
| `LEAVE_API_TOKENS` | Comma-separated bearer tokens the GP rota app may send to read `/api/v1/leave` (see "The leave feed"). Make each with `openssl rand -hex 32`. Unset, the feed answers 401 to everyone. |
| `API_RATE_LIMIT_PER_MINUTE` | Requests per minute one address may make to the leave feed, counted whether or not the token is right. Defaults to 600; `0` switches the limit off. The count is per gunicorn worker. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | The outgoing mail relay, used by Notify staff to tell people their rota changed. `EMAIL_HOST` set is what "mail is configured" means; `DEFAULT_FROM_EMAIL` is the sender staff see. With none of them, the app works and Notify staff keeps every change unsent. `EMAIL_USE_TLS` defaults on. |
| `TRUSTED_PROXY_IPS` | Comma-separated addresses whose `CF-Connecting-IP` header is believed, for the log-in log's address. Defaults to loopback, which is right behind a Cloudflare tunnel; never set it to a wildcard. The leave feed's rate limit is per client address, so if the proxy's address is not trusted here every caller shares one bucket. |
| `CSP_REPORT_ONLY` | `1` sends the Content-Security-Policy as report-only, blocking nothing: the way back if it blocks something after a deploy. Unset, it is enforced. |

Then:

    deploy/manage collectstatic --noinput
    deploy/manage migrate
    deploy/manage createsuperuser
    cp deploy/gunicorn.service /etc/systemd/system/shift-central.service
    cp deploy/shift-central-backup.* deploy/shift-central-clearsessions.* deploy/shift-central-hr-sync.* deploy/shift-central-gp-sync.* deploy/shift-central-leave-reminders.* deploy/shift-central-daily-flags.* /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --now shift-central shift-central-backup.timer shift-central-clearsessions.timer
    deploy/manage hr_sync
    systemctl enable --now shift-central-hr-sync.timer
    deploy/manage gp_sync
    systemctl enable --now shift-central-gp-sync.timer

`hr_sync` and `gp_sync` are each run by hand once, before their timers are
enabled, so that a wrong URL or token shows up as a message on your screen
rather than as a failed run on the Health card an hour later. A fresh database
has no people until `hr_sync` succeeds, and `gp_sync` needs the GPs to be there
(and `ROTA_URL` and `ROTA_API_TOKEN` set); leave the two `gp_sync` lines out until
the GP rota app has its sessions feed.

Switch the leave reminders on only once mail works (`EMAIL_HOST` set and a test
message delivered):

    deploy/manage leave_reminders
    systemctl enable --now shift-central-leave-reminders.timer
    deploy/manage daily_flags
    systemctl enable --now shift-central-daily-flags.timer

Enabled before that, each reminder is recorded as "mail not configured" and not
sent, and the request counts as reminded, so it is not reminded again; the daily
flags (leavers, returns, the year end) are claimed the same way.

**Run every management command through `deploy/manage`**, as root:
`deploy/manage createsuperuser`, `deploy/manage check --deploy`, `deploy/manage
hr_sync` and so on. It runs the command as the `shift-central` user with the
settings from `/etc/shift-central.env`, exactly as the services do. A plain
`python manage.py` as root is the one way to break this layout. The database
is in WAL mode, so a root process that opens it can leave `db.sqlite3-wal` and
`-shm` files owned by root, and the app then cannot open them. Sourcing the
settings into a shell (`. /etc/shift-central.env`) also fails on a secret key
holding `(` or `$`, which Django's generated keys do.

### The leave feed

Shift Central serves approved GP leave to the GP rota app, which shows it as
time off on its own rota. It is the mirror image of the GP feed above: there
Shift Central reads from the rota app, here the rota app reads from Shift
Central.

    GET https://shifts.example.org/api/v1/leave?from=2027-03-01&to=2027-03-31
    Authorization: Bearer <token>

- **Token.** The `<token>` must be one of `LEAVE_API_TOKENS` in
  `/etc/shift-central.env` (comma-separated; make one with `openssl rand -hex 32`,
  add it, restart Shift Central). Anything else, or no tokens configured, is a
  401. Only `GET` is accepted. Tokens are compared in constant time, every
  request counts against `API_RATE_LIMIT_PER_MINUTE` per address (429 over it),
  and every response is `Cache-Control: no-store`. Serve it over https only; the
  tunnel does.
- **Pointing the rota app at it.** In the rota app's environment file set
  `SHIFT_CENTRAL_URL=https://shifts.example.org` and
  `SHIFT_CENTRAL_TOKEN=<token>`, the same value as one of `LEAVE_API_TOKENS`
  here. The rota app's timer then reads the feed every fifteen minutes. To
  retire a token, remove it from `LEAVE_API_TOKENS` and restart.
- **Range.** `from` and `to` are dates (`YYYY-MM-DD`), `to` not before `from`
  and at most 1,100 days after it; otherwise a 400.
- **What is served.** Approved bookings (and ones with a cancellation waiting
  for a decision) of people marked as GPs, with an email address, whose days
  overlap the range, oldest first:
  `{"from", "to", "generated_at", "leave": [{"email", "first_day", "last_day",
  "part", "type"}]}`. `part` is `whole`, `am` or `pm`; a booking by the hour is
  `am` if it ends by 13:00, `pm` if it starts at or after 13:00, else `whole`.
  The email is the match key and the type is its name ("Holiday").
- **What is never served.** A booking's description, a note, a reason, its
  id, the person's name, hours or cost, pending, declined or cancelled bookings,
  and anyone who is not a GP. The response body is never logged, and no log
  line carries a token, an email or a note.

### The tunnel

Add a third public hostname to the Cloudflare tunnel, beside the GP rota's and
Practice HR's, and point its ingress at `http://127.0.0.1:8323`. (The rota is on
8321 and Practice HR on 8322.) Gunicorn binds to loopback only, on purpose; see
`deploy/gunicorn.service`. The hostname must be the one in `ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS` and the redirect URI registered in Practice HR; change it
later and sign-in stops until all three agree.

`shift-central-hr-sync.timer` runs `hr_sync` every fifteen minutes,
`shift-central-gp-sync.timer` runs `gp_sync` every fifteen minutes at seven past
the quarter hour (so the two never coincide),
`shift-central-leave-reminders.timer` runs `leave_reminders` at 08:20 on weekdays
(it emails the managers about leave requests left waiting longer than the Leave
settings page allows, once per request),
`shift-central-daily-flags.timer` runs `daily_flags` at 08:25 every day (the leaver
reminder a week out, the return from a long absence and the year-end flag, each
emailed to the managers once), and
`shift-central-clearsessions.timer` clears expired sessions nightly (a session
lasts ten minutes from the last request, and each sign-in leaves a row).

**Logs** go to the journal: `journalctl -u shift-central`. There is one line per
request (`shiftcentral.access`: the client's address from Cloudflare,
`user=<id>` or `anon`, method, path, status, time), without query strings.
Also logged: server errors with tracebacks, disallowed hosts and CSRF failures
(`django.security`), and a failed `hr_sync` (`journalctl -u
shift-central-hr-sync`, `-u shift-central-gp-sync`). The syncs' own results are also
on the Staff page's Health card.

**A Content-Security-Policy** is on every page the app renders (not the admin,
whose theme needs `eval`): no inline script, no event-handler attributes, no
`eval`, nothing from another origin. After a deploy, open the site with the
browser's console showing; a "Refused to..." line means the policy blocked
something. To turn blocking off without a code change, set `CSP_REPORT_ONLY=1`
in `/etc/shift-central.env` and restart.

`systemd-analyze security shift-central` scores the sandbox.

### Redeploying

**`collectstatic` is not optional on a redeploy.** With `DEBUG=0` every
`{% static %}` resolves through a manifest that `collectstatic` writes, so
pulling code that references a new asset without rebuilding the manifest makes
*every page* return 500, with the traceback going only to the journal. The
frontend bundle in `static/dist/` arrives with the pull, already built.

    cd /srv/shift-central
    git pull
    .venv/bin/pip install -r requirements.txt
    deploy/manage migrate
    deploy/manage collectstatic --noinput
    deploy/manage check --deploy   # fails loudly if the manifest is stale
    systemctl restart shift-central

The `git pull` runs as root, so the tree stays root's. A pull that changes a
file in `deploy/` needs that unit copied into `/etc/systemd/system/` again,
then `systemctl daemon-reload`. The `.service` files are the ones that change.

### Check the deployment is not in debug mode

`DEBUG` defaults to off, but a stray `DEBUG=1` turns on tracebacks, publishes
the URL map on every 404, and drops HSTS and the `Secure` cookie flags. Two
commands tell you:

    curl -sI https://shifts.example.org/accounts/login/ | grep -i 'strict-transport\|set-cookie'
    curl -s https://shifts.example.org/no-such-path/ | grep -c 'Django tried these URL patterns'

The first must show `Strict-Transport-Security` and a `csrftoken` cookie marked
`Secure`; the second must print `0`.

## Backups

`shift-central-backup.timer` runs `deploy/backup.sh` at 02:30 as the
`shift-central` user: a SQLite `.backup` copy of the database into
`/var/lib/shift-central/backups/db-YYYY-MM-DD.sqlite3`, kept 30 days, readable
only by that user. Each copy is complete: names, emails, hours, allowances,
managers' notes, and session keys that work as login cookies. That is why it
lives in the closed state directory, and why a root `sqlite3` is never used on
the live file.

### Off-site backup to a Proxmox Backup Server

The nightly copy sits on the same machine as the database.
`shift-central-pbs.service` pushes `/var/lib/shift-central/backups` to a
Proxmox Backup Server (PBS) with `proxmox-backup-client`, straight after
`shift-central-backup.service` succeeds. It sends the finished copies, never the
live WAL database, and encrypts them before they leave, so the PBS holds no
plaintext. It is optional: a host without it still backs up locally.

1. **Install the client** (Debian 13; for 12 use `bookworm` and Proxmox's
   `proxmox-release-bookworm.gpg`, and check the key against the checksum on
   Proxmox's docs page):

       wget https://enterprise.proxmox.com/debian/proxmox-archive-keyring-trixie.gpg -O /usr/share/keyrings/proxmox-archive-keyring.gpg
       printf 'Types: deb\nURIs: http://download.proxmox.com/debian/pbs-client\nSuites: trixie\nComponents: main\nSigned-By: /usr/share/keyrings/proxmox-archive-keyring.gpg\n' > /etc/apt/sources.list.d/pbs-client.sources
       apt update && apt install proxmox-backup-client

2. **Reach the PBS over a private link**, never over the internet: WireGuard on
   the PBS host, so it answers on an address like `10.88.0.1`, with its firewall
   allowing port 8007 only from this host's tunnel address.

3. **On the PBS**: one namespace, user and token for this app, allowed only to
   *back up* into that namespace. `DatastoreBackup` cannot prune or delete, so
   a compromised host cannot erase its own history. Grant the role to the user
   and to the token (a token never has more than its user), then add a prune
   job for the namespace in the web UI (Datastore, Prune & GC).

       proxmox-backup-client namespace create shift-central --repository root@pam@localhost:<datastore>
       proxmox-backup-manager user create vps-shift-central@pbs
       proxmox-backup-manager user generate-token vps-shift-central@pbs backup
       proxmox-backup-manager acl update /datastore/<datastore>/shift-central DatastoreBackup --auth-id vps-shift-central@pbs
       proxmox-backup-manager acl update /datastore/<datastore>/shift-central DatastoreBackup --auth-id 'vps-shift-central@pbs!backup'

   Keep the token secret it prints, and the certificate fingerprint from the
   dashboard (Show Fingerprint). Choose the prune retention by how long the
   practice may keep this data.

4. **On this host**: the key and the secrets, root-only.

       install -d -m 700 /etc/pbs-backup
       proxmox-backup-client key create /etc/pbs-backup/shift-central.key --kdf none
       proxmox-backup-client key paperkey /etc/pbs-backup/shift-central.key
       ( umask 077
       printf 'PBS_REPOSITORY=vps-shift-central@pbs!backup@10.88.0.1:8007:<datastore>\nPBS_FINGERPRINT=<fingerprint>\n' > /etc/pbs-backup/shift-central.env
       printf '%s' '<token secret>' > /etc/pbs-backup/shift-central.token )

   The token is a file, not a variable, so it is never in a process environment
   where the web service could read it. **Copy the key (or its paper print)
   somewhere off this host now.** Without it every pushed backup is unreadable.
   Then install the units; the drop-in makes the push follow each successful
   backup:

       cp deploy/shift-central-pbs.service /etc/systemd/system/
       install -D deploy/shift-central-backup-pbs.conf /etc/systemd/system/shift-central-backup.service.d/pbs.conf
       systemctl daemon-reload

5. **Test it, including a restore.** Run a backup, check the snapshot appears
   under the `shift-central` namespace, then restore it on another machine with
   only the key, and open the copy:

       systemctl start shift-central-backup.service && journalctl -u shift-central-pbs -n 20 --no-pager
       proxmox-backup-client snapshot list --ns shift-central
       proxmox-backup-client restore host/shift-central/<timestamp> data.pxar ./restore-test --ns shift-central --keyfile shift-central.key
       sqlite3 restore-test/db-<date>.sqlite3 'select count(*) from people_person'

   A failed push shows in `journalctl -u shift-central-pbs` and `systemctl
   status shift-central-pbs`; nothing else tells you, so look after the first
   night.

## Restore

From the box's own copy (the usual case: a bad deploy or a mistaken change):

    systemctl stop shift-central shift-central-hr-sync.timer shift-central-gp-sync.timer shift-central-leave-reminders.timer shift-central-daily-flags.timer
    ls -l /var/lib/shift-central/backups
    cp -p /var/lib/shift-central/db.sqlite3 /root/db-before-restore.sqlite3
    install -o shift-central -g shift-central -m 600 /var/lib/shift-central/backups/db-<date>.sqlite3 /var/lib/shift-central/db.sqlite3
    rm -f /var/lib/shift-central/db.sqlite3-wal /var/lib/shift-central/db.sqlite3-shm
    deploy/manage migrate
    systemctl start shift-central shift-central-hr-sync.timer

Then start `shift-central-gp-sync.timer`, `shift-central-leave-reminders.timer` and
`shift-central-daily-flags.timer` as well, but only the ones that were enabled (`systemctl
is-enabled shift-central-gp-sync.timer shift-central-leave-reminders.timer
shift-central-daily-flags.timer` says): a timer started before its settings are in place
fails every fifteen minutes (the GP sync) or marks requests and flags as sent when no mail can go
(the reminders and the daily flags).

Stopping first matters: a copy dropped under a running app leaves the old
`-wal` file beside it, and SQLite would replay it into the restored database.
The first line also stops the syncs and the reminders, so they cannot write into the restored file
before you have looked at it. Keep the `cp -p` of the database you are
replacing until you are sure. `deploy/manage migrate` brings an older copy up
to the current code, and the next `hr_sync` (within fifteen minutes) brings
the people it holds up to date from Practice HR, so a restore never needs HR
restored with it. What a restore loses is what was typed here after the copy:
hours, allowances, notes, departments, manager grants, leave requested or booked, and
the audit entries for them.

From the PBS (the box is gone): install the same units on a fresh VPS, restore
the snapshot as in step 5 above using the key you kept off the box, copy the
`db-<date>.sqlite3` to `/var/lib/shift-central/db.sqlite3`, owned by
`shift-central` and mode 600, and carry on from `deploy/manage migrate`. The
`/etc/shift-central.env` has to be written again: it is not in the backup,
because it holds secrets. The `SECRET_KEY` may be new (everyone signs in
again); the OIDC client id and secret are those printed by Practice HR, or
register again with `--rotate`.
