# Engagement (spec 5) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open shifts that staff claim and a manager approves; the installable phone app with queued push notifications for everything the app already emails; messages, a notice board, shared and per-person documents and the Outbox page; the dashboard, the Shifts report and the Staff by hour report.

**Architecture:** `messaging.send` stays the one sender; it gains a push channel by writing a second Outbox row that a one-minute systemd timer drains with `pywebpush` (own VAPID keys, no hosted service). Open shifts are two models in `shifts` and a service that creates the claimed shift through a new `entries.add_item` verb, so the grid's cell writer, audit, Notify-staff bookkeeping and leave hooks all apply. Messages, notices and the Outbox page extend `messaging`; documents are a new `uploads` app that stores files outside anything served and only ever sends them as downloads; the dashboard sits beside `people/services/health.py`, and the two reports beside the Hours report.

**Tech Stack:** Django 5.2 / Python 3.13 / SQLite (WAL); Unfold admin; `pywebpush` (new, pinned in Task 8); openpyxl for Excel (already installed); a service worker and a plain static script for the phone app; Preact island rebuilt once (one menu item); pytest; Playwright for one e2e test.

**Spec:** `docs/superpowers/specs/2026-11-01-engagement-design.md` (binding). Read it first, then the absence spec's "Global constraints" and the grid spec's section on the entries service.

## Global Constraints

