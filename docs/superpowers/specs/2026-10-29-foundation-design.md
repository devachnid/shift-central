# AMG Shift Central: foundation — design

**Date:** 2026-10-29
**Status:** approved in conversation; spec for review
**Requirements:** `docs/requirements/` (the practice manager's pack of
29 October 2026) as amended by `docs/requirements/2026-10-29-proposed-amendments.md`.
This spec covers PEOPLE-01 to 08, PAT-01, 03, 07 (as amended), ROTA-02,
FMS items 15 to 18, 20 to 22, 24, 26, 27, 29, 55, 65, ACC-01 to 04, 06
(the rows this release has data for), 07 to 09, REP-06, INT-01 and the
dependency side of MIG-02.

AMG Shift Central replaces FindMyShift: one rota grid for every team, GPs
included, and leave calculated correctly in hours for everyone. It is the
third of the practice's apps, beside the GP rota (`devachnid/rota`) and
Practice HR (`devachnid/practice-hr`), and shares their sign-in.

## The set, and where this spec sits

Decided in conversation on 2026-10-29. Each item is its own spec, plan and
build, in this order, following the practice manager's build order and the
two dates that matter: managers start data set-up in early December 2026,
and the system launches on 1 January 2027.

1. **Foundation** — this spec. The project, deploy, sign-in through
   Practice HR, people fed from Practice HR, teams and manager access,
   departments, staff profiles with hours and allowances, log-in and
   activity logs, and the FindMyShift-style shell. What managers need to
   start set-up.
2. **Rota grid** — shifts, the grid and all its editing, overtime marks,
   notify staff, the hours report, GP sessions shown from the rota app.
3. **Leave** — allowances in use, the ledger, costing from the rota, the
   pro-rata rules, bank holidays, requests and approvals, balances and
   reports, every worked example as a test; the rota reads GP leave from
   here. Email notifications.
4. **Absence and payroll** — sickness instances and triggers, the past
   schedule section, TOIL, leaver flags, the payroll report, one-pagers,
   year-end carry-over.
5. **Engagement** — open shifts, the installable phone app with push
   notifications, messages, notice board, uploads, outbox, dashboard and
   remaining reports.

## Decisions made in conversation

| Decision | Rationale |
|---|---|
| **A separate Django project in its own repository**, own database, own service and hostname on the same VPS as the rota and HR, through the existing Cloudflare tunnel. | Shift Central holds its own staff data, rotas and leave; neither existing app's data model fits it (HR's leave design is superseded, the rota models GP sessions only). Its only cross-app traffic is to HR's API and OIDC endpoints, which work the same from a third hostname. |
| **People come from Practice HR**, not typed in twice. Shift Central polls HR's existing read API for names, emails, teams, start and end dates. Managers type only what HR does not hold. | A leaving date entered in one system and not the other is the kind of wrong leave figure the project exists to remove. HR's `people` endpoint already serves these fields for the rota. Amends PAT-07 and INT-01; the practice manager's decision is pending. |
| **HR is the identity provider; its `employee_id` claim binds a sign-in to a person**, and its per-app `admin` claim makes the all-teams managers. | One account across the practice's apps (ACC-01). Binding by employee id is more reliable than by email, and reusing the `admin` claim avoids a second list of who the practice manager and assistants are. |
| **GP sessions stay in the rota app; GP leave lives here** (spec 2 shows sessions read-only; spec 3 serves leave to the rota). | One master for each thing. Amends ROTA-GP-01, 03, 04; the practice manager's decision is pending. This spec only needs to know who is a GP. |
| **Server-rendered Django with one built island for the grid.** Lists, forms, reports and pop-ups are Django templates; the grid (spec 2) is a Preact + TypeScript component built by Vite. The built bundle is committed, so the VPS still deploys by `git pull`. | The grid needs a real frontend; the forty-odd simple screens do not, and a full SPA would double the work on them with nine weeks to launch. The "no build step" rule of the other two repositories is relaxed for this one, on purpose. |
| **This spec ships the toolchain with one small component** (the colour picker) rather than waiting for the grid. | The pipeline — build, commit, CI staleness check, collectstatic, CSP — is proved before spec 2 depends on it. |
| **Date of birth, gender, mobile and alternate phone are not held here**, though FindMyShift's profile has them (FMS item 16). | Nothing in the pack uses them (SMS was dropped), HR holds them, and a rota app should not duplicate personal data. A deliberate deviation from FMS-00, recorded for the practice manager. |
| **Allowances are stored in this release**, as plain figures per person per leave year, and used in spec 3. | December set-up needs the boxes; the arithmetic can follow. |
| **SQLite with WAL**, as the rota and HR. | One practice's headcount; the backup tooling exists. |

