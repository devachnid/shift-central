# AMG Shift Central: engagement — design

**Date:** 2026-11-01
**Status:** approved in conversation; written spec approved 2026-11-01; built and reviewed, with the deviations recorded at the end
**Requirements:** `docs/requirements/` as amended by
`docs/requirements/2026-10-29-proposed-amendments.md`. This spec covers
ROTA-11 and REQ-16 (open shifts); NOTIF-01 (push, for every notification
the app sends), NOTIF-03 and NOTIF-04; D-27; FMS items 12 (message from the
grid), 25 (per-person uploads), 52 (internal messages), 53 (notice board),
56 and REP-07 (dashboard, shifts and staff-by-hour reports), 57 (installable
app with push), 58 (open shifts), 63 (uploads area) and 64 (Outbox). It
builds on the Foundation, rota grid, leave and absence specs
(`2026-10-29-foundation-design.md`, `2026-10-29-rota-grid-design.md`,
`2026-10-31-leave-design.md`, `2026-10-31-absence-payroll-design.md`),
whose constraints, shell, people, access rules, audit, grid, entries
service, messaging and API conventions it reuses unchanged unless this
spec says so.

Engagement is the fifth and last of the planned releases. It makes the
app something staff use from their phones and managers use to talk to
staff: open shifts that staff claim and a manager approves, the installable
phone app and push notifications for everything the app already emails,
messages and a notice board, shared and per-person documents, the Outbox
page, and the dashboard and the two remaining reports. After it, every
item in the requirements pack's "In scope" list is built except the
could-have budget report.

## Decisions made in conversation