- Every write goes through a service; views never touch models. Audit through `people.services.audit.record(actor, obj, changes, note)` or `record_as(actor, model, object_id, changes, note)` under `shifts.openshift`, `messaging.message`, `messaging.notice`, `uploads.sharedfile` (object_id the file's pk) and `uploads.personfile` (object_id the person's pk).
- Log lines, `Outbox.error` and push payloads never carry a message body, a note, a description or an address; `Outbox.error` is an exception class name or a fixed phrase.
- A push payload is exactly `{"title": "AMG Shift Central", "body": <the email's subject>, "url": <a path>}`.
- User text (messages, notices, comments, titles, file names) is plain text, auto-escaped, never rendered as HTML (no `|safe`, no `mark_safe`).
- Files live under `MEDIA_ROOT`, outside anything the web server serves, and are only sent as downloads (`Content-Disposition: attachment`, `X-Content-Type-Options: nosniff`).
- Spreadsheet cells are written as text through `exports.xlsx.workbook` (it types every string cell explicitly); CSV through `shifts.services.csv_safe`.
- Dates and "today" are Europe/London: `timezone.localdate()`. Tests run under the pinned clock (`tests/clock.py`: `PIN` = Mon 2 Nov 2026 09:00; `@pytest.mark.today(date)` per test or module).
- No network in tests: the push sender (`messaging.services.push.deliver`) and the mail backend (Django's locmem) are faked. `conftest.py` already sets `EMAIL_HOST = "smtp.example.org"` and runs a `transaction.on_commit` callback at once only when no nested `atomic` block is open. So a service registers its `on_commit` callbacks **after** its own `with transaction.atomic():` block closes, never inside it (inside, the callback would wait for a commit the test never makes).
- CSP forbids inline scripts and handlers: no `onclick`, no `<script>` in templates. Dialogs use `data-dialog`, `data-dialog-form`, `data-dialog-close`, answers `{"refresh": true}` or `{"redirect": url}`. Styles may be inline.
- Unauthorised access to a message, file, post or claim by id answers 404, not 403.
- Commit messages: `Area: what changed` (Shifts:, Messaging:, Uploads:, People:, Deploy:, Docs:). Every commit ends with the two trailer lines the session gives (Co-Authored-By and Claude-Session). No model identifier anywhere in a repo file.
- Checks before every commit: `python -m pytest -q <the task's tests>`; before the last commit of a task also `ruff check .` (pyflakes only: an unused import fails CI) and `DEBUG=1 python manage.py makemigrations --check --dry-run`. Run from `/home/user/shift-central` with the venv (`.venv/bin/python`). The e2e: `E2E=1 E2E_CHROMIUM=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/e2e -q`.
- One implementer at a time; tasks run in order. Branch `claude/hopeful-keller-lankio`, started from `main` once the spec PR (#7) is merged or, if it is still open, from the branch as it stands.

---

## File structure

**Create:**

```
messaging/services/__init__.py          (moved from messaging/services.py, Task 1)
messaging/services/push.py messages.py notices.py outbox.py
messaging/forms.py urls.py
messaging/views/__init__.py app.py push.py messages.py notices.py outbox.py
messaging/management/__init__.py commands/__init__.py commands/send_push.py commands/vapid_keys.py
messaging/migrations/0002_outbox_channel.py 0003_push_devices.py 0004_messages.py 0005_notices.py (the makemigrations -n names)
shifts/models/open_shift.py
shifts/services/open_shifts.py open_shift_mail.py shift_report.py staff_by_hour.py
shifts/views/open_shifts.py
shifts/migrations/0003_open_shifts.py
uploads/__init__.py apps.py models.py admin.py forms.py urls.py views.py migrations/0001_initial.py
uploads/services.py
people/services/dashboard.py
people/views/dashboard.py
templates/shifts/ open_shifts.html open_detail.html open_post_dialog.html open_claim_dialog.html open_decide_dialog.html
                  shifts_report.html staff_by_hour.html
templates/messaging/ offline.html notifications.html inbox.html message.html send_dialog.html sent.html
                     notices.html notice_dialog.html outbox.html
templates/uploads/ list.html person.html
templates/people/dashboard.html
static/js/sw.js push.js
static/img/icon-192.png icon-512.png     (copied from docs/brand/)
deploy/shift-central-push.service shift-central-push.timer
docs/admin/engagement.md
tests/test_messaging_groundwork.py test_open_shift_models.py test_open_shifts.py test_open_shift_views.py
      test_app_files.py test_push_devices.py test_push_delivery.py test_inbox.py test_notices.py test_uploads.py
      test_outbox.py test_dashboard.py test_shifts_report.py test_staff_by_hour.py
tests/e2e/test_open_shifts.py
```

**Modified:** `config/settings.py` (`uploads` app, VAPID, MEDIA_ROOT and limits), `config/urls.py`, `config/middleware.py` (CSP), `requirements.txt`, `messaging/models.py`, `messaging/admin.py`, `shifts/models/__init__.py`, `shifts/admin.py`, `shifts/forms.py`, `shifts/urls.py`, `shifts/views/reports.py`, `shifts/services/entries.py`, `leave/services/notify.py`, `people/urls.py`, `people/views/__init__.py`, `people/views/activity.py`, `people/services/health.py`, `templates/people/_health.html`, `templates/people/profile_dialog.html`, `templates/base.html`, `templates/ui/_sidebar.html`, `static/css/components.css`, `ui/context_processors.py`, `frontend/src/rota-grid/menu-items.ts` and the rebuilt `static/dist/`, `people/management/commands/seed_demo.py`, `leave/management/commands/daily_flags.py`, `deploy/backup.sh`, `tests/factories.py`, `tests/conftest.py`, `tests/test_deploy_units.py`, `tests/test_shell.py`, `tests/test_shifts_entries.py`, `tests/test_seed_demo.py`, `README.md`, `docs/admin/README.md`, `docs/requirements/2026-10-29-proposed-amendments.md`, the spec's deviations section.

---

### Task 1: Messaging groundwork, activity registrations, test helper

The package conversion, the three new Outbox fields, a `url` argument on `send`, a batch helper and a link helper, and the Activity log learning the new audit labels. Nothing user-visible yet.

**Files:**
- Move: `messaging/services.py` → `messaging/services/__init__.py`
- Modify: `messaging/models.py`, `people/views/activity.py`, `people/management/commands/seed_demo.py:122-124`, `tests/factories.py`
- Create: `messaging/migrations/0002_outbox_channel.py` (generated), `tests/test_messaging_groundwork.py`
- Test: `tests/test_messaging.py` (unchanged, must still pass), `tests/test_messaging_groundwork.py`

**Interfaces:**
- Produces: `Outbox.Channel` (`EMAIL`, `PUSH`), fields `channel`, `url`, `attempts`; `messaging.services.send(person, subject, body, connection=None, url=None)`; `messaging.services.batch()` (context manager yielding an open connection or `None`); `messaging.services.absolute_link(base_url, path) -> str`; `tests.factories.client_for(person, **user_kw) -> Client` (reuses `person.user` when they have one); Activity log labels for `shifts.openshift`, `messaging.message`, `messaging.notice`, `uploads.sharedfile`, `uploads.personfile`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_messaging_groundwork.py`:

```python
"""Task 1 of spec 5: the Outbox grows a channel, send takes a link, and the
Activity log knows the labels later tasks write."""

import pytest
from django.test import Client

from accounts.models import User
from messaging import services
from messaging.models import Outbox
from people.services import audit
from tests.factories import client_for, make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


def test_a_sent_email_row_is_on_the_email_channel_with_no_attempts():
    row = services.send(make_person(), "Subject", "Body")
    assert row.channel == Outbox.Channel.EMAIL and row.attempts == 0 and row.url == ""


def test_send_accepts_a_link_without_changing_the_email():
    from django.core import mail
    row = services.send(make_person(), "Subject", "Body", url="/rota/open/")
    assert row.sent_at and len(mail.outbox) == 1 and mail.outbox[0].body == "Body"


def test_absolute_link_uses_the_given_base_else_the_first_trusted_origin(settings):
    settings.CSRF_TRUSTED_ORIGINS = ["https://shifts.example.org"]
    assert services.absolute_link("", "/rota/") == "https://shifts.example.org/rota/"
    assert services.absolute_link("https://x.example/", "/rota/") == "https://x.example/rota/"
    settings.CSRF_TRUSTED_ORIGINS = []
    assert services.absolute_link("", "/rota/") == "/rota/"


def test_batch_yields_nothing_when_no_relay_is_configured(settings):
    settings.EMAIL_HOST = ""
    with services.batch() as connection:
        assert connection is None


def test_batch_opens_one_connection_and_closes_it(monkeypatch):
    calls = []

    class Fake:
        def open(self):
            calls.append("open")

        def close(self):
            calls.append("close")

    monkeypatch.setattr(services, "get_connection", lambda: Fake())
    with services.batch() as connection:
        assert isinstance(connection, Fake)
    assert calls == ["open", "close"]


def test_batch_yields_nothing_when_the_relay_cannot_be_opened(monkeypatch):
    class Broken:
        def open(self):
            raise OSError("down")

        def close(self):
            raise AssertionError("never opened, so never closed")

    monkeypatch.setattr(services, "get_connection", lambda: Broken())
    with services.batch() as connection:
        assert connection is None


def test_client_for_signs_a_person_in():
    p = make_person()
    assert client_for(p).get("/rota/").status_code == 200


def test_the_activity_log_names_the_engagement_rows():
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    user = make_user_for(lead)
    sam = make_person(first_name="Sam", team=team)
    audit.record_as(user, "uploads.personfile", sam.pk, {"added": ("", "Contract")}, note="x")
    audit.record_as(user, "uploads.sharedfile", 7, {"added": ("", "Handbook")}, note="x")
    audit.record_as(user, "shifts.openshift", 3, {"posted": ("", "2026-11-09")}, note="x")
    audit.record_as(user, "messaging.message", 4, {"sent": ("", "to 2 people")}, note="x")
    audit.record_as(user, "messaging.notice", 5, {"posted": ("", "Fire drill")}, note="x")
    client = Client()
    client.force_login(user)
    records = {e.model: e.record for e in client.get("/activity/").context["entries"]}
    assert records["uploads.personfile"] == sam.name
    assert records["uploads.sharedfile"] == "Shared file"
    assert records["shifts.openshift"] == "Open shift"
    assert records["messaging.message"] == "Message"
    assert records["messaging.notice"] == "Notice"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_messaging_groundwork.py -q`
Expected: FAIL (`cannot import name 'client_for'`, then missing attributes).

- [ ] **Step 3: Convert `services.py` to a package**

```bash
mkdir messaging/services
git mv messaging/services.py messaging/services/__init__.py
```

Replace the file's import block and `send` so the whole of `messaging/services/__init__.py` reads:

```python
"""The one sender. Writes the Outbox row first, so a message is on record
whether or not the relay takes it; never raises; never puts a body or an
address in a log line or in `error`. `error` is the exception's class name
only; the relay's own log has the rest.

There is no console fallback: with no EMAIL_HOST nothing is tried and the
row says "mail not configured", so a box without a relay keeps every change
for Notify staff rather than printing mail nobody reads. A caller sending a
batch passes one open connection (`batch()` gives one, `notify.send` makes
its own), so the relay sees one login, not one per person.

`url` is the page a push notification opens (spec 5); until push exists it
is accepted and ignored."""

import logging
from contextlib import contextmanager

from django.conf import settings
from django.core.mail import get_connection, send_mail
from django.utils import timezone

from messaging.models import Outbox

log = logging.getLogger("messaging")
NOT_CONFIGURED = "mail not configured"


def configured():
    return bool(settings.EMAIL_HOST)


def absolute_link(base_url, path):
    """An absolute link: the request's own address, or, for mail sent with
    none (a timer, a rota write), the first trusted origin."""
    base_url = base_url or (settings.CSRF_TRUSTED_ORIGINS or [""])[0]
    return (base_url.rstrip("/") + path) if base_url else path


@contextmanager
def batch():
    """One open relay connection for a run of sends; None when no relay is
    configured or it cannot be reached (each send then records its own
    failure)."""
    connection = None
    if configured():
        connection = get_connection()
        try:
            connection.open()
        except Exception:  # whatever open() raises, the relay cannot be reached
            connection = None
    try:
        yield connection
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:  # closing a dead connection is not news
                pass


def send(person, subject, body, connection=None, url=None):
    """Send one message, on `connection` when given. Returns the Outbox row;
    its `sent_at` is None when nothing was sent."""
    row = Outbox.objects.create(to_person=person, to_email=person.email or "", subject=subject, body=body)
    if not person.email:
        row.error = "no email address"
        row.save(update_fields=["error"])
        return row
    if not configured():
        row.error = NOT_CONFIGURED
        row.save(update_fields=["error"])
        return row
    try:
        send_mail(subject, body, None, [person.email], fail_silently=False, connection=connection)
    except Exception as e:  # anything the backend raises is a failed send, not a crash
        row.error = e.__class__.__name__
        row.failure = e   # for the caller in this request only; never stored
        log.warning("send failed to person %s: %s", person.pk, e.__class__.__name__)
    else:
        row.sent_at = timezone.now()
    row.save(update_fields=["sent_at", "error"])
    return row
```

- [ ] **Step 4: Add the Outbox fields**

In `messaging/models.py`, replace the class with:

```python
class Outbox(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        PUSH = "push", "Push"

    to_person = models.ForeignKey("people.Person", null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="messages")
    to_email = models.EmailField(blank=True, default="")
    channel = models.CharField(max_length=5, choices=Channel.choices, default=Channel.EMAIL)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    # The page a push opens, and how many times the timer has tried it.
    url = models.CharField(max_length=200, blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=0)
    queued_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-queued_at"]
        verbose_name_plural = "outbox"
        indexes = [models.Index(fields=["channel", "sent_at"])]
```

(keep the module docstring, updating "email the app sends" to "email or push the app sends"). Then:

```bash
DEBUG=1 python manage.py makemigrations messaging -n outbox_channel
```

- [ ] **Step 5: The seed's stub, the factory helper, the Activity labels**

`people/management/commands/seed_demo.py`: change the stub's signature to `def _dropped_send(person, subject, body, connection=None, url=None):`.

`tests/factories.py`, append:

```python
def client_for(person, **user_kw):
    """A test client signed in as the person: their existing login, else a
    new one made with `user_kw` (is_all_teams_manager=True and the like)."""
    from django.test import Client
    client = Client()
    client.force_login(person.user if person.user_id else make_user_for(person, **user_kw))
    return client
```

`people/views/activity.py`: add `"uploads.personfile"` to `PERSON_MODELS` and extend the practice-wide labels:

```python
PERSON_MODELS = ("people.person", "shifts.entry", "leave.booking", "leave.adjustment", "leave.yearend",
                 "uploads.personfile")

LEAVE_SETTING_MODELS = {"leave.bankholiday": "Bank holiday", "leave.blackout": "Blackout",
                        "leave.leavetype": "Leave type", "leave.leavesetting": "Leave settings",
                        "payroll.payrollrun": "Payroll", "shifts.openshift": "Open shift",
                        "messaging.message": "Message", "messaging.notice": "Notice",
                        "uploads.sharedfile": "Shared file"}
```

- [ ] **Step 6: Run the tests**

Run: `python -m pytest tests/test_messaging_groundwork.py tests/test_messaging.py tests/test_activity.py tests/test_seed_demo.py -q`
Expected: PASS. (`test_activity` and `test_seed_demo` prove the move and the new keyword broke nothing.)

- [ ] **Step 7: Commit**

```bash
git add messaging people tests
git commit -m "Messaging: services become a package; the Outbox gains channel, url and attempts; send takes a link; the Activity log knows the engagement labels

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---

### Task 2: Open shift models

**Files:**
- Create: `shifts/models/open_shift.py`, `shifts/migrations/0003_open_shifts.py` (generated), `tests/test_open_shift_models.py`
- Modify: `shifts/models/__init__.py`, `shifts/admin.py`, `tests/factories.py`

**Interfaces:**
- Produces: `shifts.models.OpenShift` (fields `team, day, start, finish, break_minutes, department, comment, everyone, audience, posted_by, state, filled_by, entry, created_at`; `State.OPEN/FILLED/WITHDRAWN`; property `expired`), `shifts.models.OpenShiftClaim` (fields `open_shift` (related name `claims`), `person` (related name `open_shift_claims`), `overtime, note, state, decided_by, decided_at, created_at`; `State.WAITING/APPROVED/DECLINED/WITHDRAWN/CLOSED`); factories `make_open_shift(team=None, day=None, **kw)` and `make_claim(open_shift, person, **kw)`.

- [ ] **Step 1: Write the failing tests**

```python
"""Open shifts: the two tables and their rules (spec 5, section 2)."""

from datetime import date, time

import pytest
from django.db import IntegrityError, transaction

from shifts.models import OpenShift, OpenShiftClaim
from tests.factories import make_claim, make_open_shift, make_person, make_team

pytestmark = pytest.mark.django_db


def test_a_new_post_is_open_and_is_for_its_audience_teams():
    nursing = make_team("Nursing")
    post = make_open_shift(day=date(2026, 11, 9))
    post.audience.add(nursing)
    assert post.state == OpenShift.State.OPEN and list(post.audience.all()) == [nursing]
    assert post.everyone is False and post.filled_by is None and post.entry is None


def test_a_post_whose_day_has_passed_is_expired_not_closed():
    assert make_open_shift(day=date(2026, 11, 1)).expired          # the pin is 2 Nov 2026
    assert not make_open_shift(day=date(2026, 11, 2)).expired      # today is not expired
    assert not make_open_shift(day=date(2026, 11, 3)).expired


def test_a_shift_needs_a_later_finish():
    with pytest.raises(IntegrityError), transaction.atomic():
        make_open_shift(start=time(12), finish=time(12))


def test_one_waiting_claim_per_person_but_a_withdrawn_one_may_be_remade():
    post, sam = make_open_shift(), make_person()
    first = make_claim(post, sam)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_claim(post, sam)
    first.state = OpenShiftClaim.State.WITHDRAWN
    first.save()
    assert make_claim(post, sam).state == OpenShiftClaim.State.WAITING


def test_claims_hang_off_the_post_and_the_person():
    post, sam = make_open_shift(), make_person()
    claim = make_claim(post, sam, overtime="toil", note="Happy to")
    assert list(post.claims.all()) == [claim] and list(sam.open_shift_claims.all()) == [claim]
    assert claim.overtime == "toil" and claim.decided_by is None and claim.decided_at is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_open_shift_models.py -q`
Expected: FAIL (cannot import `OpenShift` / `make_open_shift`).

- [ ] **Step 3: The models**

`shifts/models/open_shift.py`:

```python
"""Open shifts (ROTA-11, spec 5 section 2): a manager posts an unfilled
shift for chosen teams or everyone, staff claim it, a manager of the owning
team approves one claim and the shift goes on that person's rota."""

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from shifts.models.entry import Entry


class OpenShift(models.Model):
    class State(models.TextChoices):
        OPEN = "open"
        FILLED = "filled"
        WITHDRAWN = "withdrawn"

    # The owning team decides which managers approve; the audience decides
    # who is told and who can claim.
    team = models.ForeignKey("people.Team", on_delete=models.PROTECT, related_name="open_shifts")
    day = models.DateField()
    start = models.TimeField()
    finish = models.TimeField()
    break_minutes = models.PositiveSmallIntegerField(default=0)
    department = models.ForeignKey("people.Department", null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="+")
    comment = models.CharField(max_length=200, blank=True, default="")
    everyone = models.BooleanField(default=False)
    audience = models.ManyToManyField("people.Team", blank=True, related_name="open_shifts_offered")
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="+")
    state = models.CharField(max_length=9, choices=State.choices, default=State.OPEN)
    filled_by = models.ForeignKey("people.Person", null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="+")
    entry = models.ForeignKey("shifts.Entry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["day", "start", "pk"]
        constraints = [models.CheckConstraint(condition=Q(finish__gt=F("start")), name="open_shift_finish_after_start")]
        indexes = [models.Index(fields=["state", "day"])]

    def __str__(self):
        return f"open shift {self.day} {self.start:%H:%M}-{self.finish:%H:%M}"

    @property
    def expired(self):
        """Not a state: an open post whose day has gone just reads as expired."""
        return self.day < timezone.localdate()


class OpenShiftClaim(models.Model):
    class State(models.TextChoices):
        WAITING = "waiting"
        APPROVED = "approved"
        DECLINED = "declined"
        WITHDRAWN = "withdrawn"
        CLOSED = "closed"      # another claim was approved, or the post withdrawn

    open_shift = models.ForeignKey(OpenShift, on_delete=models.CASCADE, related_name="claims")
    person = models.ForeignKey("people.Person", on_delete=models.CASCADE, related_name="open_shift_claims")
    # The claimant's choice (ROTA-06): normal hours, or overtime paid / TOIL.
    overtime = models.CharField(max_length=4, choices=Entry.Overtime.choices, blank=True, default="")
    note = models.CharField(max_length=200, blank=True, default="")
    state = models.CharField(max_length=9, choices=State.choices, default=State.WAITING)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [models.UniqueConstraint(fields=["open_shift", "person"], condition=Q(state="waiting"),
                                               name="one_waiting_claim")]
```

`shifts/models/__init__.py`: add `from .open_shift import OpenShift, OpenShiftClaim` and both names to `__all__`.

`shifts/admin.py`: append (keep the file's existing imports and style; `ReadOnlyModelAdmin` is in `people.admin`):

```python
from people.admin import ReadOnlyModelAdmin
from shifts.models import OpenShift, OpenShiftClaim


@admin.register(OpenShift)
class OpenShiftAdmin(ReadOnlyModelAdmin):
    list_display = ("day", "start", "finish", "team", "state")


@admin.register(OpenShiftClaim)
class OpenShiftClaimAdmin(ReadOnlyModelAdmin):
    list_display = ("open_shift", "person", "state", "created_at")
```

(If `shifts/admin.py` already imports `admin` and `ReadOnlyModelAdmin`, add only the two model names to its existing imports.)

`tests/factories.py`, append:

```python
def make_open_shift(team=None, day=None, **kw):
    from datetime import timedelta

    from shifts.models import OpenShift
    kw.setdefault("start", time(9, 0))
    kw.setdefault("finish", time(13, 0))
    return OpenShift.objects.create(team=team or make_team(), day=day or (timezone.localdate() + timedelta(days=7)), **kw)


def make_claim(open_shift, person, **kw):
    from shifts.models import OpenShiftClaim
    return OpenShiftClaim.objects.create(open_shift=open_shift, person=person, **kw)
```

- [ ] **Step 4: Migrate and run**

```bash
DEBUG=1 python manage.py makemigrations shifts -n open_shifts
python -m pytest tests/test_open_shift_models.py tests/test_shifts_models.py -q
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add shifts tests
git commit -m "Shifts: OpenShift and OpenShiftClaim models

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---

### Task 3: `entries.add_item`, the approval path through the cell writer

**Files:**
- Modify: `shifts/services/entries.py` (after `set_cell`, before `PATCHABLE`)
- Test: `tests/test_shifts_entries.py` (append)

**Interfaces:**
- Consumes: `entries._items_of`, `_clean_item`, `_departments`, `_write`, `_check`.
- Produces: `entries.add_item(user, person, day, raw, via_open_shift=False) -> list[Entry]` (the cell's visible rows after the write; the new shift is the last one unless leave hid it).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_shifts_entries.py`; reuse that file's existing imports and add what is missing at the top: `PermissionDenied`, `make_team_manager`, `make_user_for`)

```python
# --- add_item (spec 5, section 3) ---------------------------------------------

def _shift(start="13:00", finish="17:00", **kw):
    return {"kind": "shift", "start": start, "finish": finish, "break_minutes": 0, **kw}


def test_add_item_appends_beside_the_existing_shift(db):
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    user = make_user_for(lead)
    sam = make_person(first_name="Sam", team=team)
    make_entry(sam, MON, start=time(8), finish=time(12))
    rows = entries.add_item(user, sam, MON, _shift(overtime="toil", text="Cover"))
    assert [(e.start, e.finish, e.overtime, e.text) for e in rows] == [
        (time(8), time(12), "", ""), (time(13), time(17), "toil", "Cover")]
    assert Entry.objects.filter(person=sam, day=MON).count() == 2


def test_add_item_on_an_empty_day_makes_the_only_shift(db):
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    sam = make_person(first_name="Sam", team=team)
    (row,) = entries.add_item(make_user_for(lead), sam, MON, _shift())
    assert row.person == sam and row.day == MON and row.start == time(13)


def test_add_item_is_refused_for_a_manager_of_another_team(db):
    mine, theirs = make_team("Nursing"), make_team("Reception")
    lead = make_person(first_name="Lead", team=mine)
    make_team_manager(lead, mine)
    sam = make_person(first_name="Sam", team=theirs)
    with pytest.raises(PermissionDenied):
        entries.add_item(make_user_for(lead), sam, MON, _shift())


def test_add_item_through_an_open_shift_skips_only_the_team_check(db):
    mine, theirs = make_team("Nursing"), make_team("Reception")
    lead = make_person(first_name="Lead", team=mine)
    make_team_manager(lead, mine)
    sam = make_person(first_name="Sam", team=theirs)
    (row,) = entries.add_item(make_user_for(lead), sam, MON, _shift(), via_open_shift=True)
    assert row.person == sam
    with pytest.raises(ValueError):          # the item is still validated
        entries.add_item(make_user_for(make_person(first_name="X", team=mine)), sam, MON, _shift("17:00", "13:00"), via_open_shift=True)


def test_add_item_takes_a_shift_and_nothing_else(db):
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    sam = make_person(first_name="Sam", team=team)
    with pytest.raises(ValueError):
        entries.add_item(make_user_for(lead), sam, MON, {"kind": "comment", "text": "hi"})


def test_add_item_records_the_day_for_notify_staff(db):
    from shifts.models import DayChange
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    sam = make_person(first_name="Sam", team=team)
    entries.add_item(make_user_for(lead), sam, MON, _shift())
    assert DayChange.objects.filter(person=sam, day=MON).exists()
```

(`MON`, `time`, `make_entry`, `make_person`, `make_team`, `entries`, `Entry` and `pytest` are already imported in that file; check the top of the file and add only what is missing. In the fourth test the second call uses a user who does not manage Sam, with a bad item: with `via_open_shift=True` the item check must still raise `ValueError`.)

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_shifts_entries.py -q -k add_item`
Expected: FAIL (`module 'shifts.services.entries' has no attribute 'add_item'`).

- [ ] **Step 3: Implement**

In `shifts/services/entries.py`, after `set_cell`:

```python
def add_item(user, person, day, raw, via_open_shift=False):
    """Add one shift to the person's cell, keeping what is already there
    (overtime beside a normal shift, a split day). The same writer as
    set_cell, so the day is recorded for Notify staff, leave covers it as it
    covers any shift, and the cell change is audited.

    `via_open_shift` is for open_shifts.approve only: that service has
    already checked the user manages the post's owning team, whatever team
    the claimant is in, so only the "you manage this person" check is
    skipped. The item is validated either way."""
    if not via_open_shift:
        _check(user, person)
    item = _clean_item(raw, _departments())
    if item["kind"] != Entry.Kind.SHIFT:
        raise ValueError("only a shift can be added this way")
    with transaction.atomic():
        return _write(user, person, day, [*_items_of(person, day), item], keep_appearance=True)
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_shifts_entries.py -q`
Expected: PASS (the new tests and all earlier ones).

- [ ] **Step 5: Commit**

```bash
git add shifts tests
git commit -m "Shifts: entries.add_item appends one shift to a cell, for open-shift approval

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---
### Task 4: The open-shifts service and its mail

**Files:**
- Create: `shifts/services/open_shifts.py`, `shifts/services/open_shift_mail.py`, `tests/test_open_shifts.py`

**Interfaces:**
- Consumes: Task 2's models; `entries.add_item` (Task 3); `messaging.services.send/batch/absolute_link` (Task 1); `access.can_manage_team`, `access.managed_teams`, `access.is_all_teams`; `leave.services.costing.active_day(person, day)` (a `BookingDay` or None, with `.booking.part` and `.booking.type`); `rota_notify.settle_baseline(actor, people, since, note)`.
- Produces (all in `shifts.services.open_shifts`; every function that writes takes the acting `user` first):
  - `class OpenShiftError(Exception)` with `.message` (a sentence to show).
  - `post(user, team, day, start, finish, break_minutes=0, department=None, comment="", everyone=False, audience_teams=(), base_url="") -> OpenShift`
  - `withdraw(user, shift, base_url="") -> OpenShift`
  - `claim(user, shift, overtime="", note="", base_url="") -> OpenShiftClaim`
  - `withdraw_claim(user, claim) -> OpenShiftClaim`
  - `approve(user, claim, overtime=None, base_url="") -> OpenShiftClaim`
  - `decline(user, claim, base_url="") -> OpenShiftClaim`
  - `clashes(claim) -> list[str]`
  - `audience(shift) -> QuerySet[Person]`, `managers_of(team) -> list[Person]`
  - `visible_to(user) -> QuerySet[OpenShift]`, `can_claim(user, shift) -> bool`, `waiting_claims(user) -> QuerySet[OpenShiftClaim]` (live waiting claims on posts of teams the user manages)

- [ ] **Step 1: Write the failing tests**

`tests/test_open_shifts.py`:

```python
"""Open shifts: posting, claiming, approving (spec 5, section 3)."""

from datetime import date, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.exceptions import PermissionDenied

from leave.services import bookings
from messaging.models import Outbox
from people.models import AuditEntry
from shifts.models import DayChange, Entry, OpenShift, OpenShiftClaim
from shifts.services import open_shifts
from shifts.services.open_shifts import OpenShiftError
from tests.factories import make_entry, make_person, make_team, make_team_manager, make_type, make_user_for

pytestmark = pytest.mark.django_db
DAY = date(2026, 11, 9)      # the Monday after the pinned Monday 2 Nov 2026


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")

    def staff(first, team, **user_kw):
        p = make_person(first_name=first, team=team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
        make_user_for(p, **user_kw)
        return p

    lead = staff("Lead", reception)
    make_team_manager(lead, reception)
    nurse_lead = staff("Nurse", nursing)
    make_team_manager(nurse_lead, nursing)
    return SimpleNamespace(
        reception=reception, nursing=nursing, lead=lead, nurse_lead=nurse_lead,
        boss=staff("Boss", reception, is_all_teams_manager=True),
        sam=staff("Sam", reception), ann=staff("Ann", reception), nina=staff("Nina", nursing))


def post(c, **kw):
    args = dict(team=c.reception, day=DAY, start=time(9), finish=time(13), break_minutes=0, department=None,
                comment="", everyone=False, audience_teams=[c.reception])
    args.update(kw)
    return open_shifts.post(c.lead.user, **args)


def subjects(person):
    return list(Outbox.objects.filter(to_person=person).values_list("subject", flat=True))


# --- posting -------------------------------------------------------------------

def test_a_manager_of_the_owning_team_posts_and_the_audience_is_told(cast):
    shift = post(cast, comment="Secret comment")
    assert shift.state == "open" and list(shift.audience.all()) == [cast.reception]
    assert subjects(cast.sam) == ["Open shift: Mon 9 Nov, 09:00–13:00"]
    assert subjects(cast.ann) == subjects(cast.sam)
    assert subjects(cast.nina) == [] and subjects(cast.lead) == []        # other team; the poster
    body = Outbox.objects.get(to_person=cast.sam).body
    assert "Secret comment" not in body and "/rota/open/" in body


def test_everyone_tells_every_current_person_with_a_login(cast):
    shift = post(cast, everyone=True, audience_teams=[])
    assert shift.everyone and shift.audience.count() == 0
    assert subjects(cast.nina) and subjects(cast.sam)


def test_only_a_manager_of_the_owning_team_may_post(cast):
    with pytest.raises(PermissionDenied):
        open_shifts.post(cast.nurse_lead.user, cast.reception, DAY, time(9), time(13), audience_teams=[cast.reception])
    with pytest.raises(PermissionDenied):
        open_shifts.post(cast.sam.user, cast.reception, DAY, time(9), time(13), audience_teams=[cast.reception])
    assert open_shifts.post(cast.boss.user, cast.nursing, DAY, time(9), time(13), audience_teams=[cast.nursing])


@pytest.mark.parametrize("kw, message", [
    ({"day": date(2026, 11, 1)}, "passed"),
    ({"start": time(13), "finish": time(9)}, "later"),
    ({"break_minutes": 20}, "break"),
    ({"audience_teams": []}, "who is offered"),
])
def test_a_bad_post_is_refused_with_a_sentence(cast, kw, message):
    with pytest.raises(OpenShiftError, match=message):
        post(cast, **kw)
    assert OpenShift.objects.count() == 0


def test_posting_is_audited(cast):
    post(cast)
    assert AuditEntry.objects.filter(model="shifts.openshift", field="posted").count() == 1


# --- claiming ------------------------------------------------------------------

def test_an_audience_member_claims_and_the_owning_managers_are_told(cast):
    shift = post(cast, comment="x")
    claim = open_shifts.claim(cast.sam.user, shift, overtime="toil", note="Happy to")
    assert claim.state == "waiting" and claim.overtime == "toil" and claim.person == cast.sam
    assert "Sam Patel has claimed an open shift" in subjects(cast.lead)
    assert "Sam Patel has claimed an open shift" in subjects(cast.boss)
    assert subjects(cast.sam) == ["Open shift: Mon 9 Nov, 09:00–13:00"]     # not told of their own claim
    assert all("Happy to" not in b for b in Outbox.objects.values_list("body", flat=True))


def test_someone_outside_the_audience_cannot_claim(cast):
    shift = post(cast)
    with pytest.raises(PermissionDenied):
        open_shifts.claim(cast.nina.user, shift)


def test_one_waiting_claim_each_and_a_withdrawn_one_can_be_remade(cast):
    shift = post(cast)
    claim = open_shifts.claim(cast.sam.user, shift)
    with pytest.raises(OpenShiftError, match="already"):
        open_shifts.claim(cast.sam.user, shift)
    open_shifts.withdraw_claim(cast.sam.user, claim)
    assert OpenShiftClaim.objects.get(pk=claim.pk).state == "withdrawn"
    assert open_shifts.claim(cast.sam.user, shift).state == "waiting"


def test_nobody_can_withdraw_someone_elses_claim(cast):
    claim = open_shifts.claim(cast.sam.user, post(cast))
    with pytest.raises(PermissionDenied):
        open_shifts.withdraw_claim(cast.ann.user, claim)


def test_a_filled_or_withdrawn_post_cannot_be_claimed(cast, today):
    shift = post(cast)
    open_shifts.withdraw(cast.lead.user, shift)
    with pytest.raises(OpenShiftError, match="no longer open"):
        open_shifts.claim(cast.sam.user, shift)
    again = post(cast)
    today(DAY + timedelta(days=1))
    with pytest.raises(OpenShiftError, match="no longer open"):      # expired
        open_shifts.claim(cast.sam.user, again)


def test_an_invalid_overtime_choice_is_refused(cast):
    with pytest.raises(OpenShiftError, match="Overtime"):
        open_shifts.claim(cast.sam.user, post(cast), overtime="gold")


# --- approving -----------------------------------------------------------------

def test_approving_puts_the_shift_on_the_claimants_rota_beside_their_own(cast):
    make_entry(cast.sam, DAY, start=time(14), finish=time(18))
    shift = post(cast, comment="Cover", break_minutes=0)
    claim = open_shifts.claim(cast.sam.user, shift, overtime="paid")
    open_shifts.approve(cast.lead.user, claim)
    rows = list(Entry.objects.filter(person=cast.sam, day=DAY).order_by("position"))
    assert [(e.start, e.finish, e.overtime, e.text) for e in rows] == [(time(14), time(18), "", ""), (time(9), time(13), "paid", "Cover")]
    shift.refresh_from_db()
    claim.refresh_from_db()
    assert shift.state == "filled" and shift.filled_by == cast.sam and shift.entry == rows[-1]
    assert claim.state == "approved" and claim.decided_by == cast.lead.user and claim.decided_at


def test_the_approver_may_change_the_overtime_choice(cast):
    claim = open_shifts.claim(cast.sam.user, post(cast), overtime="paid")
    open_shifts.approve(cast.lead.user, claim, overtime="")
    assert Entry.objects.get(person=cast.sam, day=DAY).overtime == ""


def test_approving_tells_the_claimant_and_the_others_it_has_gone_and_closes_their_claims(cast):
    shift = post(cast)
    first = open_shifts.claim(cast.sam.user, shift)
    second = open_shifts.claim(cast.ann.user, shift)
    open_shifts.approve(cast.lead.user, first)
    second.refresh_from_db()
    assert second.state == "closed"
    assert "Your open shift claim for Mon 9 Nov is approved" in subjects(cast.sam)
    assert "The open shift on Mon 9 Nov has been filled" in subjects(cast.ann)


def test_approving_does_not_leave_the_day_for_notify_staff(cast):
    claim = open_shifts.claim(cast.sam.user, post(cast))
    open_shifts.approve(cast.lead.user, claim)
    assert not DayChange.objects.filter(person=cast.sam).exists()
    assert AuditEntry.objects.filter(model="shifts.entry", object_id=cast.sam.pk, field="cell").exists()


def test_an_owning_team_manager_approves_a_claimant_from_another_team(cast):
    shift = post(cast, everyone=True, audience_teams=[])
    claim = open_shifts.claim(cast.nina.user, shift)
    open_shifts.approve(cast.lead.user, claim)             # Lead manages Reception, Nina is in Nursing
    assert Entry.objects.filter(person=cast.nina, day=DAY).count() == 1


def test_a_manager_of_another_team_cannot_approve_or_decline(cast):
    claim = open_shifts.claim(cast.sam.user, post(cast))
    with pytest.raises(PermissionDenied):
        open_shifts.approve(cast.nurse_lead.user, claim)
    with pytest.raises(PermissionDenied):
        open_shifts.decline(cast.nurse_lead.user, claim)
    with pytest.raises(PermissionDenied):
        open_shifts.approve(cast.sam.user, claim)


def test_a_claim_already_decided_cannot_be_decided_again(cast):
    shift = post(cast)
    first = open_shifts.claim(cast.sam.user, shift)
    second = open_shifts.claim(cast.ann.user, shift)
    open_shifts.approve(cast.lead.user, first)
    with pytest.raises(OpenShiftError, match="already decided"):
        open_shifts.approve(cast.lead.user, first)
    with pytest.raises(OpenShiftError, match="already decided"):
        open_shifts.approve(cast.lead.user, second)           # closed when the first was approved
    assert Entry.objects.filter(day=DAY).count() == 1


def test_approving_is_refused_on_a_whole_day_of_leave_and_changes_nothing(cast):
    bookings.book(cast.boss.user, cast.sam, make_type("Training"), DAY, DAY, "whole")
    shift = post(cast)
    claim = open_shifts.claim(cast.sam.user, shift)
    with pytest.raises(OpenShiftError, match="on leave"):
        open_shifts.approve(cast.lead.user, claim)
    claim.refresh_from_db()
    shift.refresh_from_db()
    assert claim.state == "waiting" and shift.state == "open"
    assert not Entry.objects.filter(person=cast.sam, day=DAY, start=time(9)).exists()


def test_an_overlapping_shift_only_warns(cast):
    make_entry(cast.sam, DAY, start=time(12), finish=time(16))
    claim = open_shifts.claim(cast.sam.user, post(cast))
    assert any("12:00–16:00" in w for w in open_shifts.clashes(claim))
    assert open_shifts.approve(cast.lead.user, claim).state == "approved"


def test_part_day_leave_only_warns_and_names_the_type(cast):
    bookings.book(cast.boss.user, cast.sam, make_type("Training"), DAY, DAY, "pm")
    claim = open_shifts.claim(cast.sam.user, post(cast))
    assert any("Training" in w for w in open_shifts.clashes(claim))
    assert open_shifts.approve(cast.lead.user, claim).state == "approved"


def test_declining_tells_the_claimant_and_leaves_the_post_open(cast):
    shift = post(cast)
    claim = open_shifts.claim(cast.sam.user, shift)
    open_shifts.decline(cast.lead.user, claim)
    claim.refresh_from_db()
    shift.refresh_from_db()
    assert claim.state == "declined" and shift.state == "open"
    assert "Your open shift claim for Mon 9 Nov was declined" in subjects(cast.sam)


def test_withdrawing_a_post_closes_its_claims_and_tells_the_claimants(cast):
    shift = post(cast)
    claim = open_shifts.claim(cast.sam.user, shift)
    open_shifts.withdraw(cast.lead.user, shift)
    claim.refresh_from_db()
    shift.refresh_from_db()
    assert shift.state == "withdrawn" and claim.state == "closed"
    assert "The open shift on Mon 9 Nov has been withdrawn" in subjects(cast.sam)
    with pytest.raises(PermissionDenied):
        open_shifts.withdraw(cast.nurse_lead.user, post(cast))


# --- who sees what ---------------------------------------------------------------

def test_visible_to(cast):
    reception_only = post(cast)
    nursing_post = open_shifts.post(cast.nurse_lead.user, cast.nursing, DAY, time(9), time(13), audience_teams=[cast.nursing])
    everyone = post(cast, everyone=True, audience_teams=[])
    seen = lambda p: set(open_shifts.visible_to(p.user))                     # noqa: E731
    assert seen(cast.sam) == {reception_only, everyone}
    assert seen(cast.nina) == {nursing_post, everyone}
    assert seen(cast.lead) == {reception_only, everyone}                     # Lead manages Reception; also in its audience
    assert seen(cast.nurse_lead) == {nursing_post, everyone}
    assert seen(cast.boss) == {reception_only, nursing_post, everyone}


def test_waiting_claims_are_those_on_posts_the_user_manages(cast):
    mine = open_shifts.claim(cast.sam.user, post(cast))
    open_shifts.claim(cast.nina.user, open_shifts.post(cast.nurse_lead.user, cast.nursing, DAY, time(9), time(13), audience_teams=[cast.nursing]))
    assert list(open_shifts.waiting_claims(cast.lead.user)) == [mine]
    assert open_shifts.waiting_claims(cast.boss.user).count() == 2
    assert open_shifts.waiting_claims(cast.sam.user).count() == 0
```

(One assertion above ends `or True`; delete that line when Task 8 adds `Outbox.url` for push, or simply delete it now: the line carries no information. Remove it before running.)

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_open_shifts.py -q`
Expected: FAIL (`No module named 'shifts.services.open_shifts'`).

- [ ] **Step 3: The mail module**

`shifts/services/open_shift_mail.py`:

```python
"""The emails of open shifts (and, through messaging.send, their pushes):
NOTIF-03 and NOTIF-04, plus the three spec 5 adds. A subject names the day
and times only; a body never carries the post's comment or a claim's note."""

import logging

from messaging import services as messaging

log = logging.getLogger("shifts.open_shifts")


def _day(shift):
    return f"{shift.day:%a %-d %b}"


def _when(shift):
    return f"{shift.start:%H:%M}–{shift.finish:%H:%M}"


def _body(shift, intro, path, base_url):
    lines = [intro, "", f"Day: {_day(shift)}", f"Times: {_when(shift)}"]
    if shift.break_minutes:
        lines.append(f"Break: {shift.break_minutes} minutes")
    if shift.department_id:
        lines.append(f"Department: {shift.department.name}")
    lines += ["", messaging.absolute_link(base_url, path)]
    return "\n".join(lines) + "\n"


def _send_all(people, subject, body, path):
    with messaging.batch() as connection:
        for person in people:
            try:
                messaging.send(person, subject, body, connection=connection, url=path)
            except Exception:  # send never raises; a bug here must not undo the booking
                log.exception("open shift mail failed")


def posted(shift, people, base_url=""):
    _send_all(people, f"Open shift: {_day(shift)}, {_when(shift)}",
              _body(shift, "A shift is open and you can claim it.", "/rota/open/", base_url), "/rota/open/")


def claimed(claim, managers, base_url=""):
    shift, path = claim.open_shift, f"/rota/open/{claim.open_shift_id}/"
    _send_all(managers, f"{claim.person.name} has claimed an open shift",
              _body(shift, f"{claim.person.name} has claimed this open shift. Decide here.", path, base_url), path)


def approved(claim, base_url=""):
    shift = claim.open_shift
    _send_all([claim.person], f"Your open shift claim for {_day(shift)} is approved",
              _body(shift, "Your claim is approved and the shift is on your rota.", "/rota/", base_url), "/rota/")


def declined(claim, base_url=""):
    shift = claim.open_shift
    _send_all([claim.person], f"Your open shift claim for {_day(shift)} was declined",
              _body(shift, "Your claim was not accepted.", "/rota/open/", base_url), "/rota/open/")


def closed(claims, shift, word, base_url=""):
    """`word` is "filled" or "withdrawn": told to everyone whose claim was waiting."""
    _send_all([c.person for c in claims], f"The open shift on {_day(shift)} has been {word}",
              _body(shift, f"This open shift has been {word}.", "/rota/open/", base_url), "/rota/open/")
```

- [ ] **Step 4: The service**

`shifts/services/open_shifts.py`:

```python
"""Open shifts (ROTA-11, REQ-16; spec 5 section 3). A manager of the owning
team posts a shift for chosen teams or everyone; people in the audience
claim it; a manager of the owning team approves one claim, which adds the
shift to the claimant's rota through entries.add_item and closes the post."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from leave.services import costing as leave_costing
from people.models import Person
from people.services import access, audit
from shifts.models import Entry, OpenShift, OpenShiftClaim
from shifts.services import entries
from shifts.services import notify as rota_notify
from shifts.services import open_shift_mail as mail

OPEN, FILLED, WITHDRAWN = OpenShift.State.OPEN, OpenShift.State.FILLED, OpenShift.State.WITHDRAWN
WAITING, APPROVED, DECLINED, WITHDRAWN_CLAIM, CLOSED = (
    OpenShiftClaim.State.WAITING, OpenShiftClaim.State.APPROVED, OpenShiftClaim.State.DECLINED,
    OpenShiftClaim.State.WITHDRAWN, OpenShiftClaim.State.CLOSED)


class OpenShiftError(Exception):
    """Something the person can fix or should be told; `.message` is the
    sentence to show."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


# --- who ----------------------------------------------------------------------

def _me(user):
    person = getattr(user, "person", None)
    if person is None:
        raise PermissionDenied("you are not on the rota")
    return person


def _require_owner(user, shift):
    if not access.can_manage_team(user, shift.team):
        raise PermissionDenied("you don't manage this team")


def audience(shift):
    """The people offered the shift: current on its day, able to sign in,
    and in a chosen team (or anyone, for everyone)."""
    people = Person.objects.current(on=shift.day).filter(user__isnull=False, user__is_active=True)
    if not shift.everyone:
        people = people.filter(team__in=shift.audience.all())
    return people


def managers_of(team):
    """All-teams managers and the team's managers who can sign in and are
    current (the people who can approve a claim on the team's posts)."""
    reachable = Person.objects.current().filter(user__is_active=True)
    out = {p.pk: p for p in reachable.filter(user__is_all_teams_manager=True)}
    for p in reachable.filter(manager_of__team_id=team.pk):
        out[p.pk] = p
    return [out[k] for k in sorted(out)]


def visible_to(user):
    """The posts a user may see: those offered to their team (or everyone),
    and every post of a team they manage; all of them for an all-teams manager."""
    if access.is_all_teams(user):
        return OpenShift.objects.all()
    q = Q(team__in=access.managed_teams(user))
    me = getattr(user, "person", None)
    if me is not None:
        q |= Q(everyone=True)
        if me.team_id:
            q |= Q(audience=me.team_id)
    return OpenShift.objects.filter(q).distinct()


def can_claim(user, shift):
    me = getattr(user, "person", None)
    return (me is not None and shift.state == OPEN and not shift.expired
            and audience(shift).filter(pk=me.pk).exists())


def waiting_claims(user):
    return OpenShiftClaim.objects.filter(state=WAITING, open_shift__state=OPEN,
                                         open_shift__team__in=access.managed_teams(user))


# --- posting ------------------------------------------------------------------

def post(user, team, day, start, finish, break_minutes=0, department=None, comment="",
         everyone=False, audience_teams=(), base_url=""):
    if not access.can_manage_team(user, team):
        raise PermissionDenied("you don't manage this team")
    teams = list(audience_teams)
    if day < timezone.localdate():
        raise OpenShiftError("That day has passed.")
    if finish <= start:
        raise OpenShiftError("The finish must be later than the start.")
    if break_minutes not in Entry.BREAKS:
        raise OpenShiftError("The break must be none, 15, 30, 45 or 60 minutes.")
    if not everyone and not teams:
        raise OpenShiftError("Choose who is offered this shift.")
    with transaction.atomic():
        shift = OpenShift.objects.create(team=team, day=day, start=start, finish=finish, break_minutes=break_minutes,
                                         department=department, comment=(comment or "")[:200],
                                         everyone=bool(everyone), posted_by=user)
        if not everyone:
            shift.audience.set(teams)
        audit.record(user, shift, {"posted": ("", f"{day.isoformat()} {start:%H:%M}-{finish:%H:%M}")},
                     note=f"open shift · {team.name}")
    # Registered after the block, so it runs when the caller's own transaction (if any) commits.
    transaction.on_commit(lambda: mail.posted(shift, list(audience(shift).exclude(user=user)), base_url))
    return shift


def withdraw(user, shift, base_url=""):
    with transaction.atomic():
        shift = OpenShift.objects.select_related("team").get(pk=shift.pk)
        _require_owner(user, shift)
        if shift.state != OPEN:
            raise OpenShiftError("This open shift is no longer open.")
        waiting = list(shift.claims.filter(state=WAITING).select_related("person"))
        shift.claims.filter(state=WAITING).update(state=CLOSED, decided_by=user, decided_at=timezone.now())
        shift.state = WITHDRAWN
        shift.save(update_fields=["state"])
        audit.record(user, shift, {"state": ("open", "withdrawn")}, note=f"open shift · {shift.team.name}")
    transaction.on_commit(lambda: mail.closed(waiting, shift, "withdrawn", base_url))
    return shift


# --- claiming -----------------------------------------------------------------

def claim(user, shift, overtime="", note="", base_url=""):
    person = _me(user)
    if overtime not in Entry.Overtime.values:
        raise OpenShiftError("Overtime must be normal hours, paid or TOIL.")
    with transaction.atomic():
        shift = OpenShift.objects.select_related("team", "department").get(pk=shift.pk)
        if shift.state != OPEN or shift.expired:
            raise OpenShiftError("This open shift is no longer open.")
        if not audience(shift).filter(pk=person.pk).exists():
            raise PermissionDenied("this shift is not offered to you")
        if shift.claims.filter(person=person, state=WAITING).exists():
            raise OpenShiftError("You have already claimed this shift.")
        made = OpenShiftClaim.objects.create(open_shift=shift, person=person, overtime=overtime, note=(note or "")[:200])
        managers = [m for m in managers_of(shift.team) if m.pk != person.pk]
    transaction.on_commit(lambda: mail.claimed(made, managers, base_url))
    return made


def withdraw_claim(user, claim):
    person = _me(user)
    with transaction.atomic():
        claim = OpenShiftClaim.objects.get(pk=claim.pk)
        if claim.person_id != person.pk:
            raise PermissionDenied("not your claim")
        if claim.state != WAITING:
            raise OpenShiftError("This claim has already been decided.")
        claim.state = WITHDRAWN_CLAIM
        claim.save(update_fields=["state"])
    return claim


# --- deciding -----------------------------------------------------------------

def clashes(claim):
    """Plain sentences about the claimant's own rota that day: an overlapping
    shift, or leave (its type only). Warnings, never blocks."""
    shift, out = claim.open_shift, []
    for e in Entry.objects.filter(person=claim.person, day=shift.day, kind=Entry.Kind.SHIFT, covered_by__isnull=True):
        if e.start < shift.finish and shift.start < e.finish:
            out.append(f"Already working {e.start:%H:%M}–{e.finish:%H:%M} that day.")
    booked = leave_costing.active_day(claim.person, shift.day)
    if booked is not None:
        out.append(f"Has {booked.booking.type.name} booked that day.")
    return out


def approve(user, claim, overtime=None, base_url=""):
    with transaction.atomic():
        claim = OpenShiftClaim.objects.select_related("open_shift__team", "open_shift__department", "person").get(pk=claim.pk)
        shift = claim.open_shift
        _require_owner(user, shift)
        if claim.state != WAITING or shift.state != OPEN:
            raise OpenShiftError("This claim has already been decided.")
        overtime = claim.overtime if overtime is None else overtime
        if overtime not in Entry.Overtime.values:
            raise OpenShiftError("Overtime must be normal hours, paid or TOIL.")
        booked = leave_costing.active_day(claim.person, shift.day)
        if booked is not None and booked.booking.part == "whole":
            raise OpenShiftError(f"{claim.person.name} is on leave that day.")
        since = timezone.now()
        item = {"kind": "shift", "start": shift.start.strftime("%H:%M"), "finish": shift.finish.strftime("%H:%M"),
                "break_minutes": shift.break_minutes, "department": shift.department_id, "text": shift.comment,
                "wfh": False, "overtime": overtime}
        try:
            rows = entries.add_item(user, claim.person, shift.day, item, via_open_shift=True)
        except ValueError as e:
            raise OpenShiftError(str(e)) from None
        others = list(shift.claims.filter(state=WAITING).exclude(pk=claim.pk).select_related("person"))
        now = timezone.now()
        shift.claims.filter(pk__in=[c.pk for c in others]).update(state=CLOSED, decided_by=user, decided_at=now)
        claim.state, claim.overtime, claim.decided_by, claim.decided_at = APPROVED, overtime, user, now
        claim.save(update_fields=["state", "overtime", "decided_by", "decided_at"])
        shift.state, shift.filled_by, shift.entry = FILLED, claim.person, (rows[-1] if rows else None)
        shift.save(update_fields=["state", "filled_by", "entry"])
        # The claimant hears from the approval email; the day is not left for the next Notify staff.
        rota_notify.settle_baseline(user, [claim.person], since, "open shift approved: the claimant is told by the approval email")
        audit.record(user, shift, {"state": ("open", "filled"), "filled_by": ("", claim.person.name)},
                     note=f"open shift · {shift.team.name}")

    def tell():
        mail.approved(claim, base_url)
        mail.closed(others, shift, "filled", base_url)
    transaction.on_commit(tell)
    return claim


def decline(user, claim, base_url=""):
    with transaction.atomic():
        claim = OpenShiftClaim.objects.select_related("open_shift__team", "open_shift__department", "person").get(pk=claim.pk)
        shift = claim.open_shift
        _require_owner(user, shift)
        if claim.state != WAITING or shift.state != OPEN:
            raise OpenShiftError("This claim has already been decided.")
        claim.state, claim.decided_by, claim.decided_at = DECLINED, user, timezone.now()
        claim.save(update_fields=["state", "decided_by", "decided_at"])
        audit.record(user, shift, {"claim": ("waiting", "declined")}, note=f"open shift · {claim.person.name}")
    transaction.on_commit(lambda: mail.declined(claim, base_url))
    return claim
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_open_shifts.py -q`
Expected: PASS. If a booking helper call (`bookings.book(...)`) complains about the person's hours or allowance, give Sam `weekly_hours`/`days_per_week` as the fixture already does and, for a type that draws on an allowance, use `make_type("Training")` (draws from nothing). If a mail subject comparison fails on the person's display name, print `subjects(cast.lead)`: the fixture names are "Sam Patel" because `make_person` defaults `last_name="Patel"`.

- [ ] **Step 6: Commit**

```bash
git add shifts tests
git commit -m "Shifts: the open-shifts service (post, claim, approve, decline, withdraw) and its mail

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---

### Task 5: The open-shifts pages, pop-ups and nav

**Files:**
- Create: `shifts/views/open_shifts.py`, `templates/ui/_field.html`, `templates/shifts/open_shifts.html`, `open_detail.html`, `open_post_dialog.html`, `open_claim_dialog.html`, `open_decide_dialog.html`, `tests/test_open_shift_views.py`
- Modify: `shifts/forms.py`, `shifts/urls.py`, `ui/context_processors.py`, `static/css/components.css`

**Interfaces:**
- Consumes: Task 4's service.
- Produces: URLs `open-shifts` (`/rota/open/`), `open-shift-post` (`/rota/open/post/`), `open-shift-detail` (`/rota/open/<pk>/`), `open-shift-claim` (`/rota/open/<pk>/claim/`), `open-shift-withdraw` (`/rota/open/<pk>/withdraw/`, POST), `open-claim-decide` (`/rota/open/claims/<pk>/decide/`), `open-claim-withdraw` (`/rota/open/claims/<pk>/withdraw/`, POST); forms `OpenShiftForm(user=…)`, `ClaimForm`, `DecideForm`; the partial `ui/_field.html` (`{% include "ui/_field.html" with field=form.x %}`); nav child "Open shifts" under Rota for everyone.

- [ ] **Step 1: Write the failing tests**

`tests/test_open_shift_views.py`:

```python
"""The open-shifts pages and their pop-ups (spec 5, section 3)."""

import json
from datetime import date, time
from types import SimpleNamespace

import pytest
from django.test import Client

from shifts.models import Entry, OpenShift, OpenShiftClaim
from shifts.services import open_shifts
from tests.factories import make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db
DAY = date(2026, 11, 9)


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")

    def staff(first, team, **kw):
        p = make_person(first_name=first, team=team)
        client = Client()
        client.force_login(make_user_for(p, **kw))
        return SimpleNamespace(person=p, client=client)

    lead = staff("Lead", reception)
    make_team_manager(lead.person, reception)
    return SimpleNamespace(reception=reception, nursing=nursing, lead=lead, sam=staff("Sam", reception),
                           nina=staff("Nina", nursing), boss=staff("Boss", reception, is_all_teams_manager=True))


def make_post(c, **kw):
    args = dict(team=c.reception, day=DAY, start=time(9), finish=time(13), audience_teams=[c.reception])
    args.update(kw)
    return open_shifts.post(c.lead.person.user, **args)


def test_the_list_shows_posts_offered_to_you_with_a_claim_button(cast):
    make_post(cast, comment="Front desk")
    body = cast.sam.client.get("/rota/open/").content.decode()
    assert "Mon 9 Nov" in body and "09:00" in body and "Front desk" in body and "Reception" in body
    assert f'/rota/open/{OpenShift.objects.get().pk}/claim/' in body
    assert "Post an open shift" not in body


def test_someone_outside_the_audience_sees_nothing(cast):
    make_post(cast)
    body = cast.nina.client.get("/rota/open/").content.decode()
    assert "Mon 9 Nov" not in body and "Nothing is open" in body


def test_a_manager_sees_the_post_action_and_the_waiting_claims(cast):
    post = make_post(cast)
    open_shifts.claim(cast.sam.person.user, post, note="Keen")
    body = cast.lead.client.get("/rota/open/").content.decode()
    assert "Post an open shift" in body and "Sam Patel" in body and "Keen" in body
    assert "/rota/open/claims/" in body


def test_staff_may_not_open_the_post_dialog_but_a_manager_may(cast):
    assert cast.sam.client.get("/rota/open/post/").status_code == 403
    assert cast.lead.client.get("/rota/open/post/").status_code == 200


def test_posting_from_the_dialog_creates_the_post_and_refreshes(cast):
    r = cast.lead.client.post("/rota/open/post/", {
        "team": cast.reception.pk, "day": "2026-11-10", "start": "09:00", "finish": "13:00", "break_minutes": "0",
        "comment": "Phones", "audience": [cast.reception.pk]})
    assert r.status_code == 200 and json.loads(r.content) == {"refresh": True}
    post = OpenShift.objects.get()
    assert post.day == date(2026, 11, 10) and post.comment == "Phones" and list(post.audience.all()) == [cast.reception]


def test_a_bad_post_shows_the_error_in_the_dialog(cast):
    r = cast.lead.client.post("/rota/open/post/", {
        "team": cast.reception.pk, "day": "2026-10-01", "start": "09:00", "finish": "13:00", "break_minutes": "0",
        "audience": [cast.reception.pk]})
    assert r.status_code == 200 and b"That day has passed" in r.content and OpenShift.objects.count() == 0


def test_the_dialog_only_offers_the_managers_own_team_as_owner(cast):
    body = cast.lead.client.get("/rota/open/post/").content.decode()
    owner = body.split('name="team"')[1].split("</select>")[0]
    assert "Reception" in owner and "Nursing" not in owner


def test_claiming_from_the_dialog(cast):
    post = make_post(cast)
    assert cast.sam.client.get(f"/rota/open/{post.pk}/claim/").status_code == 200
    r = cast.sam.client.post(f"/rota/open/{post.pk}/claim/", {"overtime": "toil", "note": "Yes please"})
    assert json.loads(r.content) == {"refresh": True}
    claim = OpenShiftClaim.objects.get()
    assert claim.person == cast.sam.person and claim.overtime == "toil" and claim.note == "Yes please"


def test_claiming_a_post_you_cannot_see_is_a_404(cast):
    post = make_post(cast)
    assert cast.nina.client.get(f"/rota/open/{post.pk}/claim/").status_code == 404
    assert cast.nina.client.post(f"/rota/open/{post.pk}/claim/", {"overtime": ""}).status_code == 404


def test_claiming_twice_shows_the_sentence(cast):
    post = make_post(cast)
    cast.sam.client.post(f"/rota/open/{post.pk}/claim/", {"overtime": ""})
    r = cast.sam.client.post(f"/rota/open/{post.pk}/claim/", {"overtime": ""})
    assert r.status_code == 200 and b"already claimed" in r.content


def test_withdrawing_your_own_claim_redirects_to_the_list(cast):
    claim = open_shifts.claim(cast.sam.person.user, make_post(cast))
    r = cast.sam.client.post(f"/rota/open/claims/{claim.pk}/withdraw/")
    assert r.status_code == 302 and r["Location"] == "/rota/open/"
    claim.refresh_from_db()
    assert claim.state == "withdrawn"
    assert cast.sam.client.get(f"/rota/open/claims/{claim.pk}/withdraw/").status_code == 405


def test_the_decide_dialog_approves_with_a_changed_overtime_choice(cast):
    claim = open_shifts.claim(cast.sam.person.user, make_post(cast), overtime="paid")
    page = cast.lead.client.get(f"/rota/open/claims/{claim.pk}/decide/").content.decode()
    assert "Sam Patel" in page and "Approve" in page and "Decline" in page
    r = cast.lead.client.post(f"/rota/open/claims/{claim.pk}/decide/", {"action": "approve", "overtime": ""})
    assert json.loads(r.content) == {"refresh": True}
    assert Entry.objects.get(person=cast.sam.person, day=DAY).overtime == ""


def test_the_decide_dialog_declines(cast):
    claim = open_shifts.claim(cast.sam.person.user, make_post(cast))
    r = cast.lead.client.post(f"/rota/open/claims/{claim.pk}/decide/", {"action": "decline", "overtime": ""})
    assert json.loads(r.content) == {"refresh": True}
    claim.refresh_from_db()
    assert claim.state == "declined"


def test_staff_and_other_teams_cannot_open_the_decide_dialog(cast):
    claim = open_shifts.claim(cast.sam.person.user, make_post(cast))
    assert cast.sam.client.get(f"/rota/open/claims/{claim.pk}/decide/").status_code == 404
    assert cast.nina.client.post(f"/rota/open/claims/{claim.pk}/decide/", {"action": "approve", "overtime": ""}).status_code == 404


def test_the_detail_page_is_for_the_owning_managers_only(cast):
    post = make_post(cast)
    open_shifts.claim(cast.sam.person.user, post)
    assert cast.lead.client.get(f"/rota/open/{post.pk}/").status_code == 200
    assert cast.boss.client.get(f"/rota/open/{post.pk}/").status_code == 200
    assert cast.sam.client.get(f"/rota/open/{post.pk}/").status_code == 404


def test_withdrawing_a_post(cast):
    post = make_post(cast)
    r = cast.lead.client.post(f"/rota/open/{post.pk}/withdraw/")
    assert r.status_code == 302
    post.refresh_from_db()
    assert post.state == "withdrawn"
    assert cast.sam.client.post(f"/rota/open/{post.pk}/withdraw/").status_code in (403, 404)


def test_the_rota_menu_has_open_shifts_for_everyone(cast):
    for who in (cast.sam, cast.lead):
        body = who.client.get("/rota/").content.decode()
        assert 'href="/rota/open/"' in body


def test_closed_posts_from_the_last_month_are_listed_apart(cast):
    post = make_post(cast)
    open_shifts.withdraw(cast.lead.person.user, post)
    body = cast.lead.client.get("/rota/open/").content.decode()
    assert "Filled and past" in body and "withdrawn" in body
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_open_shift_views.py -q`
Expected: FAIL (404 on `/rota/open/`).

- [ ] **Step 3: The forms** (append to `shifts/forms.py`; add `Team` to the `people.models` import and `access` to a new `from people.services import access` import, then these classes)

```python
OVERTIME_CHOICES = [("", "Normal hours"), ("paid", "Overtime – paid"), ("toil", "Overtime – TOIL")]


class OpenShiftForm(forms.Form):
    team = forms.ModelChoiceField(Team.objects.none(), label="Owning team",
                                  help_text="Its managers approve the claims.")
    day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    start = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    finish = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"))
    break_minutes = forms.TypedChoiceField(choices=BREAK_CHOICES, coerce=int, initial=0, label="Break")
    department = forms.ModelChoiceField(Department.objects.filter(archived=False), required=False, empty_label="None")
    comment = forms.CharField(max_length=200, required=False)
    everyone = forms.BooleanField(required=False, label="Offer it to everyone")
    audience = forms.ModelMultipleChoiceField(Team.objects.filter(active=True), required=False,
                                              widget=forms.CheckboxSelectMultiple, label="Or to these teams")

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = access.managed_teams(user).filter(active=True)


class ClaimForm(forms.Form):
    overtime = forms.ChoiceField(choices=OVERTIME_CHOICES, required=False, initial="", widget=forms.RadioSelect)
    note = forms.CharField(max_length=200, required=False, label="Note for the manager")


class DecideForm(forms.Form):
    overtime = forms.ChoiceField(choices=OVERTIME_CHOICES, required=False, widget=forms.RadioSelect)
```

- [ ] **Step 4: The views**

`shifts/views/open_shifts.py`:

```python
"""Open shifts: the list, the post and claim pop-ups, the decision pop-up
and the detail page (spec 5, section 3). A post or claim the user may not
see is a 404, never a 403."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from people.services import access
from shifts.forms import ClaimForm, DecideForm, OpenShiftForm
from shifts.models import OpenShift, OpenShiftClaim
from shifts.services import open_shifts

REFRESH = {"refresh": True}
WAITING = OpenShiftClaim.State.WAITING


def _visible_post(request, pk):
    return get_object_or_404(open_shifts.visible_to(request.user).select_related("team", "department"), pk=pk)


def _managed_claim(request, pk):
    """A claim on a post of a team the user manages, else 404."""
    claim = get_object_or_404(OpenShiftClaim.objects.select_related("open_shift__team", "open_shift__department", "person"), pk=pk)
    if not access.can_manage_team(request.user, claim.open_shift.team):
        raise Http404
    return claim


def _decorate(request, post):
    me = getattr(request.user, "person", None)
    claims = list(post.claims.all())
    post.can_claim = open_shifts.can_claim(request.user, post)
    post.my_claim = next((c for c in claims if me is not None and c.person_id == me.pk and c.state == WAITING), None)
    post.is_owner = access.can_manage_team(request.user, post.team)
    post.waiting = [c for c in claims if c.state == WAITING] if post.is_owner else []
    for c in post.waiting:
        c.clashes = open_shifts.clashes(c)
    post.audience_text = "Everyone" if post.everyone else ", ".join(t.name for t in post.audience.all())
    return post


@login_required
def open_list(request):
    today = timezone.localdate()
    posts = (open_shifts.visible_to(request.user).select_related("team", "department", "filled_by")
             .prefetch_related("audience", "claims__person"))
    live, past = [], []
    for post in posts:
        _decorate(request, post)
        if post.state == OpenShift.State.OPEN and not post.expired:
            live.append(post)
        elif post.day >= today - timedelta(days=30):
            past.append(post)
    past.sort(key=lambda p: (p.day, p.start), reverse=True)
    return render(request, "shifts/open_shifts.html", {
        "page_title": "Open shifts", "live": live, "past": past, "is_manager": access.is_manager(request.user)})


@login_required
@access.manager_required
def post_dialog(request):
    form = OpenShiftForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            open_shifts.post(request.user, d["team"], d["day"], d["start"], d["finish"], d["break_minutes"],
                             d["department"], d["comment"], d["everyone"], d["audience"],
                             base_url=request.build_absolute_uri("/"))
            return JsonResponse(REFRESH)
        except open_shifts.OpenShiftError as e:
            form.add_error(None, e.message)
    return render(request, "shifts/open_post_dialog.html", {"form": form})


@login_required
def claim_dialog(request, pk):
    post = _visible_post(request, pk)
    form = ClaimForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            open_shifts.claim(request.user, post, form.cleaned_data["overtime"], form.cleaned_data["note"],
                              base_url=request.build_absolute_uri("/"))
            return JsonResponse(REFRESH)
        except open_shifts.OpenShiftError as e:
            form.add_error(None, e.message)
        except PermissionDenied:
            raise Http404 from None
    return render(request, "shifts/open_claim_dialog.html", {"form": form, "post": post})


@login_required
@require_POST
def withdraw_claim(request, pk):
    claim = get_object_or_404(OpenShiftClaim, pk=pk, person__user=request.user)
    try:
        open_shifts.withdraw_claim(request.user, claim)
        messages.success(request, "Your claim is withdrawn.")
    except open_shifts.OpenShiftError as e:
        messages.error(request, e.message)
    return redirect("open-shifts")


@login_required
def detail(request, pk):
    post = _visible_post(request, pk)
    if not access.can_manage_team(request.user, post.team):
        raise Http404
    post = (OpenShift.objects.select_related("team", "department", "filled_by").prefetch_related("audience", "claims__person")
            .get(pk=post.pk))
    _decorate(request, post)
    post.history = [c for c in post.claims.all() if c.state != WAITING]
    return render(request, "shifts/open_detail.html", {"page_title": "Open shift", "post": post})


@login_required
def decide_dialog(request, pk):
    claim = _managed_claim(request, pk)
    form = DecideForm(request.POST or None, initial={"overtime": claim.overtime})
    if request.method == "POST" and form.is_valid():
        action = request.POST.get("action")
        try:
            if action == "approve":
                open_shifts.approve(request.user, claim, form.cleaned_data["overtime"],
                                    base_url=request.build_absolute_uri("/"))
            elif action == "decline":
                open_shifts.decline(request.user, claim, base_url=request.build_absolute_uri("/"))
            else:
                form.add_error(None, "Choose approve or decline.")
            if not form.errors:
                return JsonResponse(REFRESH)
        except open_shifts.OpenShiftError as e:
            form.add_error(None, e.message)
    return render(request, "shifts/open_decide_dialog.html", {
        "form": form, "claim": claim, "post": claim.open_shift, "clashes": open_shifts.clashes(claim)})


@login_required
@require_POST
def withdraw_post(request, pk):
    post = _visible_post(request, pk)
    try:
        open_shifts.withdraw(request.user, post, base_url=request.build_absolute_uri("/"))
        messages.success(request, "The open shift is withdrawn.")
    except open_shifts.OpenShiftError as e:
        messages.error(request, e.message)
    return redirect("open-shifts")
```

(`withdraw_post` calls the service, which raises `PermissionDenied` (a 403) for a non-owner; the test accepts 403 or 404.)

`shifts/urls.py`: import `open_shifts` in `from shifts.views import api, dialogs, grid, open_shifts, reports, today` and add before `path("rota/", ...)`:

```python
    path("rota/open/", open_shifts.open_list, name="open-shifts"),
    path("rota/open/post/", open_shifts.post_dialog, name="open-shift-post"),
    path("rota/open/<int:pk>/", open_shifts.detail, name="open-shift-detail"),
    path("rota/open/<int:pk>/claim/", open_shifts.claim_dialog, name="open-shift-claim"),
    path("rota/open/<int:pk>/withdraw/", open_shifts.withdraw_post, name="open-shift-withdraw"),
    path("rota/open/claims/<int:pk>/decide/", open_shifts.decide_dialog, name="open-claim-decide"),
    path("rota/open/claims/<int:pk>/withdraw/", open_shifts.withdraw_claim, name="open-claim-withdraw"),
```

- [ ] **Step 5: The templates**

`templates/ui/_field.html`:

```html
<div class="field{% if field.errors %} has-error{% endif %}"><label for="{{ field.id_for_label }}">{{ field.label }}</label>{{ field }}{% for e in field.errors %}<p class="field-error">{{ e }}</p>{% endfor %}{% if field.help_text %}<p class="field-help">{{ field.help_text }}</p>{% endif %}</div>
```

`templates/shifts/open_shifts.html`:

```html
{% extends "base.html" %}
{% block title %}Open shifts · AMG Shift Central{% endblock %}
{% block topbar_actions %}{% if is_manager %}<a class="topbar-action is-primary" href="{% url 'open-shift-post' %}" data-dialog>Post an open shift +</a>{% endif %}{% endblock %}
{% block content %}
<div class="open-cards">
{% for post in live %}
  <article class="open-card">
    <header><strong>{{ post.day|date:"D j M" }}</strong> {{ post.start|time:"H:i" }}–{{ post.finish|time:"H:i" }}{% if post.break_minutes %} · {{ post.break_minutes }} min break{% endif %}</header>
    <p>{% if post.department %}{{ post.department.name }}{% endif %}{% if post.comment %} {{ post.comment }}{% endif %}</p>
    <p class="muted">For {{ post.audience_text }} · owned by {{ post.team.name }}</p>
    {% if post.my_claim %}
      <p>You've claimed this.</p>
      <form method="post" action="{% url 'open-claim-withdraw' post.my_claim.pk %}">{% csrf_token %}<button class="btn btn-quiet">Withdraw my claim</button></form>
    {% elif post.can_claim %}
      <a class="btn btn-dark" href="{% url 'open-shift-claim' post.pk %}" data-dialog>Claim</a>
    {% endif %}
    {% if post.is_owner %}
      {% for c in post.waiting %}
      <div class="open-claim"><strong>{{ c.person.name }}</strong> — {% if c.overtime %}{{ c.get_overtime_display }}{% else %}Normal hours{% endif %}{% if c.note %}: {{ c.note }}{% endif %}
        {% for w in c.clashes %}<span class="flash flash-warning">{{ w }}</span>{% endfor %}
        <a href="{% url 'open-claim-decide' c.pk %}" data-dialog>Decide</a></div>
      {% endfor %}
      <p><a href="{% url 'open-shift-detail' post.pk %}">Details</a></p>
    {% endif %}
  </article>
{% empty %}<p>Nothing is open.</p>{% endfor %}
</div>
{% if past %}
<details class="open-past"><summary>Filled and past</summary>
  <table class="table"><tbody>
  {% for post in past %}
    <tr><td>{{ post.day|date:"D j M" }} {{ post.start|time:"H:i" }}–{{ post.finish|time:"H:i" }}</td>
        <td>{% if post.state == "filled" %}filled by {{ post.filled_by.name }}{% elif post.state == "withdrawn" %}withdrawn{% else %}expired{% endif %}</td>
        <td>{% if post.is_owner %}<a href="{% url 'open-shift-detail' post.pk %}">Details</a>{% endif %}</td></tr>
  {% endfor %}
  </tbody></table>
</details>
{% endif %}
{% endblock %}
```

`templates/shifts/open_detail.html`:

```html
{% extends "base.html" %}
{% block title %}Open shift · AMG Shift Central{% endblock %}
{% block content %}
<h2>{{ post.day|date:"l j F Y" }}, {{ post.start|time:"H:i" }}–{{ post.finish|time:"H:i" }}</h2>
<p>{% if post.department %}{{ post.department.name }}. {% endif %}{{ post.comment }}</p>
<p class="muted">For {{ post.audience_text }} · owned by {{ post.team.name }} · {{ post.get_state_display }}{% if post.filled_by %} by {{ post.filled_by.name }}{% endif %}</p>
{% if post.state == "open" %}
<form method="post" action="{% url 'open-shift-withdraw' post.pk %}">{% csrf_token %}<button class="btn btn-quiet">Withdraw this open shift</button></form>
{% endif %}
<h3>Waiting</h3>
<table class="table"><tbody>
{% for c in post.waiting %}
  <tr><td>{{ c.person.name }}</td><td>{% if c.overtime %}{{ c.get_overtime_display }}{% else %}Normal hours{% endif %}</td><td>{{ c.note }}</td>
      <td>{% for w in c.clashes %}{{ w }} {% endfor %}</td><td><a href="{% url 'open-claim-decide' c.pk %}" data-dialog>Decide</a></td></tr>
{% empty %}<tr><td colspan="5">No claims waiting.</td></tr>{% endfor %}
</tbody></table>
<h3>History</h3>
<table class="table"><tbody>
{% for c in post.history %}<tr><td>{{ c.person.name }}</td><td>{{ c.get_state_display }}</td><td>{{ c.decided_at|date:"j M H:i" }}</td></tr>
{% empty %}<tr><td colspan="3">Nothing decided yet.</td></tr>{% endfor %}
</tbody></table>
{% endblock %}
```

`templates/shifts/open_post_dialog.html`:

```html
{% extends "ui/_dialog.html" %}
{% block dialog_title %}Post an open shift{% endblock %}
{% block dialog_body %}
<form method="post" action="{% url 'open-shift-post' %}" data-dialog-form>
  {% csrf_token %}
  {% for e in form.non_field_errors %}<p class="flash flash-error">{{ e }}</p>{% endfor %}
  {% include "ui/_field.html" with field=form.team %}
  {% include "ui/_field.html" with field=form.day %}
  <div class="field-row">
    <div class="field">{% include "ui/_field.html" with field=form.start %}</div>
    <div class="field">{% include "ui/_field.html" with field=form.finish %}</div>
    <div class="field">{% include "ui/_field.html" with field=form.break_minutes %}</div>
  </div>
  {% include "ui/_field.html" with field=form.department %}
  {% include "ui/_field.html" with field=form.comment %}
  <div class="field"><label>{{ form.everyone }} {{ form.everyone.label }}</label></div>
  {% include "ui/_field.html" with field=form.audience %}
  <button class="btn btn-dark">Post it</button>
</form>
{% endblock %}
```

`templates/shifts/open_claim_dialog.html`:

```html
{% extends "ui/_dialog.html" %}
{% block dialog_title %}Claim this shift{% endblock %}
{% block dialog_body %}
<p>{{ post.day|date:"l j F" }}, {{ post.start|time:"H:i" }}–{{ post.finish|time:"H:i" }}{% if post.department %} · {{ post.department.name }}{% endif %}</p>
<form method="post" action="{% url 'open-shift-claim' post.pk %}" data-dialog-form>
  {% csrf_token %}
  {% for e in form.non_field_errors %}<p class="flash flash-error">{{ e }}</p>{% endfor %}
  <fieldset class="field"><legend>How will you work it?</legend>
    {% for value, label in form.fields.overtime.choices %}<label><input type="radio" name="overtime" value="{{ value }}"{% if form.overtime.value|default:"" == value %} checked{% endif %}> {{ label }}</label> {% endfor %}
  </fieldset>
  {% include "ui/_field.html" with field=form.note %}
  <button class="btn btn-dark">Claim it</button>
</form>
{% endblock %}
```

`templates/shifts/open_decide_dialog.html`:

```html
{% extends "ui/_dialog.html" %}
{% block dialog_title %}{{ claim.person.name }} · {{ post.day|date:"D j M" }}{% endblock %}
{% block dialog_body %}
<p>{{ post.start|time:"H:i" }}–{{ post.finish|time:"H:i" }}{% if post.department %} · {{ post.department.name }}{% endif %}</p>
{% if claim.note %}<p>"{{ claim.note }}"</p>{% endif %}
{% for w in clashes %}<p class="flash flash-warning">{{ w }}</p>{% endfor %}
<form method="post" action="{% url 'open-claim-decide' claim.pk %}" data-dialog-form>
  {% csrf_token %}
  {% for e in form.non_field_errors %}<p class="flash flash-error">{{ e }}</p>{% endfor %}
  <fieldset class="field"><legend>Hours worked as</legend>
    {% for value, label in form.fields.overtime.choices %}<label><input type="radio" name="overtime" value="{{ value }}"{% if form.overtime.value|default:"" == value %} checked{% endif %}> {{ label }}</label> {% endfor %}
  </fieldset>
  <button class="btn btn-dark" name="action" value="approve">Approve</button>
  <button class="btn btn-quiet" name="action" value="decline">Decline</button>
</form>
{% endblock %}
```

(The decision dialog has two submit buttons. `static/js/modal.js` already appends the clicked button's `name` and `value` to the posted data, so the view reads `action` from `request.POST`.)

- [ ] **Step 6: The nav and the styles**

`ui/context_processors.py`: the Rota item's children become (for everyone) the open-shifts link, then the manager-only ones:

```python
    rota_children = [{"label": "Open shifts", "url": "/rota/open/"}]
    if role != "staff":
        rota_children += [{"label": "Who's in today", "url": "/rota/today/"}, {"label": "Time off…", "url": "/time-off/add/", "dialog": True}]
    items = [{"key": "rota", "label": "Rota", "icon": "calendar", "url": "/rota/",
              "active": path.startswith("/rota/"), "children": rota_children},
```

(replacing the existing inline `children=` expression for the Rota item).

`static/css/components.css`, append:

```css
/* Open shifts */
.open-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--sp-4); }
.open-card { background: var(--surface); border: 1px solid var(--hairline); border-radius: var(--radius); padding: var(--sp-4); }
.open-card header { font-size: var(--fs-lg); margin-bottom: var(--sp-2); }
.open-claim { border-top: 1px solid var(--hairline); padding-top: var(--sp-2); margin-top: var(--sp-2); }
.open-past { margin-top: var(--sp-5); }
```


- [ ] **Step 7: Run the tests**

Run: `python -m pytest tests/test_open_shift_views.py tests/test_shell.py tests/test_shifts_views.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add shifts templates static ui tests
git commit -m "Shifts: the Open shifts page, the post, claim and decision pop-ups, and the Rota menu entry

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---
### Task 6: The installable app: manifest, service worker, offline page

**Files:**
- Create: `messaging/urls.py`, `messaging/views/__init__.py`, `messaging/views/app.py`, `templates/messaging/offline.html`, `static/js/sw.js`, `static/img/icon-192.png`, `static/img/icon-512.png`, `tests/test_app_files.py`
- Modify: `config/urls.py`, `config/middleware.py` (the `POLICY`), `templates/base.html`

**Interfaces:**
- Produces: public URLs `manifest` (`/manifest.webmanifest`), `service-worker` (`/sw.js`), `offline` (`/offline/`); `messaging/urls.py` (later tasks append to its `urlpatterns`); `messaging/views/__init__.py` exports nothing yet (later tasks `from . import app, push, ...` as they add modules).

- [ ] **Step 1: Write the failing tests**

`tests/test_app_files.py`:

```python
"""The installable app (spec 5, section 4): a manifest, a service worker that
stores no data, and an offline page, all public."""

import json
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client

from tests.factories import client_for, make_person

pytestmark = pytest.mark.django_db


def test_the_manifest_is_public_json_with_both_icons():
    r = Client().get("/manifest.webmanifest")
    assert r.status_code == 200 and r["Content-Type"].startswith("application/manifest+json")
    assert r["Cache-Control"] == "no-cache"
    data = json.loads(r.content)
    assert data["name"] == "AMG Shift Central" and data["short_name"] == "Shift Central"
    assert data["display"] == "standalone" and data["start_url"] == "/rota/" and data["scope"] == "/"
    assert {i["sizes"] for i in data["icons"]} == {"192x192", "512x512"}


def test_the_service_worker_is_served_from_the_root_with_its_own_cache_header():
    for client in (Client(), client_for(make_person())):         # signed out and signed in
        r = client.get("/sw.js")
        assert r.status_code == 200 and r["Content-Type"].startswith("application/javascript")
        assert r["Cache-Control"] == "no-cache"


def test_the_service_worker_handles_push_and_clicks_and_stores_no_pages():
    body = Client().get("/sw.js").content.decode()
    assert 'addEventListener("push"' in body and 'addEventListener("notificationclick"' in body
    assert 'addEventListener("fetch"' in body
    assert ".put(" not in body and "addAll" not in body, "only the offline page is ever stored"


def test_the_offline_page_needs_no_sign_in_and_is_self_contained():
    r = Client().get("/offline/")
    assert r.status_code == 200 and b"offline" in r.content.lower()
    assert b"<link" not in r.content and b"<script" not in r.content


def test_every_page_links_the_manifest():
    body = client_for(make_person()).get("/rota/").content.decode()
    assert '<link rel="manifest" href="/manifest.webmanifest">' in body


def test_the_policy_allows_the_worker_and_the_manifest_from_our_own_origin():
    policy = Client().get("/accounts/login/")["Content-Security-Policy"]
    assert "worker-src 'self'" in policy and "manifest-src 'self'" in policy


def test_the_icons_are_in_the_static_folder():
    for name in ("icon-192.png", "icon-512.png"):
        assert (Path(settings.BASE_DIR) / "static" / "img" / name).is_file()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_app_files.py -q`
Expected: FAIL (404s).

- [ ] **Step 3: The icons and the policy**

```bash
cp docs/brand/amg-shift-central-icon-192.png static/img/icon-192.png
cp docs/brand/amg-shift-central-icon-512.png static/img/icon-512.png
```

`config/middleware.py`, in `POLICY` add two lines after `"img-src 'self' data:"`:

```python
    "worker-src 'self'",
    "manifest-src 'self'",
```

`templates/base.html`: after the `apple-touch-icon` link add `<link rel="manifest" href="{% url 'manifest' %}">`.

- [ ] **Step 4: The service worker**

`static/js/sw.js`:

```js
/* The phone app's service worker (spec 5, section 4). It receives push and
 * shows an offline page when the network fails. It stores NO rota, leave or
 * personal page: the only thing ever cached is /offline/, which is
 * self-contained. */
var CACHE = "shift-central-offline-v1";

self.addEventListener("install", function (event) {
  event.waitUntil(caches.open(CACHE).then(function (cache) { return cache.add("/offline/"); })
    .then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

// Pages come from the network. Only when it fails does the offline page show.
self.addEventListener("fetch", function (event) {
  if (event.request.mode !== "navigate") { return; }
  event.respondWith(fetch(event.request).catch(function () { return caches.match("/offline/"); }));
});

self.addEventListener("push", function (event) {
  var data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = {}; }
  var url = typeof data.url === "string" ? data.url : "/rota/";
  event.waitUntil(self.registration.showNotification(data.title || "AMG Shift Central", {
    body: data.body || "",
    tag: url,
    icon: "/static/img/icon-192.png",
    data: { url: url },
  }));
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var target = new URL((event.notification.data && event.notification.data.url) || "/rota/", self.location.origin);
  // Only ever a page on this site, whatever the payload said.
  if (target.origin !== self.location.origin) { target = new URL("/rota/", self.location.origin); }
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (windows) {
    for (var i = 0; i < windows.length; i++) {
      if ("focus" in windows[i]) { windows[i].navigate(target.href); return windows[i].focus(); }
    }
    return self.clients.openWindow(target.href);
  }));
});
```

- [ ] **Step 5: The views, the offline page and the routes**

`messaging/views/__init__.py`: empty.

`messaging/views/app.py`:

```python
"""The three public files of the installable app. They hold nothing
personal, so none needs a sign-in (a service worker is fetched without one
when a session has ended)."""

import json
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.templatetags.static import static


def _no_cache(response):
    response["Cache-Control"] = "no-cache"
    return response


def manifest(request):
    data = {
        "name": "AMG Shift Central", "short_name": "Shift Central",
        "start_url": "/rota/", "scope": "/", "display": "standalone",
        "background_color": "#ffffff", "theme_color": "#143D5C",
        "icons": [{"src": static("img/icon-192.png"), "sizes": "192x192", "type": "image/png"},
                  {"src": static("img/icon-512.png"), "sizes": "512x512", "type": "image/png"}],
    }
    return _no_cache(HttpResponse(json.dumps(data), content_type="application/manifest+json"))


def service_worker(request):
    source = (Path(settings.BASE_DIR) / "static" / "js" / "sw.js").read_text()
    return _no_cache(HttpResponse(source, content_type="application/javascript"))


def offline(request):
    return _no_cache(render(request, "messaging/offline.html"))
```

`templates/messaging/offline.html` (no `<link>`, no `<script>`; styles inline):

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Offline · AMG Shift Central</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f4f6f8; color: #143D5C; }
  main { max-width: 22rem; padding: 1.5rem; text-align: center; }
  h1 { font-size: 1.4rem; }
  a { color: #143D5C; font-weight: 700; }
</style>
</head>
<body>
<main>
  <h1>You're offline</h1>
  <p>AMG Shift Central needs a connection to show the rota. Nothing is saved on this phone. Check your signal and try again.</p>
  <p><a href="/rota/">Try again</a></p>
</main>
</body>
</html>
```

`messaging/urls.py`:

```python
from django.urls import path

from messaging.views import app

urlpatterns = [
    path("manifest.webmanifest", app.manifest, name="manifest"),
    path("sw.js", app.service_worker, name="service-worker"),
    path("offline/", app.offline, name="offline"),
]
```

`config/urls.py`: add `path("", include("messaging.urls")),` after the `payroll.urls` include.

- [ ] **Step 6: Run the tests**

Run: `python -m pytest tests/test_app_files.py tests/test_csp.py tests/test_shell.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add messaging config static templates tests
git commit -m "Messaging: the installable app (manifest, service worker that stores no pages, offline page)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---

### Task 7: Devices, keys and the Notifications page

**Files:**
- Create: `messaging/services/push.py`, `messaging/management/__init__.py`, `messaging/management/commands/__init__.py`, `messaging/management/commands/vapid_keys.py`, `messaging/views/push.py`, `templates/messaging/notifications.html`, `static/js/push.js`, `messaging/migrations/0003_push_devices.py` (generated), `tests/test_push_devices.py`
- Modify: `messaging/models.py`, `messaging/admin.py`, `messaging/urls.py`, `config/settings.py`, `ui/context_processors.py`, `static/img/icons.svg`, `tests/conftest.py`, `tests/factories.py`, `deploy/gunicorn.service` (the env-file comment)

**Interfaces:**
- Produces: `messaging.models.PushDevice(person [related_name push_devices], endpoint (unique), p256dh, auth, label, created_at, last_ok_at, failures)`; `messaging.services.push.configured() -> bool`, `register(person, endpoint, p256dh, auth, user_agent) -> PushDevice` (raises `ValueError` with a sentence), `unregister(person, endpoint) -> bool`, `label_for(user_agent) -> str`; settings `VAPID_PRIVATE_KEY_FILE`, `VAPID_PUBLIC_KEY`, `VAPID_SUBJECT`; URLs `notifications`, `push-subscribe`, `push-unsubscribe`, `push-device-remove`; the fixture `push_on` (in `tests/conftest.py`) and factory `make_push_device(person, endpoint=None, **kw)`; a "Notifications" nav item for everyone.

- [ ] **Step 1: Write the failing tests**

`tests/test_push_devices.py`:

```python
"""Registering a phone for push (spec 5, section 4)."""

import json
from io import StringIO

import pytest
from django.core.management import call_command

from messaging.models import PushDevice
from messaging.services import push
from tests.factories import client_for, make_person, make_push_device

pytestmark = pytest.mark.django_db
GOOD = {"endpoint": "https://push.example.net/send/abc123", "keys": {"p256dh": "BNc-key_1=", "auth": "au-th_2"}}


def post_json(client, url, data):
    return client.post(url, json.dumps(data), content_type="application/json")


def test_push_is_off_until_all_three_settings_and_the_key_file_exist(settings, tmp_path):
    assert not push.configured()
    settings.VAPID_PUBLIC_KEY, settings.VAPID_SUBJECT = "BKey", "mailto:a@example.org"
    settings.VAPID_PRIVATE_KEY_FILE = str(tmp_path / "missing.pem")
    assert not push.configured()                       # the file is not there
    (tmp_path / "missing.pem").write_text("pem")
    assert push.configured()
    settings.VAPID_SUBJECT = ""
    assert not push.configured()


def test_the_page_says_push_is_off_when_it_is_not_configured():
    body = client_for(make_person()).get("/notifications/").content.decode()
    assert "not switched on" in body and 'id="push-card"' not in body


def test_the_page_carries_the_public_key_and_the_urls_when_configured(push_on):
    body = client_for(make_person()).get("/notifications/").content.decode()
    assert 'id="push-card"' in body and 'data-key="BPublicKeyForTests"' in body
    assert 'data-subscribe-url="/push/subscribe/"' in body and "/static/js/push.js" in body


def test_subscribing_registers_the_device_for_the_signed_in_person(push_on):
    me = make_person()
    r = post_json(client_for(me), "/push/subscribe/", GOOD)
    assert r.status_code == 200 and r.json()["ok"] is True
    (d,) = PushDevice.objects.all()
    assert d.person == me and d.endpoint == GOOD["endpoint"] and d.p256dh == "BNc-key_1=" and d.auth == "au-th_2"


def test_subscribing_again_updates_rather_than_duplicates_and_moves_to_the_new_owner(push_on):
    a, b = make_person(first_name="A"), make_person(first_name="B")
    post_json(client_for(a), "/push/subscribe/", GOOD)
    post_json(client_for(b), "/push/subscribe/", GOOD)         # the same browser, a different person
    (d,) = PushDevice.objects.all()
    assert d.person == b


@pytest.mark.parametrize("bad", [
    {}, {"endpoint": "http://insecure.example/x", "keys": {"p256dh": "a", "auth": "b"}},
    {"endpoint": "https://x.example/" + "a" * 1100, "keys": {"p256dh": "a", "auth": "b"}},
    {"endpoint": "https://x.example/a", "keys": {"p256dh": "not valid!", "auth": "b"}},
    {"endpoint": "https://x.example/a", "keys": {}},
])
def test_a_bad_subscription_is_refused(push_on, bad):
    r = post_json(client_for(make_person()), "/push/subscribe/", bad)
    assert r.status_code == 400 and PushDevice.objects.count() == 0


def test_subscribing_needs_a_person_keys_and_a_sign_in(push_on, settings):
    from django.test import Client
    assert post_json(Client(), "/push/subscribe/", GOOD).status_code == 302          # to the sign-in
    settings.VAPID_PUBLIC_KEY = ""
    assert post_json(client_for(make_person()), "/push/subscribe/", GOOD).status_code == 400


def test_a_device_label_is_taken_from_the_user_agent(push_on):
    c = client_for(make_person())
    c.post("/push/subscribe/", json.dumps(GOOD), content_type="application/json",
           HTTP_USER_AGENT="Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36")
    assert PushDevice.objects.get().label == "Android Chrome"
    assert push.label_for("Mozilla/5.0 (iPhone; CPU iPhone OS 17 like Mac OS X) Version/17 Safari/604") == "iPhone Safari"
    assert push.label_for("") == "Device browser"


def test_unsubscribing_removes_only_your_own_device(push_on):
    a, b = make_person(first_name="A"), make_person(first_name="B")
    make_push_device(a, endpoint="https://x.example/a")
    ca, cb = client_for(a), client_for(b)
    assert post_json(cb, "/push/unsubscribe/", {"endpoint": "https://x.example/a"}).status_code == 404
    assert PushDevice.objects.count() == 1
    assert post_json(ca, "/push/unsubscribe/", {"endpoint": "https://x.example/a"}).status_code == 200
    assert PushDevice.objects.count() == 0


def test_the_page_lists_your_devices_and_removes_one(push_on):
    me = make_person()
    d = make_push_device(me, label="Android Chrome")
    other = make_push_device(make_person(first_name="Z"), label="Someone else's")
    c = client_for(me)
    body = c.get("/notifications/").content.decode()
    assert "Android Chrome" in body and "Someone else's" not in body
    assert c.post(f"/push/devices/{other.pk}/remove/").status_code == 404
    assert c.post(f"/push/devices/{d.pk}/remove/").status_code == 302
    assert not PushDevice.objects.filter(pk=d.pk).exists()


def test_subscribe_is_post_only_and_csrf_protected(push_on):
    from django.test import Client
    me = make_person()
    c = client_for(me)
    assert c.get("/push/subscribe/").status_code == 405
    strict = Client(enforce_csrf_checks=True)
    strict.force_login(me.user)
    assert post_json(strict, "/push/subscribe/", GOOD).status_code == 403


def test_vapid_keys_writes_a_private_key_file_and_prints_the_public_key(tmp_path):
    out = StringIO()
    target = tmp_path / "vapid.pem"
    call_command("vapid_keys", "--out", str(target), stdout=out)
    assert target.read_text().startswith("-----BEGIN PRIVATE KEY-----")
    assert oct(target.stat().st_mode & 0o777) == "0o640"
    text = out.getvalue()
    assert f"VAPID_PRIVATE_KEY_FILE={target}" in text and "VAPID_PUBLIC_KEY=B" in text and "VAPID_SUBJECT=mailto:" in text


def test_vapid_keys_will_not_overwrite_a_key(tmp_path):
    from django.core.management import CommandError
    target = tmp_path / "vapid.pem"
    target.write_text("keep me")
    with pytest.raises(CommandError):
        call_command("vapid_keys", "--out", str(target), stdout=StringIO())
    assert target.read_text() == "keep me"


def test_the_nav_has_notifications_for_everyone():
    assert 'data-nav="notifications"' in client_for(make_person()).get("/rota/").content.decode()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_push_devices.py -q`
Expected: FAIL.

- [ ] **Step 3: Settings, the model, the fixtures**

`config/settings.py`, after the email block:

```python
# Web push (spec 5). Push is off unless all three are set and the key file
# exists. The private key is a file, never an environment line (a PEM folded
# onto one line arrives broken), readable by the app's group only.
VAPID_PRIVATE_KEY_FILE = os.environ.get("VAPID_PRIVATE_KEY_FILE", "").strip()
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "").strip()
```

`messaging/models.py`, append:

```python
class PushDevice(models.Model):
    """One phone or browser that said yes to notifications (spec 5)."""
    person = models.ForeignKey("people.Person", on_delete=models.CASCADE, related_name="push_devices")
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    label = models.CharField(max_length=80, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_ok_at = models.DateTimeField(null=True, blank=True)
    failures = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.label or 'device'} of person {self.person_id}"
```

`messaging/admin.py`: register `PushDevice` read-only (`list_display = ("person", "label", "created_at", "last_ok_at", "failures")`).

Then `DEBUG=1 python manage.py makemigrations messaging -n push_devices`.

`tests/conftest.py`, append:

```python
@pytest.fixture
def push_on(settings, tmp_path):
    """Web push configured, as on the practice's box (no real key needed:
    the sender is always faked in tests)."""
    key = tmp_path / "vapid.pem"
    key.write_text("test key")
    settings.VAPID_PRIVATE_KEY_FILE = str(key)
    settings.VAPID_PUBLIC_KEY = "BPublicKeyForTests"
    settings.VAPID_SUBJECT = "mailto:test@example.org"
```

`tests/factories.py`, append:

```python
def make_push_device(person, endpoint=None, **kw):
    from messaging.models import PushDevice
    endpoint = endpoint or f"https://push.example.net/send/{next(_next_id)}"
    kw.setdefault("p256dh", "BNcPublic")
    kw.setdefault("auth", "authsecret")
    return PushDevice.objects.create(person=person, endpoint=endpoint, **kw)
```

- [ ] **Step 4: The service**

`messaging/services/push.py` (Task 8 adds `queue`, `deliver`, `send_pending`, `status` to this file):

```python
"""Web push (spec 5, section 4): which phones are registered and whether
push is switched on. Delivery is further down this file (queue, deliver,
send_pending)."""

import os
import re

from django.conf import settings

from messaging.models import PushDevice

_B64URL = re.compile(r"^[A-Za-z0-9_\-=]+$")


def configured():
    """All three settings present and the private key file there."""
    return bool(settings.VAPID_PRIVATE_KEY_FILE and settings.VAPID_PUBLIC_KEY and settings.VAPID_SUBJECT
                and os.path.isfile(settings.VAPID_PRIVATE_KEY_FILE))


def label_for(user_agent):
    ua = user_agent or ""
    system = next((name for key, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"),
                                          ("Windows", "Windows"), ("Mac OS X", "Mac"), ("Linux", "Linux")) if key in ua), "Device")
    browser = next((name for key, name in (("Edg/", "Edge"), ("Firefox", "Firefox"), ("Chrome", "Chrome"),
                                           ("Safari", "Safari")) if key in ua), "browser")
    return f"{system} {browser}"[:80]


def register(person, endpoint, p256dh, auth, user_agent=""):
    """Add (or take over) the device behind this subscription. ValueError
    with a sentence when the subscription is not one a push service made."""
    if not (isinstance(endpoint, str) and endpoint.startswith("https://") and len(endpoint) <= 1000):
        raise ValueError("That is not a push address.")
    for value, limit in ((p256dh, 200), (auth, 100)):
        if not (isinstance(value, str) and 0 < len(value) <= limit and _B64URL.match(value)):
            raise ValueError("That is not a valid push key.")
    device, _ = PushDevice.objects.update_or_create(
        endpoint=endpoint,
        defaults={"person": person, "p256dh": p256dh, "auth": auth, "label": label_for(user_agent), "failures": 0})
    return device


def unregister(person, endpoint):
    """Remove this person's device with the endpoint; False when they have none."""
    deleted, _ = PushDevice.objects.filter(person=person, endpoint=endpoint).delete()
    return bool(deleted)
```

- [ ] **Step 5: The command**

`messaging/management/__init__.py` and `commands/__init__.py`: empty.

`messaging/management/commands/vapid_keys.py`:

```python
"""Make the push keys, once:

    cd /srv/shift-central && .venv/bin/python manage.py vapid_keys \\
        --out /etc/shift-central/vapid.pem --group shift-central

Run it as root: the key file belongs in /etc, readable by the app's group
(mode 640). It refuses to overwrite a key: replacing one cuts off every
registered phone until each person turns notifications on again."""

import base64
import os
import shutil

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Write a new VAPID private key file and print the settings for /etc/shift-central.env"

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True, help="where to write the private key (PEM)")
        parser.add_argument("--group", default="", help="group to own the file, e.g. shift-central")
        parser.add_argument("--subject", default="mailto:webmaster@localhost", help="a mailto: address push services can reach")

    def handle(self, *args, out, group, subject, **options):
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        try:
            fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        except FileExistsError:
            raise CommandError(f"{out} exists; not overwriting a key that phones are registered against.") from None
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
        os.chmod(out, 0o640)
        if group:
            shutil.chown(out, group=group)
        self.stdout.write("Add these to /etc/shift-central.env, then restart shift-central:\n")
        self.stdout.write(f"VAPID_PRIVATE_KEY_FILE={out}")
        self.stdout.write("VAPID_PUBLIC_KEY=" + base64.urlsafe_b64encode(public).rstrip(b"=").decode())
        self.stdout.write(f"VAPID_SUBJECT={subject}")
```

- [ ] **Step 6: The views, URLs, page and script**

`messaging/views/push.py`:

```python
"""Turning push on for a phone (spec 5, section 4)."""

import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from messaging.models import PushDevice
from messaging.services import push


def _person(request):
    return getattr(request.user, "person", None)


@login_required
def notifications(request):
    person = _person(request)
    return render(request, "messaging/notifications.html", {
        "page_title": "Notifications", "configured": push.configured(), "public_key": settings.VAPID_PUBLIC_KEY,
        "devices": person.push_devices.all() if person is not None else []})


def _body(request):
    try:
        data = json.loads(request.body)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


@login_required
@require_POST
def subscribe(request):
    person = _person(request)
    if person is None or not push.configured():
        return JsonResponse({"error": "Notifications are not available."}, status=400)
    data = _body(request)
    keys = data.get("keys") if isinstance(data.get("keys"), dict) else {}
    try:
        device = push.register(person, data.get("endpoint"), keys.get("p256dh"), keys.get("auth"),
                               request.META.get("HTTP_USER_AGENT", ""))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"ok": True, "id": device.pk})