## Global constraints

Inherited from the rota and HR unless stated.

- Django 5.2 LTS, Python 3.13, SQLite WAL. Unfold for the Django admin,
  which is for the superuser's setup and break-glass only; every day-to-day
  screen is the app's own. No third-party request from a page: fonts,
  scripts and styles are served from this app.
- **Secrets from the environment only.** No key, token or password in any
  file in the repository or in any log line.
- **All writes to `people` go through `people/services/`**, never a view,
  a form's `save()` or the admin directly. Every service call that changes
  a field writes an `AuditEntry` per field (section 6).
- **Frontend source lives in `frontend/`; its build output in
  `static/dist/` is committed.** CI rebuilds and fails if the committed
  output differs. No node on the VPS.
- Every colour from `static/css/tokens.css`. The brand: navy `#143D5C`,
  amber `#F2A33A`, white, pale grey-blue `#DDE7EE`; Manrope (SIL OFL)
  self-hosted as woff2 in `static/fonts/`, falling back to Segoe UI and
  Arial.
- Dates and times are Europe/London. Money never appears.

## 1. Architecture

**Apps in this release.** `accounts` (sign-in, sessions, log-in log),
`people` (people, teams, departments, manager access, allowances, audit),
`ui` (the shell: base template, side panel, top bar, shared widgets). Later
specs add `rota`, `leave`, `absence`, `engage`. `config/` holds settings,
URLs and the service-layer rule.

**Repository layout.**

    config/            settings.py, urls.py, wsgi.py
    accounts/ people/ ui/
    frontend/          Vite + Preact + TypeScript source; package.json, package-lock.json
    static/            css/, fonts/, js/ (hand-written), dist/ (built, committed)
    templates/
    deploy/            gunicorn.service, timers, backup, manage
    docs/              requirements/, brand/, admin/, superpowers/
    tests/
    manage.py requirements.txt pytest.ini ruff.toml

**Data flow.**

- HR → Shift Central, every 15 minutes: `GET /api/v1/people` (section 3).
- HR ↔ Shift Central at sign-in: OpenID Connect (section 2).
- Nothing flows back to HR. Nothing flows to or from the rota app in this
  release (spec 2 reads GP sessions; spec 3 serves GP leave).

**Dependency.** HR must be deployed, with everyone's employee record and
position entered, before Shift Central set-up starts in early December.
This is HR's own go-live step 1 (`practice-hr/docs/superpowers/backlog.md`);
it now has a date.

## 2. Sign-in, sessions and roles

**Sign-in** is the rota's `accounts` app adapted: `mozilla-django-oidc`
against HR's provider, authorization-code flow with PKCE, RS256, scopes
`openid email`. Shift Central is registered in HR with
`deploy/manage register_oidc_client --name shift-central --redirect-uri
https://<host>/oidc/callback/`; HR then shows an **Admin of shift-central**
box on every login account.