| Decision | Rationale |
|---|---|
| **One spec, four parts built in priority order**: A open shifts, B phone app and push, C messages, notice board, uploads and Outbox page, D dashboard and reports. | Matches specs 1 to 4 and the Foundation's list. The amendments want open shifts for 1 January, push in January, and the rest in February; ordering the tasks A to D lets each part merge on its own if the dates press. |
| **A claim is for one place**: one person per post. Approving one claim closes the post and tells the other claimants it has gone. | The pack says "a shift". Cover for two people is two posts. Places-per-post would add counts to the form and the state rules for no stated need. |
| **The claimant chooses the overtime treatment when claiming** (normal hours, overtime paid, overtime TOIL); the approving manager may change it. | ROTA-06: "the person working extra chooses overtime pay or TOIL". |
| **Only the audience sees a post; a clash with the claimant's own rota warns, it does not block**, except a whole day of approved leave, which refuses approval. | Overtime beside a normal shift and split shifts are deliberate. A shift on a whole day off would be hidden under the leave at once, so approving it would do nothing visible. |
| **The owning team's managers approve**, whatever team the claimant is in, through a new entries verb that records the approver. | The audience may span teams; the manager who posted the shift and offered it is the one who agrees it. The grid's own rule (you manage the person's team) is for editing a cell by hand. |
| **Push is delivered through a queue**: Outbox rows with a channel, drained every minute by a systemd timer. | A push is one HTTPS call per phone to Apple's or Google's push service, which can be slow or fail. Email stays in the request, as now. The cost is up to a minute of delay. |
| **Own VAPID keys and `pywebpush`; no third-party push service.** | Staff names and notification text should not go to a hosted service; it matches the self-hosted pattern of the other apps. |
| **Push is opt-in per device and email stays on.** | NOTIF-01 says email and push, so nothing important depends on a push arriving. No preferences page to build or explain. |
| **A push shows the email's subject, never its body.** | Phone lock screens are seen by others; subjects already carry no descriptions or notes. |
| **The phone app caches no data**: static files and an offline page only. | The rota is personal data on phones that may be lost; the 10-minute inactivity logout (ACC-09) must not be undermined by a cached copy. |
| **Managers send messages; staff read only**, and the notice board is managers-only too. | The pack says "send" and "sent messages". Staff-to-staff chat or replies would add moderation and privacy questions the pack never raised. |
| **Uploads: the shared area is read by all staff and written by managers; a person's uploads are seen by their managers only.** | Matches notes being manager-only (ACC-04). |
| **Dashboard, Shifts and Staff by hour are defined here** (sections 8 to 10), because the pack says only "as FindMyShift today". | The practice manager confirmed the shapes in conversation; redacted screenshots, when they arrive, may change the layout, not the data. |

## Global constraints

Inherited from the earlier specs. In addition:

- Every write goes through a service; views never touch models. Audit rows
  under `shifts.openshift`, `messaging.message`, `messaging.notice` and
  `uploads.uploadedfile`.
- Log lines, `Outbox.error` and push payloads never carry a message body,
  a note, a description or an address; `error` is an exception class name
  or a fixed phrase.
- A push payload is `{title: "AMG Shift Central", body: <email subject>,
  url: <path>}` and nothing else.
- User text (messages, notices, comments, titles, file names) is plain
  text, auto-escaped, never rendered as HTML.
- Files are stored under `MEDIA_ROOT` outside anything the web server
  serves, and are only ever sent as downloads (`Content-Disposition:
  attachment`, `X-Content-Type-Options: nosniff`).
- Spreadsheet cells follow the absence spec's rule: written as text,
  cleaned by `csv_safe.cell`.
- Times and dates are Europe/London; "today" is `timezone.localdate()`;
  tests run under the pinned clock (`tests/clock.py`).
- No network in tests: the push sender and the mail backend are faked.
- Scripts are served from our own origin only (the CSP allows no inline
  script); the page script for push is a static file.

## 1. Architecture

One new app, `uploads`, and one new timer (`send_push`); everything else
extends the apps that exist.

- **`shifts`** gains the open-shift models and service
  (`shifts/models/open_shift.py`, `shifts/services/open_shifts.py`), the
  Shifts and Staff by hour services (`shifts/services/shift_report.py`,
  `shifts/services/staff_by_hour.py`) and their views.
- **`messaging`** gains push (`PushDevice`, `services/push.py`, the
  `send_push` and `vapid_keys` commands, the manifest, service worker and
  offline views), `Message` and `Notice` with their services, and the
  Outbox page. `messaging.send` stays the one sender.
- **`uploads`** (new) holds `UploadedFile`, its validation, storage and the
  download view.
- **`people.services.dashboard`** (beside `health.py`, which already
  aggregates across apps with imports inside the function) builds the
  dashboard's cards.
- **`ui/context_processors.py`** appends the new nav items.
- **The grid island** gains one menu item, "Send a message to [name]".
  The built bundle is rebuilt and committed as in the earlier specs.

Imports follow the existing direction: `shifts` calls `entries`,
`messaging` and `leave`; `messaging` imports nothing from `shifts`;
`uploads` imports `people.services.access` and `audit` only.

URLs added:

| Path | Page |
|---|---|
| `/rota/open/` | Open shifts (everyone; managers also post and approve) |
| `/rota/open/<id>/` | Post detail with claims (managers) |
| `/messages/`, `/messages/<id>/` | Inbox and message (everyone) |
| `/messages/new/`, `/messages/sent/` | Send, Sent messages (managers) |
| `/notices/` | Notice board (everyone; managers post) |
| `/uploads/` | Shared documents |
| `/staff/<id>/uploads/` | One person's documents (their managers) |
| `/outbox/` | Outbox (managers) |
| `/notifications/` | "Notifications on this phone" (everyone) |
| `/push/subscribe/`, `/push/unsubscribe/` | JSON, POST |
| `/manifest.webmanifest`, `/sw.js`, `/offline/` | The installable app |
| `/reports/dashboard/`, `/reports/shifts/`, `/reports/staff-by-hour/` | Reports (managers) |

Nav: Rota gains the child "Open shifts"; new top-level items **Messages**
(unread badge), **Notice board**, **Uploads**, **Outbox** (managers, failure
badge) and **Notifications**; Reports gains Dashboard, Shifts, Staff by
hour (managers) and Sent messages (managers, the Outbox page).

## 2. Data model

New models, all with `created_at` and the audit conventions of the earlier
specs. Names are final.

**`shifts.OpenShift`**: `team` (FK Team, the owning team), `day`, `start`,
`finish`, `break_minutes` (0, 15, 30, 45 or 60, as `Entry.BREAKS`),
`department` (FK Department, optional), `comment` (200 characters),
`everyone` (bool), `audience` (M2M Team, used when `everyone` is false),
`posted_by` (FK User), `state` (`open`, `filled`, `withdrawn`), `filled_by`
(FK Person, null), `entry` (FK Entry, null, set when filled). A shift needs
a later finish than start. `day` may not be before today when posting.
"Expired" is not a state: an open post whose day is before today is shown
as expired and cannot be claimed.

**`shifts.OpenShiftClaim`**: `open_shift` (FK), `person` (FK Person),
`overtime` (`""`, `paid`, `toil`, using `Entry.Overtime` plus the empty
value), `note` (200 characters), `state` (`waiting`, `approved`,
`declined`, `withdrawn`, `closed`), `decided_by` (FK User, null),
`decided_at`. A partial unique constraint allows one `waiting` claim per
(open shift, person); a person who withdrew may claim again.

**`messaging.Outbox`** gains `channel` (`email` default, `push`), `url`
(200 characters, the push click-through path) and `attempts` (small
integer, default 0), and an index on `(channel, sent_at)`. Existing rows
are `email`.

**`messaging.PushDevice`**: `person` (FK Person), `endpoint` (text, unique),
`p256dh`, `auth`, `label` (80 characters, derived from the user agent such
as "Android Chrome"), `created_at`, `last_ok_at` (null), `failures`.

**`messaging.Message`**: `sender` (FK User), `subject` (150), `body` (5000),
`created_at`, `everyone` (bool), `teams` (M2M Team), and
**`messaging.MessageRecipient`**: `message` (FK), `person` (FK Person),
`read_at` (null). The recipient rows are written when the message is sent
(a snapshot), so teams that change later do not change who was told.

**`messaging.Notice`**: `title` (120), `body` (5000), `everyone` (bool),
`teams` (M2M Team), `pinned` (bool), `show_until` (date, null),
`posted_by` (FK User), `created_at`, `updated_at`.

**`uploads.UploadedFile`**: `kind` (`shared`, `person`), `person` (FK
Person, null; set when `kind` is `person`), `title` (120), `original_name`
(200, display only), `stored_name` (32 hex characters plus the extension),
`size`, `uploaded_by` (FK User), `created_at`.

Migrations are additive. No existing row changes meaning.

## 3. Open shifts (part A)

### Services (`shifts/services/open_shifts.py`)

All take the acting `user` first and check access before touching data.

- `post(user, team, day, start, finish, break_minutes, department, comment, everyone, audience_teams)`:
  the user must manage `team` (`access.can_manage_team`). The audience
  teams are any teams; `everyone` overrides them. Creates the post, audits
  it, and sends NOTIF-03 to the audience (below).
- `withdraw(user, open_shift)`: managers of the owning team. Open posts
  only. Marks waiting claims `closed` and tells those claimants.
- `claim(user, open_shift, overtime, note)`: the user must have a Person
  in the post's audience and the post must be open, not expired. Creates a
  `waiting` claim and tells the owning team's managers.
- `withdraw_claim(user, claim)`: the claimant, while waiting.
- `clashes(claim)`: a list of plain sentences about the claimant's own rota
  on that day: an overlapping shift, or approved leave, with the leave type
  only. Used for the warning; never blocks.
- `approve(user, claim, overtime=None)`, `decline(user, claim)`:
  managers of the owning team. See below.
- `visible_to(user)`: the open posts a user may see: audience members'
  posts, plus every post of a team the user manages.

### Approval

Inside one transaction:

1. Re-read the post and claim; both must still be open and waiting.
2. If the claimant has approved leave covering the whole day (via
   `leave.services.costing.active_day`), refuse with "is on leave that
   day".
3. Create the shift with a new entries verb,
   `entries.add_item(user, person, day, item, via_open_shift=True)`. It
   appends the shift to the claimant's cell (`_items_of` plus the new
   item, written by the existing `_write`), so an existing shift that day
   is kept. It skips only the `can_manage(person)` check; the open-shift
   service has already checked that the approver manages the owning team.
   Everything else is `_write`'s: the DayChange for Notify staff, the leave
   hooks, the cell audit row. The item carries start, finish, break,
   department, comment as text, and the claim's (possibly changed)
   overtime.