@login_required
@require_POST
def unsubscribe(request):
    person = _person(request)
    if person is None or not push.unregister(person, _body(request).get("endpoint")):
        return JsonResponse({"error": "No such device."}, status=404)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def remove_device(request, pk):
    person = _person(request)
    if person is None:
        raise Http404
    get_object_or_404(PushDevice, pk=pk, person=person).delete()
    return redirect("notifications")
```

`messaging/urls.py`: import `push` too (`from messaging.views import app, push`) and add:

```python
    path("notifications/", push.notifications, name="notifications"),
    path("push/subscribe/", push.subscribe, name="push-subscribe"),
    path("push/unsubscribe/", push.unsubscribe, name="push-unsubscribe"),
    path("push/devices/<int:pk>/remove/", push.remove_device, name="push-device-remove"),
```

`templates/messaging/notifications.html`:

```html
{% extends "base.html" %}
{% load static %}
{% block title %}Notifications · AMG Shift Central{% endblock %}
{% block content %}
<section class="notifications">
  <h2>Notifications on this phone</h2>
  {% if not configured %}
    <p>Phone notifications are not switched on for this practice yet. Everything still reaches you by email.</p>
  {% else %}
  <div id="push-card" data-key="{{ public_key }}" data-subscribe-url="{% url 'push-subscribe' %}" data-unsubscribe-url="{% url 'push-unsubscribe' %}">
    <p data-push-status>Checking this device…</p>
    <p data-push-hint hidden>On an iPhone or iPad, add this app to your Home Screen first (Share, then Add to Home Screen), then open it from there and come back to this page.</p>
    <button type="button" class="btn btn-dark" data-push-on hidden>Turn on notifications on this phone</button>
    <button type="button" class="btn btn-quiet" data-push-off hidden>Turn off notifications on this phone</button>
  </div>
  <script src="{% static 'js/push.js' %}" defer></script>
  {% endif %}
  <p class="muted">Email keeps working whatever you choose here. A notification shows only the subject, never the message.</p>
  <h3>Your devices</h3>
  <table class="table"><tbody>
  {% for d in devices %}
    <tr><td>{{ d.label|default:"Device" }}</td><td>added {{ d.created_at|date:"j M Y" }}</td>
        <td><form method="post" action="{% url 'push-device-remove' d.pk %}">{% csrf_token %}<button class="btn btn-quiet">Remove</button></form></td></tr>
  {% empty %}<tr><td colspan="3">No devices are registered.</td></tr>{% endfor %}
  </tbody></table>