**`User`** (custom, email as the username): `email`, `oidc_sub`
(unique once set), `is_all_teams_manager` (from the `admin` claim at every
sign-in, as the rota's `is_rota_admin`), `is_superuser`, `is_active`. No
usable password except the superuser's; no passkeys, no invitations, no
lockout — HR does all of that.

**Binding to a person.** The backend reads `sub`, `email` and
`employee_id`. A user is found by `sub`; failing that, by `email`
(case-insensitive) among users with no `sub` yet, as the rota does; failing
that, created. At every sign-in, if `employee_id` names a `Person` with
that `hr_employee_id`, `Person.user` is set to this user (and cleared from
any other). A sign-in with no `employee_id`, or one naming no person here
yet, succeeds and reaches a page saying the account is not yet on the
rota and who to ask; the next `hr_sync` usually resolves it.

**Roles**, decided at request time, never stored on the person:

| Role | Who | How decided |
|---|---|---|
| Staff member | Everyone signed in | — |
| Team manager | Lead nurse, head pharmacist | A `TeamManager(person, team)` row exists for their person |
| All-teams manager | Practice manager, three assistants | `User.is_all_teams_manager` (HR's `admin` claim) |

`people/services/access.py` is the one place that answers *can this user
manage this team / this person* and *which teams does this user manage*;
every view and template calls it. A team manager manages the people whose
`team` is theirs; an all-teams manager manages everyone. Nobody manages
themselves for the purposes later specs care about (approving one's own
leave) — that rule lives in spec 3, but `access.py` exposes
`is_self(user, person)` for it.

**Sessions.** `SESSION_COOKIE_AGE = 600` with `SESSION_SAVE_EVERY_REQUEST`,
so a session lasts ten minutes from the last request (ACC-09, D-26). A
page's form that outlives the session fails safely: the POST is refused
with a message to sign in again, and the sign-in returns to that page.
Logging out ends the HR session too, as the rota does. Signing out is one
click, top of the side panel's bottom item (`03`, overall layout).

**Log-in log.** `LoginEvent`: `user`, `at`, `ip`, `user_agent` (truncated
to 200 characters), written on Django's `user_logged_in` signal. Listed
under Activity logs › Log in logs for all-teams managers (ACC-07, REP-06),
newest first, filterable by person and date. Never deleted in this release.

## 3. People from Practice HR

**`Team`** — `name` (unique; HR's team name), `display_order`, `active`.
Created by the sync when a new name arrives; order and active flag edited
here. The practice's teams today: GPs, Reception, Admin/Secretarial,
Nursing, Pharmacy, Management, Cleaning — whatever HR calls them.

**`Person`** — one row per HR employee. From HR, read-only here:
`hr_employee_id` (unique), `first_name`, `last_name`, `name`, `email`,
`team` (FK, from the first position's team; null if HR gives none),
`start_date`, `end_date` (null while employed), `is_gp` (HR's contract
unit is `sessions`), `last_seen_from_hr` (the last sync that included
them). Typed here, on the profile: `job_title` (shown on the rota),
`name_colour` (hex), `display_order`, `display_on_rota`,
`show_to_other_staff`, `can_see_other_staff` (all default true),
`weekly_hours` (decimal, two places; null for a GP), `days_per_week`
(1–7; null for a GP), `notes` (managers only). Plus `user` (OneToOne,
nullable; section 2). **Derived, not stored:** `average_day =
weekly_hours / days_per_week` (PAT-05); `current(on)` is true when
`start_date <= on` and (`end_date` is null or `end_date >= on`).

**`Allowance`** — `person`, `leave_year` (the year's first day, so a
per-person leave year can be added in spec 3 without a rebuild),
`annual_hours`, `bank_holiday_hours` (decimals, two places), unique on
the first two. Edited on the profile's Pay & time off tab for the current
and next leave year. Spec 3 reads them; this release only stores and
audits them.

**`hr_sync`** — a management command and `people/services/hr_sync.py`,
run every 15 minutes by `deploy/shift-central-hr-sync.timer` and on
demand. One GET to `PRACTICE_HR_URL/api/v1/people` with
`Authorization: Bearer $HR_API_TOKEN` (HR's `HR_API_TOKENS` holds it), a
10-second timeout, in one transaction:

- Each record upserts a `Person` by `id` → `hr_employee_id`; the HR-owned
  fields are overwritten, the typed fields never touched. A changed team
  moves the person (their `TeamManager` rows, if any, are kept and
  reported). A changed email or name is just a change.
- A team name not seen before creates a `Team`.
- A person in the database but absent from the feed is **not deleted**:
  `last_seen_from_hr` stops advancing, and the Health card lists them
  (below). Deletion is a manual act by the superuser in the admin.
- Every field the sync changes is audited with actor "Practice HR"
  (section 6), so a manager can see when a leaving date arrived.
- `SyncRun`: `started_at`, `finished_at`, `ok`, `people_seen`, `message`
  (an error's text, never a record's values). The last run shows on the
  Health card; a run that fails leaves the previous data untouched.

Starters appear as soon as HR has them, with no hours or allowances, and
are listed on the Health card as "needs hours and allowances" until a
manager fills the profile in. A leaver stays on record and visible on the
Staff list under a *Left* filter; spec 2 hides them from the grid after
their end date; spec 4 raises the leaver flags.

**What HR does not send** — date of birth, gender, phone numbers, address,
NI number, pay, patterns, contracts, absences — is not fetched. The
`patterns` and `absences` endpoints are not called by this app.

## 4. Departments and manager access

**`Department`** — `name` (unique), `colour` (hex), `display_order`,
`archived`. Seeded by migration with the seventeen names in ROTA-02, each
with a distinct default colour; managers add, recolour, reorder and archive
(never delete: spec 2's shifts will reference them) on the Departments
page. The page is FindMyShift's: a white table (Name, Colour, Date added),
Options and the orange **Add department +** in the top bar, edit in a
pop-up.

**`TeamManager`** — `person`, `team`, `granted_by`, `granted_at`, unique
on the pair. Granted and revoked by all-teams managers only, through the
**Permissions** link under a profile (FMS item 26): a list of teams with a
tick each; the all-teams managers' own access is shown as "all teams, set
in Practice HR" and is not editable here. Revoking never deletes history.

PEOPLE-04 in these terms: the practice manager and assistants are admins
of shift-central in HR; the lead nurse has a `TeamManager` row for
Nursing; the head pharmacist for Pharmacy. The four all-teams managers
cover every team including GPs, Reception, Admin/Secretarial, Management
and Cleaning.

## 5. The shell and the pages

**Base template** (`ui/templates/base.html`), after `03` overall layout:

- A **navy side panel** on the left, 220 px, collapsible to icons by a
  chevron and unpinnable (then it overlays on hover); the state is kept in
  `localStorage` per browser. At the top, the dark logo
  (`docs/brand/amg-shift-central-logo-dark.svg`); below, icon + label
  items in the order FindMyShift uses — Rota, Staff, Departments, Time off,
  Messages, Notice board, Outbox, Uploads, Reports, Activity logs,
  Settings — **of which only Staff, Departments and Activity logs appear
  in this release**; each later spec adds its items. Log out sits at the
  bottom. A flyout submenu opens to the right on hover or click, in the
  same navy; Activity logs' flyout has *Log in logs* and *Activity log*
  (all-teams managers; team managers see Activity log only).
- A **light top bar**: page title left, then actions as small text links
  with icons, the page's main "add" action in amber (`#F2A33A`, white
  text). The signed-in person's name and the collapse chevron right.
- On a phone (under 768 px) the side panel becomes a bottom bar with
  the same items and the top bar's actions fold into an overflow menu.
  This release's pages are usable on a phone; spec 5 makes the app
  installable.
- Pop-ups are `<dialog>` elements rendered by Django and fetched into the
  page by `static/js/modal.js` (the rota's pattern): dark header bar with
  the title and a close icon, outlined fields with floating labels, a
  full-width dark button. A form error re-renders the dialog's body in
  place.

**Staff list** (`/staff/`): a white table — Name (in the person's colour
chip), Job title, Team, Email, Start date — sorted by team then display
order; filters by team and *Current / Starting / Left*; Options (which
columns), Download (CSV of the visible rows, managers only), and
**Add staff +** which, since people come from HR, opens a dialog saying
to add them in Practice HR with a link there and a *Sync now* button
(managers; runs `hr_sync` at once and reports). Staff see every current
person's name, job title and team; managers see the rest.

**Profile pop-up**, opened from a name (own profile for staff; anyone's
for a manager of their team), titled "[Name]'s profile" or "Your profile",
with the tabs of FMS items 16–18, 21–22, 24:

| Tab | Fields | Who edits |
|---|---|---|
| General | Name, email (read-only, "from Practice HR"); avatar initials in the name colour | — |
| Display | Job title, team (read-only), start and finish dates (read-only), name colour (the built colour picker), display order, display on rota, show to other staff, can see other staff | Managers of the person's team |
| Pay & time off | Weekly hours and days per week (not shown for a GP, who shows "sessions, from the GP rota"); for the current and next leave year, annual leave allowance (hours) and bank holiday allowance (hours) | Managers of the person's team |
| Notes | Free text | Managers of the person's team; hidden from everyone else (ACC-04) |

Under the form, *Update profile* (dark, full width), then links:
**Permissions** (all-teams managers; section 4) and **History** (the
person's audit entries, managers). *Uploads* and *Delete this staff
member* are not in this release (uploads are spec 5; people are removed in
HR).

**Departments page** — section 4.

**Activity log** (`/activity/`): every `AuditEntry`, newest first,
filterable by person, model and date, with actor, time, what changed from
and to, and the note. Team managers see entries for people in their
teams; all-teams managers see everything. The log's shape serves specs 2
to 5 unchanged (FMS item 65).

**Health card** on the Staff page for managers: last HR sync (time,
result), people needing hours and allowances, people not seen in the HR
feed for over a day, leavers in the next 30 days (spec 4 adds the flags
proper).

**Settings** has no page in this release; the Settings item appears when
spec 3 gives it content. The admin (Unfold, `/admin/`, superuser only)
exposes every model read-mostly for setup and repair.

**Styling.** `static/css/tokens.css` defines the palette (navy and amber
as above, the greys FindMyShift's white pages use, the tile colours
managers pick from), the type scale and spacing; `components.css` the
panel, bar, tables, dialogs and forms. Density follows FindMyShift —
small type, tight rows — because managers compare the two.

**The built island.** `frontend/src/colour-picker.tsx`: the swatch grid
and hex field used on the Display tab and the Departments dialog,
mounted by a `data-component="colour-picker"` attribute, writing to a
hidden input. `frontend/src/main.ts` registers components by that
attribute; spec 2 registers the grid the same way. `npm run build`
emits `static/dist/main.js` and `main.css` with stable names (no hashes,
so templates reference them directly; WhiteNoise's manifest storage
adds the cache-busting hash at collectstatic). Pinned versions:
Vite 6, Preact 10, TypeScript 5; `package-lock.json` committed.

## 6. Audit

**`AuditEntry`** (in `people`, the HR shape): `actor` (FK User, nullable),
`actor_email`, `at`, `kind` (`change`, `viewed`), `model`, `object_id`,
`field`, `before`, `after`, `note`. `people/services/audit.py` has the one
writer, `record(actor, obj, changes, note="")`, taking `{field: (before,
after)}` and skipping unchanged pairs; the sync passes a sentinel actor
whose `actor_email` is `practice-hr`. Allowance and hours changes, and
manager-access grants, are the entries this release writes; spec 2's
shifts and spec 3's ledger reuse it. LEAVE-31's "typed reason" is the
`note`, required by the allowance form when an existing figure changes.
Never edited or deleted.

## 7. Deploy, operations and CI

**Layout on the VPS**, as the rota's README documents for `rota`:
`/srv/shift-central` (code, `.venv`, `staticfiles/`, root-owned),
`/var/lib/shift-central` (database and backups, owned by the
`shift-central` system user), `/etc/shift-central.env` (root, 600). Units
in `deploy/`, each sandboxed as the rota's: `gunicorn.service` (installed as
`shift-central.service`), `shift-central-hr-sync.{service,timer}` (every 15
minutes), `shift-central-clearsessions.{service,timer}` (daily),
`shift-central-backup.{service,timer}` and the PBS push, copied from HR's.
`deploy/manage` runs any management command as the app user with the env
file. The tunnel gets a third hostname routed to this service's socket.

**Environment:** `SECRET_KEY`, `DEBUG=0`, `DB_PATH`, `ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS`, `PRACTICE_HR_URL`, `OIDC_RP_CLIENT_ID`,
`OIDC_RP_CLIENT_SECRET`, `HR_API_TOKEN`, `EMAIL_HOST` and friends (unused
until spec 3 but wired now, through a `mail.py` copied from HR), `TZ`.
Local development: `DEBUG=1` generates a checkout-local secret as the
other two do; without `PRACTICE_HR_URL` the sign-in page offers the
superuser's password form only; without `HR_API_TOKEN` `hr_sync` refuses
to run and says so.

**Setup order**, written in `docs/admin/setup.md` and shown as a checklist
on the Health card: register the client in HR → env file → migrate →
superuser → `hr_sync` → tick *Admin of shift-central* for the four
managers in HR → each signs in → grant Nursing and Pharmacy access → fill
in hours, days and allowances → departments' colours.

**CI** (`.github/workflows/tests.yml`): `ruff check .` (pyflakes rules, as
`ruff.toml` in the other two); `makemigrations --check`; `pytest`;
`collectstatic` + `check --deploy` against a throwaway environment; and a
`frontend` job: `npm ci`, `npm run build`, `git diff --exit-code
static/dist` (fails when the committed bundle is stale), `npx tsc
--noEmit`. A second job on Python 3.14, not required.

**Backups and restore** as HR: nightly SQLite backup, pushed to the
Proxmox Backup Server; restore documented in `docs/admin/setup.md`.

## 8. Errors and testing

**Errors.** A failed HR sync keeps the last good data and shows on the
Health card; it never raises into a page. A sign-in whose `employee_id`
matches nobody here lands on a plain page, not a 500. A form POST after
session expiry is refused with "Your session ended; sign in again" and
returns to the page after sign-in. `mail.py` never raises into a page.

**Tests** (`pytest`, SQLite in memory, fixtures in `tests/fixtures/`):

- *Sync:* a fixture feed of six people → six `Person` rows and the teams;
  a second identical run changes nothing and writes no audit rows; a
  changed end date, team and email are applied and audited; a person
  missing from the feed is kept and listed on the Health card; a new team
  name creates a `Team`; typed fields survive a sync; an HTTP error or bad
  JSON leaves the data untouched and records a failed `SyncRun`; a record
  with `unit: "sessions"` sets `is_gp`.
- *Sign-in:* the `PracticeAccountBackend` tests from the rota, plus binding
  by `employee_id` (first sign-in binds; a later sign-in with a different
  `employee_id` rebinds and unbinds the old person); the `admin` claim
  sets and clears `is_all_teams_manager`; no `employee_id` → the holding
  page; a `LoginEvent` per sign-in.
- *Access:* for each page and action, a table of (role, own/other team,
  self) → allowed or 403, driven through `access.py`; team manager sees
  Notes for their team only; staff never see Notes, hours or allowances
  of others; the Permissions link is all-teams only.
- *Profile and departments:* every typed field round-trips; an allowance
  change without a note is refused; each change writes one `AuditEntry`
  per field; the colour field accepts `#rrggbb` only.
- *Sessions:* a request after 600 seconds is signed out; a request at 599
  extends it.
- *Shell:* every menu item in this release renders for the roles that
  have it and not otherwise; the base template carries no external URL.
- *Deploy units* parse and reference existing files (the rota's
  `test_deploy_units` pattern).

## Documentation

`README.md` (develop, deploy, first-time setup); `docs/admin/README.md`
and one page per area — `people.md` (teams, people, the profile, what HR
owns), `departments.md`, `access.md` (roles and manager access),
`sync.md` (the HR feed and the Health card), `setup.md` (the go-live
order, backups, restore); `docs/requirements/` untouched.

## Not done, on purpose

- Shifts, the grid, the hours report, GP sessions (spec 2).
- Leave arithmetic, requests, bank holidays, the leave year override,
  Settings (spec 3); the allowances are stored, not used.
- Sickness, TOIL, payroll, leaver flags (spec 4).
- Open shifts, push notifications, the installable app, messages, notice
  board, uploads, outbox, reports beyond the two logs (spec 5).
- Any write to Practice HR; reading HR's patterns or absences.
- Date of birth, gender, phone numbers, pay rates (FMS items 16 in part,
  19).
- Deleting people here; guests; passkeys or passwords for anyone but the
  superuser.
- Importing anything from FindMyShift.