4. Mark the claim `approved`, the post `filled` with `filled_by` and
   `entry`, and every other waiting claim `closed`.
5. After commit: NOTIF-04 to the claimant; "it has gone" to the closed
   claimants.

`decline` marks the claim `declined`, tells the claimant, and leaves the
post open. Approving the shift does not trigger the claimant's Notify
staff summary: they have already been told by NOTIF-04, and the DayChange
that approval records is settled for that person in the same transaction
(`notify.settle_baseline` for one person, so the next "Notify staff" does
not list it again).

### Screens

- **Rota ▸ Open shifts** (`/rota/open/`): cards, newest day first within
  open posts, then a collapsed "Filled and past" list. Each card shows day,
  times, break, department, comment, and the audience as "Everyone" or the
  team names. A staff member sees a **Claim** button, which opens a dialog
  with the overtime choice and a note; a claimed card shows "You've
  claimed this" with Withdraw. Phone-first layout.
- A manager also sees **Post an open shift** (the highlighted top-bar
  action) and, on each of their teams' posts, the waiting claims with
  Approve and Decline, the clash warnings, and the overtime choice to
  change. The post's detail page (`/rota/open/<id>/`) shows the full claim
  history. Managers' waiting claims also appear on the dashboard.
- Dialogs are server-rendered pop-ups like Add time off.