</section>
{% endblock %}
```

`static/js/push.js`:

```js
/* The Notifications page: ask permission, subscribe this device and tell the
 * server, or undo it. A static file because the CSP allows no inline script. */
(function () {
  "use strict";
  var card = document.getElementById("push-card");
  if (!card) { return; }
  var csrf = document.querySelector('meta[name="csrf-token"]').content;
  var statusEl = card.querySelector("[data-push-status]");
  var hint = card.querySelector("[data-push-hint]");
  var turnOn = card.querySelector("[data-push-on]");
  var turnOff = card.querySelector("[data-push-off]");
  var ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
  var standalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  var supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

  function show(el, yes) { el.hidden = !yes; }
  function say(text) { statusEl.textContent = text; }
  function keyBytes(base64) {
    var padded = base64 + "=".repeat((4 - base64.length % 4) % 4);
    var raw = atob(padded.replace(/-/g, "+").replace(/_/g, "/"));
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) { out[i] = raw.charCodeAt(i); }
    return out;
  }
  function post(url, body) {
    return fetch(url, { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf }, body: JSON.stringify(body) });
  }
  function registration() {
    return navigator.serviceWorker.register("/sw.js").then(function () { return navigator.serviceWorker.ready; });
  }

  function refresh() {
    show(turnOn, false); show(turnOff, false); show(hint, false);
    if (ios && !standalone) { say(""); show(hint, true); return Promise.resolve(); }
    if (!supported) { say("This browser can't receive notifications."); return Promise.resolve(); }
    if (Notification.permission === "denied") {
      say("Notifications are blocked for this site in your browser's settings."); return Promise.resolve();
    }
    return registration().then(function (reg) { return reg.pushManager.getSubscription(); }).then(function (sub) {
      if (sub) { say("Notifications are on for this device."); show(turnOff, true); }
      else { say("Notifications are off for this device."); show(turnOn, true); }
    });
  }

  turnOn.addEventListener("click", function () {
    turnOn.disabled = true;
    Notification.requestPermission().then(function (permission) {
      if (permission !== "granted") { return null; }
      return registration().then(function (reg) {
        return reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(card.dataset.key) });
      }).then(function (sub) {
        return post(card.dataset.subscribeUrl, sub.toJSON());
      }).then(function (r) {
        if (!r.ok) { throw new Error("server"); }
        window.location.assign(window.location.href);
      });
    }).catch(function () { say("That didn't work. Try again."); }).then(function () { turnOn.disabled = false; });
  });

  turnOff.addEventListener("click", function () {
    turnOff.disabled = true;
    registration().then(function (reg) { return reg.pushManager.getSubscription(); }).then(function (sub) {
      if (!sub) { return null; }
      return post(card.dataset.unsubscribeUrl, { endpoint: sub.endpoint }).then(function () { return sub.unsubscribe(); });
    }).then(function () { window.location.assign(window.location.href); })
      .catch(function () { say("That didn't work. Try again."); turnOff.disabled = false; });
  });

  refresh().catch(function () { say("This device can't receive notifications."); });
})();
```

- [ ] **Step 7: The nav item and its icon**

`static/img/icons.svg`: before `</svg>` add

```xml
<symbol id="bell" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></symbol>
```

`ui/context_processors.py`: after the `settings` item block (so for everyone, before the `return items`), add:

```python
    items.append({"key": "notifications", "label": "Notifications", "icon": "bell", "url": "/notifications/",
                  "active": path.startswith("/notifications/"), "children": []})
```

`deploy/gunicorn.service`: in the env-file comment block (the lines starting `#   OIDC_RSA_PRIVATE_KEY_FILE=…` area) add after the OIDC lines:

```
# Phone notifications are optional (README, Phone notifications); with these
# three set the app queues a push beside every email:
#
#   VAPID_PRIVATE_KEY_FILE=/etc/shift-central/vapid.pem
#   VAPID_PUBLIC_KEY=<printed by manage vapid_keys>
#   VAPID_SUBJECT=mailto:webmaster@example.org
```

(Keep the comment lines prefixed `#` with no `=` outside comments: `test_deploy_units._directives` skips comments.)

- [ ] **Step 8: Run the tests**

Run: `python -m pytest tests/test_push_devices.py tests/test_deploy_units.py tests/test_shell.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add messaging config static ui deploy tests
git commit -m "Messaging: push devices, VAPID settings and the vapid_keys command, and the Notifications page

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---

### Task 8: Push delivery: the queue, the sender, the timer, Health

**Files:**
- Create: `messaging/management/commands/send_push.py`, `deploy/shift-central-push.service`, `deploy/shift-central-push.timer`, `tests/test_push_delivery.py`
- Modify: `messaging/services/push.py`, `messaging/services/__init__.py`, `requirements.txt`, `people/services/health.py`, `templates/people/_health.html`, `tests/test_deploy_units.py`

**Interfaces:**
- Consumes: Task 1's `Outbox` fields; Task 7's `PushDevice`, `configured()`.
- Produces: `push.queue(person, subject, url) -> Outbox | None`, `push.deliver(device, payload) -> "ok" | "gone" | "failed"` (the one function tests fake), `push.send_pending() -> Counter` (keys `sent`, `failed`, `expired`, `no_device`, `gone`), `push.status() -> dict` (`configured`, `devices`, `queued`, `last_ok`), constants `EXPIRY`, `MAX_ATTEMPTS`, `BATCH`; `messaging.services.send` now also queues a push; `manage send_push`; units `shift-central-push.service/.timer`; `figures(user)["push"]` for all-teams managers.

- [ ] **Step 1: Install and pin the library**

```bash
.venv/bin/pip install pywebpush
diff <(sort requirements.txt) <(.venv/bin/pip freeze | sort)
```

Add every line the diff shows as new (`pywebpush` and what it pulled in) to `requirements.txt`, keeping the file in its alphabetical order and exact `==` pins. (Do not add anything from `requirements-dev.txt`.)

- [ ] **Step 2: Write the failing tests**

`tests/test_push_delivery.py`:

```python
"""Push delivery: the queue and the one-minute sender (spec 5, section 4)."""

from datetime import date
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command

from messaging import services
from messaging.models import Outbox, PushDevice
from messaging.services import push
from tests.factories import client_for, make_person, make_push_device, make_team, make_team_manager

pytestmark = pytest.mark.django_db


@pytest.fixture
def sender(monkeypatch):
    """Replaces the library call; records (device id, payload) and answers as told."""
    box = SimpleNamespace(calls=[], answer="ok")

    def fake(device, payload):
        box.calls.append((device.pk, payload))
        return box.answer
    monkeypatch.setattr(push, "deliver", fake)
    return box


def pushes():
    return Outbox.objects.filter(channel="push")


# --- queueing --------------------------------------------------------------------

def test_send_writes_the_email_and_queues_a_push_for_a_person_with_a_device(push_on):
    p = make_person()
    make_push_device(p)
    services.send(p, "Your shift", "The long body text", url="/rota/open/")
    email = Outbox.objects.get(channel="email")
    queued = pushes().get()
    assert email.body == "The long body text" and email.sent_at
    assert queued.subject == "Your shift" and queued.body == "" and queued.url == "/rota/open/"
    assert queued.sent_at is None and queued.to_person == p and queued.attempts == 0


def test_the_default_link_is_the_rota(push_on):
    p = make_person()
    make_push_device(p)
    services.send(p, "S", "B")
    assert pushes().get().url == "/rota/"


def test_nothing_is_queued_without_keys_or_without_a_device(push_on, settings):
    quiet = make_person(first_name="Quiet")
    services.send(quiet, "S", "B")                              # no device
    loud = make_person(first_name="Loud")
    make_push_device(loud)
    settings.VAPID_PUBLIC_KEY = ""                              # push switched off
    services.send(loud, "S", "B")
    assert pushes().count() == 0 and Outbox.objects.count() == 2


def test_a_push_is_queued_even_when_the_email_cannot_be_sent(push_on):
    p = make_person(email="")
    make_push_device(p)
    services.send(p, "S", "B")
    assert Outbox.objects.get(channel="email").error == "no email address"
    assert pushes().count() == 1


def test_a_failure_while_queueing_never_breaks_send(push_on, monkeypatch):
    p = make_person()
    make_push_device(p)
    monkeypatch.setattr(push, "queue", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert services.send(p, "S", "B").sent_at


# --- sending ---------------------------------------------------------------------

def test_the_payload_is_the_title_the_subject_and_the_link_only(push_on, sender):
    p = make_person()
    make_push_device(p)
    services.send(p, "Your open shift claim is approved", "SECRET BODY", url="/rota/")
    push.send_pending()
    ((_, payload),) = sender.calls
    assert payload == {"title": "AMG Shift Central", "body": "Your open shift claim is approved", "url": "/rota/"}


def test_a_delivered_push_is_marked_sent_and_the_device_stamped(push_on, sender):
    p = make_person()
    d = make_push_device(p, failures=2)
    services.send(p, "S", "B")
    counts = push.send_pending()
    row, d = pushes().get(), PushDevice.objects.get(pk=d.pk)
    assert row.sent_at and row.error == "" and counts["sent"] == 1
    assert d.last_ok_at and d.failures == 0


def test_one_success_among_several_devices_marks_the_row_sent(push_on, monkeypatch):
    p = make_person()
    good, bad = make_push_device(p), make_push_device(p)
    monkeypatch.setattr(push, "deliver", lambda device, payload: "ok" if device.pk == good.pk else "failed")
    services.send(p, "S", "B")
    push.send_pending()
    assert pushes().get().sent_at and PushDevice.objects.get(pk=bad.pk).failures == 1


def test_a_gone_device_is_deleted_and_a_person_left_with_none_gets_no_retries(push_on, sender):
    sender.answer = "gone"
    p = make_person()
    make_push_device(p)
    services.send(p, "S", "B")
    counts = push.send_pending()
    row = pushes().get()
    assert PushDevice.objects.count() == 0 and row.error == "no device" and row.sent_at is None and counts["gone"] == 1
    assert push.send_pending()["sent"] == 0                    # not tried again


def test_failures_are_retried_each_run_and_given_up_after_the_fifth(push_on, sender):
    sender.answer = "failed"
    p = make_person()
    make_push_device(p)
    services.send(p, "S", "B")
    for attempt in range(1, push.MAX_ATTEMPTS):
        push.send_pending()
        row = pushes().get()
        assert row.attempts == attempt and row.error == "" and row.sent_at is None
    push.send_pending()
    row = pushes().get()
    assert row.attempts == push.MAX_ATTEMPTS and row.error == "push failed"
    calls = len(sender.calls)
    push.send_pending()
    assert len(sender.calls) == calls                           # finished: not tried again


def test_a_push_older_than_a_day_is_dropped_not_sent(push_on, sender, today):
    p = make_person()
    make_push_device(p)
    services.send(p, "Your shift is tomorrow", "B")
    today(date(2026, 11, 4))                                    # the pinned clock was 2 Nov 09:00
    counts = push.send_pending()
    assert pushes().get().error == "expired" and sender.calls == [] and counts["expired"] == 1


def test_a_run_sends_at_most_one_batch_oldest_first(push_on, sender, monkeypatch):
    monkeypatch.setattr(push, "BATCH", 2)
    people = [make_person(first_name=f"P{n}") for n in range(3)]
    for p in people:
        make_push_device(p)
        services.send(p, f"For {p.first_name}", "B")
    push.send_pending()
    assert [r.subject for r in pushes().order_by("queued_at") if r.sent_at] == ["For P0", "For P1"]
    push.send_pending()
    assert pushes().filter(sent_at__isnull=False).count() == 3


# --- deliver (the library call) ----------------------------------------------------

def test_deliver_maps_the_library_outcomes(push_on, monkeypatch):
    import pywebpush
    device = make_push_device(make_person())
    sent = []
    monkeypatch.setattr(pywebpush, "webpush", lambda **kw: sent.append(kw))
    assert push.deliver(device, {"title": "T", "body": "B", "url": "/rota/"}) == "ok"
    kw = sent[0]
    assert kw["subscription_info"] == {"endpoint": device.endpoint, "keys": {"p256dh": device.p256dh, "auth": device.auth}}
    assert kw["timeout"] == 5 and kw["vapid_claims"]["sub"] == "mailto:test@example.org"

    def boom(status):
        def raiser(**kw):
            raise pywebpush.WebPushException("x", response=SimpleNamespace(status_code=status))
        return raiser

    for status, outcome in ((410, "gone"), (404, "gone"), (500, "failed"), (429, "failed")):
        monkeypatch.setattr(pywebpush, "webpush", boom(status))
        assert push.deliver(device, {}) == outcome
    monkeypatch.setattr(pywebpush, "webpush", lambda **kw: (_ for _ in ()).throw(OSError("net")))
    assert push.deliver(device, {}) == "failed"


# --- the command, status and Health -------------------------------------------------

def test_the_command_reports_and_exits_cleanly(push_on, sender):
    p = make_person()
    make_push_device(p)
    services.send(p, "S", "B")
    out = StringIO()
    call_command("send_push", stdout=out)
    assert "1 sent" in out.getvalue()


def test_the_command_says_so_when_push_is_not_configured():
    out = StringIO()
    call_command("send_push", stdout=out)
    assert "not configured" in out.getvalue()


def test_status_counts_devices_the_queue_and_the_last_success(push_on, sender):
    p = make_person()
    make_push_device(p)
    services.send(p, "S", "B")
    assert push.status()["queued"] == 1 and push.status()["devices"] == 1 and push.status()["last_ok"] is None
    push.send_pending()
    st = push.status()
    assert st["queued"] == 0 and st["last_ok"] and st["configured"]


def test_only_all_teams_managers_see_the_push_line_on_the_health_card(push_on):
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    boss = make_person(first_name="Boss", team=team)
    assert b"Phone notifications" not in client_for(lead).get("/staff/").content
    assert b"Phone notifications" in client_for(boss, is_all_teams_manager=True).get("/staff/").content
```

- [ ] **Step 3: Run to verify they fail**

Run: `python -m pytest tests/test_push_delivery.py -q`
Expected: FAIL.

- [ ] **Step 4: The queue and the sender**

Append to `messaging/services/push.py` (add the imports at the top of the file: `from collections import Counter`, `from datetime import timedelta`, `from django.utils import timezone`, and change the model import to `from messaging.models import Outbox, PushDevice`):

```python
EXPIRY = timedelta(hours=24)     # a late "your shift is tomorrow" is worse than none
MAX_ATTEMPTS = 5
BATCH = 200
TIMEOUT = 5


def queue(person, subject, url):
    """Write the push row for a notification, or nothing: push must be
    switched on and the person must have a device. The row carries the
    subject and the page to open, never the message."""
    if not configured() or not person.push_devices.exists():
        return None
    return Outbox.objects.create(to_person=person, channel=Outbox.Channel.PUSH, subject=subject[:200],
                                 body="", url=url or "/rota/")


def deliver(device, payload):
    """One push to one device: "ok", "gone" (the push service says the
    device is no more: delete it) or "failed" (try again later). The only
    function that talks to the network; tests replace it."""
    import json

    from pywebpush import WebPushException, webpush
    try:
        webpush(subscription_info={"endpoint": device.endpoint, "keys": {"p256dh": device.p256dh, "auth": device.auth}},
                data=json.dumps(payload), vapid_private_key=settings.VAPID_PRIVATE_KEY_FILE,
                vapid_claims={"sub": settings.VAPID_SUBJECT}, timeout=TIMEOUT)
    except WebPushException as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        return "gone" if status in (404, 410) else "failed"
    except Exception:  # a network error is a failed push, not a crash
        return "failed"
    return "ok"


def send_pending():
    """Send the queued pushes, oldest first, at most BATCH. Returns counts."""
    counts = Counter()
    now = timezone.now()
    rows = (Outbox.objects.filter(channel=Outbox.Channel.PUSH, sent_at__isnull=True, error="")
            .select_related("to_person").order_by("queued_at", "pk")[:BATCH])
    for row in rows:
        if now - row.queued_at > EXPIRY:
            row.error = "expired"
            row.save(update_fields=["error"])
            counts["expired"] += 1
            continue
        devices = list(row.to_person.push_devices.all()) if row.to_person_id else []
        payload = {"title": "AMG Shift Central", "body": row.subject, "url": row.url}
        delivered = False
        for device in devices:
            outcome = deliver(device, payload)
            if outcome == "ok":
                delivered = True
                device.last_ok_at, device.failures = timezone.now(), 0
                device.save(update_fields=["last_ok_at", "failures"])
            elif outcome == "gone":
                device.delete()
                counts["gone"] += 1
            else:
                device.failures += 1
                device.save(update_fields=["failures"])
        if delivered:
            row.sent_at = timezone.now()
            row.save(update_fields=["sent_at"])
            counts["sent"] += 1
            continue
        row.attempts += 1
        if not row.to_person_id or not row.to_person.push_devices.exists():
            row.error = "no device"
            counts["no_device"] += 1
        elif row.attempts >= MAX_ATTEMPTS:
            row.error = "push failed"
            counts["failed"] += 1
        row.save(update_fields=["attempts", "error"])
    return counts


def status():
    """For the Health card and the dashboard."""
    last = (Outbox.objects.filter(channel=Outbox.Channel.PUSH, sent_at__isnull=False)
            .order_by("-sent_at").values_list("sent_at", flat=True).first())
    return {"configured": configured(), "devices": PushDevice.objects.count(), "last_ok": last,
            "queued": Outbox.objects.filter(channel=Outbox.Channel.PUSH, sent_at__isnull=True, error="").count()}
```

In `messaging/services/__init__.py` rename the existing `send` to `_send_email` (same body, minus `url`), and add after it:

```python
def send(person, subject, body, connection=None, url=None):
    """Send one message by email and, when push is on and the person has a
    phone registered, queue a push for the timer to send. Returns the email's
    Outbox row; its `sent_at` is None when nothing was sent. `url` is the page
    a tap on the push opens (default: the rota)."""
    row = _send_email(person, subject, body, connection)
    try:
        push.queue(person, subject, url)
    except Exception:  # a push must never break the message that caused it
        log.warning("queueing a push failed for person %s", person.pk)
    return row
```

and at the top `from messaging.services import push` placed AFTER the other imports is a circular-import trap; instead write `from . import push` at the bottom of the imports block (`push` imports `messaging.models` only, so there is no cycle). Update the module docstring's last paragraph to describe push instead of "accepted and ignored".

- [ ] **Step 5: The command, units and Health**

`messaging/management/commands/send_push.py`:

```python
"""Send the queued phone notifications. Run every minute by
shift-central-push.timer; exits 0 whatever happened so the timer does not go
red for one bad phone."""

from django.core.management.base import BaseCommand

from messaging.services import push


class Command(BaseCommand):
    help = "Send the queued push notifications"

    def handle(self, *args, **options):
        if not push.configured():
            self.stdout.write("push is not configured; nothing to send")
            return
        c = push.send_pending()
        self.stdout.write(f"{c['sent']} sent, {c['failed']} given up, {c['expired']} expired, "
                          f"{c['gone']} devices removed, {c['no_device']} with no device")
```

`deploy/shift-central-push.service`: copy `deploy/shift-central-daily-flags.service` byte for byte, changing only `Description=Send the queued phone notifications` and `ExecStart=/srv/shift-central/.venv/bin/python manage.py send_push` (and the comment about "A run with nothing due…" to "A run with nothing queued sends nothing and says so in the journal."). `deploy/shift-central-push.timer`:

```ini
[Unit]
Description=Send the queued phone notifications, every minute

[Timer]
OnCalendar=minutely
AccuracySec=10s

[Install]
WantedBy=timers.target
```

`tests/test_deploy_units.py`: rename `test_there_are_eight_services` to `test_there_are_nine_services` and add `"shift-central-push.service"` as the last element of its list (after `"shift-central-pbs.service"`); add:

```python
def test_the_push_service_runs_send_push_every_minute():
    (cmd,) = _directives(DEPLOY / "shift-central-push.service")["ExecStart"]
    assert cmd == "/srv/shift-central/.venv/bin/python manage.py send_push"
    assert "OnCalendar=minutely" in (DEPLOY / "shift-central-push.timer").read_text()
```

`people/services/health.py`: in `figures`, before the final `return`, add `push_status = push.status() if access.is_all_teams(user) else None`, import `from messaging.services import push` inside the function (as the others are) and add `"push": push_status,` to the returned dict. `templates/people/_health.html`: after the GP rota block add

```html
  {% if health.push %}
  <div class="health-item{% if health.push.configured and health.push.queued > 5 %} is-warning{% endif %}">
    Phone notifications
    <strong>{% if not health.push.configured %}not configured{% else %}{{ health.push.devices }} device{{ health.push.devices|pluralize }}, {{ health.push.queued }} queued{% endif %}</strong>
    {% if health.push.last_ok %}<span>last sent {{ health.push.last_ok|date:"j M H:i" }}</span>{% endif %}
  </div>
  {% endif %}
```

- [ ] **Step 6: The leave emails carry a link**

A tap on a push should open the page it is about. `leave/services/notify.py`: give `_send_all` a `url` and pass it to `messaging.send`:

```python
def _send_all(people, subject, body, url=None):
    rows = []
    for p in people:
        try:
            rows.append(messaging.send(p, subject, body, url=url))
        except Exception:   # messaging.send never raises; belt and braces for the booking's sake
            log.exception("leave mail failed")
    return rows
```

and add `url=` to each call in the file, leaving everything else as it is: `request_made`, `cancel_requested` and `reminder` → `"/time-off/approve/"`; `decided`, `cancel_decided` and `converted` → `"/time-off/mine/"`; `cost_to_check`, `negative_balance`, `trigger_reached`, `leaving` and `returned` → `"/staff/"`; `year_end` → `"/time-off/year-end/"`. (`shifts/services/notify.py` already sends through `messaging.send`; its default link, the rota, is right for "your rota has changed".)

Append to `tests/test_push_delivery.py`:

```python
def test_a_leave_decision_opens_my_leave(push_on):
    from leave.services import notify as leave_notify
    from tests.factories import make_booking
    p = make_person()
    make_push_device(p)
    leave_notify.decided(make_booking(p, date(2026, 11, 9)))
    assert pushes().get().url == "/time-off/mine/"
```

- [ ] **Step 7: Run the tests**

Run: `python -m pytest tests/test_push_delivery.py tests/test_push_devices.py tests/test_messaging.py tests/test_messaging_groundwork.py tests/test_deploy_units.py tests/test_staff_page.py tests/test_leave_notify.py tests/test_shifts_notify.py -q`
Expected: PASS (the last two prove existing mail still works through the renamed sender).

- [ ] **Step 8: Commit**

```bash
git add messaging leave people templates deploy requirements.txt tests
git commit -m "Messaging: push delivery (queue beside every email, one-minute timer, retries, expiry, Health line)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---
### Task 9: Messages: send, inbox, sent, and the grid's "Message [name]"

**Files:**
- Create: `messaging/services/messages.py`, `messaging/forms.py`, `messaging/views/messages.py`, `templates/messaging/inbox.html`, `message.html`, `send_dialog.html`, `sent.html`, `messaging/migrations/0004_messages.py` (generated), `tests/test_inbox.py`
- Modify: `messaging/models.py`, `messaging/admin.py`, `messaging/urls.py`, `ui/context_processors.py`, `templates/ui/_sidebar.html`, `static/css/components.css`, `static/img/icons.svg`, `frontend/src/rota-grid/menu-items.ts` (and the rebuilt `static/dist/`), `tests/test_shell.py`

**Interfaces:**
- Consumes: `messaging.services.send/batch/absolute_link` (Tasks 1, 8).
- Produces: models `Message(sender, subject, body, everyone, teams, created_at)` and `MessageRecipient(message [related_name recipients], person [related_name message_receipts], read_at)`; `messaging.services.messages`: `MessageError`, `send(user, subject, body, person_ids=(), team_ids=(), everyone=False, base_url="") -> Message`, `inbox(user) -> QuerySet[MessageRecipient]`, `unread_count(user) -> int`, `open_message(user, pk) -> (Message, MessageRecipient | None)` (Http404 unless recipient, sender or all-teams manager; marks read for a recipient), `sent(user) -> QuerySet[Message]`; URLs `messages-inbox`, `message`, `message-new` (dialog), `messages-sent`; nav item "Messages" with an unread badge; `ui.context_processors._items(request, role, badges)` where `badges` is `{"messages": int, "outbox": int}` and every item carries `"badge"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_inbox.py`:

```python
"""Messages from managers to staff (spec 5, section 5)."""

from datetime import date
from types import SimpleNamespace

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.http import Http404

from messaging.models import Message, MessageRecipient, Outbox
from messaging.services import messages as svc
from messaging.services.messages import MessageError
from people.models import AuditEntry
from tests.factories import client_for, make_person, make_push_device, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_team_manager(lead, reception)
    people = SimpleNamespace(reception=reception, nursing=nursing, lead=lead,
                             sam=make_person(first_name="Sam", team=reception),
                             ann=make_person(first_name="Ann", team=reception),
                             nina=make_person(first_name="Nina", team=nursing),
                             boss=make_person(first_name="Boss", team=reception))
    for p in (lead, people.sam, people.ann, people.nina):
        make_user_for(p)
    make_user_for(people.boss, is_all_teams_manager=True)
    return people


def test_a_manager_sends_to_named_people_and_each_gets_an_email_and_a_receipt(cast):
    m = svc.send(cast.lead.user, "Fire drill", "Thursday at 10.", person_ids=[cast.sam.pk, cast.nina.pk])
    assert sorted(MessageRecipient.objects.filter(message=m).values_list("person__first_name", flat=True)) == ["Nina", "Sam"]
    assert len(mail.outbox) == 2 and mail.outbox[0].subject == "Fire drill"
    assert "Lead Patel wrote:" in mail.outbox[0].body and "Thursday at 10." in mail.outbox[0].body and f"/messages/{m.pk}/" in mail.outbox[0].body


def test_a_team_and_everyone_resolve_to_current_people_without_the_sender(cast):
    left = make_person(first_name="Gone", team=cast.reception, end_date=date(2026, 10, 1))
    make_user_for(left)
    m = svc.send(cast.lead.user, "Hello", "Team", team_ids=[cast.reception.pk])
    assert {r.person.first_name for r in m.recipients.all()} == {"Sam", "Ann", "Boss"}      # not Lead (the sender), not Gone
    m2 = svc.send(cast.lead.user, "Everyone", "All", everyone=True)
    assert {r.person.first_name for r in m2.recipients.all()} == {"Sam", "Ann", "Boss", "Nina"}
    assert m2.everyone and m.teams.get() == cast.reception


def test_recipients_are_a_snapshot(cast):
    m = svc.send(cast.lead.user, "S", "B", team_ids=[cast.reception.pk])
    cast.ann.team = cast.nursing
    cast.ann.save()
    assert cast.ann.pk in m.recipients.values_list("person_id", flat=True)


def test_send_is_for_managers_and_needs_text_and_an_audience(cast):
    with pytest.raises(PermissionDenied):
        svc.send(cast.sam.user, "S", "B", person_ids=[cast.ann.pk])
    for kw, text in (({"subject": "", "body": "B"}, "subject"), ({"subject": "S", "body": "  "}, "subject and some text"),
                     ({"subject": "S" * 151, "body": "B"}, "too long"), ({"subject": "S", "body": "B" * 5001}, "too long")):
        with pytest.raises(MessageError, match=text):
            svc.send(cast.lead.user, person_ids=[cast.sam.pk], **kw)
    with pytest.raises(MessageError, match="Choose who"):
        svc.send(cast.lead.user, "S", "B")
    with pytest.raises(MessageError, match="Nobody"):
        svc.send(cast.lead.user, "S", "B", person_ids=[cast.lead.pk])        # only the sender
    assert Message.objects.count() == 0


def test_the_send_is_audited_and_queues_a_push_with_the_subject_only(cast, push_on):
    make_push_device(cast.sam)
    m = svc.send(cast.lead.user, "Fire drill", "Private details", person_ids=[cast.sam.pk])
    assert AuditEntry.objects.filter(model="messaging.message", object_id=m.pk, field="sent").exists()
    push = Outbox.objects.get(channel="push")
    assert push.subject == "Fire drill" and push.body == "" and push.url == f"/messages/{m.pk}/"


def test_the_inbox_and_the_unread_count(cast):
    m = svc.send(cast.lead.user, "One", "B", person_ids=[cast.sam.pk])
    svc.send(cast.lead.user, "Two", "B", person_ids=[cast.sam.pk])
    assert svc.unread_count(cast.sam.user) == 2 and svc.unread_count(cast.ann.user) == 0
    assert [r.message.subject for r in svc.inbox(cast.sam.user)] == ["Two", "One"]
    svc.open_message(cast.sam.user, m.pk)
    assert svc.unread_count(cast.sam.user) == 1


def test_opening_a_message_marks_it_read_for_the_recipient_only(cast):
    m = svc.send(cast.lead.user, "S", "B", person_ids=[cast.sam.pk])
    svc.open_message(cast.lead.user, m.pk)                       # the sender may read it, unmarked
    assert MessageRecipient.objects.get(message=m).read_at is None
    svc.open_message(cast.sam.user, m.pk)
    assert MessageRecipient.objects.get(message=m).read_at


def test_a_stranger_gets_a_404_but_an_all_teams_manager_may_read_anything(cast):
    m = svc.send(cast.lead.user, "S", "B", person_ids=[cast.sam.pk])
    with pytest.raises(Http404):
        svc.open_message(cast.ann.user, m.pk)
    assert svc.open_message(cast.boss.user, m.pk)[0] == m
    with pytest.raises(Http404):
        svc.open_message(cast.sam.user, 9999)


def test_sent_lists_your_own_and_an_all_teams_manager_sees_all(cast):
    mine = svc.send(cast.lead.user, "Mine", "B", person_ids=[cast.sam.pk])
    theirs = svc.send(cast.boss.user, "Theirs", "B", person_ids=[cast.sam.pk])
    assert list(svc.sent(cast.lead.user)) == [mine]
    assert set(svc.sent(cast.boss.user)) == {mine, theirs}


# --- pages -----------------------------------------------------------------------

def test_the_pages(cast):
    m = svc.send(cast.lead.user, "Fire drill", "Line one\n<b>not bold</b>", person_ids=[cast.sam.pk])
    sam, lead = client_for(cast.sam), client_for(cast.lead)
    body = sam.get("/messages/").content.decode()
    assert "Fire drill" in body and 'data-nav="messages"' in body and 'class="nav-badge"' in body
    page = sam.get(f"/messages/{m.pk}/").content.decode()
    assert "Line one" in page and "&lt;b&gt;not bold&lt;/b&gt;" in page and "<b>not bold</b>" not in page
    assert 'class="nav-badge"' not in sam.get("/messages/").content.decode()          # read now
    assert sam.get("/messages/sent/").status_code == 403 and sam.get("/messages/new/").status_code == 403
    assert client_for(cast.ann).get(f"/messages/{m.pk}/").status_code == 404
    sent = lead.get("/messages/sent/").content.decode()
    assert "Fire drill" in sent and "Sam Patel" in sent and "Read" in sent


def test_the_send_dialog_sends_and_says_how_many(cast):
    lead = client_for(cast.lead)
    form = lead.get(f"/messages/new/?person={cast.sam.pk}").content.decode()
    assert f'value="{cast.sam.pk}" selected' in form
    r = lead.post("/messages/new/", {"subject": "Hi", "body": "There", "people": [cast.sam.pk, cast.ann.pk]})
    assert r.status_code == 200 and b"Sent to 2 people" in r.content
    assert Message.objects.get().subject == "Hi"


def test_the_send_dialog_shows_a_problem_in_the_form(cast):
    r = client_for(cast.lead).post("/messages/new/", {"subject": "Hi", "body": "There"})
    assert r.status_code == 200 and b"Choose who" in r.content and Message.objects.count() == 0


def test_the_nav_offers_staff_the_inbox_and_managers_send_and_sent(cast):
    staff = client_for(cast.sam).get("/rota/").content.decode()
    assert 'href="/messages/"' in staff and "/messages/sent/" not in staff
    manager = client_for(cast.lead).get("/rota/").content.decode()
    assert "/messages/sent/" in manager and "/messages/new/" in manager
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_inbox.py -q`
Expected: FAIL.

- [ ] **Step 3: Models**

`messaging/models.py`, append:

```python
class Message(models.Model):
    """A message from a manager (spec 5). One row per message; who it went to
    is MessageRecipient, written when it is sent."""
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    subject = models.CharField(max_length=150)
    body = models.TextField()
    everyone = models.BooleanField(default=False)
    teams = models.ManyToManyField("people.Team", blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]

    def __str__(self):
        return self.subject


class MessageRecipient(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="recipients")
    person = models.ForeignKey("people.Person", on_delete=models.CASCADE, related_name="message_receipts")
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["message", "person"], name="one_receipt_per_person")]
        indexes = [models.Index(fields=["person", "read_at"])]
```

Add `from django.conf import settings` to the file's imports. Register both read-only in `messaging/admin.py`. Then `DEBUG=1 python manage.py makemigrations messaging -n messages`.

- [ ] **Step 4: The service**

`messaging/services/messages.py`:

```python
"""Messages from managers to staff (spec 5, section 5): any manager may send
to people, teams or everyone; staff read and cannot reply. The email carries
the full text, the push only the subject."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from messaging import services as mail
from messaging.models import Message, MessageRecipient
from people.models import Person, Team
from people.services import access, audit

SUBJECT_MAX, BODY_MAX = 150, 5000


class MessageError(Exception):
    """A problem the sender can fix; `.message` is the sentence to show."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _recipients(sender, person_ids, team_ids, everyone):
    people = Person.objects.current()
    if everyone:
        chosen = people
    else:
        if not person_ids and not team_ids:
            raise MessageError("Choose who the message is for.")
        chosen = people.filter(Q(pk__in=list(person_ids)) | Q(team_id__in=list(team_ids)))
    me = getattr(sender, "person", None)
    if me is not None:
        chosen = chosen.exclude(pk=me.pk)
    out = list(chosen.distinct())
    if not out:
        raise MessageError("Nobody to send that to.")
    return out


def send(user, subject, body, person_ids=(), team_ids=(), everyone=False, base_url=""):
    if not access.is_manager(user):
        raise PermissionDenied("only managers send messages")
    subject, body = (subject or "").strip(), (body or "").strip()
    if not subject or not body:
        raise MessageError("A message needs a subject and some text.")
    if len(subject) > SUBJECT_MAX or len(body) > BODY_MAX:
        raise MessageError(f"That is too long: the subject is at most {SUBJECT_MAX} characters and the text {BODY_MAX}.")
    people = _recipients(user, person_ids, team_ids, everyone)
    with transaction.atomic():
        message = Message.objects.create(sender=user, subject=subject, body=body, everyone=bool(everyone))
        if not everyone:
            message.teams.set(Team.objects.filter(pk__in=list(team_ids)))
        MessageRecipient.objects.bulk_create([MessageRecipient(message=message, person=p) for p in people])
        audit.record(user, message, {"sent": ("", f"to {len(people)} people: {subject[:80]}")}, note="message")
    transaction.on_commit(lambda: _deliver(message, people, base_url))
    return message


def _deliver(message, people, base_url):
    sender = getattr(message.sender, "person", None) if message.sender_id else None
    path = f"/messages/{message.pk}/"
    text = f"{sender.name if sender else 'A manager'} wrote:\n\n{message.body}\n\n{mail.absolute_link(base_url, path)}\n"
    with mail.batch() as connection:
        for person in people:
            mail.send(person, message.subject, text, connection=connection, url=path)


def inbox(user):
    me = getattr(user, "person", None)
    if me is None:
        return MessageRecipient.objects.none()
    return (MessageRecipient.objects.filter(person=me).select_related("message__sender__person")
            .order_by("-message__created_at", "-message_id"))


def unread_count(user):
    if not getattr(user, "is_authenticated", False):
        return 0
    return inbox(user).filter(read_at__isnull=True).count()


def open_message(user, pk):
    message = Message.objects.select_related("sender__person").filter(pk=pk).first()
    me = getattr(user, "person", None)
    receipt = MessageRecipient.objects.filter(message_id=pk, person=me).first() if me is not None else None
    if message is None or not (receipt or message.sender_id == user.pk or access.is_all_teams(user)):
        raise Http404
    if receipt is not None and receipt.read_at is None:
        receipt.read_at = timezone.now()
        receipt.save(update_fields=["read_at"])
    return message, receipt


def sent(user):
    rows = Message.objects.select_related("sender__person").prefetch_related("recipients__person")
    return rows if access.is_all_teams(user) else rows.filter(sender=user)
```

- [ ] **Step 5: Form, views, URLs, templates**

`messaging/forms.py`:

```python
from django import forms

from people.models import Person, Team


class MessageForm(forms.Form):
    subject = forms.CharField(max_length=150)
    body = forms.CharField(max_length=5000, widget=forms.Textarea(attrs={"rows": 6}), label="Message")
    people = forms.ModelMultipleChoiceField(Person.objects.none(), required=False, label="People",
                                            widget=forms.SelectMultiple(attrs={"size": 8}))
    teams = forms.ModelMultipleChoiceField(Team.objects.filter(active=True), required=False,
                                           widget=forms.CheckboxSelectMultiple)
    everyone = forms.BooleanField(required=False, label="Everyone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["people"].queryset = Person.objects.current().order_by("name")
```

`messaging/views/messages.py`:

```python
"""Messages: inbox, one message, send, sent (spec 5, section 5)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from messaging.forms import MessageForm
from messaging.services import messages as svc
from people.services import access


@login_required
def inbox(request):
    return render(request, "messaging/inbox.html", {"page_title": "Messages", "rows": svc.inbox(request.user)})


@login_required
def detail(request, pk):
    message, receipt = svc.open_message(request.user, pk)
    return render(request, "messaging/message.html", {"page_title": "Message", "message": message, "receipt": receipt})


@login_required
@access.manager_required
def new(request):
    initial = {}
    person = request.GET.get("person", "")
    if person.isascii() and person.isdigit():
        initial["people"] = [int(person)]
    form = MessageForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            message = svc.send(request.user, d["subject"], d["body"], [p.pk for p in d["people"]],
                               [t.pk for t in d["teams"]], d["everyone"], base_url=request.build_absolute_uri("/"))
            return render(request, "messaging/send_dialog.html", {"form": None, "sent_to": message.recipients.count()})
        except svc.MessageError as e:
            form.add_error(None, e.message)
    return render(request, "messaging/send_dialog.html", {"form": form, "sent_to": None})


@login_required
@access.manager_required
def sent(request):
    return render(request, "messaging/sent.html", {"page_title": "Sent messages", "rows": svc.sent(request.user)})
```

`messaging/urls.py`: import `messages` (`from messaging.views import app, messages, push`) and add

```python
    path("messages/", messages.inbox, name="messages-inbox"),
    path("messages/new/", messages.new, name="message-new"),
    path("messages/sent/", messages.sent, name="messages-sent"),
    path("messages/<int:pk>/", messages.detail, name="message"),
```

Templates:

`templates/messaging/inbox.html`:

```html
{% extends "base.html" %}
{% block title %}Messages · AMG Shift Central{% endblock %}
{% block content %}
<table class="table">
  <thead><tr><th>From</th><th>Subject</th><th>Sent</th></tr></thead>
  <tbody>
  {% for r in rows %}
    <tr{% if not r.read_at %} class="is-unread"{% endif %}><td>{{ r.message.sender.person.name|default:"A manager" }}</td>
        <td><a href="{% url 'message' r.message.pk %}">{% if not r.read_at %}<strong>{{ r.message.subject }}</strong>{% else %}{{ r.message.subject }}{% endif %}</a></td>
        <td>{{ r.message.created_at|date:"j M Y H:i" }}</td></tr>
  {% empty %}<tr><td colspan="3">No messages.</td></tr>{% endfor %}
  </tbody>
</table>
{% endblock %}
```

`templates/messaging/message.html`:

```html
{% extends "base.html" %}
{% block title %}{{ message.subject }} · AMG Shift Central{% endblock %}
{% block content %}
<article class="message">
  <h2>{{ message.subject }}</h2>
  <p class="muted">From {{ message.sender.person.name|default:"a manager" }} · {{ message.created_at|date:"l j F Y H:i" }}</p>
  <div class="message-body">{{ message.body|linebreaks }}</div>
</article>
<p><a href="{% url 'messages-inbox' %}">Back to messages</a></p>
{% endblock %}
```

`templates/messaging/sent.html`:

```html
{% extends "base.html" %}
{% block title %}Sent messages · AMG Shift Central{% endblock %}
{% block topbar_actions %}<a class="topbar-action is-primary" href="{% url 'message-new' %}" data-dialog>Send a message +</a>{% endblock %}
{% block content %}
<table class="table">
  <thead><tr><th>Subject</th><th>From</th><th>Sent</th><th>To</th><th>Read</th></tr></thead>
  <tbody>
  {% for m in rows %}
    <tr><td><a href="{% url 'message' m.pk %}">{{ m.subject }}</a></td><td>{{ m.sender.person.name|default:"—" }}</td><td>{{ m.created_at|date:"j M Y H:i" }}</td>
        <td>{% for r in m.recipients.all %}{{ r.person.name }}{% if not forloop.last %}, {% endif %}{% endfor %}</td>
        <td>{% for r in m.recipients.all %}{% if r.read_at %}{{ r.person.first_name }}{% if not forloop.last %}, {% endif %}{% endif %}{% endfor %}</td></tr>
  {% empty %}<tr><td colspan="5">Nothing sent.</td></tr>{% endfor %}
  </tbody>
</table>
{% endblock %}
```

(The "Read" column's test expects the word "Read" in the header ✓.)

`templates/messaging/send_dialog.html`:

```html
{% extends "ui/_dialog.html" %}
{% block dialog_title %}Send a message{% endblock %}
{% block dialog_body %}
{% if sent_to is not None %}
  <p class="flash">Sent to {{ sent_to }} {{ sent_to|pluralize:"person,people" }}.</p>
  <button type="button" class="btn btn-quiet" data-dialog-close>Close</button>
{% else %}
<form method="post" action="{% url 'message-new' %}" data-dialog-form>
  {% csrf_token %}
  {% for e in form.non_field_errors %}<p class="flash flash-error">{{ e }}</p>{% endfor %}
  {% include "ui/_field.html" with field=form.subject %}
  {% include "ui/_field.html" with field=form.body %}
  {% include "ui/_field.html" with field=form.people %}
  {% include "ui/_field.html" with field=form.teams %}
  <div class="field"><label>{{ form.everyone }} {{ form.everyone.label }}</label></div>
  <p class="field-help">Everyone chosen gets the message by email, and by notification if they have turned it on.</p>
  <button class="btn btn-dark">Send</button>
</form>
{% endif %}
{% endblock %}
```

Note the template line `Sent to {{ sent_to }} {{ sent_to|pluralize:"person,people" }}` renders "Sent to 2 people." ✓ ("1 person").

The dialog test for the preselected person looks for `value="<pk>" selected`: Django renders `<option value="5" selected>`; fix the test to the single form `f'value="{cast.sam.pk}" selected'` (remove the `or`). **Apply that now when you create the test:** use only `assert f'value="{cast.sam.pk}" selected' in form`.

- [ ] **Step 6: Nav, badge, icon**

`static/img/icons.svg`: add

```xml
<symbol id="mail" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></symbol>
```

`templates/ui/_sidebar.html`: inside `.nav-link`, after the `<span class="nav-label">…</span>`, add `{% if item.badge %}<span class="nav-badge" aria-label="{{ item.badge }} unread">{{ item.badge }}</span>{% endif %}`.

`static/css/components.css`: `.nav-badge { margin-left: auto; min-width: 1.4em; padding: 0 6px; border-radius: 999px; background: var(--amber); color: var(--amber-ink); font-size: var(--fs-xs); text-align: center; }`

`ui/context_processors.py`: change the signature to `def _items(request, role, badges)`; wrap each appended/inserted item with a badge by post-processing at the end of `_items`:

```python
    for item in items:
        item["badge"] = badges.get(item["key"], 0)
    return items
```

add the Messages item (for everyone) before Reports:

```python
    message_children = [{"label": "Inbox", "url": "/messages/"}]
    if role != "staff":
        message_children += [{"label": "Send a message…", "url": "/messages/new/", "dialog": True},
                             {"label": "Sent messages", "url": "/messages/sent/"}]
    items.append({"key": "messages", "label": "Messages", "icon": "mail", "url": "/messages/",
                  "active": path.startswith("/messages/"), "children": message_children})
```

and in `shell()` compute and pass the badges:

```python
    from messaging.services import messages as message_service
    badges = {"messages": message_service.unread_count(user) if user is not None else 0, "outbox": 0}
    ...
        "nav_items": _items(request, role, badges) if user is not None and user.is_authenticated else [],
```

`tests/test_shell.py`: in `test_all_teams_managers_see_everything_in_this_release` add `"messages"` to the positive tuple and delete the `for later in ("messages",)` loop.

- [ ] **Step 7: The grid's "Message [name]" item**

`frontend/src/rota-grid/menu-items.ts`: replace the last item with

```ts
    { label: `Message ${first}`.trim(), href: `/messages/new/?person=${p}` },
```

```bash
cd frontend && npm ci && npm run check && npm test && npm run build && cd ..
git status --short static/dist
```

Expected: `static/dist/main.js` changed (and nothing else new). If an existing vitest test asserts the old disabled item, update it to the new label and `href`.

- [ ] **Step 8: Run the tests**

Run: `python -m pytest tests/test_inbox.py tests/test_shell.py tests/test_frontend_build.py tests/test_shifts_views.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add messaging ui templates static frontend tests
git commit -m "Messaging: messages from managers (send, inbox, sent), the unread badge and the grid's Message item

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---

### Task 10: The notice board

**Files:**
- Create: `messaging/services/notices.py`, `messaging/views/notices.py`, `templates/messaging/notices.html`, `notice_dialog.html`, `tests/test_notices.py`
- Modify: `messaging/models.py`, `messaging/admin.py`, `messaging/forms.py`, `messaging/urls.py`, `ui/context_processors.py`, `static/img/icons.svg`, `messaging/migrations/0005_notices.py` (generated)

**Interfaces:**
- Produces: `messaging.models.Notice(title, body, everyone, teams, pinned, show_until, posted_by, created_at, updated_at)`; `messaging.services.notices`: `NoticeError`, `post(user, title, body, everyone, team_ids, pinned=False, show_until=None, notify=False, base_url="") -> Notice`, `edit(user, notice, …same fields…) -> Notice`, `remove(user, notice)`, `visible_to(user) -> QuerySet[Notice]`, `editable(user) -> QuerySet[Notice]`; URLs `notices`, `notice-new` (dialog), `notice-edit` (`/notices/<pk>/edit/`, dialog), `notice-remove` (`/notices/<pk>/remove/`, POST); a "Notice board" nav item.

- [ ] **Step 1: Write the failing tests**

`tests/test_notices.py`:

```python
"""The notice board (spec 5, section 5)."""

from datetime import date
from types import SimpleNamespace

import pytest
from django.core.exceptions import PermissionDenied

from messaging.models import Notice, Outbox
from messaging.services import notices
from messaging.services.notices import NoticeError
from people.models import AuditEntry
from tests.factories import client_for, make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_team_manager(lead, reception)
    c = SimpleNamespace(reception=reception, nursing=nursing, lead=lead, sam=make_person(first_name="Sam", team=reception),
                        nina=make_person(first_name="Nina", team=nursing), boss=make_person(first_name="Boss", team=reception))
    for p in (lead, c.sam, c.nina):
        make_user_for(p)
    make_user_for(c.boss, is_all_teams_manager=True)
    return c


def test_a_manager_posts_and_it_is_audited(cast):
    n = notices.post(cast.lead.user, "Fire drill", "Thursday", True, [], pinned=True, show_until=date(2026, 12, 1))
    assert n.title == "Fire drill" and n.pinned and n.everyone and n.posted_by == cast.lead.user
    assert AuditEntry.objects.filter(model="messaging.notice", object_id=n.pk, field="posted").exists()
    assert Outbox.objects.count() == 0                                # posting tells nobody by itself


def test_only_managers_post_and_the_text_is_checked(cast):
    with pytest.raises(PermissionDenied):
        notices.post(cast.sam.user, "T", "B", True, [])
    for title, body, text in (("", "B", "title"), ("T", "", "text"), ("T" * 121, "B", "too long"), ("T", "B" * 5001, "too long")):
        with pytest.raises(NoticeError, match=text):
            notices.post(cast.lead.user, title, body, True, [])
    with pytest.raises(NoticeError, match="Choose"):
        notices.post(cast.lead.user, "T", "B", False, [])


def test_visibility_by_team_everyone_and_show_until(cast, today):
    notices.post(cast.lead.user, "All", "B", True, [])
    notices.post(cast.lead.user, "Reception", "B", False, [cast.reception.pk])
    notices.post(cast.lead.user, "Old", "B", True, [], show_until=date(2026, 11, 3))
    seen = lambda p: [n.title for n in notices.visible_to(p.user)]        # noqa: E731
    assert set(seen(cast.sam)) == {"All", "Reception", "Old"} and set(seen(cast.nina)) == {"All", "Old"}
    today(date(2026, 11, 4))
    assert set(seen(cast.sam)) == {"All", "Reception"}


def test_pinned_first_then_newest(cast):
    notices.post(cast.lead.user, "Older", "B", True, [])
    notices.post(cast.lead.user, "Pinned", "B", True, [], pinned=True)
    notices.post(cast.lead.user, "Newest", "B", True, [])
    assert [n.title for n in notices.visible_to(cast.sam.user)] == ["Pinned", "Newest", "Older"]


def test_the_poster_and_an_all_teams_manager_edit_and_remove(cast):
    n = notices.post(cast.lead.user, "Fire drill", "Thursday", True, [])
    notices.edit(cast.lead.user, n, "Fire drill (moved)", "Friday", True, [])
    n.refresh_from_db()
    assert n.title == "Fire drill (moved)" and n.body == "Friday"
    notices.edit(cast.boss.user, n, "Boss edit", "Friday", True, [])
    other = make_person(first_name="Other", team=cast.reception)
    make_team_manager(other, cast.reception)
    make_user_for(other)
    with pytest.raises(PermissionDenied):
        notices.edit(other.user, n, "x", "y", True, [])
    with pytest.raises(PermissionDenied):
        notices.remove(other.user, n)
    notices.remove(cast.boss.user, n)
    assert Notice.objects.count() == 0
    assert AuditEntry.objects.filter(model="messaging.notice", field="removed").exists()


def test_editable_is_your_own_notices_or_all_of_them_for_an_all_teams_manager(cast):
    mine = notices.post(cast.lead.user, "Mine", "B", True, [])
    boss_one = notices.post(cast.boss.user, "Boss's", "B", True, [])
    assert list(notices.editable(cast.lead.user)) == [mine]
    assert set(notices.editable(cast.boss.user)) == {mine, boss_one}
    assert notices.editable(cast.sam.user).count() == 0


def test_ticking_notify_sends_the_title_once_to_the_audience(cast):
    notices.post(cast.lead.user, "Fire drill", "Private details", False, [cast.reception.pk], notify=True)
    subjects = list(Outbox.objects.filter(channel="email").values_list("to_person__first_name", "subject"))
    assert sorted(subjects) == [("Boss", "Fire drill"), ("Sam", "Fire drill")]      # not the poster; not Nursing
    assert all("Private details" not in b for b in Outbox.objects.values_list("body", flat=True))


def test_the_board_shows_plain_text_only(cast):
    notices.post(cast.lead.user, "<script>alert(1)</script>", "Line one\n<b>two</b>", True, [])
    body = client_for(cast.sam).get("/notices/").content.decode()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body and "<script>alert(1)" not in body
    assert "&lt;b&gt;two&lt;/b&gt;" in body


def test_pages_and_dialogs(cast):
    sam, lead, nina = client_for(cast.sam), client_for(cast.lead), client_for(cast.nina)
    assert sam.get("/notices/").status_code == 200 and "Post a notice" not in sam.get("/notices/").content.decode()
    assert "Post a notice" in lead.get("/notices/").content.decode()
    assert sam.get("/notices/new/").status_code == 403
    r = lead.post("/notices/new/", {"title": "Bins", "body": "Tuesday", "everyone": "on", "pinned": "on"})
    assert r.status_code == 200 and r.json() == {"refresh": True}
    n = Notice.objects.get()
    assert n.pinned and n.everyone
    assert lead.get(f"/notices/{n.pk}/edit/").status_code == 200
    assert sam.get(f"/notices/{n.pk}/edit/").status_code == 404
    assert nina.post(f"/notices/{n.pk}/remove/").status_code == 404
    assert lead.post(f"/notices/{n.pk}/remove/").status_code == 302
    assert Notice.objects.count() == 0


def test_a_bad_notice_shows_the_error(cast):
    r = client_for(cast.lead).post("/notices/new/", {"title": "", "body": "x", "everyone": "on"})
    assert r.status_code == 200 and b"required" in r.content.lower() and Notice.objects.count() == 0


def test_the_nav_has_the_notice_board_for_everyone(cast):
    assert 'data-nav="notices"' in client_for(cast.sam).get("/rota/").content.decode()


def test_show_until_defaults_to_forever(cast):
    n = notices.post(cast.lead.user, "T", "B", True, [])
    assert n.show_until is None
    assert notices.visible_to(cast.sam.user).filter(pk=n.pk).exists()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_notices.py -q`
Expected: FAIL.

- [ ] **Step 3: Model**

`messaging/models.py`, append:

```python
class Notice(models.Model):
    """A notice-board post (spec 5): plain text for everyone or chosen teams."""
    title = models.CharField(max_length=120)
    body = models.TextField()
    everyone = models.BooleanField(default=False)
    teams = models.ManyToManyField("people.Team", blank=True, related_name="+")
    pinned = models.BooleanField(default=False)
    show_until = models.DateField(null=True, blank=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-pinned", "-created_at", "-pk"]

    def __str__(self):
        return self.title
```

Register it read-only in `messaging/admin.py`; `DEBUG=1 python manage.py makemigrations messaging -n notices`.

- [ ] **Step 4: The service**

`messaging/services/notices.py`:

```python
"""The notice board (spec 5, section 5): managers post plain text for
everyone or chosen teams; staff read. Posting tells nobody unless asked."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from messaging import services as mail
from messaging.models import Notice
from people.models import Person, Team
from people.services import access, audit

TITLE_MAX, BODY_MAX = 120, 5000


class NoticeError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _check(title, body, everyone, team_ids):
    title, body = (title or "").strip(), (body or "").strip()
    if not title:
        raise NoticeError("A notice needs a title.")
    if not body:
        raise NoticeError("A notice needs some text.")
    if len(title) > TITLE_MAX or len(body) > BODY_MAX:
        raise NoticeError(f"That is too long: the title is at most {TITLE_MAX} characters and the text {BODY_MAX}.")
    if not everyone and not list(team_ids):
        raise NoticeError("Choose everyone or at least one team.")
    return title, body


def post(user, title, body, everyone, team_ids, pinned=False, show_until=None, notify=False, base_url=""):
    if not access.is_manager(user):
        raise PermissionDenied("only managers post notices")
    title, body = _check(title, body, everyone, team_ids)
    with transaction.atomic():
        notice = Notice.objects.create(title=title, body=body, everyone=bool(everyone), pinned=bool(pinned),
                                       show_until=show_until, posted_by=user)
        if not everyone:
            notice.teams.set(Team.objects.filter(pk__in=list(team_ids)))
        audit.record(user, notice, {"posted": ("", title)}, note="notice")
    if notify:
        transaction.on_commit(lambda: _tell(notice, user, base_url))
    return notice


def _may_change(user, notice):
    if not (access.is_all_teams(user) or (access.is_manager(user) and notice.posted_by_id == user.pk)):
        raise PermissionDenied("not your notice")


def edit(user, notice, title, body, everyone, team_ids, pinned=False, show_until=None):
    _may_change(user, notice)
    title, body = _check(title, body, everyone, team_ids)
    with transaction.atomic():
        notice.title, notice.body, notice.everyone, notice.pinned, notice.show_until = title, body, bool(everyone), bool(pinned), show_until
        notice.save()
        notice.teams.set([] if everyone else Team.objects.filter(pk__in=list(team_ids)))
        audit.record(user, notice, {"edited": ("", title)}, note="notice")
    return notice


def remove(user, notice):
    _may_change(user, notice)
    with transaction.atomic():
        audit.record(user, notice, {"removed": ("", notice.title)}, note="notice")
        notice.delete()


def visible_to(user):
    """The notices this user's team (or everyone) was given, not past their
    show-until date; pinned first, then newest."""
    me = getattr(user, "person", None)
    audience = Q(everyone=True)
    if me is not None and me.team_id:
        audience |= Q(teams=me.team_id)
    today = timezone.localdate()
    return (Notice.objects.filter(audience).filter(Q(show_until__isnull=True) | Q(show_until__gte=today))
            .distinct().order_by("-pinned", "-created_at", "-pk"))


def editable(user):
    if access.is_all_teams(user):
        return Notice.objects.all()
    if access.is_manager(user):
        return Notice.objects.filter(posted_by=user)
    return Notice.objects.none()


def _tell(notice, poster, base_url):
    people = Person.objects.current().filter(user__isnull=False, user__is_active=True).exclude(user=poster)
    if not notice.everyone:
        people = people.filter(team__in=notice.teams.all())
    text = f"{notice.title}\n\nRead it on the notice board: {mail.absolute_link(base_url, '/notices/')}\n"
    with mail.batch() as connection:
        for person in people:
            mail.send(person, notice.title, text, connection=connection, url="/notices/")
```

- [ ] **Step 5: Form, views, URLs, templates, nav**

`messaging/forms.py`, append:

```python
class NoticeForm(forms.Form):
    title = forms.CharField(max_length=120)
    body = forms.CharField(max_length=5000, widget=forms.Textarea(attrs={"rows": 8}), label="Text")
    everyone = forms.BooleanField(required=False, label="Everyone")
    teams = forms.ModelMultipleChoiceField(Team.objects.filter(active=True), required=False,
                                           widget=forms.CheckboxSelectMultiple, label="Or these teams")
    pinned = forms.BooleanField(required=False, label="Pin to the top")
    show_until = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                                 label="Show until", help_text="Leave empty to keep it up.")
    notify = forms.BooleanField(required=False, label="Also tell staff by email and notification")
```

`messaging/views/notices.py`:

```python
"""The notice board (spec 5, section 5)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from messaging.forms import NoticeForm
from messaging.services import notices as svc
from people.services import access


@login_required
def board(request):
    return render(request, "messaging/notices.html", {
        "page_title": "Notice board", "notices": svc.visible_to(request.user), "is_manager": access.is_manager(request.user),
        "editable": svc.editable(request.user) if access.is_manager(request.user) else []})


def _editable_notice(request, pk):
    return get_object_or_404(svc.editable(request.user), pk=pk)


def _dialog(request, notice=None):
    initial = {}
    if notice is not None:
        initial = {"title": notice.title, "body": notice.body, "everyone": notice.everyone, "teams": notice.teams.all(),
                   "pinned": notice.pinned, "show_until": notice.show_until}
    form = NoticeForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        team_ids = [t.pk for t in d["teams"]]
        try:
            if notice is None:
                svc.post(request.user, d["title"], d["body"], d["everyone"], team_ids, d["pinned"], d["show_until"],
                         d["notify"], base_url=request.build_absolute_uri("/"))
            else:
                svc.edit(request.user, notice, d["title"], d["body"], d["everyone"], team_ids, d["pinned"], d["show_until"])
            return JsonResponse({"refresh": True})
        except svc.NoticeError as e:
            form.add_error(None, e.message)
    return render(request, "messaging/notice_dialog.html", {"form": form, "notice": notice})


@login_required
@access.manager_required
def new(request):
    return _dialog(request)


@login_required
def edit(request, pk):
    if not access.is_manager(request.user):
        raise Http404
    return _dialog(request, _editable_notice(request, pk))


@login_required
@require_POST
def remove(request, pk):
    notice = _editable_notice(request, pk)
    try:
        svc.remove(request.user, notice)
        messages.success(request, "The notice is removed.")
    except PermissionDenied:
        raise Http404 from None
    return redirect("notices")
```


`messaging/urls.py`: import `notices` and add

```python
    path("notices/", notices.board, name="notices"),
    path("notices/new/", notices.new, name="notice-new"),
    path("notices/<int:pk>/edit/", notices.edit, name="notice-edit"),
    path("notices/<int:pk>/remove/", notices.remove, name="notice-remove"),
```

`templates/messaging/notices.html`:

```html
{% extends "base.html" %}
{% block title %}Notice board · AMG Shift Central{% endblock %}
{% block topbar_actions %}{% if is_manager %}<a class="topbar-action is-primary" href="{% url 'notice-new' %}" data-dialog>Post a notice +</a>{% endif %}{% endblock %}
{% block content %}
<div class="notice-cards">
{% for n in notices %}
  <article class="notice-card{% if n.pinned %} is-pinned{% endif %}">
    <h2>{% if n.pinned %}📌 {% endif %}{{ n.title }}</h2>
    <p class="muted">{{ n.created_at|date:"j M Y" }}{% if n.show_until %} · until {{ n.show_until|date:"j M Y" }}{% endif %}</p>
    <div>{{ n.body|linebreaks }}</div>
  </article>
{% empty %}<p>Nothing on the board.</p>{% endfor %}
</div>
{% if editable %}
<h3>Notices you can edit</h3>
<table class="table"><tbody>
{% for n in editable %}
  <tr><td>{{ n.title }}</td><td>{{ n.created_at|date:"j M Y" }}</td>
      <td><a href="{% url 'notice-edit' n.pk %}" data-dialog>Edit</a></td>
      <td><form method="post" action="{% url 'notice-remove' n.pk %}">{% csrf_token %}<button class="btn btn-quiet">Remove</button></form></td></tr>
{% endfor %}
</tbody></table>
{% endif %}
{% endblock %}
```

`templates/messaging/notice_dialog.html`:

```html
{% extends "ui/_dialog.html" %}
{% block dialog_title %}{% if notice %}Edit notice{% else %}Post a notice{% endif %}{% endblock %}
{% block dialog_body %}
<form method="post" action="{% if notice %}{% url 'notice-edit' notice.pk %}{% else %}{% url 'notice-new' %}{% endif %}" data-dialog-form>
  {% csrf_token %}
  {% for e in form.non_field_errors %}<p class="flash flash-error">{{ e }}</p>{% endfor %}
  {% include "ui/_field.html" with field=form.title %}
  {% include "ui/_field.html" with field=form.body %}
  <div class="field"><label>{{ form.everyone }} {{ form.everyone.label }}</label></div>
  {% include "ui/_field.html" with field=form.teams %}
  <div class="field"><label>{{ form.pinned }} {{ form.pinned.label }}</label></div>
  {% include "ui/_field.html" with field=form.show_until %}
  {% if not notice %}<div class="field"><label>{{ form.notify }} {{ form.notify.label }}</label></div>{% endif %}
  <button class="btn btn-dark">{% if notice %}Save{% else %}Post{% endif %}</button>
</form>
{% endblock %}
```

`static/img/icons.svg` add `<symbol id="notice" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></symbol>`. `ui/context_processors.py`: after the Messages item add `items.append({"key": "notices", "label": "Notice board", "icon": "notice", "url": "/notices/", "active": path.startswith("/notices/"), "children": []})`. CSS: `.notice-cards { display: grid; gap: var(--sp-4); max-width: 46rem; } .notice-card { background: var(--surface); border: 1px solid var(--hairline); border-radius: var(--radius); padding: var(--sp-4); } .notice-card.is-pinned { border-color: var(--navy); }`.

- [ ] **Step 6: Run the tests**

Run: `python -m pytest tests/test_notices.py tests/test_inbox.py tests/test_shell.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add messaging ui templates static tests
git commit -m "Messaging: the notice board (plain-text notices for everyone or chosen teams)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---

### Task 11: Uploads: the shared area and a person's documents

**Files:**
- Create: `uploads/__init__.py`, `uploads/apps.py`, `uploads/models.py`, `uploads/admin.py`, `uploads/forms.py`, `uploads/services.py`, `uploads/views.py`, `uploads/urls.py`, `uploads/migrations/0001_initial.py` (generated), `templates/uploads/list.html`, `templates/uploads/person.html`, `tests/test_uploads.py`
- Modify: `config/settings.py`, `config/urls.py`, `people/views/profile.py`, `templates/people/profile_dialog.html`, `ui/context_processors.py`, `static/img/icons.svg`, `deploy/backup.sh`

**Interfaces:**
- Produces: `uploads.models.UploadedFile(kind, person, title, original_name, stored_name, size, uploaded_by, created_at)` (`Kind.SHARED/PERSON`); `uploads.services`: `UploadError`, `add(user, upload, title, kind, person=None) -> UploadedFile`, `remove(user, uploaded)`, `open_file(user, uploaded) -> FileResponse` (Http404 unless allowed), `shared_files(user)`, `person_files(user, person)` (Http404 unless the user manages the person), `can_manage_person_files(user, person) -> bool`, constants `TYPES`; settings `MEDIA_ROOT`, `UPLOAD_MAX_BYTES`; URLs `uploads` (`/uploads/`), `upload-download` (`/uploads/<pk>/download/`), `upload-delete` (`/uploads/<pk>/delete/`, POST), `person-uploads` (`/staff/<pk>/uploads/`).

- [ ] **Step 1: Write the failing tests**

`tests/test_uploads.py`:

```python
"""Shared documents and a person's documents (spec 5, section 6)."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404

from people.models import AuditEntry
from tests.factories import client_for, make_person, make_team, make_team_manager, make_user_for
from uploads import services
from uploads.models import UploadedFile
from uploads.services import UploadError

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.UPLOAD_MAX_BYTES = 1024 * 1024


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_team_manager(lead, reception)
    c = SimpleNamespace(reception=reception, nursing=nursing, lead=lead, sam=make_person(first_name="Sam", team=reception),
                        nina=make_person(first_name="Nina", team=nursing), boss=make_person(first_name="Boss", team=reception),
                        nurse_lead=make_person(first_name="NurseLead", team=nursing))
    make_team_manager(c.nurse_lead, nursing)
    for p in (lead, c.sam, c.nina, c.nurse_lead):
        make_user_for(p)
    make_user_for(c.boss, is_all_teams_manager=True)
    return c


def up(name="Handbook.pdf", data=PDF):
    return SimpleUploadedFile(name, data)


def add_shared(cast, **kw):
    return services.add(cast.lead.user, up(**kw), "Staff handbook", UploadedFile.Kind.SHARED)


def test_a_manager_adds_a_shared_file_stored_under_a_random_name(cast):
    f = add_shared(cast)
    assert f.kind == "shared" and f.original_name == "Handbook.pdf" and f.size == len(PDF) and f.title == "Staff handbook"
    assert len(f.stored_name) == 36 and f.stored_name.endswith(".pdf") and f.stored_name != "Handbook.pdf"
    path = Path(services.root()) / f.stored_name
    assert path.read_bytes() == PDF and oct(path.stat().st_mode & 0o777) == "0o600"
    assert AuditEntry.objects.filter(model="uploads.sharedfile", object_id=f.pk, field="added").exists()


def test_staff_cannot_add(cast):
    with pytest.raises(Http404):
        services.add(cast.sam.user, up(), "T", UploadedFile.Kind.SHARED)


@pytest.mark.parametrize("name, data, text", [
    ("run.exe", b"MZ\x90", "can't be uploaded"),
    ("page.html", b"<script>", "can't be uploaded"),
    ("notes", b"x", "can't be uploaded"),
    ("fake.pdf", b"<html>not a pdf</html>", "doesn't look like"),
    ("fake.png", PDF, "doesn't look like"),
    ("fake.docx", b"%PDF", "doesn't look like"),
    ("empty.pdf", b"", "empty"),
    ("big.pdf", PDF + b"0" * (1024 * 1024), "too big"),
    ("bin.txt", b"hello\x00world", "doesn't look like"),
])
def test_a_bad_file_is_refused_and_nothing_is_stored(cast, name, data, text):
    Path(services.root()).mkdir(parents=True, exist_ok=True)
    with pytest.raises(UploadError, match=text):
        services.add(cast.lead.user, up(name, data), "T", UploadedFile.Kind.SHARED)
    assert UploadedFile.objects.count() == 0
    assert not list(Path(services.root()).glob("*"))


@pytest.mark.parametrize("name, data", [
    ("pic.PNG", PNG), ("doc.docx", b"PK\x03\x04rest"), ("old.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1x"),
    ("sheet.csv", "a,b\n1,£2\n".encode("cp1252")), ("notes.txt", "héllo".encode("utf-8")), ("photo.jpeg", b"\xff\xd8\xff\xe0abc")])
def test_each_allowed_type_is_accepted(cast, name, data):
    assert services.add(cast.lead.user, up(name, data), "T", UploadedFile.Kind.SHARED).original_name == name


def test_a_hostile_file_name_is_cleaned_for_display(cast):
    f = services.add(cast.lead.user, up("../../etc/pass\nwd.pdf"), "T", UploadedFile.Kind.SHARED)
    assert "/" not in f.original_name and "\n" not in f.original_name and f.original_name.endswith(".pdf")


def test_a_failed_save_leaves_no_file_and_no_row(cast, monkeypatch):
    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(services.os, "replace", boom)
    with pytest.raises(OSError):
        add_shared(cast)
    assert UploadedFile.objects.count() == 0
    assert not list(Path(services.root()).glob("*"))


def test_everyone_downloads_shared_files_as_attachments_only(cast):
    f = add_shared(cast)
    r = client_for(cast.sam).get(f"/uploads/{f.pk}/download/")
    assert r.status_code == 200 and b"".join(r.streaming_content) == PDF
    assert r["Content-Disposition"].startswith("attachment") and "Handbook.pdf" in r["Content-Disposition"]
    assert r["Content-Type"] == "application/pdf" and r["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in r["Cache-Control"]


def test_a_missing_file_on_disk_is_a_404(cast):
    f = add_shared(cast)
    (Path(services.root()) / f.stored_name).unlink()
    assert client_for(cast.sam).get(f"/uploads/{f.pk}/download/").status_code == 404


def test_shared_delete_is_the_uploader_or_an_all_teams_manager(cast):
    other = make_person(first_name="Other", team=cast.reception)
    make_team_manager(other, cast.reception)
    make_user_for(other)
    f = add_shared(cast)
    with pytest.raises(Http404):
        services.remove(other.user, f)
    with pytest.raises(Http404):
        services.remove(cast.sam.user, f)
    services.remove(cast.boss.user, f)
    assert not UploadedFile.objects.exists() and not (Path(services.root()) / f.stored_name).exists()
    g = add_shared(cast)
    services.remove(cast.lead.user, g)
    assert AuditEntry.objects.filter(model="uploads.sharedfile", field="removed").count() == 2


def test_personal_files_are_for_that_persons_managers_only(cast):
    f = services.add(cast.lead.user, up("contract.pdf"), "Contract", UploadedFile.Kind.PERSON, person=cast.sam)
    assert AuditEntry.objects.filter(model="uploads.personfile", object_id=cast.sam.pk, field="added").exists()
    for who, status in ((cast.lead, 200), (cast.boss, 200), (cast.sam, 404), (cast.nurse_lead, 404), (cast.nina, 404)):
        assert client_for(who).get(f"/uploads/{f.pk}/download/").status_code == status, who.first_name
    assert client_for(cast.lead).get(f"/staff/{cast.sam.pk}/uploads/").status_code == 200
    for who in (cast.sam, cast.nurse_lead, cast.nina):
        assert client_for(who).get(f"/staff/{cast.sam.pk}/uploads/").status_code == 404
    assert AuditEntry.objects.filter(model="uploads.personfile", field="downloaded").count() == 2
    with pytest.raises(Http404):
        services.add(cast.nurse_lead.user, up(), "T", UploadedFile.Kind.PERSON, person=cast.sam)


def test_a_manager_cannot_see_their_own_personal_files(cast):
    f = services.add(cast.boss.user, up(), "Mine", UploadedFile.Kind.PERSON, person=cast.lead)
    assert client_for(cast.lead).get(f"/uploads/{f.pk}/download/").status_code == 404


def test_the_pages(cast):
    add_shared(cast)
    sam, lead = client_for(cast.sam), client_for(cast.lead)
    page = sam.get("/uploads/").content.decode()
    assert "Staff handbook" in page and "Handbook.pdf" in page and "Add a document" not in page
    assert "Add a document" in lead.get("/uploads/").content.decode()
    r = lead.post("/uploads/", {"title": "Rota policy", "file": up("policy.pdf")})
    assert r.status_code == 302 and UploadedFile.objects.filter(title="Rota policy").exists()
    bad = lead.post("/uploads/", {"title": "Bad", "file": up("x.exe", b"MZ")})
    assert bad.status_code == 200 and b"be uploaded" in bad.content and not UploadedFile.objects.filter(title="Bad").exists()
    assert sam.post("/uploads/", {"title": "Nope", "file": up()}).status_code == 403


def test_the_person_page_uploads_and_deletes(cast):
    lead = client_for(cast.lead)
    r = lead.post(f"/staff/{cast.sam.pk}/uploads/", {"title": "Contract", "file": up("c.pdf")})
    assert r.status_code == 302
    f = UploadedFile.objects.get()
    assert f.kind == "person" and f.person == cast.sam
    assert "Contract" in lead.get(f"/staff/{cast.sam.pk}/uploads/").content.decode()
    assert lead.post(f"/uploads/{f.pk}/delete/").status_code == 302
    assert UploadedFile.objects.count() == 0


def test_the_profile_window_links_to_a_persons_documents_for_managers(cast):
    body = client_for(cast.lead).get(f"/staff/{cast.sam.pk}/profile/").content.decode()
    assert f'href="/staff/{cast.sam.pk}/uploads/"' in body
    own = client_for(cast.sam).get(f"/staff/{cast.sam.pk}/profile/").content.decode()
    assert f"/staff/{cast.sam.pk}/uploads/" not in own


def test_the_nav_has_uploads_for_everyone(cast):
    assert 'data-nav="uploads"' in client_for(cast.sam).get("/rota/").content.decode()


def test_the_backup_script_also_archives_the_media_folder():
    script = (Path(__file__).resolve().parents[1] / "deploy" / "backup.sh").read_text()
    assert "media" in script and "tar" in script
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_uploads.py -q`
Expected: FAIL (no `uploads` app).

- [ ] **Step 3: The app, settings and model**

`uploads/__init__.py` empty. `uploads/apps.py`:

```python
from django.apps import AppConfig


class UploadsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "uploads"
```

`config/settings.py`: add `"uploads",` to `INSTALLED_APPS` after `"messaging"`, and near the other path settings:

```python
# Uploaded documents (spec 5). Outside anything the web server serves; the
# app writes here and the download view reads it. In production this is
# under the systemd StateDirectory, so it is backed up with the database.
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT") or BASE_DIR / "media")
UPLOAD_MAX_BYTES = int(os.environ.get("UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
```

`config/urls.py`: `path("", include("uploads.urls")),` before the `home` route. `uploads/models.py`:

```python
"""A document held for the practice (spec 5, section 6): shared with all
staff, or kept on one person's file for their managers."""

from django.conf import settings
from django.db import models


class UploadedFile(models.Model):
    class Kind(models.TextChoices):
        SHARED = "shared"
        PERSON = "person"

    kind = models.CharField(max_length=6, choices=Kind.choices)
    person = models.ForeignKey("people.Person", null=True, blank=True, on_delete=models.CASCADE, related_name="uploads")
    title = models.CharField(max_length=120)
    original_name = models.CharField(max_length=200)
    stored_name = models.CharField(max_length=40, unique=True)
    size = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.CheckConstraint(
            condition=models.Q(kind="shared", person__isnull=True) | models.Q(kind="person", person__isnull=False),
            name="person_file_has_a_person")]

    def __str__(self):
        return self.title
```

`uploads/admin.py`: `@admin.register(UploadedFile)` `ReadOnlyModelAdmin` with `list_display = ("title", "kind", "person", "size", "created_at")`. Then `DEBUG=1 python manage.py makemigrations uploads -n initial` (Django names it `0001_initial`).

- [ ] **Step 4: The service**

`uploads/services.py`:

```python
"""Uploaded documents (spec 5, section 6). Files are stored under a random
name outside anything served; the only way out is open_file, which checks
the permission and always sends a download."""

import os
import secrets
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, Http404

from people.services import access, audit
from uploads.models import UploadedFile

# extension -> (content type, the signature its first bytes must carry)
ZIP, OLE = b"PK\x03\x04", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
TYPES = {
    "pdf": ("application/pdf", (b"%PDF",)),
    "doc": ("application/msword", (OLE,)),
    "xls": ("application/vnd.ms-excel", (OLE,)),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", (ZIP,)),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", (ZIP,)),
    "odt": ("application/vnd.oasis.opendocument.text", (ZIP,)),
    "ods": ("application/vnd.oasis.opendocument.spreadsheet", (ZIP,)),
    "png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    "jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "txt": ("text/plain; charset=utf-8", None),
    "csv": ("text/csv; charset=utf-8", None),
}


class UploadError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def root():
    return Path(settings.MEDIA_ROOT) / "uploads"


def _clean_name(name):
    base = os.path.basename((name or "").replace("\\", "/"))
    base = "".join(ch for ch in base if ch.isprintable() and ch not in '<>:"|?*')
    return base.strip()[:200] or "file"


def _looks_like_text(data):
    if b"\x00" in data:
        return False
    for encoding in ("utf-8", "cp1252"):
        try:
            data.decode(encoding)
            return True
        except UnicodeDecodeError:
            continue
    return False


# --- who ----------------------------------------------------------------------

def can_manage_person_files(user, person):
    return access.can_manage(user, person)


def _may_add(user, kind, person):
    if not access.is_manager(user):
        raise Http404
    if kind == UploadedFile.Kind.PERSON and (person is None or not can_manage_person_files(user, person)):
        raise Http404


def _may_see(user, uploaded):
    if uploaded.kind == UploadedFile.Kind.SHARED:
        return user.is_authenticated
    return can_manage_person_files(user, uploaded.person)


def _may_delete(user, uploaded):
    if uploaded.kind == UploadedFile.Kind.SHARED:
        return access.is_all_teams(user) or (access.is_manager(user) and uploaded.uploaded_by_id == user.pk)
    return can_manage_person_files(user, uploaded.person)


# --- the verbs ----------------------------------------------------------------

def add(user, upload, title, kind, person=None):
    _may_add(user, kind, person)
    original = _clean_name(upload.name)
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in TYPES:
        raise UploadError("That kind of file can't be uploaded. Use PDF, Word, Excel, OpenDocument, text, CSV, PNG or JPEG.")
    if upload.size == 0:
        raise UploadError("That file is empty.")
    if upload.size > settings.UPLOAD_MAX_BYTES:
        raise UploadError(f"That file is too big: the limit is {settings.UPLOAD_MAX_BYTES // (1024 * 1024)} MB.")
    content_type, signatures = TYPES[ext]
    head = upload.read(8192)
    upload.seek(0)
    ok = _looks_like_text(upload.read()) if signatures is None else any(head.startswith(s) for s in signatures)
    upload.seek(0)
    if not ok:
        raise UploadError(f"That file doesn't look like a .{ext} file.")
    title = (title or "").strip()[:120] or original
    stored = f"{secrets.token_hex(16)}.{ext}"
    folder = root()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    final, partial = folder / stored, folder / (stored + ".part")
    try:
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as out:
            for chunk in upload.chunks():
                out.write(chunk)
        os.replace(partial, final)
        with transaction.atomic():
            row = UploadedFile.objects.create(kind=kind, person=person, title=title, original_name=original,
                                              stored_name=stored, size=upload.size, uploaded_by=user)
            _audit(user, row, "added", title)
    except BaseException:
        for leftover in (partial, final):
            leftover.unlink(missing_ok=True)
        raise
    return row


def _audit(user, row, field, text):
    if row.kind == UploadedFile.Kind.SHARED:
        audit.record_as(user, "uploads.sharedfile", row.pk, {field: ("", text)}, note="document")
    else:
        audit.record_as(user, "uploads.personfile", row.person_id, {field: ("", text)}, note=f"document · {row.person.name}")


def remove(user, uploaded):
    if not _may_delete(user, uploaded):
        raise Http404
    with transaction.atomic():
        _audit(user, uploaded, "removed", uploaded.title)
        uploaded.delete()
    (root() / uploaded.stored_name).unlink(missing_ok=True)


def open_file(user, uploaded):
    if not _may_see(user, uploaded):
        raise Http404
    path = root() / uploaded.stored_name
    if not path.is_file():
        raise Http404
    if uploaded.kind == UploadedFile.Kind.PERSON:
        _audit(user, uploaded, "downloaded", uploaded.title)
    ext = uploaded.stored_name.rsplit(".", 1)[-1]
    response = FileResponse(open(path, "rb"), as_attachment=True, filename=uploaded.original_name)
    response["Content-Type"] = TYPES[ext][0]
    response["X-Content-Type-Options"] = "nosniff"
    return response


def shared_files():
    return UploadedFile.objects.filter(kind=UploadedFile.Kind.SHARED).select_related("uploaded_by__person")


def person_files(user, person):
    if not can_manage_person_files(user, person):
        raise Http404
    return UploadedFile.objects.filter(kind=UploadedFile.Kind.PERSON, person=person).select_related("uploaded_by__person")
```

- [ ] **Step 5: Form, views, URLs, templates**

`uploads/forms.py`:

```python
from django import forms


class UploadForm(forms.Form):
    title = forms.CharField(max_length=120, required=False, help_text="Leave empty to use the file's name.")
    file = forms.FileField()
```

`uploads/views.py`:

```python
"""The shared Uploads page, a person's documents, and the download."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from people.models import Person
from people.services import access
from uploads import services
from uploads.forms import UploadForm
from uploads.models import UploadedFile


def _handle_upload(request, kind, person=None):
    """The POST of either page: True on success (a flash is queued)."""
    form = UploadForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            services.add(request.user, form.cleaned_data["file"], form.cleaned_data["title"], kind, person)
            messages.success(request, "The document is added.")
            return form, True
        except services.UploadError as e:
            form.add_error("file", e.message)
    return form, False


@login_required
def shared(request):
    form = UploadForm()
    if request.method == "POST":
        if not access.is_manager(request.user):
            raise PermissionDenied
        form, ok = _handle_upload(request, UploadedFile.Kind.SHARED)
        if ok:
            return redirect("uploads")
    return render(request, "uploads/list.html", {
        "page_title": "Uploads", "files": services.shared_files(), "form": form, "is_manager": access.is_manager(request.user),
        "all_teams": access.is_all_teams(request.user)})


@login_required
def person(request, pk):
    owner = get_object_or_404(Person, pk=pk)
    files = services.person_files(request.user, owner)        # 404 unless the user manages them
    form = UploadForm()
    if request.method == "POST":
        form, ok = _handle_upload(request, UploadedFile.Kind.PERSON, owner)
        if ok:
            return redirect("person-uploads", pk=owner.pk)
    return render(request, "uploads/person.html", {"page_title": f"{owner.name}: documents", "owner": owner, "files": files, "form": form})


@login_required
def download(request, pk):
    return services.open_file(request.user, get_object_or_404(UploadedFile, pk=pk))


@login_required
@require_POST
def delete(request, pk):
    uploaded = get_object_or_404(UploadedFile, pk=pk)
    owner_pk = uploaded.person_id
    services.remove(request.user, uploaded)
    messages.success(request, "The document is removed.")
    return redirect("person-uploads", pk=owner_pk) if owner_pk else redirect("uploads")
```


`uploads/urls.py`:

```python
from django.urls import path

from uploads import views

urlpatterns = [
    path("uploads/", views.shared, name="uploads"),
    path("uploads/<int:pk>/download/", views.download, name="upload-download"),
    path("uploads/<int:pk>/delete/", views.delete, name="upload-delete"),
    path("staff/<int:pk>/uploads/", views.person, name="person-uploads"),
]
```

`templates/uploads/list.html`:

```html
{% extends "base.html" %}
{% block title %}Uploads · AMG Shift Central{% endblock %}
{% block content %}
{% if is_manager %}
<form class="filters" method="post" enctype="multipart/form-data">{% csrf_token %}
  <strong>Add a document</strong>
  {% for e in form.non_field_errors %}<span class="field-error">{{ e }}</span>{% endfor %}
  <label>Title {{ form.title }}</label>
  <label>File {{ form.file }}</label>{% for e in form.file.errors %}<span class="field-error">{{ e }}</span>{% endfor %}
  <button class="btn btn-quiet" type="submit">Upload</button>
</form>
{% endif %}
<table class="table">
  <thead><tr><th>Document</th><th>File</th><th>Size</th><th>Added</th><th></th></tr></thead>
  <tbody>
  {% for f in files %}
    <tr><td><a href="{% url 'upload-download' f.pk %}">{{ f.title }}</a></td><td>{{ f.original_name }}</td><td>{{ f.size|filesizeformat }}</td>
        <td>{{ f.created_at|date:"j M Y" }}{% if f.uploaded_by.person %} · {{ f.uploaded_by.person.name }}{% endif %}</td>
        <td>{% if all_teams or f.uploaded_by_id == user.pk %}<form method="post" action="{% url 'upload-delete' f.pk %}">{% csrf_token %}<button class="btn btn-quiet">Delete</button></form>{% endif %}</td></tr>
  {% empty %}<tr><td colspan="5">No documents yet.</td></tr>{% endfor %}
  </tbody>
</table>
{% endblock %}
```

`templates/uploads/person.html`: the same table and form, headed `{{ owner.name }}`, the form without any `is_manager` condition (the view already limits it), each row's delete form always shown, and a link back: `<p><a href="{% url 'profile' owner.pk %}" data-dialog>Back to the profile</a></p>`.

`templates/people/profile_dialog.html`: in the `dialog-links` block add (for managers, who are the only people who see the link; use the same condition the Permissions line uses for visibility but for any manager of the person) `{% if can_manage_files %}<a href="{% url 'person-uploads' person.pk %}">Uploads</a>{% endif %}` and add `can_manage_files` to the profile view's context: `"can_manage_files": access.can_manage(request.user, person)` in `people/views/profile.py` where the dialog's context is built.

`ui/context_processors.py`: add the Uploads item for everyone after Notice board: `items.append({"key": "uploads", "label": "Uploads", "icon": "folder", "url": "/uploads/", "active": path.startswith("/uploads/"), "children": []})` and add the icon `<symbol id="folder" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6a2 2 0 0 1 2-2h4l2 3h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></symbol>` to `static/img/icons.svg`.

`deploy/backup.sh`: after the `find … -delete` line append

```sh
# The uploaded documents (managers' papers on people), kept with the same care:
# one archive a night, 30 days, readable by nobody else (umask 077 above).
if [ -d "$state/media" ]; then
    tar -C "$state" -czf "$state/backups/media-$(date +%F).tar.gz" media
    find "$state/backups" -name 'media-*.tar.gz' -mtime +30 -delete
fi
```

- [ ] **Step 6: Run the tests**

Run: `python -m pytest tests/test_uploads.py tests/test_deploy_units.py tests/test_profile.py tests/test_shell.py -q`
Expected: PASS. (`test_the_backup_script_runs_and_keeps_its_copies_private` still passes: with no `media` directory the new block is skipped.)

- [ ] **Step 7: Commit**

```bash
git add uploads config templates ui static deploy people tests
git commit -m "Uploads: shared documents for all staff and a person's documents for their managers, as downloads only

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---
### Task 12: The Outbox page, its badge, and body retention

**Files:**
- Create: `messaging/services/outbox.py`, `messaging/views/outbox.py`, `templates/messaging/outbox.html`, `tests/test_outbox.py`
- Modify: `messaging/urls.py`, `config/settings.py`, `ui/context_processors.py`, `static/img/icons.svg`, `leave/management/commands/daily_flags.py`

**Interfaces:**
- Consumes: `Outbox` (Task 1), `messaging.services.NOT_CONFIGURED`.
- Produces: `messaging.services.outbox`: `STATUSES`, `status(row) -> "sent" | "queued" | "failed" | "not configured"`, `scope(user) -> QuerySet[Outbox]`, `rows(user, state="", person=None, start=None, end=None)`, `failure_count(user, now=None) -> int`, `blank_old_bodies(months=None, now=None) -> int`; setting `OUTBOX_BODY_MONTHS` (default 12; 0 keeps bodies for ever); URL `outbox` (`/outbox/`); the Outbox nav item (managers) with the failure badge (`badges["outbox"]` in the context processor); Reports ▸ Sent messages.

- [ ] **Step 1: Write the failing tests**

`tests/test_outbox.py`:

```python
"""The Outbox page (spec 5, section 7)."""

from datetime import date, timedelta
from io import StringIO
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.utils import timezone

from messaging.models import Outbox
from messaging.services import NOT_CONFIGURED, outbox
from tests.factories import client_for, make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


def row(person=None, state="sent", channel="email", subject="Subject", body="The body", age=timedelta(0), error=""):
    kw = {}
    if state == "sent":
        kw["sent_at"] = timezone.now()
    r = Outbox.objects.create(to_person=person, to_email=person.email if person else "", channel=channel, subject=subject,
                              body=body, error=error, **kw)
    if age:
        Outbox.objects.filter(pk=r.pk).update(queued_at=timezone.now() - age)
    return Outbox.objects.get(pk=r.pk)


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_team_manager(lead, reception)
    c = SimpleNamespace(lead=lead, sam=make_person(first_name="Sam", team=reception), nina=make_person(first_name="Nina", team=nursing),
                        boss=make_person(first_name="Boss", team=reception))
    for p in (lead, c.sam, c.nina):
        make_user_for(p)
    make_user_for(c.boss, is_all_teams_manager=True)
    return c


def test_status_has_four_values(cast):
    assert outbox.status(row(cast.sam, "sent")) == "sent"
    assert outbox.status(row(cast.sam, "queued", channel="push")) == "queued"
    assert outbox.status(row(cast.sam, "failed", error="SMTPException")) == "failed"
    assert outbox.status(row(cast.sam, "failed", error="no email address")) == "failed"
    assert outbox.status(row(cast.sam, "failed", error=NOT_CONFIGURED)) == "not configured"


def test_a_team_manager_sees_rows_to_their_team_and_an_all_teams_manager_sees_all(cast):
    mine, theirs, nobody = row(cast.sam), row(cast.nina), row(None)
    assert set(outbox.scope(cast.lead.user)) == {mine}
    assert set(outbox.scope(cast.boss.user)) == {mine, theirs, nobody}
    assert outbox.scope(cast.sam.user).count() == 0


def test_filters(cast):
    a = row(cast.sam, subject="A", age=timedelta(days=3))
    b = row(cast.sam, "failed", subject="B", error="OSError")
    c = row(cast.nina, subject="C")
    boss = cast.boss.user
    assert set(outbox.rows(boss, state="failed")) == {b}
    assert set(outbox.rows(boss, person=cast.nina)) == {c}
    assert set(outbox.rows(boss, start=date(2026, 11, 2))) == {b, c}
    assert set(outbox.rows(boss, end=date(2026, 10, 30))) == {a}
    assert set(outbox.rows(boss)) == {a, b, c}


def test_the_failure_count_is_failures_and_stuck_pushes_in_the_last_week_only(cast):
    row(cast.sam, "failed", error="OSError")                                                  # counts
    row(cast.sam, "failed", error="no email address")                                         # counts
    row(cast.sam, "failed", error=NOT_CONFIGURED)                                             # a box with no relay: not a failure
    row(cast.sam, "failed", error="OSError", age=timedelta(days=8))                           # too old
    row(cast.sam, "queued", channel="push", age=timedelta(minutes=10))                        # stuck
    row(cast.sam, "queued", channel="push", age=timedelta(minutes=1))                         # just queued
    row(cast.sam, "sent")
    row(cast.nina, "failed", error="OSError")                                                 # another team
    assert outbox.failure_count(cast.boss.user) == 4
    assert outbox.failure_count(cast.lead.user) == 3
    assert outbox.failure_count(cast.sam.user) == 0


def test_the_page_lists_rows_with_status_and_an_expandable_body(cast):
    row(cast.sam, subject="Your rota", body="Mon 8 Mar: 08:00-16:15")
    row(cast.sam, "failed", subject="Broken", error="SMTPException")
    row(cast.sam, "queued", channel="push", subject="Pushy", body="")
    body = client_for(cast.lead).get("/outbox/").content.decode()
    assert "Your rota" in body and "Mon 8 Mar: 08:00-16:15" in body and "Sent" in body
    assert "Broken" in body and "SMTPException" in body and "Failed" in body
    assert "Pushy" in body and "Queued" in body and "Sam Patel" in body


def test_the_page_filters_and_pages(cast):
    for n in range(55):
        row(cast.sam, subject=f"Message {n:02d}")
    c = client_for(cast.lead)
    first, second = c.get("/outbox/").content.decode(), c.get("/outbox/?page=2").content.decode()
    assert "Message 54" in first and "Message 04" not in first and "Message 04" in second
    row(cast.sam, "failed", subject="Only me", error="OSError")
    only = c.get("/outbox/?status=failed").content.decode()
    assert "Only me" in only and "Message 54" not in only
    assert c.get("/outbox/?status=nonsense&person=abc&from=junk").status_code == 200


def test_staff_have_no_outbox_and_the_nav_badge_shows_failures(cast):
    assert client_for(cast.sam).get("/outbox/").status_code == 403
    row(cast.sam, "failed", error="OSError")
    manager = client_for(cast.lead).get("/rota/").content.decode()
    assert 'data-nav="outbox"' in manager and 'class="nav-badge"' in manager and 'href="/outbox/"' in manager
    assert 'data-nav="outbox"' not in client_for(cast.sam).get("/rota/").content.decode()


def test_bodies_older_than_the_retention_are_blanked_and_the_rest_kept(cast, settings):
    old = row(cast.sam, subject="Old", body="private", age=timedelta(days=400))
    new = row(cast.sam, subject="New", body="recent", age=timedelta(days=30))
    assert outbox.blank_old_bodies() == 1
    old.refresh_from_db()
    new.refresh_from_db()
    assert old.body == "" and old.subject == "Old" and new.body == "recent"
    settings.OUTBOX_BODY_MONTHS = 0
    assert outbox.blank_old_bodies() == 0                      # 0 keeps bodies for ever


def test_the_daily_job_applies_the_retention(cast):
    old = row(cast.sam, body="private", age=timedelta(days=400))
    out = StringIO()
    call_command("daily_flags", stdout=out)
    old.refresh_from_db()
    assert old.body == "" and "outbox" in out.getvalue()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_outbox.py -q`
Expected: FAIL.

- [ ] **Step 3: The service**

`messaging/services/outbox.py`:

```python
"""What the Outbox page shows and counts (spec 5, section 7)."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from messaging.models import Outbox
from messaging.services import NOT_CONFIGURED
from people.services import access

RECENT = timedelta(days=7)      # how far back the nav badge looks
STUCK = timedelta(minutes=5)    # a queued push older than this is not just waiting its turn
STATUSES = ("sent", "queued", "failed", "not configured")


def status(row):
    if row.sent_at:
        return "sent"
    if row.error == NOT_CONFIGURED:
        return "not configured"
    if row.error:
        return "failed"
    return "queued"


def scope(user):
    """All rows for an all-teams manager; rows to people in their teams for a
    team manager; nothing for anyone else."""
    if access.is_all_teams(user):
        return Outbox.objects.all()
    if access.is_manager(user):
        return Outbox.objects.filter(to_person__in=access.managed_people(user))
    return Outbox.objects.none()


def _with_status(rows, state):
    if state == "sent":
        return rows.filter(sent_at__isnull=False)
    unsent = rows.filter(sent_at__isnull=True)
    if state == "not configured":
        return unsent.filter(error=NOT_CONFIGURED)
    if state == "failed":
        return unsent.exclude(error="").exclude(error=NOT_CONFIGURED)
    if state == "queued":
        return unsent.filter(error="")
    return rows


def rows(user, state="", person=None, start=None, end=None):
    found = _with_status(scope(user).select_related("to_person"), state)
    if person is not None:
        found = found.filter(to_person=person)
    if start:
        found = found.filter(queued_at__date__gte=start)
    if end:
        found = found.filter(queued_at__date__lte=end)
    return found


def failure_count(user, now=None):
    """Rows in the last week that failed (a missing relay is not a failure)
    plus pushes still queued after five minutes."""
    now = now or timezone.now()
    recent = scope(user).filter(queued_at__gte=now - RECENT, sent_at__isnull=True)
    failed = recent.exclude(error="").exclude(error=NOT_CONFIGURED).count()
    stuck = recent.filter(channel=Outbox.Channel.PUSH, error="", queued_at__lt=now - STUCK).count()
    return failed + stuck


def blank_old_bodies(months=None, now=None):
    """Messages hold personal details, so their text goes after OUTBOX_BODY_MONTHS
    (the row, who and when stay). 0 keeps the text for ever."""
    months = settings.OUTBOX_BODY_MONTHS if months is None else months
    if months <= 0:
        return 0
    cutoff = (now or timezone.now()) - timedelta(days=round(months * 30.44))
    return Outbox.objects.filter(queued_at__lt=cutoff).exclude(body="").update(body="")
```

`config/settings.py`: after the `UPLOAD_MAX_BYTES` line add `OUTBOX_BODY_MONTHS = int(os.environ.get("OUTBOX_BODY_MONTHS", "12"))`.

`leave/management/commands/daily_flags.py`: import `from messaging.services import outbox` and add a fourth step to `steps`:

```python
                 ("year-end flags", lambda: yearend.run(base_url=base)),
                 ("outbox bodies blanked", outbox.blank_old_bodies))
```

(the command prints `f"{n} {name}"`, so the test's `"outbox" in out` holds), and update the module docstring's list to mention it.

- [ ] **Step 4: The view, template, URL, nav**

`messaging/views/outbox.py`:

```python
"""The Outbox page (spec 5, section 7)."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from messaging.services import outbox
from people.services import access

PER_PAGE = 50


def _day(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@login_required
@access.manager_required
def index(request):
    state = request.GET.get("status", "")
    state = state if state in outbox.STATUSES else ""
    people = access.managed_people(request.user)
    raw = request.GET.get("person", "")
    person = people.filter(pk=int(raw)).first() if raw.isascii() and raw.isdigit() else None
    start, end = _day(request.GET.get("from")), _day(request.GET.get("to"))
    page = Paginator(outbox.rows(request.user, state, person, start, end), PER_PAGE).get_page(request.GET.get("page"))
    for r in page:
        r.state = outbox.status(r)
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "messaging/outbox.html", {
        "page_title": "Outbox", "page": page, "statuses": outbox.STATUSES, "state": state, "person": person,
        "people": people.order_by("name"), "date_from": start.isoformat() if start else "",
        "date_to": end.isoformat() if end else "", "query": params.urlencode()})
```

`messaging/urls.py`: import `outbox as outbox_views` (`from messaging.views import app, messages, notices, outbox as outbox_views, push`) and add `path("outbox/", outbox_views.index, name="outbox"),`.

`templates/messaging/outbox.html`:

```html
{% extends "base.html" %}
{% block title %}Outbox · AMG Shift Central{% endblock %}
{% block content %}
<form class="filters" method="get">
  <label>Status <select name="status"><option value="">Any</option>{% for s in statuses %}<option value="{{ s }}"{% if s == state %} selected{% endif %}>{{ s|capfirst }}</option>{% endfor %}</select></label>
  <label>Person <select name="person"><option value="">Anyone</option>{% for p in people %}<option value="{{ p.pk }}"{% if person and p.pk == person.pk %} selected{% endif %}>{{ p.name }}</option>{% endfor %}</select></label>
  <label>From <input type="date" name="from" value="{{ date_from }}"></label>
  <label>To <input type="date" name="to" value="{{ date_to }}"></label>
  <button class="btn btn-quiet" type="submit">Refresh</button>
</form>
<table class="table">
  <thead><tr><th>Queued</th><th>To</th><th>Channel</th><th>Subject</th><th>Status</th><th>Text</th></tr></thead>
  <tbody>
  {% for r in page %}
    <tr><td>{{ r.queued_at|date:"j M H:i" }}</td><td>{{ r.to_person.name|default:r.to_email|default:"—" }}</td><td>{{ r.get_channel_display }}</td>
        <td>{{ r.subject }}</td>
        <td>{{ r.state|capfirst }}{% if r.state == "failed" %}: {{ r.error }}{% endif %}</td>
        <td>{% if r.body %}<details><summary>Show</summary><pre class="outbox-body">{{ r.body }}</pre></details>{% else %}—{% endif %}</td></tr>
  {% empty %}<tr><td colspan="6">Nothing here.</td></tr>{% endfor %}
  </tbody>
</table>
<p class="pager">
  {% if page.has_previous %}<a href="?{{ query }}&amp;page={{ page.previous_page_number }}">‹ Newer</a>{% endif %}
  Page {{ page.number }} of {{ page.paginator.num_pages }}
  {% if page.has_next %}<a href="?{{ query }}&amp;page={{ page.next_page_number }}">Older ›</a>{% endif %}
</p>
{% endblock %}
```

`static/img/icons.svg`: `<symbol id="outbox" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13"/><path d="M22 2 15 22l-4-9-9-4z"/></symbol>`.

`ui/context_processors.py`: for managers add, after the Messages item, `{"key": "outbox", "label": "Outbox", "icon": "outbox", "url": "/outbox/", "active": path.startswith("/outbox/"), "children": []}`; add `"Sent messages"` (`/outbox/`) to the managers' `report_children`; and in `shell()` set `badges["outbox"]` to `outbox.failure_count(user)` when the user is a manager (import `from messaging.services import outbox`).

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_outbox.py tests/test_leave_yearend.py tests/test_shell.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add messaging leave config ui templates static tests
git commit -m "Messaging: the Outbox page, its failure badge, and a year's retention for message text

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---

### Task 13: The dashboard

**Files:**
- Create: `people/services/dashboard.py`, `people/views/dashboard.py`, `templates/people/dashboard.html`, `tests/test_dashboard.py`
- Modify: `people/views/__init__.py`, `people/urls.py`, `ui/context_processors.py`

**Interfaces:**
- Consumes: `open_shifts.waiting_claims` (Task 4), `outbox.failure_count` (Task 12), `push.status` (Task 8), `health._leaving`, `returns.due`, `sickness.level_for/level_label`, `today.site_of`/`SITES`.
- Produces: `people.services.dashboard.build(user, today=None) -> dict` with keys `day`, `today` (`{"sites": [(site, n)], "wfh": n, "off": n}`), `waiting` (`{"leave", "leave_oldest_days", "claims"}`), `next` (`{"leave": [Booking], "open_shifts": [OpenShift], "end": date}`), `flags` (`{"triggers": [{"person", "label"}], "leaving": [...], "returning": [Booking]}`), `system` (all-teams only, else None: `{"hr", "gp_configured", "gp", "push", "outbox_failures"}`); URL `report-dashboard` (`/reports/dashboard/`); Reports ▸ Dashboard.

- [ ] **Step 1: Write the failing tests**

`tests/test_dashboard.py`:

```python
"""The manager's dashboard (spec 5, section 8)."""

from datetime import date, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from leave.services import bookings
from people.services import dashboard
from shifts.services import open_shifts
from tests.factories import (client_for, make_booking, make_department, make_entry, make_person, make_sick, make_team,
                             make_team_manager, make_type, make_user_for)

pytestmark = pytest.mark.django_db
TODAY = date(2026, 11, 2)       # the pinned Monday


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")

    def staff(first, team, **kw):
        p = make_person(first_name=first, team=team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5, **kw)
        make_user_for(p)
        return p

    lead = staff("Lead", reception)
    make_team_manager(lead, reception)
    boss = make_person(first_name="Boss", team=reception)
    make_user_for(boss, is_all_teams_manager=True)
    return SimpleNamespace(reception=reception, nursing=nursing, lead=lead, boss=boss, sam=staff("Sam", reception),
                           ann=staff("Ann", reception), wfh=staff("Wendy", reception), nina=staff("Nina", nursing))


def test_the_today_card_counts_people_in_by_site_working_from_home_and_off(cast):
    ag, pmc = make_department("Reception AG"), make_department("Reception PMC")
    make_entry(cast.sam, TODAY, department=ag)
    make_entry(cast.ann, TODAY, department=pmc)
    make_entry(cast.wfh, TODAY, wfh=True)
    make_entry(cast.nina, TODAY, department=ag)
    make_entry(cast.lead, TODAY)                                                # no site
    bookings.book(cast.boss.user, cast.nina, make_type("Training"), TODAY, TODAY, "whole")
    card = dashboard.build(cast.boss.user, TODAY)["today"]
    assert dict(card["sites"]) == {"PMC": 1, "AG": 1, "Either": 1}
    assert card["wfh"] == 1 and card["off"] == 1


def test_a_team_manager_sees_only_their_own_teams_people(cast):
    make_entry(cast.sam, TODAY, department=make_department("Reception AG"))
    make_entry(cast.nina, TODAY, department=make_department("Nursing AG"))
    assert dict(dashboard.build(cast.lead.user, TODAY)["today"]["sites"]) == {"AG": 1}
    assert dict(dashboard.build(cast.boss.user, TODAY)["today"]["sites"]) == {"AG": 2}


def test_the_waiting_card_counts_leave_requests_and_open_shift_claims(cast):
    make_booking(cast.sam, TODAY + timedelta(days=7), status="pending")
    make_booking(cast.nina, TODAY + timedelta(days=8), status="pending")
    post = open_shifts.post(cast.lead.user, cast.reception, TODAY + timedelta(days=7), time(9), time(13), audience_teams=[cast.reception])
    open_shifts.claim(cast.sam.user, post)
    assert dashboard.build(cast.lead.user, TODAY)["waiting"] == {"leave": 1, "leave_oldest_days": 0, "claims": 1}
    assert dashboard.build(cast.boss.user, TODAY)["waiting"]["leave"] == 2


def test_your_own_request_is_not_waiting_for_you(cast):
    make_booking(cast.lead, TODAY + timedelta(days=7), status="pending")
    assert dashboard.build(cast.lead.user, TODAY)["waiting"]["leave"] == 0


def test_the_next_fourteen_days_list_leave_starting_and_open_shifts(cast):
    inside = make_booking(cast.sam, TODAY + timedelta(days=13))
    make_booking(cast.ann, TODAY + timedelta(days=14))                           # the fifteenth day: outside
    post = open_shifts.post(cast.lead.user, cast.reception, TODAY + timedelta(days=3), time(9), time(13), audience_teams=[cast.reception])
    filled = open_shifts.post(cast.lead.user, cast.reception, TODAY + timedelta(days=4), time(9), time(13), audience_teams=[cast.reception])
    open_shifts.approve(cast.lead.user, open_shifts.claim(cast.sam.user, filled))
    nxt = dashboard.build(cast.lead.user, TODAY)["next"]
    assert nxt["leave"] == [inside] and nxt["open_shifts"] == [post] and nxt["end"] == TODAY + timedelta(days=13)


def test_flags_list_triggers_leavers_and_people_returning(cast):
    for n in range(3):                                                           # three instances: trigger 1
        make_sick(cast.sam, TODAY - timedelta(days=60 - 14 * n))
    cast.ann.end_date = TODAY + timedelta(days=10)
    cast.ann.save()
    maternity = make_type("Maternity", flag_return=True)
    returning = make_booking(cast.wfh, TODAY - timedelta(days=20), TODAY - timedelta(days=2), type=maternity)
    flags = dashboard.build(cast.lead.user, TODAY)["flags"]
    assert [(t["person"], t["label"]) for t in flags["triggers"]] == [(cast.sam, "Trigger 1")]
    assert [r["person"] for r in flags["leaving"]] == [cast.ann]
    assert flags["returning"] == [returning]


def test_the_system_card_is_for_all_teams_managers_only(cast, push_on):
    assert dashboard.build(cast.lead.user, TODAY)["system"] is None
    system = dashboard.build(cast.boss.user, TODAY)["system"]
    assert system["push"]["configured"] and system["outbox_failures"] == 0 and system["hr"] is None


def test_the_page(cast):
    make_entry(cast.sam, TODAY, department=make_department("Reception AG"))
    assert client_for(cast.sam).get("/reports/dashboard/").status_code == 403
    page = client_for(cast.lead).get("/reports/dashboard/").content.decode()
    assert "Today" in page and "Waiting for you" in page and "Next 14 days" in page and "Flags" in page
    assert "System" not in page
    assert "System" in client_for(cast.boss).get("/reports/dashboard/").content.decode()
    assert 'href="/reports/dashboard/"' in client_for(cast.lead).get("/rota/").content.decode()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_dashboard.py -q`
Expected: FAIL.

- [ ] **Step 3: The service**

`people/services/dashboard.py`:

```python
"""The manager's dashboard (REP-07, spec 5 section 8): a few cards, each one
function so each is tested alone. Team managers see their own teams' people;
all-teams managers see everyone. The home page still goes to the rota."""

from datetime import timedelta

from django.utils import timezone

from leave.models import Booking, BookingDay
from leave.services import returns, sickness
from messaging.services import outbox, push
from people.services import access, health, hr_sync
from shifts.models import Entry, OpenShift
from shifts.services import gp_sync, open_shifts
from shifts.services.today import SITES, site_of

NEXT_DAYS = 14


def today_card(people, today):
    by_site = {site: set() for site in SITES}
    home = set()
    shifts = Entry.objects.filter(person__in=people, day=today, kind=Entry.Kind.SHIFT, covered_by__isnull=True).select_related("department")
    for e in shifts:
        if e.wfh:
            home.add(e.person_id)
        else:
            by_site[site_of(e)].add(e.person_id)
    off = (BookingDay.objects.filter(booking__person__in=people, day=today, booking__status__in=Booking.ACTIVE)
           .values("booking__person").distinct().count())
    return {"sites": [(site, len(ids)) for site, ids in by_site.items() if ids], "wfh": len(home), "off": off}


def waiting_card(user, people, today):
    waiting = Booking.objects.filter(person__in=people, status__in=(Booking.Status.PENDING, Booking.Status.CANCEL_REQUESTED))
    me = getattr(user, "person", None)
    if me is not None:
        waiting = waiting.exclude(person=me)          # another manager decides your own
    since = [b.cancel_requested_at or b.requested_at for b in waiting.only("requested_at", "cancel_requested_at")]
    return {"leave": len(since), "leave_oldest_days": (timezone.now() - min(since)).days if since else 0,
            "claims": open_shifts.waiting_claims(user).count()}


def next_card(user, people, today):
    end = today + timedelta(days=NEXT_DAYS - 1)
    leave = list(Booking.objects.filter(person__in=people, status__in=Booking.ACTIVE, dates_only=False, first_day__range=(today, end))
                 .select_related("person", "type").order_by("first_day", "person__name"))
    posts = list(OpenShift.objects.filter(team__in=access.managed_teams(user), state=OpenShift.State.OPEN, day__range=(today, end))
                 .select_related("team").order_by("day", "start"))
    return {"leave": leave, "open_shifts": posts, "end": end}


def flags_card(people, today):
    triggers = []
    for p in people.current(on=today).order_by("name"):
        level = sickness.level_for(p, today)
        if level:
            triggers.append({"person": p, "label": sickness.level_label(level)})
    mine = set(people.values_list("pk", flat=True))
    return {"triggers": triggers, "leaving": health._leaving(people, today),
            "returning": [b for b in returns.due(today) if b.person_id in mine]}


def system_card(user):
    return {"hr": hr_sync.last_run(), "gp_configured": gp_sync.configured(), "gp": gp_sync.last_run(),
            "push": push.status(), "outbox_failures": outbox.failure_count(user)}


def build(user, today=None):
    today = today or timezone.localdate()
    people = access.managed_people(user)
    return {"day": today, "today": today_card(people, today), "waiting": waiting_card(user, people, today),
            "next": next_card(user, people, today), "flags": flags_card(people, today),
            "system": system_card(user) if access.is_all_teams(user) else None}
```

- [ ] **Step 4: View, URL, template, nav**

`people/views/dashboard.py`:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from people.services import access, dashboard


@login_required
@access.manager_required
def index(request):
    return render(request, "people/dashboard.html", {"page_title": "Dashboard", "cards": dashboard.build(request.user)})
```

`people/views/__init__.py`: add `dashboard` to its module imports the way `activity` is exposed (follow the file's existing pattern: `from . import activity, dashboard, departments, ...`). `people/urls.py`: add `path("reports/dashboard/", views.dashboard.index, name="report-dashboard"),`.

`templates/people/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}Dashboard · AMG Shift Central{% endblock %}
{% block content %}
<div class="dash">
  <section class="dash-card"><h2>Today</h2>
    <p class="muted">{{ cards.day|date:"l j F" }}</p>
    <ul>{% for site, n in cards.today.sites %}<li><strong>{{ n }}</strong> in at {% if site == "Either" %}no site{% else %}{{ site }}{% endif %}</li>{% empty %}<li>Nobody on shift.</li>{% endfor %}
      <li><strong>{{ cards.today.wfh }}</strong> working from home</li><li><strong>{{ cards.today.off }}</strong> off</li></ul>
    <a href="{% url 'rota-today' %}">Who's in today</a></section>
  <section class="dash-card"><h2>Waiting for you</h2>
    <ul><li><strong>{{ cards.waiting.leave }}</strong> leave request{{ cards.waiting.leave|pluralize }}{% if cards.waiting.leave %}, the oldest {{ cards.waiting.leave_oldest_days }} day{{ cards.waiting.leave_oldest_days|pluralize }} · <a href="{% url 'time-off-approve' %}">Decide</a>{% endif %}</li>
      <li><strong>{{ cards.waiting.claims }}</strong> open shift claim{{ cards.waiting.claims|pluralize }}{% if cards.waiting.claims %} · <a href="{% url 'open-shifts' %}">Decide</a>{% endif %}</li></ul></section>
  <section class="dash-card"><h2>Next 14 days</h2>
    <h3>Leave starting</h3>
    <ul>{% for b in cards.next.leave %}<li>{{ b.person.name }} · {{ b.type.name }} · {{ b.first_day|date:"D j M" }}</li>{% empty %}<li>None.</li>{% endfor %}</ul>
    <h3>Open shifts</h3>
    <ul>{% for s in cards.next.open_shifts %}<li><a href="{% url 'open-shift-detail' s.pk %}">{{ s.day|date:"D j M" }} {{ s.start|time:"H:i" }}–{{ s.finish|time:"H:i" }}</a> · {{ s.team.name }}</li>{% empty %}<li>None unfilled.</li>{% endfor %}</ul></section>
  <section class="dash-card"><h2>Flags</h2>
    <h3>Sickness triggers</h3>
    <ul>{% for t in cards.flags.triggers %}<li>{{ t.person.name }} · {{ t.label }}</li>{% empty %}<li>None.</li>{% endfor %}</ul>
    <h3>Leaving in 30 days</h3>
    <ul>{% for r in cards.flags.leaving %}<li>{{ r.person.name }} · {{ r.person.end_date|date:"j M" }}</li>{% empty %}<li>None.</li>{% endfor %}</ul>
    <h3>Returning from absence</h3>
    <ul>{% for b in cards.flags.returning %}<li>{{ b.person.name }} · {{ b.type.name }} ended {{ b.last_day|date:"j M" }}</li>{% empty %}<li>None.</li>{% endfor %}</ul></section>
  {% if cards.system %}
  <section class="dash-card"><h2>System</h2>
    <ul><li>Practice HR: {% if cards.system.hr %}{{ cards.system.hr.finished_at|date:"j M H:i" }}{% else %}never read{% endif %}</li>
      <li>GP rota: {% if not cards.system.gp_configured %}not configured{% elif cards.system.gp %}{{ cards.system.gp.finished_at|date:"j M H:i" }}{% else %}never read{% endif %}</li>
      <li>Phone notifications: {% if cards.system.push.configured %}{{ cards.system.push.devices }} device{{ cards.system.push.devices|pluralize }}, {{ cards.system.push.queued }} queued{% else %}not configured{% endif %}</li>
      <li>Failed or stuck messages this week: <strong>{{ cards.system.outbox_failures }}</strong>{% if cards.system.outbox_failures %} · <a href="{% url 'outbox' %}?status=failed">Outbox</a>{% endif %}</li></ul></section>
  {% endif %}
</div>
{% endblock %}
```

`static/css/components.css`: `.dash { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--sp-4); } .dash-card { background: var(--surface); border: 1px solid var(--hairline); border-radius: var(--radius); padding: var(--sp-4); } .dash-card h3 { font-size: var(--fs-md); margin: var(--sp-3) 0 var(--sp-1); } .dash-card ul { margin: 0; padding-left: 1.1rem; }`

`ui/context_processors.py`: the managers' `report_children` starts with Dashboard: `report_children = ([{"label": "Dashboard", "url": "/reports/dashboard/"}] if role != "staff" else []) + [Hours, Leave…]` (keep the existing children after it).

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_dashboard.py tests/test_shell.py -q`
Expected: PASS. If a `make_booking(..., type=maternity)` call is refused for the type name, pass `type=` as the factory allows (`make_booking` accepts a `type` kwarg and otherwise builds Holiday).

- [ ] **Step 6: Commit**

```bash
git add people ui templates static tests
git commit -m "People: the manager's dashboard (today, waiting, next 14 days, flags, system)

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---

### Task 14: The Shifts report and Staff by hour

**Files:**
- Create: `shifts/services/shift_report.py`, `shifts/services/staff_by_hour.py`, `templates/shifts/shifts_report.html`, `templates/shifts/staff_by_hour.html`, `tests/test_shifts_report.py`, `tests/test_staff_by_hour.py`
- Modify: `shifts/views/reports.py`, `shifts/urls.py`, `ui/context_processors.py`

**Interfaces:**
- Consumes: `exports.xlsx.workbook/Hours/response`, `access.managed_people/managed_teams`, `today.site_of`, `render.duration` (the `fmt.duration(timedelta)` the Hours report uses).
- Produces: `shift_report.report(user, start, end, team=None, department=None, person=None) -> dict` (`blocks` [`person`, `rows` [`entry`], `total`, `overtime`], `start`, `end`, `grand_total`, `grand_overtime`); `staff_by_hour.report(user, start, end, site="", team=None) -> dict` (`columns` [int hours], `labels`, `rows` [`day`, `counts`, `wfh`, `peak`], `start`, `end`); URLs `report-shifts` (`/reports/shifts/`), `report-staff-by-hour` (`/reports/staff-by-hour/`); both accept `?download=1` for Excel.

- [ ] **Step 1: Write the failing tests**

`tests/test_shifts_report.py`:

```python
"""The Shifts report (spec 5, section 9)."""

import io
from datetime import date, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from leave.services import bookings
from shifts.services import shift_report
from tests.factories import (client_for, make_department, make_entry, make_person, make_team, make_team_manager, make_type,
                             make_user_for)

pytestmark = pytest.mark.django_db
MON = date(2026, 11, 9)


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_team_manager(lead, reception)
    c = SimpleNamespace(reception=reception, nursing=nursing, lead=lead, boss=make_person(first_name="Boss", team=reception),
                        sam=make_person(first_name="Sam", team=reception, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5),
                        nina=make_person(first_name="Nina", team=nursing))
    for p in (lead, c.sam, c.nina):
        make_user_for(p)
    make_user_for(c.boss, is_all_teams_manager=True)
    return c


def shift(person, day, **kw):
    kw.setdefault("start", time(8))
    kw.setdefault("finish", time(16, 15))
    kw.setdefault("break_minutes", 45)
    return make_entry(person, day, **kw)


def test_net_hours_are_finish_less_start_less_break_with_overtime_shown_apart(cast):
    shift(cast.sam, MON)
    shift(cast.sam, MON + timedelta(days=1), start=time(9), finish=time(12), break_minutes=0, overtime="paid")
    (block,) = shift_report.report(cast.boss.user, MON, MON + timedelta(days=6))["blocks"]
    assert block["person"] == cast.sam and len(block["rows"]) == 2
    assert block["total"] == timedelta(hours=10, minutes=30) and block["overtime"] == timedelta(hours=3)


def test_the_grand_total_adds_every_person(cast):
    shift(cast.sam, MON)
    shift(cast.nina, MON)
    r = shift_report.report(cast.boss.user, MON, MON)
    assert r["grand_total"] == timedelta(hours=15) and len(r["blocks"]) == 2


def test_shifts_replaced_by_leave_are_left_out(cast):
    shift(cast.sam, MON)
    bookings.book(cast.boss.user, cast.sam, make_type("Training"), MON, MON, "whole")
    assert shift_report.report(cast.boss.user, MON, MON)["blocks"] == []


def test_a_team_manager_sees_only_their_own_teams(cast):
    shift(cast.sam, MON)
    shift(cast.nina, MON)
    assert [b["person"] for b in shift_report.report(cast.lead.user, MON, MON)["blocks"]] == [cast.sam]


def test_filters(cast):
    dept = make_department("Reception AG")
    shift(cast.sam, MON, department=dept)
    shift(cast.sam, MON + timedelta(days=1))
    shift(cast.nina, MON)
    boss = cast.boss.user
    assert len(shift_report.report(boss, MON, MON + timedelta(days=6), team=cast.nursing)["blocks"]) == 1
    (block,) = shift_report.report(boss, MON, MON + timedelta(days=6), department=dept)["blocks"]
    assert len(block["rows"]) == 1
    (block,) = shift_report.report(boss, MON, MON + timedelta(days=6), person=cast.sam)["blocks"]
    assert len(block["rows"]) == 2


def test_the_range_is_swapped_when_backwards_and_capped_at_a_year(cast):
    r = shift_report.report(cast.boss.user, MON + timedelta(days=6), MON)
    assert (r["start"], r["end"]) == (MON, MON + timedelta(days=6))
    r = shift_report.report(cast.boss.user, MON - timedelta(days=900), MON)
    assert (r["end"] - r["start"]).days == 366


def test_the_page_and_the_download(cast):
    shift(cast.sam, MON, text="Cover")
    assert client_for(cast.sam).get("/reports/shifts/").status_code == 403
    c = client_for(cast.lead)
    page = c.get(f"/reports/shifts/?from={MON}&to={MON}").content.decode()
    assert "Sam Patel" in page and "08:00" in page and "16:15" in page and "7 h 30 min" in page and "Cover" in page
    r = c.get(f"/reports/shifts/?from={MON}&to={MON}&download=1")
    assert r["Content-Type"].endswith("spreadsheetml.sheet") and f"shifts-{MON}-{MON}.xlsx" in r["Content-Disposition"]
    ws = load_workbook(io.BytesIO(r.content)).active
    assert [c.value for c in ws[1]][:3] == ["Date", "Day", "Name"]
    assert ws["C2"].value == "Sam Patel" and ws["F2"].value == "08:00" and ws["I2"].value == 7.5
    assert ws["A3"].value == "Total" and ws["I3"].value == 7.5


def test_a_name_that_looks_like_a_formula_is_written_as_text(cast):
    evil = make_person(first_name="=HYPERLINK", team=cast.reception)
    shift(evil, MON)
    ws = load_workbook(io.BytesIO(client_for(cast.boss).get(f"/reports/shifts/?from={MON}&to={MON}&download=1").content)).active
    assert ws["C2"].data_type == "s" and ws["C2"].value.startswith("=HYPERLINK")


def test_the_nav_has_the_report_for_managers_only(cast):
    assert 'href="/reports/shifts/"' in client_for(cast.lead).get("/rota/").content.decode()
    assert 'href="/reports/shifts/"' not in client_for(cast.sam).get("/rota/").content.decode()
```

`tests/test_staff_by_hour.py`:

```python
"""Staff by hour (spec 5, section 10)."""

import io
from datetime import date, time, timedelta
from types import SimpleNamespace

import pytest
from openpyxl import load_workbook

from shifts.services import staff_by_hour
from tests.factories import (client_for, make_department, make_entry, make_person, make_team, make_team_manager, make_user_for)

pytestmark = pytest.mark.django_db
MON = date(2026, 11, 9)


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_team_manager(lead, reception)
    c = SimpleNamespace(reception=reception, nursing=nursing, lead=lead, boss=make_person(first_name="Boss", team=reception),
                        sam=make_person(first_name="Sam", team=reception), ann=make_person(first_name="Ann", team=reception),
                        nina=make_person(first_name="Nina", team=nursing))
    for p in (lead, c.sam, c.nina):
        make_user_for(p)
    make_user_for(c.boss, is_all_teams_manager=True)
    return c


def day(report, d=MON):
    (row,) = [r for r in report["rows"] if r["day"] == d]
    return dict(zip(report["columns"], row["counts"])), row


def test_a_shift_counts_in_every_hour_it_touches_and_a_quarter_hour_still_counts(cast):
    make_entry(cast.sam, MON, start=time(8), finish=time(16, 15))
    report = staff_by_hour.report(cast.boss.user, MON, MON)
    counts, _ = day(report)
    assert report["columns"] == list(range(8, 17)) and set(counts.values()) == {1}
    assert report["labels"][0] == "08:00" and report["labels"][-1] == "16:00"


def test_a_shift_ending_on_the_hour_does_not_count_in_that_hour(cast):
    make_entry(cast.sam, MON, start=time(9), finish=time(12))
    counts, _ = day(staff_by_hour.report(cast.boss.user, MON, MON))
    assert counts == {9: 1, 10: 1, 11: 1}


def test_overlapping_people_add_up_and_the_peak_is_the_busiest_hour(cast):
    make_entry(cast.sam, MON, start=time(8), finish=time(12))
    make_entry(cast.ann, MON, start=time(10), finish=time(14))
    counts, row = day(staff_by_hour.report(cast.boss.user, MON, MON))
    assert counts == {8: 1, 9: 1, 10: 2, 11: 2, 12: 1, 13: 1} and row["peak"] == 2


def test_one_person_with_two_shifts_in_an_hour_counts_once(cast):
    make_entry(cast.sam, MON, start=time(8), finish=time(10))
    make_entry(cast.sam, MON, start=time(9, 30), finish=time(11))
    counts, _ = day(staff_by_hour.report(cast.boss.user, MON, MON))
    assert counts == {8: 1, 9: 1, 10: 1}


def test_working_from_home_people_count_and_have_their_own_line(cast):
    make_entry(cast.sam, MON, start=time(8), finish=time(10))
    make_entry(cast.ann, MON, start=time(8), finish=time(10), wfh=True)
    report = staff_by_hour.report(cast.boss.user, MON, MON)
    counts, row = day(report)
    assert counts == {8: 2, 9: 2} and row["wfh"] == [1, 1]


def test_the_site_filter_keeps_only_that_sites_shifts(cast):
    ag, pmc = make_department("Reception AG"), make_department("Reception PMC")
    make_entry(cast.sam, MON, start=time(8), finish=time(10), department=ag)
    make_entry(cast.ann, MON, start=time(8), finish=time(10), department=pmc)
    make_entry(cast.nina, MON, start=time(8), finish=time(10))                       # no site
    boss = cast.boss.user
    assert day(staff_by_hour.report(boss, MON, MON, site="AG"))[0] == {8: 1, 9: 1}
    assert day(staff_by_hour.report(boss, MON, MON, site="PMC"))[0] == {8: 1, 9: 1}
    assert day(staff_by_hour.report(boss, MON, MON))[0] == {8: 3, 9: 3}


def test_the_team_filter_and_a_team_managers_scope(cast):
    make_entry(cast.sam, MON, start=time(8), finish=time(10))
    make_entry(cast.nina, MON, start=time(8), finish=time(10))
    assert day(staff_by_hour.report(cast.boss.user, MON, MON, team=cast.nursing))[0] == {8: 1, 9: 1}
    assert day(staff_by_hour.report(cast.lead.user, MON, MON))[0] == {8: 1, 9: 1}


def test_gps_are_left_out(cast):
    gp = make_person(first_name="Gina", team=cast.reception, is_gp=True)
    make_entry(gp, MON, start=time(8), finish=time(10))
    assert staff_by_hour.report(cast.boss.user, MON, MON)["columns"] == []


def test_the_range_is_capped_at_thirty_one_days_and_an_empty_range_has_rows_but_no_columns(cast):
    r = staff_by_hour.report(cast.boss.user, MON, MON + timedelta(days=90))
    assert len(r["rows"]) == 31 and r["columns"] == [] and all(row["counts"] == [] for row in r["rows"])
    swapped = staff_by_hour.report(cast.boss.user, MON + timedelta(days=2), MON)
    assert swapped["start"] == MON and len(swapped["rows"]) == 3


def test_the_page_and_the_download(cast):
    make_entry(cast.sam, MON, start=time(8), finish=time(10))
    assert client_for(cast.sam).get("/reports/staff-by-hour/").status_code == 403
    c = client_for(cast.lead)
    page = c.get(f"/reports/staff-by-hour/?from={MON}&to={MON}").content.decode()
    assert "08:00" in page and "09:00" in page and "of which WFH" in page and "GPs" in page
    r = c.get(f"/reports/staff-by-hour/?from={MON}&to={MON}&download=1")
    ws = load_workbook(io.BytesIO(r.content)).active
    assert [c.value for c in ws[1]][:4] == ["Date", "Day", "08:00", "09:00"] and ws["C2"].value == 1
    assert 'href="/reports/staff-by-hour/"' in c.get("/rota/").content.decode()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_shifts_report.py tests/test_staff_by_hour.py -q`
Expected: FAIL.

- [ ] **Step 3: The services**

`shifts/services/shift_report.py`:

```python
"""The Shifts report (REP-07, spec 5 section 9): every shift in a range for
the people the viewer manages, net hours as the Hours report counts them
(finish less start less break), overtime shown apart. Shifts covered by leave
are left out."""

from collections import OrderedDict
from datetime import timedelta

from people.services import access
from shifts.models import Entry

MAX_RANGE = timedelta(days=366)


def report(user, start, end, team=None, department=None, person=None):
    if end < start:
        start, end = end, start
    if end - start > MAX_RANGE:
        start = end - MAX_RANGE
    found = (Entry.objects.filter(person__in=access.managed_people(user), day__range=(start, end), kind=Entry.Kind.SHIFT,
                                  covered_by__isnull=True)
             .select_related("person__team", "department")
             .order_by("person__team__display_order", "person__team__name", "person__display_order", "person__last_name",
                       "person__first_name", "day", "position"))
    if team is not None:
        found = found.filter(person__team=team)
    if department is not None:
        found = found.filter(department=department)
    if person is not None:
        found = found.filter(person=person)
    blocks = OrderedDict()
    for e in found:
        block = blocks.setdefault(e.person_id, {"person": e.person, "rows": [], "total": timedelta(0), "overtime": timedelta(0)})
        block["rows"].append(e)
        block["total"] += e.hours
        if e.overtime:
            block["overtime"] += e.hours
    return {"blocks": list(blocks.values()), "start": start, "end": end,
            "grand_total": sum((b["total"] for b in blocks.values()), timedelta(0)),
            "grand_overtime": sum((b["overtime"] for b in blocks.values()), timedelta(0))}
```

`shifts/services/staff_by_hour.py`:

```python
"""Staff by hour (REP-07, spec 5 section 10): how many people are working in
each hour of each day. A shift counts in every hour it touches (08:00 to 16:15
is the 08:00 to 16:00 columns), once per person however many shifts they
have. Breaks are not subtracted (the pack does not place them). GPs are left
out: their sessions have no clock times here."""

from datetime import timedelta

from people.services import access
from shifts.models import Entry
from shifts.services.today import site_of

MAX_DAYS = 31


def _hours_of(entry):
    last = entry.finish.hour if entry.finish.minute else entry.finish.hour - 1
    return range(entry.start.hour, last + 1)


def report(user, start, end, site="", team=None):
    if end < start:
        start, end = end, start
    if (end - start).days >= MAX_DAYS:
        end = start + timedelta(days=MAX_DAYS - 1)
    people = access.managed_people(user).filter(is_gp=False)
    if team is not None:
        people = people.filter(team=team)
    shifts = (Entry.objects.filter(person__in=people, day__range=(start, end), kind=Entry.Kind.SHIFT, covered_by__isnull=True,
                                   start__isnull=False, finish__isnull=False).select_related("department"))
    per_day, first, last = {}, 24, -1
    for e in shifts:
        if site in ("AG", "PMC") and site_of(e) != site:
            continue
        hours = _hours_of(e)
        first, last = min(first, hours.start), max(last, hours.stop - 1)
        bucket = per_day.setdefault(e.day, {"all": {}, "wfh": {}})
        for h in hours:
            bucket["all"].setdefault(h, set()).add(e.person_id)
            if e.wfh:
                bucket["wfh"].setdefault(h, set()).add(e.person_id)
    columns = list(range(first, last + 1)) if last >= 0 else []
    rows, d = [], start
    while d <= end:
        bucket = per_day.get(d, {"all": {}, "wfh": {}})
        counts = [len(bucket["all"].get(h, ())) for h in columns]
        rows.append({"day": d, "counts": counts, "wfh": [len(bucket["wfh"].get(h, ())) for h in columns],
                     "peak": max(counts, default=0)})
        d += timedelta(days=1)
    return {"start": start, "end": end, "columns": columns, "labels": [f"{h:02d}:00" for h in columns],
            "rows": rows, "site": site, "team": team}
```

- [ ] **Step 4: The views, URLs, templates, nav**

`shifts/views/reports.py` — add the imports (`from exports import xlsx`, `from people.models import Department, Person, Team`, `from people.services import access`, `from shifts.services import shift_report, staff_by_hour`) and:

```python
def _pick(model, value):
    """The row with this id from a filter, else None."""
    return model.objects.filter(pk=int(value)).first() if value and value.isascii() and value.isdigit() else None


@login_required
@access.manager_required
def shifts_report(request):
    start, end = _dates(request)
    person_choices = access.managed_people(request.user).order_by("name")
    team, department = _pick(Team, request.GET.get("team")), _pick(Department, request.GET.get("department"))
    person = person_choices.filter(pk=request.GET["person"]).first() if request.GET.get("person", "").isdigit() else None
    data = shift_report.report(request.user, start, end, team, department, person)
    if request.GET.get("download"):
        rows = [[e.day, e.day.strftime("%a"), e.person.name, e.person.team.name if e.person.team else "",
                 e.department.name if e.department else "", e.start.strftime("%H:%M"), e.finish.strftime("%H:%M"),
                 e.break_minutes, xlsx.Hours(int(e.hours.total_seconds())),
                 e.get_overtime_display() if e.overtime else "", e.text]
                for b in data["blocks"] for e in b["rows"]]
        rows.append(["Total", "", "", "", "", "", "", "", xlsx.Hours(int(data["grand_total"].total_seconds())), "", ""])
        header = ["Date", "Day", "Name", "Team", "Department", "Start", "Finish", "Break (min)", "Net hours", "Overtime", "Comment"]
        return xlsx.response(xlsx.workbook([("Shifts", header, rows)]), f"shifts-{data['start']}-{data['end']}.xlsx")
    for b in data["blocks"]:
        b["total_text"], b["overtime_text"] = fmt.duration(b["total"]), fmt.duration(b["overtime"])
        for e in b["rows"]:
            e.hours_text = fmt.duration(e.hours)
    return render(request, "shifts/shifts_report.html", {
        "page_title": "Shifts", "data": data, "grand_text": fmt.duration(data["grand_total"]), "start": data["start"], "end": data["end"],
        "teams": access.managed_teams(request.user).filter(active=True), "departments": Department.objects.filter(archived=False),
        "people": person_choices, "team": team, "department": department, "person": person})


@login_required
@access.manager_required
def staff_by_hour_report(request):
    start, end = _dates(request)
    site = request.GET.get("site", "")
    site = site if site in ("AG", "PMC") else ""
    team = _pick(Team, request.GET.get("team"))
    data = staff_by_hour.report(request.user, start, end, site, team)
    if request.GET.get("download"):
        rows = []
        for r in data["rows"]:
            rows.append([r["day"], r["day"].strftime("%a"), *r["counts"], r["peak"]])
            rows.append([r["day"], "of which WFH", *r["wfh"], ""])
        return xlsx.response(xlsx.workbook([("Staff by hour", ["Date", "Day", *data["labels"], "Peak"], rows)]),
                             f"staff-by-hour-{data['start']}-{data['end']}.xlsx")
    return render(request, "shifts/staff_by_hour.html", {
        "page_title": "Staff by hour", "data": data, "start": data["start"], "end": data["end"], "site": site, "team": team,
        "teams": access.managed_teams(request.user).filter(active=True)})
```

(`_dates` is the file's existing helper: it defaults to this Monday and 6 days on. `fmt` is the file's existing `from shifts.services import render as fmt`.)

`shifts/urls.py`: add `path("reports/shifts/", reports.shifts_report, name="report-shifts"),` and `path("reports/staff-by-hour/", reports.staff_by_hour_report, name="report-staff-by-hour"),` next to the hours route.

`templates/shifts/shifts_report.html`:

```html
{% extends "base.html" %}
{% block title %}Shifts · AMG Shift Central{% endblock %}
{% block topbar_actions %}<a class="topbar-action" href="?{{ request.GET.urlencode }}{% if request.GET %}&amp;{% endif %}download=1">Download</a>{% endblock %}
{% block content %}
<form class="filters" method="get">
  <label>From <input type="date" name="from" value="{{ start|date:'Y-m-d' }}"></label>
  <label>To <input type="date" name="to" value="{{ end|date:'Y-m-d' }}"></label>
  <label>Team <select name="team"><option value="">All</option>{% for t in teams %}<option value="{{ t.pk }}"{% if team and t.pk == team.pk %} selected{% endif %}>{{ t.name }}</option>{% endfor %}</select></label>
  <label>Department <select name="department"><option value="">All</option>{% for d in departments %}<option value="{{ d.pk }}"{% if department and d.pk == department.pk %} selected{% endif %}>{{ d.name }}</option>{% endfor %}</select></label>
  <label>Person <select name="person"><option value="">Anyone</option>{% for p in people %}<option value="{{ p.pk }}"{% if person and p.pk == person.pk %} selected{% endif %}>{{ p.name }}</option>{% endfor %}</select></label>
  <button class="btn btn-quiet" type="submit">Refresh</button>
</form>
{% for b in data.blocks %}
<section class="report-block">
  <h2>{{ b.person.name }} — {{ b.rows|length }} shift{{ b.rows|length|pluralize }} / {{ b.total_text }}{% if b.overtime %} ({{ b.overtime_text }} overtime){% endif %}</h2>
  <table class="table">
    <thead><tr><th>Date</th><th>Start</th><th>Finish</th><th>Break</th><th>Net hours</th><th>Overtime</th><th>Department</th><th>Comment</th></tr></thead>
    <tbody>
    {% for e in b.rows %}
      <tr><td>{{ e.day|date:"D j M Y" }}</td><td>{{ e.start|time:"H:i" }}</td><td>{{ e.finish|time:"H:i" }}</td>
          <td>{% if e.break_minutes %}{{ e.break_minutes }} min{% endif %}</td><td>{{ e.hours_text }}</td>
          <td>{% if e.overtime %}{{ e.get_overtime_display }}{% endif %}</td><td>{{ e.department.name|default:"" }}</td><td>{{ e.text }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% empty %}<p>No shifts in this range.</p>{% endfor %}
{% if data.blocks %}<p><strong>Total: {{ grand_text }}</strong></p>{% endif %}
{% endblock %}
```

`templates/shifts/staff_by_hour.html`:

```html
{% extends "base.html" %}
{% block title %}Staff by hour · AMG Shift Central{% endblock %}
{% block topbar_actions %}<a class="topbar-action" href="?{{ request.GET.urlencode }}{% if request.GET %}&amp;{% endif %}download=1">Download</a>{% endblock %}
{% block content %}
<form class="filters" method="get">
  <label>From <input type="date" name="from" value="{{ start|date:'Y-m-d' }}"></label>
  <label>To <input type="date" name="to" value="{{ end|date:'Y-m-d' }}"></label>
  <label>Site <select name="site"><option value="">Both</option><option value="AG"{% if site == "AG" %} selected{% endif %}>AG</option><option value="PMC"{% if site == "PMC" %} selected{% endif %}>PMC</option></select></label>
  <label>Team <select name="team"><option value="">All</option>{% for t in teams %}<option value="{{ t.pk }}"{% if team and t.pk == team.pk %} selected{% endif %}>{{ t.name }}</option>{% endfor %}</select></label>
  <button class="btn btn-quiet" type="submit">Refresh</button>
</form>
<p class="muted">People working at any point in each hour; breaks are not taken off. Shifts whose department has no AG or PMC in its name show under Both only. GPs are not included: their sessions have no clock times here.</p>
<div class="table-scroll"><table class="table staff-by-hour">
  <thead><tr><th>Day</th>{% for label in data.labels %}<th>{{ label }}</th>{% endfor %}<th>Peak</th></tr></thead>
  <tbody>
  {% for r in data.rows %}
    <tr><td>{{ r.day|date:"D j M" }}</td>{% for n in r.counts %}<td>{{ n }}</td>{% endfor %}<td><strong>{{ r.peak }}</strong></td></tr>
    <tr class="muted"><td>of which WFH</td>{% for n in r.wfh %}<td>{{ n }}</td>{% endfor %}<td></td></tr>
  {% endfor %}
  </tbody>
</table></div>
{% endblock %}
```

`ui/context_processors.py`: managers' `report_children` gains `{"label": "Shifts", "url": "/reports/shifts/"}` and `{"label": "Staff by hour", "url": "/reports/staff-by-hour/"}` after Dashboard (and before the existing Hours entry); `static/css/components.css`: `.table-scroll { overflow-x: auto; } .staff-by-hour td, .staff-by-hour th { text-align: center; } .staff-by-hour td:first-child { text-align: left; white-space: nowrap; }`.

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_shifts_report.py tests/test_staff_by_hour.py tests/test_shifts_hours.py tests/test_shell.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add shifts ui templates static tests
git commit -m "Shifts: the Shifts report and Staff by hour, on screen and as Excel

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---

### Task 15: Demo data for the staging box

**Files:**
- Modify: `people/management/commands/seed_demo.py`, `tests/test_seed_demo.py`

**Interfaces:**
- Consumes: `open_shifts.post/approve`, `notices.post`, `messages.send`, `uploads.services.add`.
- Produces: `seed_demo` also writes three open shifts (one with a waiting claim, one filled), two notices, one message to everyone and one shared sample document; idempotent; no mail and no push.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_seed_demo.py`; add `from messaging.models import Message, Notice`, `from shifts.models import OpenShift, OpenShiftClaim`, `from uploads.models import UploadedFile` to its imports)