Not included: places-per-post, first-come claims, swaps (ROTA-13 stays a
manager's edit) and posting from the grid's right-click menu.

## 4. The phone app and push (part B)

### The installable app

- **`/manifest.webmanifest`**: name "AMG Shift Central", short name
  "Shift Central", `start_url` `/rota/`, `display` `standalone`, theme and
  background colours from the existing tokens, icons 192 and 512 from
  `docs/brand/` (copied to `static/img/`). Served by a view with its own
  `Cache-Control: no-cache`, as the no-store middleware expects.
- **`/sw.js`**: a view that returns `static/js/sw.js` with
  `Content-Type: application/javascript` and `Cache-Control: no-cache`
  from the site root, so its scope is the whole site. It:
  - precaches the offline page and the static files that page needs;
  - on `fetch`, handles navigations by network only, falling back to the
    offline page when the network fails, and never stores a response;
  - on `push`, shows a notification with the payload's title, body and
    url, tagged by url so repeats replace each other;
  - on `notificationclick`, closes it and opens or focuses a window at the
    url.
- **`/offline/`**: a static "You're offline" page with the logo.
- The CSP gains `worker-src 'self'` and `manifest-src 'self'`; `base.html`
  links the manifest and the Apple touch icon (already present).

### Turning push on

`/notifications/` shows, for this device, the permission state and one
button: "Turn on notifications on this phone" or "Turn off". A static
script (`static/js/push.js`, not inline) feature-detects, asks for
permission on a click, registers the service worker, subscribes with the
VAPID public key, and POSTs the subscription to `/push/subscribe/`
(CSRF-protected). Turning off unsubscribes and POSTs to
`/push/unsubscribe/`. On iPhone, where web push only works from an
installed app (iOS 16.4 or later), the page shows "Add to Home Screen
first, then open the app from there" while it is running in the browser.
A person's registered devices are listed with their labels and can be
removed. Everyone can use the page; it needs no role.

The server later calls the address a phone registers, so it accepts only an
`https` address with no credentials and no unusual port, on a known push
service: Google (`fcm.googleapis.com`), Mozilla (`push.services.mozilla.com`),
Apple (`push.apple.com`) and Windows (`notify.windows.com`), or a host added
in `PUSH_ENDPOINT_HOSTS`. A signed-in person cannot make the server call an
address of their choosing.

### Keys and switching it on

`VAPID_PRIVATE_KEY_FILE` (a file, like the OIDC key: owner root, group the
app, mode 640, because a PEM folded into an environment line arrives
broken), `VAPID_PUBLIC_KEY` and `VAPID_SUBJECT` (a `mailto:` address)
go in the env file. `manage vapid_keys` writes a new private key file and
prints the public key and the line to add. With any of the three missing,
push is off: the Notifications page says so, nothing is queued and the
Health card says "not configured".

### Delivery (`messaging/services/push.py`)

- `messaging.send(person, subject, body, connection=None, url=None)` writes
  the email row as now. If push is configured and the person has at least
  one device, it also writes one Outbox row with `channel="push"`,
  `subject` set, `body` empty and `url` set. The default `url` is `/rota/`.
  Existing callers need no change; those with a natural target (leave
  decisions, open shifts, messages) pass one.
- `send_push` (a management command, run through `deploy/manage` by
  `shift-central-push.service` from `shift-central-push.timer` every
  minute) takes queued push rows oldest first, at most 200 a run, and for
  each:
  - rows older than 24 hours are marked `error="expired"` and skipped;
  - sends to every device of the person with `pywebpush`, a 5-second
    timeout, the payload above;
  - HTTP 404 or 410 from the push service deletes that device;
  - at least one success sets `sent_at` and the device's `last_ok_at`;
  - otherwise `attempts` is incremented and the row stays queued, and
    after 5 attempts it is marked `error="push failed"`; a person left
    with no devices gets `error="no device"`.
- The library call sits behind one function, `push.deliver(device, payload)`,
  that tests replace.

### Health

The Staff page's Health card gains a push line for all-teams managers: keys
configured, devices registered, queue depth, last successful send.

## 5. Messages and the notice board (part C)

### Messages (`messaging/services/messages.py`)

- `send(user, subject, body, person_ids, team_ids, everyone, base_url)`:
  managers only. Resolves the audience to current people (`everyone`, or
  the teams plus the named people; the sender is left out), writes the
  message and one recipient row each, audits it as one row ("sent to N
  people"), and sends the email and push for each through
  `messaging.send` on one open connection (as `notify.send`). The email
  carries the full text and a link to `/messages/<id>/`; the push carries
  the subject.
- `inbox(user)` and `unread_count(user)` for the nav badge;
  `mark_read(user, message)` on opening a message.
- `sent(user)`: the user's own sent messages; an all-teams manager sees
  everyone's. Each shows the recipients and who has read it.

Screens: **Messages ▸ Inbox**, the message page, and for managers **Send a
message** (subject, text, then people, teams or everyone) and **Sent
messages**. The grid's "Send a message to [name]" opens the Send dialog with
that person chosen. There is no reply.

### Notice board (`messaging/services/notices.py`)

- `post`, `edit`, `remove`: managers; edit and remove by the poster or an
  all-teams manager. Title, plain text body, audience (everyone or teams),
  `pinned`, optional `show_until`. An optional "also tell staff by email and
  push" sends the title through `messaging.send` to the audience at posting
  time, once.
- `visible_to(user)`: notices whose audience includes the user's team (or
  everyone) and whose `show_until` is empty or not before today. Pinned
  first, then newest. A manager also sees, in a separate list, every notice
  they may edit.
- The board is a read-only page of cards for staff; line breaks are kept
  and nothing is rendered as HTML. There are no read marks or unread
  counts.

## 6. Uploads (part C)

### Storage and validation (`uploads/`)

- `MEDIA_ROOT` is `/var/lib/shift-central/media` (an `UPLOADS_DIR` setting
  beneath it), created `0700` by the app. The systemd unit already allows
  writes under the state directory; nothing in the web stack serves this
  path.
- `add(user, file, title, kind, person=None)`:
  - extension allowlist: `pdf doc docx xls xlsx odt ods txt csv png jpg
    jpeg`; anything else is refused with the list in the message;
  - the first bytes must fit the extension: `%PDF`, the PNG and JPEG
    signatures, a ZIP (`PK`) for `docx xlsx odt ods`, an OLE header for
    `doc xls`; `txt` and `csv` must decode as UTF-8 or Windows-1252 and
    hold no NUL bytes;
  - size at most `UPLOAD_MAX_BYTES` (default 10 MB); empty files refused;
  - the stored name is a random 32-character hex string plus the
    extension; the original name is kept only for display and download
    (cleaned of path separators and control characters);
  - written to a temporary name then renamed, so a failure leaves no
    half-file; the row and file are created together or not at all.
- `remove(user, uploaded)`: deletes the row and the file; shared files by
  the uploader or an all-teams manager, personal files by managers of the
  person's team.
- `open(user, uploaded)`: the permission check, then a `FileResponse` with
  `Content-Disposition: attachment`, a content type from the extension
  table, `X-Content-Type-Options: nosniff` and (via the middleware)
  `no-store`. A missing file on disk gives a 404 and a log line with the
  row id only.

### Access

| | Staff | Team manager | All-teams manager |
|---|---|---|---|
| Shared: list and download | yes | yes | yes |
| Shared: add | no | yes | yes |
| Shared: delete | no | own uploads | all |
| Person's files: list, download, add | no | their team | all |
| Person's files: delete | no | their team | all |

The person's files are reached from the profile window's "Uploads" link
(`/staff/<id>/uploads/`). The person themselves cannot see them. Adding,
deleting, and downloading a personal file are written to the activity log;
downloading a shared file is not.

No virus scanning: only managers upload, and nothing is ever opened in
the browser. No per-person quota.

## 7. The Outbox page (part C)

`/outbox/`, managers only, lists `Outbox` rows newest first, 50 a page:
when queued, to (name), channel, subject, status. Status is one of **Sent**,
**Queued**, **Failed** (with the error text, a class name or fixed phrase)
or **Not configured**. A row opens to show its body. Filters: status, person,
date range. Scope: an all-teams manager sees every row; a team manager sees
rows to people in their teams (`access.managed_people`); rows with no
person are all-teams only. Reports ▸ Sent messages links here.

The nav badge counts rows in the last 7 days that are failed, or push rows
still queued after 5 minutes, within the viewer's scope. "Not configured"
rows are not counted.

Retention: the daily job (`daily_flags`) blanks the `body` of rows older
than `OUTBOX_BODY_MONTHS` (default 12) and keeps the rest of the row.

## 8. The dashboard (part D)

`/reports/dashboard/`, managers. `people.services.dashboard.build(user,
today)` returns a dict of cards; each card is its own function so it is
tested alone. Team managers see their teams' people; all-teams managers
see everyone.

- **Today**: counts in, working from home and off, by site, from
  `shifts.services.today.board`, linking to Who's in today.
- **Waiting for you**: leave requests (from the approvals list) and open
  shift claims, each with a count and a link.
- **Next 14 days**: bookings starting, by person and type, and open shifts
  still unfilled with their days.
- **Flags**: sickness triggers reached, leavers within 30 days, people
  returning from long absence, from the services the absence spec built
  (`sickness`, `leavers`, `returns`).
- **System** (all-teams managers): HR and GP sync status, push queue and
  device count, failed Outbox rows.

The home page still goes to the rota. The page is server-rendered, with no
charts, and stacks on a phone.

## 9. The Shifts report (part D)

`/reports/shifts/`, managers. Filters: date range (default this week,
longest one year), team, department, person. Rows are the shifts in the
range for the people the viewer manages: date, day, person, team,
department, start, finish, break, net hours (`finish − start − break`,
the same rule as the Hours report), overtime mark, comment. Subtotals per
person and a grand total. Shifts replaced by leave are left out (the
`covered_by` rule used elsewhere). Screen and Excel
(`exports.xlsx`); the file name carries the range.

## 10. Staff by hour (part D)

`/reports/staff-by-hour/`, managers. Filters: date range (default this
week, longest 31 days), site (AG, PMC or both; the site of a shift is
found by `today.site_of`) and team. For each day a row of hour columns from
the earliest start to the latest finish in the range. A cell is the number
of people with a shift in that hour, counted when the shift overlaps any
part of it: 08:00 to 16:15 counts in the 08:00 to 16:00 columns. Working
from home people are counted, and a second line per day shows "of which
WFH". Each day also shows its peak. Breaks are not subtracted: the pack
does not place them. GPs are left out, because their sessions have no clock
times in this app, and the page says so. Screen and Excel.

## 11. Notifications

Every notification below goes by email and push (NOTIF-01). The existing
ones are unchanged in text; only push is added, through `messaging.send`.

| Event | Who | Subject (also the push text) | Link |
|---|---|---|---|
| Open shift posted (NOTIF-03) | The audience, minus the poster | "Open shift: <weekday d Month>, <start>–<finish>" | `/rota/open/` |
| Claim made | Managers of the owning team, minus the claimant | "<Name> has claimed an open shift" | `/rota/open/<id>/` |
| Claim approved (NOTIF-04) | The claimant | "Your open shift claim for <date> is approved" | `/rota/` |
| Claim declined | The claimant | "Your open shift claim for <date> was declined" | `/rota/open/` |
| Open shift taken or withdrawn | Other waiting claimants | "The open shift on <date> has been filled" or "…withdrawn" | `/rota/open/` |
| Message | Recipients | the message's subject | `/messages/<id>/` |
| Notice, when ticked | The audience | the notice title | `/notices/` |

The email bodies carry the day, times, department and a link, never the
comment or note. Leave, rota-change, sickness and year-end notifications
keep their existing bodies and gain push; where the sender already knows
the page (a leave decision, the approvals list, Notify staff) it passes a
`url`.

## 12. Audit and activity

Audit rows (the activity log, visible to managers):

- `shifts.openshift`: posted, withdrawn, claim approved or declined (the
  shift's cell change is also audited by `entries`).
- `messaging.message`: sent (to N people, subject only).
- `messaging.notice`: posted, edited, removed.
- `uploads.uploadedfile`: added, removed, and downloaded for personal
  files; file names are not written, only the title.

Claims, device registrations and reads are not audited: they are the
person's own actions, and the claim's outcome is.

## 13. Permissions

| | Staff | Team manager | All-teams manager |
|---|---|---|---|
| See an open shift | if in its audience | audience, plus their teams' posts | all |
| Claim | if in its audience | if in its audience | if in its audience |
| Post, withdraw, approve | no | their own team | all |
| Inbox, notices, shared files | yes | yes | yes |
| Send message, post notice, add shared file | no | yes | yes |
| A person's files | no | their team | all |
| Outbox | no | rows to their team | all |
| Dashboard, Shifts, Staff by hour | no | their teams | all |
| Turn push on for a device | own | own | own |

Every view uses the existing role decorators; every service re-checks.
A request for something the user may not see is a 404, not a 403, for
messages, files and posts, so ids reveal nothing.

## 14. Errors

- Claiming an expired, filled or withdrawn post, or approving a claim no
  longer waiting: the dialog explains and the list refreshes. Two
  managers approving at once: the first wins; the second sees "already
  decided" (the transaction re-reads, and the database writes are
  serialised by the `IMMEDIATE` transaction mode).
- The entries service refusing the shift (for example on a day the grid
  refuses) shows its message; nothing is changed.
- Push not configured, no devices, a gone device, a push service down:
  covered in section 4; never an error shown to the manager or staff
  member whose action caused the notification.
- Mail not configured: the Outbox row says so, as now; push is
  unaffected.
- An upload failing validation or the size limit: the form keeps its
  fields and names the reason. A disk write failure leaves no row.

## 15. Testing

Pytest under the existing clock fixtures, with factories extended
(`make_open_shift`, `make_claim`, `make_push_device`, `make_notice`,
`make_message`, `make_upload`).

- **Open shifts:** posting needs the owning team; audience visibility
  (team, several teams, everyone); claim states and the one-waiting
  constraint; withdraw and re-claim; approval creates the shift beside an
  existing one, keeps the overtime choice, can change it, settles the
  claimant's Notify staff baseline, closes other claims, notifies
  everyone; whole-day leave refuses; a part-day clash only warns; an
  approver from the owning team who does not manage the claimant's team
  still works; a manager of another team is refused; two approvals race;
  an expired post cannot be claimed.
- **Push:** `messaging.send` queues a push row only with keys and a
  device; the payload has subject only; `send_push` with a fake sender:
  success, 410 deletes the device, retry counting and the fifth-attempt
  failure, 24-hour expiry, per-run cap, several devices; keys missing
  turns everything off; subscribe and unsubscribe views, CSRF, one
  person's device cannot be removed by another.
- **The app files:** the manifest is valid JSON with the icons; `/sw.js`
  has the right type and `no-cache`; the CSP carries `worker-src` and
  `manifest-src`; the offline page renders without a login.
- **Messages and notices:** audience resolution, the sender excluded,
  snapshot recipients, email and push per recipient, read marks, badge,
  staff cannot send, a non-recipient gets a 404; notice visibility by
  team and `show_until`, pinning order, plain-text escaping with a hostile
  title, optional notify.
- **Uploads:** the allowlist, signature checks (a renamed executable is
  refused), the size and empty-file limits, the stored name is random,
  hostile file names, atomic failure, permission matrix, `attachment` and
  `nosniff` headers, a missing file gives 404, activity rows.
- **Outbox:** scoping for team and all-teams managers, statuses, filters,
  badge counts and the "not configured" exclusion, body blanking after
  the retention period.
- **Reports:** the dashboard cards one by one with seeded data and
  scoping; Shifts totals against hand-computed hours, covered shifts
  excluded, the year cap; Staff by hour cells for shifts that start and
  end off the hour, WFH line, site and team filters, GPs excluded, the
  31-day cap; Excel cells written as text with a hostile name.
- **Permissions:** every new view for staff, team manager, other-team
  manager and all-teams manager.
- **Browser end-to-end** (the existing Playwright test): a manager posts
  an open shift, a staff member claims it, the manager approves, and the
  shift appears on the rota; and the Notifications page is reached.

## 16. Deploy, operations and documentation

- **Requirements:** `pywebpush` pinned (with its dependencies, which pip
  resolves), recorded in `requirements.txt`.
- **Settings:** `VAPID_PRIVATE_KEY_FILE`, `VAPID_PUBLIC_KEY`,
  `VAPID_SUBJECT`, `MEDIA_ROOT`, `UPLOAD_MAX_BYTES`, `OUTBOX_BODY_MONTHS`,
  all optional, documented in the README's environment table.
- **Units:** `deploy/shift-central-push.service` and `.timer`, in the same
  sandboxed form as the other timers; the install steps in the README and
  the staging installer script gain them.
- **Backups:** `deploy/backup.sh` also archives `MEDIA_ROOT`; the restore
  notes say so.
- **Upgrade checklist:** pull, `pip install -r requirements.txt`,
  `deploy/manage migrate`, `collectstatic`, `vapid_keys` (once), enable the
  timer, restart; and a note that `sw.js` takes effect for existing
  phones on their next visit.
- **Demo data:** `seed_demo` adds a few open shifts with claims (one
  filled), two notices, a message to every fictional person and a shared
  sample document, with no mail and no push sent. It stays idempotent and
  staging-only.
- **Documentation:** a new `docs/admin/engagement.md` covers open shifts,
  messages, the notice board, uploads, the Outbox and the reports, with a
  "Putting the app on a phone" section (Android, and the iPhone Add to Home
  Screen step). The README gains the settings, the timer and the upgrade
  checklist. The amendments document gains a postscript for the practice
  manager: staff cannot reply to messages; push is opt-in per device;
  claimants choose the overtime treatment; the Outbox retention; and the
  three report definitions.

## Not done, on purpose

- Places-per-post counts, first-come claims, shift swaps (ROTA-13 stays a
  manager's edit), posting an open shift from the grid's right-click menu.
- Staff sending or replying to messages; read receipts on notices.
- Per-person or per-event notification preferences; SMS.
- Offline caching of any rota or personal page.
- A third-party push service.
- Virus scanning or quotas for uploads; versions of a file.
- Charts on the dashboard; the budget report (could have, needs pay
  rates).

## Revisit

- The dashboard's cards and the Staff by hour definition once the
  redacted FindMyShift screenshots arrive.
- Whether staff want a reply to messages after the first months.
- Whether a one-minute push delay is felt as too slow; the inline
  alternative is a small change in `messaging.send`.
- Linking GPs into Staff by hour if the rota app ever sends clock times.

## Deviations recorded during the build

### Before the build (the plan's pre-flight)

- The offline page is self-contained (inline styles, no links or scripts), so the
  service worker caches that one page only, not "the static files that page needs".
- There is no Account page to hold the push card, so it is its own page,
  **Notifications**, with its own nav item for everyone.
- `messaging/services.py` became a package so `push.py`, `messages.py`, `notices.py`
  and `outbox.py` could sit beside `send`; `messaging.services.send` is unchanged
  for its callers (a new optional `url`).
- A claim made by seed_demo is written directly: claiming through the service needs
  a signed-in login in the audience, and the fictional cast may not have signed in.
- Approving an open shift refuses a whole day of approved leave (spec section 3,
  restated here because it goes beyond "clashes only warn").

### While building

- `add_item` rebuilds the cell from all its rows, leave-covered ones included (as the
  shift dialog does), then appends: the plan's version dropped a covered shift.
- Approval is refused whenever the claimant's leave would hide the new shift (part-day
  leave covers the day's shifts too), not only on a whole day; the new entry is found by
  position, and nothing changes on refusal.
- No manager decides their own claim (REQ-04).
- Approving after the post's day has passed stays allowed (only claiming an expired post
  is refused).
- Push addresses must match one strict shape (https, an allowlisted host, no backslash,
  credentials or odd port): the first version could be bypassed with a backslash.
- Device removal goes through the push service.
- Pushes carry a 24-hour time-to-live (the library default of 0 dropped pushes to phones
  that were offline).
- `MEDIA_ROOT` defaults beside the database rather than in the code tree; uploads use
  `MEDIA_ROOT/uploads` (no separate `UPLOADS_DIR` setting).
- A missing file on disk is logged with the row id only.
- The dashboard's Today card is built from the Who's in today board (GPs counted,
  hidden-from-rota people not).
- A signed-in account with no Person cannot fetch `sw.js`, the manifest or the offline page (they
  only ever see the holding page).
- `seed_demo` writes the waiting claim directly and skips it (the claim left waiting) if
  an approval is refused.
- The Staff by hour Excel and the Shifts Excel follow the plan; the Shifts Excel has a
  grand total only (per-person subtotals are on screen).
- The decision dialog's Approve and Decline buttons did not work in a browser: the dialog
  script posted to `form.action`, which a button named `action` replaces in the page, so
  the post went to a nonsense address. `modal.js` now reads the form's `action`
  attribute. The browser test for open shifts found it.
- `vapid_keys` runs through `deploy/manage` as root, like `collectstatic`, with the settings
  read from the environment file: the brief's bare `manage.py` stops without `SECRET_KEY`,
  and the docs test forbids a hand-run `manage.py` on the server. The key file goes in
  `/etc`, which the app's own user cannot write.