```python
# --- engagement (spec 5) --------------------------------------------------------

@pytest.fixture
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


def engagement():
    return {m.__name__: m.objects.count() for m in (OpenShift, OpenShiftClaim, Notice, Message, UploadedFile)}


def test_it_seeds_open_shifts_notices_a_message_and_a_document(people, media):
    seed()
    assert engagement() == {"OpenShift": 3, "OpenShiftClaim": 2, "Notice": 2, "Message": 1, "UploadedFile": 1}
    assert OpenShift.objects.filter(state="filled").count() == 1
    assert OpenShiftClaim.objects.filter(state="waiting").count() == 1
    filled = OpenShift.objects.get(state="filled")
    assert Entry.objects.filter(person=filled.filled_by, day=filled.day, start=filled.start).exists()


def test_the_engagement_seed_sends_no_mail_and_queues_no_push(people, media, push_on):
    from tests.factories import make_push_device
    make_push_device(next(iter(people.values())))
    seed()
    assert Outbox.objects.count() == 0 and not mail.outbox


def test_a_second_run_adds_no_engagement_rows(people, media):
    seed()
    before = engagement()
    seed()
    assert engagement() == before


def test_the_report_mentions_the_engagement_rows(people, media):
    assert "open shifts" in seed()
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_seed_demo.py -q -k "engagement or open_shifts"`
Expected: FAIL.

- [ ] **Step 3: Implement**

In `seed_demo.py` add imports: `from django.core.files.uploadedfile import SimpleUploadedFile`, `from messaging.models import Message, Notice`, `from messaging.services import messages as message_service, notices as notice_service`, `from shifts.models import Entry, OpenShift, OpenShiftClaim`, `from shifts.services import open_shifts`, `from uploads.models import UploadedFile`, `from uploads import services as upload_services` (merge with the file's existing `shifts.models`/`messaging` imports rather than duplicating them). In `_seed`, after `self._leave(...)`, add `self._engagement(actor, people, today, counts)`. Add the method:

```python
    # --- engagement (spec 5) --------------------------------------------------------

    def _engagement(self, actor, people, today, counts):
        """Open shifts, notices, a message and a shared document, so the new
        pages are not empty. Posts and the one approval go through the service
        layer; the waiting claim is written directly, because claiming needs a
        signed-in login and the cast may not have one yet. No mail: _no_mail
        holds for the whole run."""
        first = max(_monday_on_or_after(today), today + timedelta(days=1))
        by_first = {m.first: p for m, p in people.items()}
        reception = Team.objects.filter(name="Reception").first()
        nursing = Team.objects.filter(name="Nursing").first()
        if reception is None or nursing is None:
            return
        desk = Department.objects.filter(name="Reception AG").first()
        plan = (
            ("demo data: front desk cover", reception, first + timedelta(days=1), time(9), time(13), [reception], desk),
            ("demo data: phones", reception, first + timedelta(days=2), time(14), time(18), [reception], desk),
            ("demo data: clinic support", nursing, first + timedelta(days=3), time(8, 30), time(12, 30), [nursing], None),
        )
        posts = []
        for comment, team, day, start, finish, audience, dept in plan:
            post = OpenShift.objects.filter(comment=comment).first()
            if post is None:
                post = open_shifts.post(actor, team, day, start, finish, 0, dept, comment, False, audience)
                counts["open_shifts"] += 1
            posts.append(post)
        sophie, liam = by_first.get("Sophie"), by_first.get("Liam")
        if sophie is not None and not posts[0].claims.exists():
            OpenShiftClaim.objects.create(open_shift=posts[0], person=sophie, overtime="toil", note="Happy to cover")
        if liam is not None and posts[1].state == OpenShift.State.OPEN and not posts[1].claims.exists():
            claim = OpenShiftClaim.objects.create(open_shift=posts[1], person=liam)
            open_shifts.approve(actor, claim)
        if not Notice.objects.filter(title="Fire drill on Thursday").exists():
            notice_service.post(actor, "Fire drill on Thursday", "Meet at the front car park at 10:30. This is a test notice.", True, [], pinned=True)
            counts["notices"] += 1
        if not Notice.objects.filter(title="Car park resurfacing").exists():
            notice_service.post(actor, "Car park resurfacing", "The staff car park is closed next Monday. This is a test notice.", False, [reception.pk])
            counts["notices"] += 1
        if not Message.objects.filter(subject="Welcome to the staging box").exists():
            message_service.send(actor, "Welcome to the staging box", "This is demo data. Nothing here is real.", everyone=True)
            counts["messages"] += 1
        if not UploadedFile.objects.filter(title="Staff handbook (sample)").exists():
            sample = SimpleUploadedFile("staff-handbook-sample.txt", b"Sample handbook. This is demo data.\n")
            upload_services.add(actor, sample, "Staff handbook (sample)", UploadedFile.Kind.SHARED)
            counts["documents"] += 1
```

In `_report`, inside the `else` after the time-off line add:

```python
            out(f"  engagement: {counts['open_shifts']} open shifts, {counts['notices']} notices, "
                f"{counts['messages']} message, {counts['documents']} document")
```

Note the seed's `Command` docstring and `--help` mention "no mail" already; add one sentence listing the engagement rows. The `(first + 1, 2, 3 days)` posts avoid weekends only by luck; that is fine for demo data (a Saturday clinic is allowed, ROTA-05).

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_seed_demo.py -q`
Expected: PASS (the earlier seed tests included: they count tables, which this release does not enlarge except `Outbox`, which stays 0).

- [ ] **Step 5: Commit**

```bash
git add people tests
git commit -m "People: seed_demo adds open shifts, notices, a message and a sample document, with no mail or push

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---

### Task 16: The browser test, the guide, the README, the amendments

**Files:**
- Create: `tests/e2e/test_open_shifts.py`, `docs/admin/engagement.md`
- Modify: `README.md`, `docs/admin/README.md`, `docs/requirements/2026-10-29-proposed-amendments.md`, `docs/superpowers/specs/2026-11-01-engagement-design.md`

- [ ] **Step 1: The end-to-end test**

`tests/e2e/test_open_shifts.py`:

```python
"""A manager posts an open shift, a staff member claims it, the manager
approves, and the shift is on the rota. Two browser contexts, each signed in
with a password as test_grid does."""

from datetime import date

import pytest
from playwright.sync_api import expect

from tests import clock
from tests.factories import make_person, make_team, make_team_manager, make_user_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.today(clock.LATE_2026)]
DAY = "2026-11-09"       # the Monday after the pinned Monday


@pytest.fixture
def cast(live_server):
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team, start_date=date(2020, 1, 6))
    make_team_manager(lead, team)
    sam = make_person(first_name="Sam", team=team, start_date=date(2020, 1, 6))
    return make_user_for(lead, password="pw"), make_user_for(sam, password="pw")


def _sign_in(page, live_server, user, next_path):
    page.goto(f"{live_server.url}/accounts/login/?next={next_path}")
    page.fill("input[name=username]", user.email)
    page.fill("input[name=password]", "pw")
    page.click("button[type=submit]")


def test_post_claim_approve_and_see_it_on_the_rota(browser, page, live_server, cast):
    lead, sam = cast
    _sign_in(page, live_server, lead, "/rota/open/")
    page.click("text=Post an open shift")
    page.wait_for_selector("#dialog form")
    page.select_option("#dialog select[name=team]", label="Reception")
    page.fill("#dialog input[name=day]", DAY)
    page.fill("#dialog input[name=start]", "09:00")
    page.fill("#dialog input[name=finish]", "13:00")
    page.check("#dialog input[name=audience]")
    page.click("#dialog button.btn-dark")
    expect(page.locator(".open-card")).to_have_count(1)

    other = browser.new_context().new_page()
    _sign_in(other, live_server, sam, "/rota/open/")
    other.click(".open-card >> text=Claim")
    other.wait_for_selector("#dialog form")
    other.click("#dialog button.btn-dark")
    expect(other.locator(".open-card")).to_contain_text("You've claimed this")

    page.reload()
    page.click(".open-card >> text=Decide")
    page.wait_for_selector("#dialog form")
    page.click("#dialog button[name=action][value=approve]")
    page.goto(f"{live_server.url}/rota/?from={DAY}")
    page.wait_for_selector("table.rota-grid")
    sam_monday = page.locator("tr:has(th.rota-name:has-text('Sam')) td").first
    expect(sam_monday.locator(".tile-shift")).to_have_count(1)
    expect(sam_monday).to_contain_text("09:00")


def test_the_notifications_page_opens_from_the_menu(page, live_server, cast):
    _sign_in(page, live_server, cast[1], "/rota/")
    page.click("a[aria-label=Notifications]")
    expect(page.locator("h2")).to_contain_text("Notifications on this phone")
```

Run: `E2E=1 E2E_CHROMIUM=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/e2e/test_open_shifts.py -q`
Expected: PASS.

- [ ] **Step 2: The admin guide**

Create `docs/admin/engagement.md` with these sections, written for the practice manager and assistants in the voice of `docs/admin/leave.md` (read its first 40 lines for tone and heading style first):

1. **Open shifts**: posting (owning team, audience, overtime is the claimant's choice), claims and the manager's decision, clashes only warn, a whole day of leave refuses approval, withdrawing a post, what staff see, who is told and when.
2. **Messages**: who can send (managers), to people/teams/everyone, staff read only, the Inbox badge, "Message [name]" on the grid, Sent messages and who has read.
3. **The notice board**: plain text, pinning, "show until", the optional "also tell staff".
4. **Uploads**: the shared area (managers add, everyone reads), a person's documents from their profile (their managers only, the person cannot see them), allowed types and the 10 MB limit, downloads only, no virus scanning, activity-log entries.
5. **The Outbox**: statuses, filters, the badge, what "Not configured" means, text blanked after 12 months.
6. **Dashboard, Shifts and Staff by hour**: what each shows, how Staff by hour counts (any part of the hour, no breaks off, GPs excluded, site rule), Excel download.
7. **Putting the app on a phone**: Android (Chrome menu, Install app / Add to Home screen), iPhone (Safari Share, Add to Home Screen, open it from the Home Screen, then Notifications ▸ Turn on); what a notification shows; turning it off; why a phone may stop receiving (permission blocked, removed device).
8. **Setting up phone notifications (for whoever runs the server)**: the three settings, `vapid_keys`, the timer; pointing at README.

Add the guide to `docs/admin/README.md`'s list.

- [ ] **Step 3: The README**

`README.md`:
- Environment table: add one row for `VAPID_PRIVATE_KEY_FILE`, `VAPID_PUBLIC_KEY`, `VAPID_SUBJECT` ("Phone notifications; all three, with the key file present, or push is off"), one for `MEDIA_ROOT`, `UPLOAD_MAX_BYTES` (default `<state dir>/media`... note the systemd unit's state directory: set `MEDIA_ROOT=/var/lib/shift-central/media`), and one for `OUTBOX_BODY_MONTHS` (default 12, 0 keeps text).
- A new section **Phone notifications (optional)** after the Notify-staff/mail section:

```bash
install -d -o root -g shift-central -m 750 /etc/shift-central
cd /srv/shift-central && .venv/bin/python manage.py vapid_keys --out /etc/shift-central/vapid.pem --group shift-central --subject mailto:you@example.org
# add the three lines it prints to /etc/shift-central.env
systemctl restart shift-central
systemctl enable --now shift-central-push.timer
```

  with two sentences: replacing the key cuts off every registered phone until each person turns notifications on again, so keep a copy; a phone's lock screen shows only the subject.
- The install lines (the `systemctl enable --now …timer` block): add `shift-central-push.timer` and say it is only worth enabling once the three settings are set.
- The "stop" and "start" lists in the upgrade/restore section: add `shift-central-push.timer` to both, with the same "only the ones that were enabled" caution.
- The backups section: say the nightly archive now also holds `media-DATE.tar.gz` (the uploaded documents), kept 30 days, and that the off-site push covers the whole state directory.
- An **Upgrading to the engagement release** checklist: `git pull`, `.venv/bin/pip install -r requirements.txt`, `deploy/manage migrate`, `deploy/manage collectstatic --noinput`, copy the new units (`cp deploy/shift-central-push.* /etc/systemd/system/ && systemctl daemon-reload`), set `MEDIA_ROOT`, restart, optionally set up phone notifications; and the note that existing phones pick up the service worker on their next visit.

- [ ] **Step 4: The amendments postscript and the spec**

Append to `docs/requirements/2026-10-29-proposed-amendments.md`:

```markdown
## Postscript, 1 November 2026 (developers), engagement

Built as the pack asks (spec 5), with these choices for you to know about:

- **Messages are one-way.** Managers send to people, teams or everyone;
  staff read them in the app, by email and (if they turn it on) by
  notification. Staff cannot send or reply. The notice board is managers-only too.
- **Phone notifications are the phone's own choice.** A person turns them on,
  per phone, on the Notifications page; email always still arrives. A
  notification shows the subject line only, never the message.
- **Open shifts:** the person claiming chooses normal hours, overtime paid or
  overtime TOIL (ROTA-06), and the approving manager can change it. A clash
  with the person's own rota warns the manager but does not stop approval,
  except a whole day of approved leave, which does.
- **Documents:** the shared area is for the whole practice to read; what is
  kept on a person is seen by their managers only, not by the person.
- **The Outbox keeps the text of messages for a year**, then removes the text
  and keeps who, when and the subject. Say if you want a different period.
- **The three reports** are defined in the spec (dashboard, shifts, staff by
  hour). Staff by hour counts people working at any point in each hour, takes
  no breaks off and leaves out GPs; if the FindMyShift screenshots show
  something different, tell us.
```

In the spec, change the status line to `**Status:** approved in conversation; written spec approved 2026-11-01; built and reviewed, with the deviations recorded at the end` and append a section `## Deviations recorded during the build` listing these (and any others met while building):

```markdown
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
```

- [ ] **Step 5: Run the checks and commit**

Run: `python -m pytest -q` (the whole suite) and `ruff check .`
Expected: PASS; no output from ruff.

```bash
git add tests docs README.md
git commit -m "Docs: the engagement guide, the README's phone-notification and upgrade steps, the amendments postscript; the browser test

Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_011dh1W8Ah5aXH6H2WmXy7qD"
```

---

### Task 17: Final whole-branch review, fix wave, finish

- [ ] **Step 1: The full checks, as CI runs them**

```bash
ruff check .
DEBUG=1 python manage.py makemigrations --check --dry-run
python -m pytest -q
E2E=1 E2E_CHROMIUM=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/e2e -q
DEBUG=0 SECRET_KEY=ci-only-4f8c1e2b9a7d3f6e0c5b8a1d2e4f7a9c3b6d8e0f1a2c4e6b8d0f2a4c6e8b0d1f3a ALLOWED_HOSTS=ci CSRF_TRUSTED_ORIGINS=https://ci EMAIL_HOST=smtp.example DEFAULT_FROM_EMAIL="Shift Central <shift-central@example.org>" python manage.py collectstatic --noinput
DEBUG=0 SECRET_KEY=ci-only-4f8c1e2b9a7d3f6e0c5b8a1d2e4f7a9c3b6d8e0f1a2c4e6b8d0f2a4c6e8b0d1f3a ALLOWED_HOSTS=ci CSRF_TRUSTED_ORIGINS=https://ci EMAIL_HOST=smtp.example DEFAULT_FROM_EMAIL="Shift Central <shift-central@example.org>" python manage.py check --deploy
git status --short
```
Expected: all pass; the last command shows nothing uncommitted except `staticfiles/` if it is untracked (do not commit it).

- [ ] **Step 2: Review the whole branch against the spec**

Use the `superpowers:requesting-code-review` skill over `git diff main...HEAD`, giving the reviewer `docs/superpowers/specs/2026-11-01-engagement-design.md` and asking specifically about: the permission matrix in spec section 13 (every view, 404 not 403 for ids); anything that could put a message body, note or comment in a push payload, log line or `Outbox.error`; the upload path (types, signatures, names, atomic write, download headers); the approval transaction (races, `settle_baseline`, leave refusal); and the service worker (nothing but `/offline/` is ever stored).

- [ ] **Step 3: Fix wave**

Fix every finding that is real (write the failing test first), record each as a deviation in the spec's last section, rerun Step 1.

- [ ] **Step 4: Finish**

Use `superpowers:finishing-a-development-branch`: push `claude/hopeful-keller-lankio`, open the pull request against `main` (body: what the four parts do, the migrations, the new timer and settings, and the README's upgrade steps; end with the session lines), subscribe to its activity. After merge, on the staging box: `git pull`, `.venv/bin/pip install -r requirements.txt`, `deploy/manage migrate`, `deploy/manage collectstatic --noinput`, copy the push units, restart; then run `seed_demo` again to add the engagement demo rows. The installer script for a fresh staging box (`install-staging.sh`, kept outside this repository) gains the push unit and the `MEDIA_ROOT` line in a follow-up.
