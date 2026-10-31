# Absence and payroll (spec 4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sickness instances and triggers over Sick leave bookings, the join-on warning, long sickness and the return flag, the past schedule section for 2026 sickness, converting annual leave to sickness, the leaver and year-end flags from one daily command, the monthly payroll report with a sent snapshot and corrections, and the sickness and leave one-pagers as PDF or Excel.

**Architecture:** No second sickness record: an approved booking of a leave type flagged `sickness` is one instance of absence, and `leave/services/sickness.py` computes the rolling window, triggers, long sickness and the join-on rule over those bookings. The past schedule's 2026 entries are bookings flagged `dates_only` (no costed days). Two thin new apps: `absence` (the sickness screens, convert, the sickness one-pager) and `payroll` (one model, `PayrollRun`, the monthly figures, corrections and the Excel), plus a shared `exports/` package (openpyxl and reportlab writers). The leaver, return and year-end flags are `leave` services driven by the HR sync and a daily command. Everything is server-rendered through `modal.js`; the island is untouched.

**Tech Stack:** Django 5.2 / Python 3.13 / SQLite (WAL); Unfold admin; openpyxl 3.1.5 and reportlab 5.1.0 (new, pure-Python wheels; reportlab pulls pillow); pytest; Playwright for one e2e test. No frontend change (`static/dist` stays as it is).

**Spec:** `docs/superpowers/specs/2026-10-31-absence-payroll-design.md` (binding). Also read the leave spec `docs/superpowers/specs/2026-10-31-leave-design.md` sections 2 to 4 before Tasks 2 to 6, and `docs/requirements/05-leave-policy.md` LEAVE-40 to 44 plus `06-leave-worked-examples.md` SICK-01 to 04, KIT-01, LV-07b, LV-15a, LV-15b, LV-16, LV-25 before writing any worked-example test.

## Global Constraints

- Every write goes through a service; views never touch models. Services audit through `people.services.audit.record_as(actor, model, object_id, changes, note)` under `leave.booking`, `leave.adjustment`, `leave.yearend` (object_id the person's pk) or `payroll.payrollrun` (object_id the run's pk).
- Secrets from the environment only. No key, token or password in any repo file, test fixture or log line. Log lines, `Outbox.error`, `SyncRun.message` and the GP leave feed never carry a description, a note, a reason or a figure.
- Figures are never stored except the payroll snapshot (`PayrollRun.figures`). Every screen reads `leave.services.balances` and `leave.services.sickness`.
- Spreadsheet and PDF cells are written as text, never as formulas: openpyxl cells get `data_type = "s"` through `exports.xlsx`; a PDF table cell is a string.
- Costs and balances are **integer seconds**; screens show `hours.fmt()` ("7 h 30 min"); the Excel shows decimal hours to two places.
- Dates and "today" are Europe/London: `timezone.localdate()`. Tests run under the pinned clock (`tests/clock.py`: `PIN` = 2 Nov 2026 09:00; `@pytest.mark.today(date)` per test or module).
- CSP forbids inline scripts and handlers: no `onclick`, no `<script>` in templates; dialogs use `data-dialog`, `data-dialog-form`, `data-submit-on-change`, `data-dialog-get`, `{"refresh": true}`.
- Commit messages: `Area: what changed` (Leave:, Absence:, Payroll:, People:, Shifts:, Docs:, Deploy:). Every commit ends with the two trailer lines given in the session (Co-Authored-By and Claude-Session). No model identifier anywhere in a repo file.
- Tests: `.venv/bin/python -m pytest -q`; `.venv/bin/ruff check .` (or `ruff check .`) clean; `DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run` clean. The e2e: `E2E=1 E2E_CHROMIUM=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/e2e -q`.
- One implementer at a time; tasks run in order. Branch `claude/hopeful-keller-lankio` in `/home/user/shift-central`; the rota repo is untouched by this release.
- New dependencies are already installed in `.venv` (openpyxl 3.1.5, et_xmlfile 2.0.0, reportlab 5.1.0, pillow 13.0.0); Task 1 pins them in `requirements.txt`.

---

## File structure

**New:**

```
absence/__init__.py apps.py forms.py urls.py
absence/services/__init__.py convert.py onepager.py
absence/views/__init__.py convert.py past.py onepager.py
templates/absence/ _sickness_preview.html convert_dialog.html past.html past_dialog.html sickness_summary.html
payroll/__init__.py apps.py admin.py models.py urls.py views.py forms.py
payroll/migrations/0001_initial.py
payroll/services/__init__.py report.py runs.py xlsx.py
templates/payroll/ report.html sent_dialog.html
exports/__init__.py xlsx.py pdf.py
leave/models/yearend.py
leave/migrations/0003_absence.py
leave/services/sickness.py leavers.py returns.py yearend.py sessions.py summary.py
leave/views/yearend.py summary.py
leave/management/commands/daily_flags.py
templates/leave/ year_end.html year_end_dialog.html summary.html
people/migrations/0007_leaver_flags.py
deploy/shift-central-daily-flags.service .timer
static/img/logo-dark.png
docs/admin/absence.md
tests/test_absence_models.py test_absence_sickness.py test_absence_convert.py test_absence_views.py test_absence_onepager.py
      test_leave_flags.py test_leave_yearend.py test_leave_summary.py test_exports.py test_payroll_report.py test_payroll_views.py
tests/e2e/test_absence.py
```

**Modified:** `config/settings.py` (INSTALLED_APPS), `config/urls.py`, `requirements.txt`, `leave/models/types.py`, `leave/models/booking.py`, `leave/models/__init__.py`, `leave/admin.py`, `leave/forms.py`, `leave/services/bookings.py`, `leave/services/notify.py`, `leave/services/types.py`, `leave/services/serialize.py`, `leave/views/__init__.py`, `leave/views/add.py`, `leave/views/detail.py`, `leave/views/list.py`, `leave/views/report.py`, `leave/views/statement.py`, `leave/urls.py`, `templates/leave/{add_dialog,view_dialog,list,report,_statement,type_dialog,types}.html`, `people/models/person.py`, `people/services/hr_sync.py`, `people/services/health.py`, `people/views/activity.py`, `templates/people/_health.html`, `shifts/services/today.py`, `ui/context_processors.py`, `tests/factories.py`, `tests/test_deploy_units.py`, `tests/test_shifts_today.py`, `docs/admin/{setup,leave,people,README}.md`, `README.md`, `docs/requirements/2026-10-29-proposed-amendments.md`, `docs/superpowers/specs/2026-10-31-leave-design.md` (two Revisit items settled), the spec's deviations section.

---

### Task 1: Models, seeds, the two new apps' skeletons, the dependency pins

**Files:**
- Create: `absence/__init__.py`, `absence/apps.py`, `absence/urls.py`, `absence/services/__init__.py`, `absence/views/__init__.py`, `payroll/__init__.py`, `payroll/apps.py`, `payroll/models.py`, `payroll/admin.py`, `payroll/urls.py`, `payroll/services/__init__.py`, `payroll/migrations/0001_initial.py`, `leave/models/yearend.py`, `leave/migrations/0003_absence.py`, `people/migrations/0007_leaver_flags.py`
- Modify: `config/settings.py:45-62` (INSTALLED_APPS), `config/urls.py`, `requirements.txt`, `leave/models/types.py`, `leave/models/booking.py`, `leave/models/__init__.py`, `leave/admin.py`, `people/models/person.py:38-48`, `tests/factories.py`
- Test: `tests/test_absence_models.py`

**Interfaces:**
- Produces: `LeaveType.sickness`, `LeaveType.flag_return` (bool, default False; seeded true on Sick leave, and on Maternity and Adoption / shared parental respectively); `Booking.dates_only` (bool, default False; constraint `dates_only_is_whole_days`), `Booking.return_flagged_at` (nullable datetime); `leave.YearEnd` with fields `person, year_ended, notified_at, annual_remaining, toil_remaining, annual_carried, annual_lost, toil_lost, decided_by, decided_at, note` and property `decided`; `Person.leaver_flagged_for`, `Person.leaver_week_flagged_for` (nullable dates); `payroll.PayrollRun` with `month, sent_at, sent_by, people, figures`; factory `make_sick(person, first, last=None, dates_only=False, **kw)`; apps `absence` and `payroll` installed with empty `urlpatterns`.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_models.py`:

```python
"""The fields and tables spec 4 adds: the two type flags and their seeds,
dates-only bookings, the year-end row, the leaver flag dates, the payroll
run, and the two new apps."""

from datetime import date
from pathlib import Path

import pytest
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from leave.models import Booking, LeaveType, YearEnd
from payroll.models import PayrollRun
from tests.factories import make_booking, make_person, make_sick, make_user_for

pytestmark = pytest.mark.django_db
ROOT = Path(__file__).resolve().parents[1]


def test_sick_leave_counts_as_sickness_and_family_leave_flags_the_return():
    assert LeaveType.objects.get(name="Sick leave").sickness is True
    assert set(LeaveType.objects.filter(flag_return=True).values_list("name", flat=True)) == {"Maternity", "Adoption / shared parental"}
    assert LeaveType.objects.filter(sickness=True).count() == 1
    assert LeaveType.objects.get(name="Paternity").flag_return is False


def test_a_dates_only_booking_is_whole_days():
    sam = make_person()
    row = make_sick(sam, date(2026, 3, 2), date(2026, 3, 6), dates_only=True)
    assert row.dates_only and row.part == "whole" and row.return_flagged_at is None
    with pytest.raises(IntegrityError):
        make_booking(sam, date(2026, 3, 9), part="am", dates_only=True, type_name="Sick leave")


def test_make_sick_books_the_seeded_type_approved():
    sam = make_person()
    row = make_sick(sam, date(2027, 1, 4))
    assert row.type.name == "Sick leave" and row.type.sickness and row.status == "approved" and row.last_day == date(2027, 1, 4)


def test_one_year_end_row_per_person_and_year():
    sam = make_person()
    row = YearEnd.objects.create(person=sam, year_ended=date(2027, 1, 1), annual_remaining=72000, toil_remaining=3600)
    assert row.decided is False
    row.decided_at = timezone.now()
    assert row.decided is True
    with pytest.raises(IntegrityError):
        YearEnd.objects.create(person=sam, year_ended=date(2027, 1, 1))


def test_a_person_starts_with_no_leaver_flags():
    sam = make_person()
    assert sam.leaver_flagged_for is None and sam.leaver_week_flagged_for is None


def test_a_payroll_run_keeps_its_figures_as_json():
    boss = make_person(first_name="Boss")
    user = make_user_for(boss, is_all_teams_manager=True)
    run = PayrollRun.objects.create(month=date(2027, 1, 1), sent_by=user, people=2,
                                    figures={"generated_at": "2027-01-24T10:00:00+00:00", "rows": {"1": {"worked": 27000}}})
    run.refresh_from_db()
    assert run.figures["rows"]["1"]["worked"] == 27000 and run.sent_at is not None
    assert str(run) == "Payroll January 2027"


def test_the_two_apps_are_installed_and_the_libraries_pinned():
    assert "absence" in settings.INSTALLED_APPS and "payroll" in settings.INSTALLED_APPS
    pins = (ROOT / "requirements.txt").read_text()
    assert "openpyxl==3.1.5" in pins and "reportlab==5.1.0" in pins and "et_xmlfile==2.0.0" in pins and "pillow==13.0.0" in pins
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `cd /home/user/shift-central && .venv/bin/python -m pytest tests/test_absence_models.py -q`
Expected: ImportError (`leave.models` has no `YearEnd`; no `payroll` module).

- [ ] **Step 3: The leave model changes**

`leave/models/types.py`, after `seeded`:

```python
    # Spec 4. A type that counts as sickness makes instances of absence
    # (LEAVE-40); a type that flags the return emails the managers when a
    # booking of it ends (LEAVE-29). Both are a manager's to set.
    sickness = models.BooleanField(default=False)
    flag_return = models.BooleanField(default=False)
```

`leave/models/booking.py`, in `Booking` after `reminded_at`:

```python
    # Spec 4. A past schedule entry (MIG-05): approved, dates only, no
    # costed days, covering nothing. return_flagged_at: the return email
    # has gone (LEAVE-29).
    dates_only = models.BooleanField(default=False)
    return_flagged_at = models.DateTimeField(null=True, blank=True)
```

and in `Booking.Meta.constraints` add:

```python
            models.CheckConstraint(condition=Q(dates_only=False) | Q(part="whole"), name="dates_only_is_whole_days"),
```

`leave/models/yearend.py`:

```python
from django.conf import settings
from django.db import models


class YearEnd(models.Model):
    """LEAVE-21's flag for one person and one leave year that has ended:
    the figures the flag found, then the manager's decision. The carry and
    any loss are written as Adjustments in the new year; this row is the
    record that the question was asked and answered."""

    person = models.ForeignKey("people.Person", on_delete=models.PROTECT, related_name="year_ends")
    year_ended = models.DateField()                   # the first day of the leave year that ended
    notified_at = models.DateTimeField(null=True, blank=True)
    annual_remaining = models.IntegerField(default=0)  # seconds, bank holiday balance folded in
    toil_remaining = models.IntegerField(default=0)
    annual_carried = models.IntegerField(null=True, blank=True)
    annual_lost = models.IntegerField(null=True, blank=True)
    toil_lost = models.IntegerField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-year_ended", "person__last_name", "person__first_name"]
        constraints = [models.UniqueConstraint(fields=["person", "year_ended"], name="one_year_end_per_person_year")]

    @property
    def decided(self):
        return self.decided_at is not None

    def __str__(self):
        return f"{self.person_id} year end {self.year_ended}"
```

`leave/models/__init__.py`: add `from .yearend import YearEnd` and `"YearEnd"` to `__all__`.

`leave/admin.py`: add

```python
@admin.register(YearEnd)
class YearEndAdmin(ReadOnlyModelAdmin):
    list_display = ("person", "year_ended", "annual_remaining", "toil_remaining", "annual_carried", "toil_lost", "decided_at")
```

(import `YearEnd` from `.models`), and add `"dates_only"` to `BookingAdmin.list_display` and `"sickness", "flag_return"` to `LeaveTypeAdmin.list_display`.

- [ ] **Step 4: The person fields**

`people/models/person.py`, after `own_leave_without_approval`:

```python
    # Spec 4. The end date each leaver email was sent for (LEAVE-14,
    # NOTIF-06): a changed date is announced again, an unchanged one is not.
    leaver_flagged_for = models.DateField(null=True, blank=True)
    leaver_week_flagged_for = models.DateField(null=True, blank=True)
```

- [ ] **Step 5: The two apps**

`absence/__init__.py`, `absence/services/__init__.py`, `absence/views/__init__.py`, `payroll/__init__.py`, `payroll/services/__init__.py` empty. `absence/apps.py`:

```python
from django.apps import AppConfig


class AbsenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "absence"
```

`payroll/apps.py` the same with `PayrollConfig` and `name = "payroll"`. `absence/urls.py` and `payroll/urls.py`:

```python
urlpatterns = []
```

`payroll/models.py`:

```python
from django.conf import settings
from django.db import models
from django.utils import timezone


class PayrollRun(models.Model):
    """One "sent to the bureau" for one calendar month (PAY-02): who marked
    it, when, and the figures as they stood, so a later report can list what
    has changed since. Several runs for a month are allowed; the latest is
    what was sent."""

    month = models.DateField()                       # the first day
    sent_at = models.DateTimeField(default=timezone.now)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    people = models.PositiveIntegerField(default=0)
    figures = models.JSONField(default=dict)          # {"generated_at": iso, "rows": {"<person pk>": {field: value}}}

    class Meta:
        ordering = ["-month", "-sent_at"]
        indexes = [models.Index(fields=["month"])]

    def __str__(self):
        return f"Payroll {self.month:%B %Y}"
```

`payroll/admin.py`:

```python
"""Read-only, as the leave admin: a run is made by Mark as sent on the
payroll page and never edited."""

from django.contrib import admin

from people.admin import ReadOnlyModelAdmin

from .models import PayrollRun


@admin.register(PayrollRun)
class PayrollRunAdmin(ReadOnlyModelAdmin):
    list_display = ("month", "sent_at", "sent_by", "people")
```

`config/settings.py` INSTALLED_APPS: add `"absence",` and `"payroll",` after `"leave",`. `config/urls.py`: add `path("", include("absence.urls")),` and `path("", include("payroll.urls")),` after the leave include.

`requirements.txt`: add, keeping the alphabetical order of the file, `et_xmlfile==2.0.0`, `openpyxl==3.1.5`, `pillow==13.0.0`, `reportlab==5.1.0`.

- [ ] **Step 6: Migrations**

Run: `DEBUG=1 .venv/bin/python manage.py makemigrations leave -n absence && DEBUG=1 .venv/bin/python manage.py makemigrations people -n leaver_flags && DEBUG=1 .venv/bin/python manage.py makemigrations payroll`

Then open `leave/migrations/0003_absence.py` and append a data step after the generated operations:

```python
def seed_flags(apps, schema_editor):
    LeaveType = apps.get_model("leave", "LeaveType")
    LeaveType.objects.filter(seeded=True, name="Sick leave").update(sickness=True)
    LeaveType.objects.filter(seeded=True, name__in=("Maternity", "Adoption / shared parental")).update(flag_return=True)
```

with `migrations.RunPython(seed_flags, migrations.RunPython.noop)` as the last operation. Check that `0003_absence.py` depends on `("leave", "0002_seed")` and `payroll/migrations/0001_initial.py` on the auth user model (`migrations.swappable_dependency(settings.AUTH_USER_MODEL)`).

Run: `DEBUG=1 .venv/bin/python manage.py migrate && DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run` → "No changes detected".

- [ ] **Step 7: The factory**

`tests/factories.py`, after `make_booking`:

```python
def make_sick(person, first, last=None, dates_only=False, **kw):
    """An approved Sick leave booking, the seeded type (so it counts as
    sickness); dates_only for a past schedule entry."""
    kw.setdefault("type", make_type("Sick leave", requestable=False, sickness=True))
    kw.setdefault("status", "approved")
    return Booking.objects.create(person=person, first_day=first, last_day=last or first, part="whole", dates_only=dates_only, **kw)
```

- [ ] **Step 8: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_absence_models.py tests/test_leave_models.py tests/test_admin.py -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add absence payroll leave people config requirements.txt tests/factories.py tests/test_absence_models.py
git commit -m "Absence: the sickness and return flags on leave types, dates-only bookings, the year-end row, the leaver flag dates, the payroll run"
```

---

### Task 2: Sickness rules, the trigger check, dates-only bookings, the type flags on the form

**Files:**
- Create: `leave/services/sickness.py`
- Modify: `leave/services/bookings.py` (`book`, `edit`, `_apply`, a trigger helper), `leave/services/notify.py` (`trigger_reached`), `leave/services/types.py:6` (`EDITABLE`), `leave/forms.py:197-240` (`TypeForm`), `templates/leave/type_dialog.html`, `templates/leave/types.html`
- Test: `tests/test_absence_sickness.py`

**Interfaces:**
- Consumes: Task 1's fields; `bookings.book/edit/cancel`, `bookings._reread`, `bookings._mail`, `common.recipients/span`, `notify._link/_send_all`.
- Produces: `sickness.LONG_DAYS = 29`, `sickness.MAX_GAP_DAYS = 7`, `sickness.window(today) -> (start, end)`, `sickness.instances(person, today=None) -> [Booking]`, `sickness.level(count) -> int` (0..3), `sickness.level_for(person, today=None) -> int`, `sickness.level_label(level) -> str` ("" / "Trigger 1" / "Trigger 2" / "Trigger 3+"), `sickness.is_long(booking) -> bool`, `sickness.joins_on(person, first, last, exclude=None) -> Booking | None`, `sickness.overlaps_window(first, last, today=None) -> bool`; `bookings.book(..., dates_only=False)`; `bookings.edit(..., note="edited by a manager")`; `notify.trigger_reached(person, level, rows, base_url="")`; `types.EDITABLE` includes `sickness`, `flag_return`.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_sickness.py`:

```python
"""Sickness as LEAVE-40 to 44 define it, over Sick leave bookings: the
rolling window, instances, triggers and their email, long sickness, the
join-on rule, and dates-only entries from the past schedule section."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.core import mail

from leave.models import Booking, BookingDay
from leave.services import balances, bookings, feed, sickness
from leave.services.common import LeaveError
from people.models import AuditEntry
from shifts.models import Entry
from tests.factories import make_allowance, make_entry, make_gp_session, make_person, make_sick, make_type, make_user_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss")
    make_user_for(boss, is_all_teams_manager=True)
    return boss


def sick_type():
    return make_type("Sick leave", requestable=False, sickness=True)


def test_the_window_is_six_months_back_plus_a_day():
    assert sickness.window(date(2026, 7, 1)) == (date(2026, 1, 2), date(2026, 7, 1))        # SICK-01
    assert sickness.window(date(2026, 8, 31)) == (date(2026, 3, 1), date(2026, 8, 31))      # 28 Feb clamped, plus a day
    assert sickness.window(date(2027, 3, 30)) == (date(2026, 10, 1), date(2027, 3, 30))     # 30 Sep, plus a day
    assert sickness.window(date(2026, 1, 15)) == (date(2025, 7, 16), date(2026, 1, 15))


def test_levels():
    assert [sickness.level(n) for n in range(7)] == [0, 0, 0, 1, 2, 3, 3]
    assert sickness.level_label(0) == "" and sickness.level_label(1) == "Trigger 1" and sickness.level_label(3) == "Trigger 3+"


@pytest.mark.today(date(2026, 7, 1))
def test_sick_01_rolling_six_months_four_instances_trigger_2(boss):
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6))
    make_sick(sam, date(2025, 12, 20), date(2026, 1, 5))        # A: ends inside the window, counts
    make_sick(sam, date(2026, 2, 10))                           # B
    make_sick(sam, date(2026, 4, 20))                           # C
    make_sick(sam, date(2025, 6, 1), date(2025, 6, 3))          # before the window: does not count
    make_sick(sam, date(2026, 5, 1), status="cancelled")        # cancelled: does not count
    assert len(sickness.instances(sam)) == 3 and sickness.level_for(sam) == 1
    bookings.book(boss.user, sam, sick_type(), date(2026, 6, 15), date(2026, 6, 15), "whole")    # D
    rows = sickness.instances(sam)
    assert [b.first_day for b in rows] == [date(2025, 12, 20), date(2026, 2, 10), date(2026, 4, 20), date(2026, 6, 15)]
    assert sickness.level_for(sam) == 2
    assert [m.subject for m in mail.outbox] == ["Sam Patel has reached Trigger 2"]
    assert "4 instances" in mail.outbox[0].body and "20 Dec 2025" in mail.outbox[0].body
    assert AuditEntry.objects.filter(model="leave.booking", object_id=sam.pk, note__contains="Trigger 2 reached").exists()


@pytest.mark.today(date(2026, 7, 1))
def test_the_trigger_email_goes_once_per_level_reached_and_never_on_the_way_down(boss):
    sam = make_person(first_name="Sam")
    for d in (date(2026, 2, 1), date(2026, 3, 1)):
        bookings.book(boss.user, sam, sick_type(), d, d, "whole")
    assert mail.outbox == []
    third = bookings.book(boss.user, sam, sick_type(), date(2026, 4, 1), date(2026, 4, 1), "whole")
    assert [m.subject for m in mail.outbox] == ["Sam Patel has reached Trigger 1"]
    bookings.edit(boss.user, third, first=date(2026, 4, 2), last=date(2026, 4, 3))      # still three: no mail
    assert len(mail.outbox) == 1
    bookings.cancel(boss.user, third)
    assert len(mail.outbox) == 2 and "cancelled" in mail.outbox[1].subject       # the person's cancel mail only
    bookings.book(boss.user, sam, sick_type(), date(2026, 5, 1), date(2026, 5, 1), "whole")    # back to three: Trigger 1 again
    assert mail.outbox[-1].subject == "Sam Patel has reached Trigger 1"


def test_sick_02_long_sickness_is_twenty_nine_days():
    sam = make_person()
    assert not sickness.is_long(make_sick(sam, date(2026, 6, 1), date(2026, 6, 28)))
    assert sickness.is_long(make_sick(sam, date(2026, 7, 1), date(2026, 7, 29)))
    assert sickness.is_long(make_sick(sam, date(2026, 8, 1), date(2026, 9, 1)))


def test_sick_04_entries_that_join_on():
    sam = make_person()
    day = date(2025, 12, 29)
    while day <= date(2026, 1, 31):               # Mon–Fri rota through January
        if day.weekday() < 5:
            make_entry(sam, day, start=time(9), finish=time(17))
        day += timedelta(days=1)
    a = make_sick(sam, date(2026, 1, 1), date(2026, 1, 5))
    assert sickness.joins_on(sam, date(2026, 1, 6), date(2026, 1, 13)) == a            # (a) adjacent
    b = make_sick(sam, date(2026, 1, 20), date(2026, 1, 23))                            # Tue–Fri 23 Jan
    assert sickness.joins_on(sam, date(2026, 1, 26), date(2026, 1, 27)) == b           # (b) only a weekend between
    assert sickness.joins_on(sam, date(2026, 1, 28), date(2026, 1, 28)) is None         # Tue 27 Jan is worked
    assert sickness.joins_on(sam, date(2026, 1, 15), date(2026, 1, 16)) is None         # worked days either side
    assert sickness.joins_on(sam, date(2026, 1, 14), date(2026, 1, 19)) == b            # before b, Mon 19 → Tue 20 adjacent
    assert sickness.joins_on(sam, date(2026, 1, 26), date(2026, 1, 27), exclude=b) is None


def test_the_join_on_rule_treats_a_rota_less_day_as_not_worked_and_stops_at_a_week():
    sam = make_person()
    a = make_sick(sam, date(2026, 3, 2), date(2026, 3, 6))
    assert sickness.joins_on(sam, date(2026, 3, 12), date(2026, 3, 12)) == a           # 7–11 Mar, no rota: not worked
    assert sickness.joins_on(sam, date(2026, 3, 16), date(2026, 3, 16)) is None         # nine days between: never joins
    make_gp_session(sam, date(2026, 3, 9))
    assert sickness.joins_on(sam, date(2026, 3, 12), date(2026, 3, 12)) is None         # a session is work


@pytest.mark.today(date(2027, 1, 15))
def test_a_dates_only_entry_has_no_days_covers_nothing_and_skips_the_year_rule(boss):
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(sam, date(2027, 1, 1), Decimal("172.5"), 0)       # no bank holiday allowance: remaining is the plain 172.5 h
    shift = make_entry(sam, date(2026, 7, 6), start=time(9), finish=time(17))
    row = bookings.book(boss.user, sam, sick_type(), date(2026, 7, 6), date(2026, 7, 10), "whole", dates_only=True)   # last year: allowed
    assert row.status == "approved" and row.dates_only and not BookingDay.objects.filter(booking=row).exists()
    shift.refresh_from_db()
    assert shift.covered_by is None
    assert mail.outbox == []
    assert sickness.instances(sam, date(2026, 7, 20)) == [row]
    assert balances.statement(sam, date(2027, 1, 1)).annual_remaining == 621000
    assert AuditEntry.objects.filter(object_id=sam.pk, note="dates only (past schedule)").exists()
    with pytest.raises(LeaveError):
        bookings.book(boss.user, sam, sick_type(), date(2027, 1, 15), date(2027, 1, 15), "whole", dates_only=True)   # today: not past
    with pytest.raises(LeaveError):
        bookings.book(boss.user, sam, make_type("Holiday"), date(2026, 8, 3), date(2026, 8, 3), "whole", dates_only=True)   # not sickness
    bookings.edit(boss.user, row, last=date(2026, 7, 13))
    row.refresh_from_db()
    assert row.last_day == date(2026, 7, 13) and not BookingDay.objects.filter(booking=row).exists()
    with pytest.raises(LeaveError):
        bookings.edit(boss.user, row, part="am", first=date(2026, 7, 6), last=date(2026, 7, 6))


@pytest.mark.today(date(2027, 1, 15))
def test_a_dates_only_entry_never_emails_but_still_counts_towards_the_level(boss):
    sam = make_person(first_name="Sam")
    for d in (date(2026, 9, 7), date(2026, 10, 5), date(2026, 11, 2)):
        bookings.book(boss.user, sam, sick_type(), d, d, "whole", dates_only=True)
    assert sickness.level_for(sam) == 1 and mail.outbox == []
    assert AuditEntry.objects.filter(object_id=sam.pk, note__contains="Trigger 1 reached").exists()


def test_a_gps_dates_only_entry_is_in_the_feed():
    gp = make_person(first_name="Gail", is_gp=True, email="gail@example.org")
    make_sick(gp, date(2026, 5, 4), date(2026, 5, 6), dates_only=True)
    (rec,) = feed.records(date(2026, 5, 1), date(2026, 5, 31))
    assert rec == {"email": "gail@example.org", "first_day": "2026-05-04", "last_day": "2026-05-06", "part": "whole", "type": "Sick leave"}


def test_overlaps_window():
    assert sickness.overlaps_window(date(2026, 1, 1), date(2026, 1, 3), today=date(2026, 7, 1))
    assert not sickness.overlaps_window(date(2025, 12, 1), date(2026, 1, 1), today=date(2026, 7, 1))
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/bin/python -m pytest tests/test_absence_sickness.py -q`
Expected: ImportError on `leave.services.sickness`.

- [ ] **Step 3: `leave/services/sickness.py`**

```python
"""Sickness as LEAVE-40 to 44 define it, over the bookings of leave types
that count as sickness: one booking is one instance of absence; instances
are counted over a rolling six months; three, four and five make the
triggers; twenty-nine days make long sickness; an entry that joins on to
another is warned about. Nothing here is stored."""

import calendar
from datetime import date, timedelta

from django.utils import timezone

from leave.models import Booking
from shifts.models import Entry, GpSession

LONG_DAYS = 29          # LEAVE-44: longer than four calendar weeks, first and last day counted
MAX_GAP_DAYS = 7        # a gap longer than a week never "joins on", whatever the rota says
LEVELS = ((5, 3), (4, 2), (3, 1))
LABELS = {0: "", 1: "Trigger 1", 2: "Trigger 2", 3: "Trigger 3+"}


def _months_back(day, months):
    month, year = day.month - months, day.year
    while month <= 0:
        month, year = month + 12, year - 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def window(today):
    """LEAVE-42's rolling six months: the same day of the month six months
    back (the month's last day when it has no such day), plus a day, to
    today. 1 July gives 2 January to 1 July (SICK-01)."""
    return _months_back(today, 6) + timedelta(days=1), today


def overlaps_window(first, last, today=None):
    start, end = window(today or timezone.localdate())
    return first <= end and last >= start


def _rows(person):
    return Booking.objects.filter(person=person, status__in=Booking.ACTIVE, type__sickness=True).select_related("type")


def instances(person, today=None):
    """The person's instances in the window, oldest first: an entry counts
    when any of its days falls inside (LEAVE-42); dates-only entries count."""
    start, end = window(today or timezone.localdate())
    return list(_rows(person).filter(first_day__lte=end, last_day__gte=start).order_by("first_day", "pk"))


def level(count):
    for at_least, lvl in LEVELS:
        if count >= at_least:
            return lvl
    return 0


def level_for(person, today=None):
    return level(len(instances(person, today)))


def level_label(lvl):
    return LABELS[lvl]


def is_long(booking):
    return (booking.last_day - booking.first_day).days + 1 >= LONG_DAYS


def _worked(person, day):
    """A day the person works: a shift on the rota (covered or not: a day
    they were due in) or a GP session."""
    return (Entry.objects.filter(person=person, day=day, kind=Entry.Kind.SHIFT).exists()
            or GpSession.objects.filter(person=person, day=day).exists())


def _bridges(person, a, b):
    """Whether the days strictly between a and b are all days the person
    does not work, and there are at most MAX_GAP_DAYS of them."""
    between = (b - a).days - 1
    if between > MAX_GAP_DAYS:
        return False
    return all(not _worked(person, a + timedelta(days=n)) for n in range(1, between + 1))


def joins_on(person, first, last, exclude=None):
    """LEAVE-41: the existing sickness booking this entry joins on to, or
    None. Adjacent dates join; so does a gap made only of days the person
    does not work (a weekend, a part-timer's day off, a week with no rota)."""
    rows = _rows(person)
    if exclude is not None:
        rows = rows.exclude(pk=exclude.pk)
    before = rows.filter(last_day__lt=first).order_by("-last_day", "-pk").first()
    if before is not None and _bridges(person, before.last_day, first):
        return before
    after = rows.filter(first_day__gt=last).order_by("first_day", "pk").first()
    if after is not None and _bridges(person, last, after.first_day):
        return after
    return None
```

- [ ] **Step 4: The trigger email**

`leave/services/notify.py`: import `sickness` (`from leave.services import hours, sickness`) and add

```python
def trigger_reached(person, lvl, rows, base_url=""):
    """NOTIF-05: the person's managers, when a sickness entry takes them to
    a higher trigger. Dates only: no description, no note."""
    lines = "\n".join(f"  {span(b)}" + (" (long sickness)" if sickness.is_long(b) else "") for b in rows)
    label = sickness.level_label(lvl)
    body = (f"{person.name} has reached {label}: {len(rows)} instances of absence in the last six months.\n\n{lines}\n\n"
            f"Profile: {_link(base_url, f'/staff/{person.pk}/profile/?tab=hours')}\n")
    return _send_all(recipients(person), f"{person.name} has reached {label}", body)
```

- [ ] **Step 5: The booking services**

`leave/services/bookings.py`. Import `sickness` with the other services. Add after `_mail`:

```python
def _trigger_before(person, leave_type, was=None):
    """The person's trigger level before a write that touches sickness, or
    None when the write does not."""
    if leave_type.sickness or (was is not None and was.type.sickness):
        return sickness.level_for(person)
    return None


def _trigger_after(person, before, dates_only=False, base_url=""):
    """Compare with the level after the write; email the managers when it
    rose (never for a dates-only entry: the manager is typing history).
    Returns the audit note's suffix, or ""."""
    if before is None:
        return ""
    after = sickness.level_for(person)
    if after <= before:
        return ""
    if not dates_only:
        _mail(notify.trigger_reached, person, after, sickness.instances(person), base_url)
    return f"; {sickness.level_label(after)} reached"
```

`_apply`: first line `if booking.dates_only:` `return []`.

`book`: new signature `def book(user, person, leave_type, first, last, part, start=None, finish=None, description="", paid=None, note="", costs=None, base_url="", dates_only=False):` and body:

```python
    if not may_book(user, person):
        raise PermissionDenied("you don't manage this person")
    if not access.can_manage(user, person):
        costs = None
    if dates_only:
        _check_dates_only(leave_type, first, last, part)
    else:
        _check_dates(person, first, last, part, start, finish)
    before_level = _trigger_before(person, leave_type)
    booking = _new(user, person, leave_type, first, last, part, start, finish, description, paid, note, Booking.Status.APPROVED)
    booking.decided_by, booking.decided_at, booking.dates_only = user, timezone.now(), dates_only
    with transaction.atomic():
        _check_overlap(person, first, last)
        booking.save()
        days = _apply(booking)
        _type_costs(user, days, costs, note or "set when booked")
        suffix = _trigger_after(person, before_level, dates_only, base_url)
        audit.record_as(user, "leave.booking", person.pk, {"booking": ("", describe(booking))},
                        note=("dates only (past schedule)" if dates_only else "booked by a manager") + suffix)
    _after_apply(booking, days, base_url)
    return booking
```

with, next to `_check_dates`:

```python
def _check_dates_only(leave_type, first, last, part):
    """A past schedule entry: whole days of a sickness type, already gone
    (MIG-05). The leave-year rule does not apply: 2026 is typed in 2027."""
    if not leave_type.sickness:
        raise LeaveError("type", f"{leave_type.name} does not count as sickness; the past schedule is for sickness only")
    if part != Booking.Part.WHOLE:
        raise LeaveError("part", "A past schedule entry is whole days")
    if first > last:
        raise LeaveError("dates", "The last day is before the first")
    if last >= timezone.localdate():
        raise LeaveError("dates", "The past schedule is for days already gone; book today's sickness as time off")
```

`edit`: signature `def edit(user, booking, base_url="", costs=None, note="edited by a manager", **fields):`. Inside the transaction, after `fresh = _reread(booking)` and the status check:

```python
        before_level = _trigger_before(fresh.person, fields.get("type", fresh.type), was=fresh)
```

and replace the `if moves(...)` block with:

```python
        if fresh.dates_only:
            if part != Booking.Part.WHOLE or costs:
                raise LeaveError("part", "A past schedule entry is whole days with no hours")
            _check_dates_only(new_type, first, last, part)
            _check_overlap(fresh.person, first, last, exclude=fresh)
        elif moves(fresh, first, last, part, start, finish):     # a type change on the same days is a correction, in any year
            _check_dates(fresh.person, first, last, part, start, finish, was=fresh)
            _check_overlap(fresh.person, first, last, exclude=fresh)
```

and the audit line becomes:

```python
        suffix = _trigger_after(fresh.person, before_level, fresh.dates_only, base_url)
        audit.record_as(user, "leave.booking", fresh.person_id, {"booking": (before, describe(fresh)), **typed}, note=note + suffix)
```

Nothing else in `edit` changes: a dates-only booking has no rows, so `_undo` and `_apply` do nothing for it.

- [ ] **Step 6: The type flags**

`leave/services/types.py`: `EDITABLE = ("name", "colour", "requestable", "paid_choice", "default_paid", "display_order", "draws_from", "on_payroll", "archived", "sickness", "flag_return")` and `add(..., default_paid=True, sickness=False, flag_return=False)` passing both to `create`.

`leave/forms.py` `TypeForm`: add fields after `default_paid`

```python
    sickness = forms.BooleanField(required=False, label="Counts as sickness (instances, triggers, the sickness summary)")
    flag_return = forms.BooleanField(required=False, label="Email the managers when the person returns")
```

add `"sickness", "flag_return"` to the `initial` tuple in `__init__`, to the `fields` tuple in `save` and to the `types.add` call (`sickness=d["sickness"], flag_return=d["flag_return"]`).

`templates/leave/type_dialog.html`: after the `default_paid` line add

```html
  <div class="field"><label class="check">{{ form.sickness }} {{ form.sickness.label }}</label></div>
  <div class="field"><label class="check">{{ form.flag_return }} {{ form.flag_return.label }}</label></div>
```

`templates/leave/types.html`: a new column `<th>Flags</th>` before Status with `<td>{% if t.sickness %}Sickness{% endif %}{% if t.sickness and t.flag_return %} · {% endif %}{% if t.flag_return %}Return flagged{% endif %}</td>`.

- [ ] **Step 7: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_absence_sickness.py tests/test_leave_bookings.py tests/test_leave_examples.py tests/test_leave_views.py tests/test_leave_reports.py -q`
Expected: all pass. If `test_leave_reports.py` asserts the types table's exact columns, update that assertion for the Flags column.

- [ ] **Step 8: Commit**

```bash
git add leave tests/test_absence_sickness.py
git commit -m "Leave: sickness instances, triggers and the join-on rule over Sick leave bookings; dates-only entries; the type flags"
```

---

### Task 3: Converting annual leave to sickness (LEAVE-28), the Convert dialog, notes on the booking view

**Files:**
- Create: `absence/services/convert.py`, `absence/views/convert.py`, `absence/forms.py`, `templates/absence/convert_dialog.html`
- Modify: `absence/urls.py`, `absence/views/__init__.py`, `leave/services/notify.py` (`converted`), `leave/views/detail.py:30-45`, `templates/leave/view_dialog.html`
- Test: `tests/test_absence_convert.py`

**Interfaces:**
- Consumes: `bookings.book/edit/cancel/_reread/may_decide`, `common.LeaveError/span`, `sickness.*`.
- Produces: `convert.check(booking, leave_type, first, last)` (raises `LeaveError`), `convert.convert(user, booking, leave_type, first, last, note="", base_url="") -> Booking` (the sickness booking), `convert.eligible(booking) -> bool`, `convert.hours_back(booking, first, last) -> int`; `notify.converted(original_label, original_span, sick, base_url="")`; URL `time-off-convert` at `/time-off/<pk>/convert/`; `view_dialog.html` context keys `can_convert`, `long_sickness`.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_convert.py`:

```python
"""SICK-03 and LEAVE-28: a manager turns days of booked annual leave into
sickness; the hours come back, one instance is recorded."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.test import Client

from absence.services import convert
from leave.models import Booking, BookingDay
from leave.services import balances, bookings, sickness
from leave.services.common import LeaveError
from people.models import AuditEntry
from tests import clock
from tests.factories import make_allowance, make_entry, make_person, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(clock.LATE_2026)]
Y27 = date(2027, 1, 1)
MON = date(2027, 3, 1)


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss")
    make_user_for(boss, is_all_teams_manager=True)
    return boss


@pytest.fixture
def sam():
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_user_for(sam)
    make_allowance(sam, Y27, Decimal("172.5"), 0)
    for n in range(5):
        make_entry(sam, MON + timedelta(days=n), start=time(9), finish=time(17), break_minutes=30)
    return sam


def sick():
    return make_type("Sick leave", requestable=False, sickness=True)


def test_sick_03_wednesday_and_thursday_of_a_booked_week(boss, sam):
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON, MON + timedelta(days=4), "whole")
    assert balances.statement(sam, Y27).taken["annual"] == 135000           # 37.5 h
    sick_row = convert.convert(boss.user, holiday, sick(), MON + timedelta(days=2), MON + timedelta(days=3))
    s = balances.statement(sam, Y27)
    assert s.taken["annual"] == 81000                                         # 15 h back: 22.5 h left charged
    assert sick_row.type.sickness and sick_row.status == "approved" and (sick_row.first_day, sick_row.last_day) == (MON + timedelta(days=2), MON + timedelta(days=3))
    assert sum(BookingDay.objects.filter(booking=sick_row).values_list("cost_seconds", flat=True)) == 54000      # 15 h, drawing on nothing
    assert set(BookingDay.objects.filter(booking=sick_row).values_list("account", flat=True)) == {"none"}
    holiday.refresh_from_db()
    assert (holiday.first_day, holiday.last_day, holiday.status) == (MON, MON + timedelta(days=1), "approved")
    tail = Booking.objects.get(person=sam, first_day=MON + timedelta(days=4))
    assert tail.type.name == "Holiday" and tail.last_day == MON + timedelta(days=4) and tail.status == "approved"
    assert len(sickness.instances(sam, MON + timedelta(days=10))) == 1
    assert "converted from Holiday 1–5 Mar 2027" in sick_row.manager_note
    notes = list(AuditEntry.objects.filter(object_id=sam.pk, model="leave.booking").order_by("pk").values_list("note", flat=True))
    assert notes.count("converted to sickness") == 2 and notes[-1].startswith("booked by a manager")
    assert [m.subject for m in mail.outbox] == ["Your time off has been changed"]
    assert "3–4 Mar 2027 is now recorded as Sick leave" in mail.outbox[0].body


def test_converting_the_whole_booking_cancels_it(boss, sam):
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON, MON + timedelta(days=1), "whole")
    convert.convert(boss.user, holiday, sick(), MON, MON + timedelta(days=1))
    holiday.refresh_from_db()
    assert holiday.status == "cancelled" and balances.statement(sam, Y27).taken["annual"] == 0
    assert Booking.objects.filter(person=sam, type__name="Holiday", status="approved").count() == 0


def test_a_typed_figure_on_a_tail_day_survives_the_conversion(boss, sam):
    friday = MON + timedelta(days=4)
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON, friday, "whole", costs={friday: 18000})      # Friday typed as 5 h
    convert.convert(boss.user, holiday, sick(), MON + timedelta(days=2), MON + timedelta(days=3))
    tail = BookingDay.objects.get(booking__person=sam, day=friday, booking__type__name="Holiday")
    assert (tail.cost_seconds, tail.source) == (18000, "override")


def test_converting_the_first_days_keeps_the_tail_in_the_same_booking(boss, sam):
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON, MON + timedelta(days=4), "whole", description="Spain")
    convert.convert(boss.user, holiday, sick(), MON, MON + timedelta(days=1))
    holiday.refresh_from_db()
    assert (holiday.first_day, holiday.last_day, holiday.description) == (MON + timedelta(days=2), MON + timedelta(days=4), "Spain")
    assert Booking.objects.filter(person=sam, type__name="Holiday").count() == 1


def test_refusals(boss, sam):
    pending = bookings.request(sam.user, sam, make_type("Holiday"), MON, MON, "whole")
    with pytest.raises(LeaveError):
        convert.check(pending, sick(), MON, MON)
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON + timedelta(days=1), MON + timedelta(days=2), "whole")
    with pytest.raises(LeaveError):
        convert.check(holiday, sick(), MON, MON + timedelta(days=1))              # outside the booking
    with pytest.raises(LeaveError):
        convert.check(holiday, make_type("Training"), MON + timedelta(days=1), MON + timedelta(days=1))   # not sickness
    training = bookings.book(boss.user, sam, make_type("Training"), MON + timedelta(days=3), MON + timedelta(days=3), "whole")
    with pytest.raises(LeaveError):
        convert.check(training, sick(), MON + timedelta(days=3), MON + timedelta(days=3))   # not annual leave
    assert convert.eligible(holiday) and not convert.eligible(training) and not convert.eligible(pending)
    assert convert.hours_back(holiday, MON + timedelta(days=1), MON + timedelta(days=1)) == 27000


def test_the_dialog_previews_then_converts(boss, sam):
    holiday = bookings.book(boss.user, sam, make_type("Holiday"), MON, MON + timedelta(days=4), "whole")
    c = Client()
    c.force_login(boss.user)
    body = c.get(f"/time-off/{holiday.pk}/").content.decode()
    assert f'href="/time-off/{holiday.pk}/convert/"' in body
    r = c.post(f"/time-off/{holiday.pk}/convert/", {"first_day": "2027-03-03", "last_day": "2027-03-04", "type": sick().pk, "note": "", "preview": "1"})
    assert r.status_code == 200 and "15 h" in r.content.decode() and "1 instance" in r.content.decode()
    r = c.post(f"/time-off/{holiday.pk}/convert/", {"first_day": "2027-03-03", "last_day": "2027-03-04", "type": sick().pk, "note": "called in"})
    assert r.json() == {"refresh": True}
    assert Booking.objects.filter(person=sam, type__sickness=True).count() == 1
    staff = Client()
    staff.force_login(sam.user)
    assert staff.get(f"/time-off/{holiday.pk}/convert/").status_code == 403
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/bin/python -m pytest tests/test_absence_convert.py -q`
Expected: ImportError on `absence.services.convert`.

- [ ] **Step 3: `absence/services/convert.py`**

```python
"""LEAVE-28: sick during annual leave. A manager picks the sick days inside
a booked holiday; the holiday is cut around them (its hours come back
through the booking services' own edit path) and a sickness booking is
recorded for them, costed from the rota like any sickness."""

from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction

from leave.models import Booking, BookingDay
from leave.services import bookings, notify
from leave.services.common import LeaveError, span

CONVERTIBLE = ("annual", "bank_holiday")
NOTE = "converted to sickness"


def eligible(booking):
    return (booking.status in Booking.ACTIVE and not booking.dates_only and booking.part == Booking.Part.WHOLE
            and booking.type.draws_from in CONVERTIBLE)


def check(booking, leave_type, first, last):
    if booking.status not in Booking.ACTIVE:
        raise LeaveError("status", "Only approved leave can be converted")
    if booking.dates_only or booking.part != Booking.Part.WHOLE:
        raise LeaveError("part", "Only whole days of leave can be converted")
    if booking.type.draws_from not in CONVERTIBLE:
        raise LeaveError("type", f"{booking.type.name} is not annual leave")
    if not (booking.first_day <= first <= last <= booking.last_day):
        raise LeaveError("days", "Choose days inside the booking")
    if not leave_type.sickness:
        raise LeaveError("type", f"{leave_type.name} does not count as sickness")


def hours_back(booking, first, last):
    """The seconds the booking's days in first..last were charged."""
    return sum(BookingDay.objects.filter(booking=booking, day__range=(first, last)).values_list("cost_seconds", flat=True))


def convert(user, booking, leave_type, first, last, note="", base_url=""):
    if not bookings.may_decide(user, booking):
        raise PermissionDenied("you don't manage this person")
    with transaction.atomic():
        fresh = bookings._reread(booking)
        check(fresh, leave_type, first, last)
        label, dates = fresh.label, span(fresh)
        person = fresh.person
        if first == fresh.first_day and last == fresh.last_day:
            bookings.cancel(user, fresh, note=NOTE, base_url=base_url)
        elif first == fresh.first_day:
            bookings.edit(user, fresh, base_url=base_url, note=NOTE, first=last + timedelta(days=1))
        else:
            tail_last = fresh.last_day
            # A manager's typed figure on a tail day stands: the tail is re-booked with those costs as overrides.
            typed = {bd.day: bd.cost_seconds for bd in BookingDay.objects.filter(booking=fresh, source=BookingDay.Source.OVERRIDE, day__gt=last)}
            bookings.edit(user, fresh, base_url=base_url, note=NOTE, last=first - timedelta(days=1))
            if last < tail_last:
                bookings.book(user, person, fresh.type, last + timedelta(days=1), tail_last, Booking.Part.WHOLE,
                              description=fresh.description, paid=fresh.paid, note=fresh.manager_note, costs=typed or None, base_url=base_url)
        manager_note = f"converted from {label} {dates}" + (f"; {note.strip()}" if note and note.strip() else "")
        sick = bookings.book(user, person, leave_type, first, last, Booking.Part.WHOLE, note=manager_note[:300], base_url=base_url)
    bookings._mail(notify.converted, label, dates, sick, base_url)
    return sick
```

Note `bookings.cancel` queues the person's "cancelled" email through `_mail`; for a whole-booking conversion the person therefore gets two emails (cancelled, then changed). Acceptable: both are true. Record it in the deviations if the reviewer objects.

`leave/services/notify.py`:

```python
def converted(label, dates, sick, base_url=""):
    """LEAVE-28: the person is told their leave was changed; the sickness
    itself is named by type only."""
    p = sick.person
    body = (f"Your {label} for {dates} has been changed: {span(sick)} is now recorded as {sick.type.name}, "
            f"and those hours have gone back to your allowance.\n\nYour leave: {_link(base_url, '/time-off/mine/')}\n")
    return _send_all([p], "Your time off has been changed", body)
```

- [ ] **Step 4: The form, view, template, URL**

`absence/forms.py`:

```python
from django import forms

from leave.models import LeaveType


class ConvertForm(forms.Form):
    first_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "data-submit-on-change": ""}, format="%Y-%m-%d"), label="First sick day")
    last_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date", "data-submit-on-change": ""}, format="%Y-%m-%d"), label="Last sick day")
    type = forms.ModelChoiceField(LeaveType.objects.filter(archived=False, sickness=True), label="Record as")
    note = forms.CharField(max_length=200, required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Manager notes")

    def __init__(self, *args, booking=None, **kwargs):
        if booking is not None:
            kwargs.setdefault("initial", {"first_day": booking.first_day, "last_day": booking.last_day,
                                          "type": LeaveType.objects.filter(sickness=True, archived=False).order_by("display_order").first()})
        super().__init__(*args, **kwargs)
        self.booking = booking

    def clean(self):
        d = super().clean()
        if d.get("first_day") and d.get("last_day") and d["last_day"] < d["first_day"]:
            self.add_error("last_day", "The last day is before the first")
        return d
```

`absence/views/convert.py`:

```python
"""Convert days to sickness (LEAVE-28): a manager's pop-up on an approved
annual leave booking; re-renders with a preview on each change."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from absence.forms import ConvertForm
from absence.services import convert
from leave.models import Booking
from leave.services import bookings, sickness
from leave.services.common import LeaveError
from people.services import access


def _preview(booking, first, last):
    rows = sickness.instances(booking.person)
    count = len(rows) + (1 if sickness.overlaps_window(first, last) else 0)
    return {"hours_back": convert.hours_back(booking, first, last), "instances_after": count,
            "level_label": sickness.level_label(sickness.level(count)), "long": (last - first).days + 1 >= sickness.LONG_DAYS}


@login_required
@access.manager_required
def convert_view(request, pk):
    booking = get_object_or_404(Booking.objects.select_related("person", "type"), pk=pk)
    if not bookings.may_decide(request.user, booking):
        raise PermissionDenied
    form = ConvertForm(request.POST or None, booking=booking)
    preview, error = None, None
    if form.is_valid():
        d = form.cleaned_data
        try:
            convert.check(booking, d["type"], d["first_day"], d["last_day"])
            preview = _preview(booking, d["first_day"], d["last_day"])
            if request.method == "POST" and not request.POST.get("preview"):
                convert.convert(request.user, booking, d["type"], d["first_day"], d["last_day"], d["note"], base_url=request.build_absolute_uri("/"))
                return JsonResponse({"refresh": True})
        except LeaveError as e:
            error = e.message
    return render(request, "absence/convert_dialog.html", {"b": booking, "form": form, "preview": preview, "error": error})
```

`templates/absence/convert_dialog.html`:

```html
{% extends "ui/_dialog.html" %}
{% load leave_extras %}
{% block dialog_title %}Convert days to sickness{% endblock %}
{% block dialog_body %}
<p><strong>{{ b.person.name }}</strong> · {{ b.label }} {{ b.first_day|date:"j M" }}–{{ b.last_day|date:"j M Y" }}</p>
<form method="post" action="{% url 'time-off-convert' b.pk %}" data-dialog-form>
  {% csrf_token %}
  {% for e in form.non_field_errors %}<p class="flash flash-error">{{ e }}</p>{% endfor %}
  {% if error %}<p class="flash flash-error">{{ error }}</p>{% endif %}
  <div class="field-row">
    <div class="field{% if form.first_day.errors %} has-error{% endif %}"><label for="id_first_day">{{ form.first_day.label }}</label>{{ form.first_day }}{% for e in form.first_day.errors %}<p class="field-error">{{ e }}</p>{% endfor %}</div>
    <div class="field{% if form.last_day.errors %} has-error{% endif %}"><label for="id_last_day">{{ form.last_day.label }}</label>{{ form.last_day }}{% for e in form.last_day.errors %}<p class="field-error">{{ e }}</p>{% endfor %}</div>
  </div>
  <div class="field"><label for="id_type">{{ form.type.label }}</label>{{ form.type }}</div>
  <div class="field"><label for="id_note">{{ form.note.label }}</label>{{ form.note }}</div>
  <input type="hidden" name="preview" value="1">
  {% if preview %}
  <p>{{ preview.hours_back|hm }} goes back to the allowance. Instances in the last six months after this: {{ preview.instances_after }} instance{{ preview.instances_after|pluralize }}{% if preview.level_label %} ({{ preview.level_label }}){% endif %}.</p>
  {% if preview.long %}<p class="flash flash-warning">This is long sickness (29 days or more): managers are emailed when {{ b.person.first_name }} returns.</p>{% endif %}
  {% endif %}
  <button class="btn btn-dark" name="preview" value="">Convert to {% if form.type.value %}sickness{% else %}sickness{% endif %}</button>
</form>
{% endblock %}
```

`absence/views/__init__.py`: `from .convert import convert_view  # noqa: F401`. `absence/urls.py`:

```python
from django.urls import path

from absence import views

urlpatterns = [
    path("time-off/<int:pk>/convert/", views.convert_view, name="time-off-convert"),
]
```

- [ ] **Step 5: The booking view**

`leave/views/detail.py` `view`: add to the context

```python
        "can_convert": manager and convert.eligible(b),
        "long_sickness": b.type.sickness and sickness.is_long(b),
        "after_leaving": b.person.end_date is not None and b.last_day > b.person.end_date,
```

importing `from absence.services import convert` and `from leave.services import bookings, sickness`. `templates/leave/view_dialog.html`: after the `<dl>`:

```html
{% if b.dates_only %}<p class="field-help">Dates only: a past schedule entry, with no hours.</p>{% endif %}
{% if long_sickness %}<p class="flash flash-warning">Long sickness: 29 days or more.</p>{% endif %}
{% if detail and after_leaving %}<p class="flash flash-warning">After the leaving date ({{ b.person.end_date|date:"j M Y" }}).</p>{% endif %}
```

and in `dialog_links`, inside the `<div>`, after Edit: `{% if can_convert %}<a href="{% url 'time-off-convert' b.pk %}" data-dialog>Convert days to sickness…</a>{% endif %}`, and the surrounding `{% if %}` becomes `{% if can_edit or can_cancel or can_convert %}`.

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_absence_convert.py tests/test_leave_views.py tests/test_leave_bookings.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add absence leave tests/test_absence_convert.py
git commit -m "Absence: convert days of annual leave to sickness; the booking view's notes and link"
```

---

### Task 4: The join-on warning in Add time off, the past schedule section, dates-only on the grid and list, Instances on the leave report, the sickness line on the statement, navigation

**Files:**
- Create: `absence/views/past.py`, `templates/absence/_sickness_preview.html`, `templates/absence/past.html`, `templates/absence/past_dialog.html`
- Modify: `absence/forms.py` (`PastSicknessForm`), `absence/views/__init__.py`, `absence/urls.py`, `leave/views/add.py` (`_preview`, `add`, `edit`), `templates/leave/add_dialog.html`, `leave/services/serialize.py:30-45`, `leave/views/list.py:60-75` and `templates/leave/list.html`, `leave/views/report.py` and `templates/leave/report.html`, `leave/views/statement.py` (`statement_context`) and `templates/leave/_statement.html`, `ui/context_processors.py:21-27`
- Test: `tests/test_absence_views.py`

**Interfaces:**
- Consumes: Task 2's `sickness.*` and `bookings.book(dates_only=True)`.
- Produces: `add._preview` returns `preview["sickness"] = {"joins", "extended_first", "extended_last", "long", "instances_after", "level_label"}` for a sickness type; POST field `join` = `extend` | `separate`; URLs `time-off-past` (`/time-off/past/`), `time-off-past-add` (`/time-off/past/add/`); `statement_context` gains `sickness_count`, `sickness_label`; the leave report's rows gain `instances`, `trigger`; the grid payload carries dates-only bookings.

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_views.py`:

```python
"""The sickness screens: the join-on warning in Add time off (SICK-04
through the dialog), the past schedule section, dates-only entries on the
grid and the list, the Instances column, the statement's sickness line."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.test import Client

from leave.models import Booking
from tests import clock
from tests.factories import make_allowance, make_entry, make_person, make_sick, make_team, make_team_manager, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(clock.LATE_2026)]


def _client(person, **kw):
    c = Client()
    c.force_login(person.user or make_user_for(person, **kw))
    return c


@pytest.fixture
def team():
    return make_team("Reception")


@pytest.fixture
def lead(team):
    lead = make_person(first_name="Lead", team=team)
    make_user_for(lead)
    make_team_manager(lead, team)
    return lead


@pytest.fixture
def sam(team):
    sam = make_person(first_name="Sam", team=team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_user_for(sam)
    make_allowance(sam, date(2026, 1, 1), Decimal("172.5"), 0)
    day = date(2026, 9, 28)
    while day <= date(2026, 11, 30):
        if day.weekday() < 5:
            make_entry(sam, day, start=time(9), finish=time(17), break_minutes=30)
        day += timedelta(days=1)
    return sam


def sick():
    return make_type("Sick leave", requestable=False, sickness=True)


def _post(c, person, first, last, **extra):
    data = {"person": person.pk, "type": sick().pk, "first_day": first.isoformat(), "last_day": last.isoformat(), "part": "whole", "manager_note": ""}
    return c.post("/time-off/add/", {**data, **extra})


def test_sick_04_the_dialog_warns_and_extend_makes_one_instance(sam, lead):
    first = make_sick(sam, date(2026, 10, 5), date(2026, 10, 9))          # Mon–Fri
    c = _client(lead)
    body = _post(c, sam, date(2026, 10, 12), date(2026, 10, 13), preview="1").content.decode()
    assert "joins on to Sick leave 5 Oct–9 Oct 2026" in body and 'name="join"' in body and "Extend that entry to 5 Oct–13 Oct 2026" in body
    assert "1 instance" in body or "Instances in the last six months after this entry: 1" in body
    r = _post(c, sam, date(2026, 10, 12), date(2026, 10, 13), join="extend")
    assert r.json() == {"refresh": True}
    first.refresh_from_db()
    assert first.last_day == date(2026, 10, 13) and Booking.objects.filter(person=sam, type__sickness=True).count() == 1


def test_sick_04_record_separately_makes_two_instances(sam, lead):
    make_sick(sam, date(2026, 10, 5), date(2026, 10, 9))
    r = _post(_client(lead), sam, date(2026, 10, 12), date(2026, 10, 13), join="separate")
    assert r.json() == {"refresh": True}
    assert Booking.objects.filter(person=sam, type__sickness=True, status="approved").count() == 2


def test_a_long_entry_is_marked_in_the_preview(sam, lead):
    body = _post(_client(lead), sam, date(2026, 10, 1), date(2026, 10, 29), preview="1").content.decode()
    assert "long sickness" in body


def test_a_holiday_preview_has_no_sickness_block(sam, lead):
    c = _client(lead)
    r = c.post("/time-off/add/", {"person": sam.pk, "type": make_type("Holiday").pk, "first_day": "2026-11-09", "last_day": "2026-11-09", "part": "whole", "manager_note": "", "preview": "1"})
    assert 'name="join"' not in r.content.decode() and "Instances in the last six months" not in r.content.decode()


def test_the_past_schedule_lists_adds_and_refuses_staff(sam, lead):
    c = _client(lead)
    assert c.get("/time-off/past/").status_code == 200
    r = c.post("/time-off/past/add/", {"person": sam.pk, "type": sick().pk, "first_day": "2026-07-06", "last_day": "2026-07-10", "preview": "1"})
    assert r.status_code == 200 and "Instances in the last six months after this entry: 1" in r.content.decode()
    r = c.post("/time-off/past/add/", {"person": sam.pk, "type": sick().pk, "first_day": "2026-07-06", "last_day": "2026-07-10"})
    assert r.json() == {"refresh": True}
    row = Booking.objects.get(person=sam, type__sickness=True)
    assert row.dates_only and row.status == "approved" and not row.booking_days.exists()
    body = c.get("/time-off/past/").content.decode()
    assert "Sam Patel" in body and "6 Jul 2026" in body and "10 Jul 2026" in body
    assert "<td>1</td><td></td>" in body                                        # one instance, no trigger yet
    r = c.post("/time-off/past/add/", {"person": sam.pk, "type": sick().pk, "first_day": "2026-11-02", "last_day": "2026-11-02"})
    assert r.status_code == 200 and "already gone" in r.content.decode()
    staff = _client(sam)
    assert staff.get("/time-off/past/").status_code == 403 and staff.get("/time-off/past/add/").status_code == 403
    body = c.get("/time-off/").content.decode()
    assert 'href="/time-off/past/"' in body and 'href="/time-off/past/"' not in staff.get("/time-off/").content.decode()


def test_the_past_schedule_add_offers_extend_too(sam, lead):
    make_sick(sam, date(2026, 7, 6), date(2026, 7, 10), dates_only=True)
    c = _client(lead)
    r = c.post("/time-off/past/add/", {"person": sam.pk, "type": sick().pk, "first_day": "2026-07-13", "last_day": "2026-07-14", "join": "extend"})
    assert r.json() == {"refresh": True}
    assert Booking.objects.filter(person=sam, type__sickness=True).count() == 1 and Booking.objects.get(person=sam, type__sickness=True).last_day == date(2026, 7, 14)


def test_dates_only_entries_show_on_the_list_the_grid_and_the_view(sam, lead):
    row = make_sick(sam, date(2026, 10, 5), date(2026, 10, 7), dates_only=True)
    c = _client(lead)
    body = c.get("/time-off/?from=2026-10-01&to=2026-10-31").content.decode()
    assert "dates only" in body and "0 min" not in body
    payload = c.get("/rota/api/window/?from=2026-10-05&to=2026-10-11").json()
    cell = next(r for r in payload["rows"] if r["person"]["id"] == sam.pk)["leave"]["2026-10-06"]
    assert cell["type"] == "Sick leave" and cell["status"] == "approved" and cell["cost"] is None
    assert "Dates only" in c.get(f"/time-off/{row.pk}/").content.decode()
    csv = c.get("/time-off/?from=2026-10-01&to=2026-10-31&download=1").content.decode()
    assert "dates only" in csv


def test_the_leave_report_shows_instances_and_trigger(sam, lead):
    for d in (date(2026, 6, 1), date(2026, 8, 3), date(2026, 10, 5)):
        make_sick(sam, d)
    body = _client(lead).get("/reports/leave/?from=2026-01-01&to=2026-12-31").content.decode()
    assert "<th>Instances</th>" in body and "<th>Trigger</th>" in body and "Trigger 1" in body
    csv = _client(lead).get("/reports/leave/?from=2026-01-01&to=2026-12-31&download=1").content.decode()
    assert csv.splitlines()[0].endswith("Instances,Trigger") and ",3,Trigger 1" in csv


def test_the_statement_carries_the_persons_sickness_line(sam, lead):
    make_sick(sam, date(2026, 9, 7))
    assert "Sickness: 1 instance in the last six months" in _client(sam).get("/time-off/mine/").content.decode()
    body = _client(lead).get(f"/staff/{sam.pk}/profile/?tab=hours").content.decode()
    assert "Sickness: 1 instance in the last six months" in body
    nina = make_person(first_name="Nina", team=sam.team)
    assert "Sickness:" not in _client(nina).get(f"/time-off/").content.decode()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/bin/python -m pytest tests/test_absence_views.py -q`
Expected: failures (no `join` field, 404 on `/time-off/past/`, no Instances column).

- [ ] **Step 3: The Add dialog**

`leave/views/add.py`: import `sickness` with the other services. In `_preview`, before the `account = kw["leave_type"].draws_from` line add:

```python
    out_sickness = _sickness_preview(person, kw["leave_type"], kw["first"], kw["last"], booking)
```

and include `**out_sickness` in both return dictionaries (`return out | {...} | out_sickness`). Add the helper:

```python
def _sickness_preview(person, leave_type, first, last, booking=None):
    """For a sickness type: the entry this one joins on to (LEAVE-41) with
    the dates an Extend would give, whether it is long, and the instances
    and trigger after it when recorded separately. Empty for other types."""
    if not leave_type.sickness:
        return {}
    joins = sickness.joins_on(person, first, last, exclude=booking)
    others = [b for b in sickness.instances(person) if booking is None or b.pk != booking.pk]
    count = len(others) + (1 if sickness.overlaps_window(first, last) else 0)
    return {"sickness": {
        "joins": joins,
        "extended_first": min(first, joins.first_day) if joins else None,
        "extended_last": max(last, joins.last_day) if joins else None,
        "long": (last - first).days + 1 >= sickness.LONG_DAYS,
        "instances_after": count, "level_label": sickness.level_label(sickness.level(count))}}
```

In `add`, the block under `if form.is_valid() and not request.POST.get("preview") and "error" not in preview:` becomes:

```python
            s = preview.get("sickness") or {}
            base = request.build_absolute_uri("/")
            if s.get("joins") is not None and request.POST.get("join", "extend") == "extend":
                try:        # LEAVE-41: the manager chose to extend the entry this one joins on to
                    bookings.edit(request.user, s["joins"], base_url=base, note="extended (joined on)",
                                  first=s["extended_first"], last=s["extended_last"])
                    return JsonResponse(REFRESH)
                except LeaveError as e:
                    form.add_error(None, e.message)
            else:
                person = form.cleaned_data["person"]
                kw = form.booking_kwargs()
                note = form.cleaned_data["manager_note"]
                try:
                    if bookings.may_book(request.user, person):
                        bookings.book(request.user, person, note=note, costs=form.costs(), base_url=base, **kw)
                        return JsonResponse(REFRESH)
                    if access.is_self(request.user, person):
                        bookings.request(request.user, person, note=note, base_url=base, **kw)
                        return render(request, "leave/add_dialog.html", {"form": form, "preview": {}, "pending_own": True, "refresh": True})
                    raise PermissionDenied
                except LeaveError as e:
                    form.add_error(None, e.message)
```

Pass `"join": request.POST.get("join", "extend")` and `"editing": False` into the render context of `add`; in `edit` pass `"editing": True`.

`templates/absence/_sickness_preview.html`:

```html
{% with s=preview.sickness %}
{% if s.joins %}
  {% if editing %}<p class="flash flash-warning">This joins on to {{ s.joins.type.name }} {{ s.joins.first_day|date:"j M" }}–{{ s.joins.last_day|date:"j M Y" }}: the two count as separate instances.</p>
  {% else %}<fieldset class="field"><legend>This joins on to {{ s.joins.type.name }} {{ s.joins.first_day|date:"j M" }}–{{ s.joins.last_day|date:"j M Y" }}</legend>
    <label class="check"><input type="radio" name="join" value="extend"{% if join != "separate" %} checked{% endif %}> Extend that entry to {{ s.extended_first|date:"j M" }}–{{ s.extended_last|date:"j M Y" }} (one instance)</label>
    <label class="check"><input type="radio" name="join" value="separate"{% if join == "separate" %} checked{% endif %}> Record as a separate instance</label>
  </fieldset>{% endif %}
{% endif %}
{% if s.long %}<p class="flash flash-warning">This is long sickness (29 days or more): managers are emailed when the person returns.</p>{% endif %}
<p class="field-help">Instances in the last six months after this entry: {{ s.instances_after }}{% if s.level_label %} ({{ s.level_label }}){% endif %}</p>
{% endwith %}
```

`templates/leave/add_dialog.html`: after the `{% include "leave/_preview.html" ... %}` line add `{% if preview.sickness %}{% include "absence/_sickness_preview.html" %}{% endif %}`, and the button text becomes `{% if booking %}Save changes{% elif preview.sickness.joins and join != "separate" %}Extend the existing entry{% else %}Add time off{% endif %}`.

- [ ] **Step 4: The past schedule section**

`absence/forms.py`:

```python
class PastSicknessForm(forms.Form):
    """MIG-05: 2026 sickness by hand, dates only."""
    person = forms.ModelChoiceField(Person.objects.none(), label="Staff member")
    type = forms.ModelChoiceField(LeaveType.objects.filter(archived=False, sickness=True), label="Type")
    first_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), label="First day")
    last_day = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), label="Last day")

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["person"].queryset = access.managed_people(user).distinct().order_by("last_name", "first_name")
        for name in ("person", "type", "first_day", "last_day"):
            self.fields[name].widget.attrs["data-submit-on-change"] = ""

    def clean(self):
        d = super().clean()
        if d.get("first_day") and d.get("last_day") and d["last_day"] < d["first_day"]:
            self.add_error("last_day", "The last day is before the first")
        return d
```

(imports: `from people.models import Person`, `from people.services import access`.)

`absence/views/past.py`:

```python
"""The past schedule section (MIG-05, ACC-06): managers only; 2026
sickness typed as dates-only bookings so the triggers are right from
launch. Entries are listed with each person's instances and trigger."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from absence.forms import PastSicknessForm
from leave.models import Booking
from leave.services import bookings, sickness
from leave.services.common import LeaveError
from leave.views.add import _sickness_preview
from people.services import access

REFRESH = {"refresh": True}


@login_required
@access.manager_required
def index(request):
    people = access.managed_people(request.user)
    rows = (Booking.objects.filter(person__in=people, dates_only=True, status__in=Booking.LIVE)
            .select_related("person__team", "type", "decided_by").order_by("-first_day", "person__last_name"))
    levels = {}
    out = []
    for b in rows:
        if b.person_id not in levels:
            n = len(sickness.instances(b.person))
            levels[b.person_id] = (n, sickness.level_label(sickness.level(n)))
        out.append({"b": b, "days": (b.last_day - b.first_day).days + 1, "long": sickness.is_long(b), "instances": levels[b.person_id][0], "trigger": levels[b.person_id][1]})
    return render(request, "absence/past.html", {"page_title": "Past schedule", "rows": out})


@login_required
@access.manager_required
def add(request):
    form = PastSicknessForm(request.user, request.POST or None)
    preview = {}
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        preview = _sickness_preview(d["person"], d["type"], d["first_day"], d["last_day"])
        if not request.POST.get("preview"):
            s = preview.get("sickness") or {}
            base = request.build_absolute_uri("/")
            try:
                if s.get("joins") is not None and request.POST.get("join", "extend") == "extend":
                    bookings.edit(request.user, s["joins"], base_url=base, note="extended (joined on)", first=s["extended_first"], last=s["extended_last"])
                else:
                    bookings.book(request.user, d["person"], d["type"], d["first_day"], d["last_day"], "whole", base_url=base, dates_only=True)
                return JsonResponse(REFRESH)
            except LeaveError as e:
                form.add_error(None, e.message)
    return render(request, "absence/past_dialog.html", {"form": form, "preview": preview, "join": request.POST.get("join", "extend"), "editing": False})
```

`templates/absence/past.html`:

```html
{% extends "base.html" %}
{% block title %}Past schedule · AMG Shift Central{% endblock %}
{% block topbar_actions %}<a class="topbar-action is-primary" href="{% url 'time-off-past-add' %}" data-dialog>Add past sickness +</a>{% endblock %}
{% block content %}
<p class="field-help">Sickness before the system started, typed with dates only: it counts towards instances and triggers and touches no allowance or payroll figure. Today's sickness is booked as time off.</p>
<table class="table">
  <thead><tr><th>Staff</th><th>First day</th><th>Last day</th><th>Days</th><th>Type</th><th>Long sickness</th><th>Recorded</th><th>Instances now</th><th>Trigger</th><th></th></tr></thead>
  <tbody>
  {% for r in rows %}{% with b=r.b %}
  <tr><td>{{ b.person.name }}</td><td>{{ b.first_day|date:"j M Y" }}</td><td>{{ b.last_day|date:"j M Y" }}</td><td>{{ r.days }}</td><td>{{ b.type.name }}</td>
      <td>{% if r.long %}Yes{% endif %}</td><td>{{ b.decided_by.person.name|default:b.decided_by.email|default:"—" }} · {{ b.requested_at|date:"j M Y" }}</td>
      <td>{{ r.instances }}</td><td>{{ r.trigger }}</td>
      <td><a href="{% url 'time-off-view' b.pk %}" data-dialog>View</a> <a href="{% url 'time-off-edit' b.pk %}" data-dialog>Edit</a> <a href="{% url 'time-off-cancel' b.pk %}" data-dialog>Remove</a></td></tr>
  {% endwith %}{% empty %}<tr><td colspan="10">No past sickness recorded.</td></tr>{% endfor %}
  </tbody>
</table>
{% endblock %}
```

`templates/absence/past_dialog.html`:

```html
{% extends "ui/_dialog.html" %}
{% block dialog_title %}Past sickness{% endblock %}
{% block dialog_body %}
<form method="post" action="{% url 'time-off-past-add' %}" data-dialog-form>
  {% csrf_token %}
  {% for e in form.non_field_errors %}<p class="flash flash-error">{{ e }}</p>{% endfor %}
  <div class="field{% if form.person.errors %} has-error{% endif %}"><label for="id_person">{{ form.person.label }}</label>{{ form.person }}{% for e in form.person.errors %}<p class="field-error">{{ e }}</p>{% endfor %}</div>
  <div class="field"><label for="id_type">{{ form.type.label }}</label>{{ form.type }}</div>
  <div class="field-row">
    <div class="field{% if form.first_day.errors %} has-error{% endif %}"><label for="id_first_day">{{ form.first_day.label }}</label>{{ form.first_day }}{% for e in form.first_day.errors %}<p class="field-error">{{ e }}</p>{% endfor %}</div>
    <div class="field{% if form.last_day.errors %} has-error{% endif %}"><label for="id_last_day">{{ form.last_day.label }}</label>{{ form.last_day }}{% for e in form.last_day.errors %}<p class="field-error">{{ e }}</p>{% endfor %}</div>
  </div>
  <input type="hidden" name="preview" value="1">
  {% if preview.sickness %}{% include "absence/_sickness_preview.html" %}{% endif %}
  <button class="btn btn-dark" name="preview" value="">{% if preview.sickness.joins and join != "separate" %}Extend the existing entry{% else %}Add past sickness{% endif %}</button>
</form>
{% endblock %}
```

`absence/views/__init__.py` adds `from .past import add as past_add, index as past_index  # noqa: F401`; `absence/urls.py` adds `path("time-off/past/", views.past_index, name="time-off-past")` and `path("time-off/past/add/", views.past_add, name="time-off-past-add")`.

- [ ] **Step 5: Grid, list, report, statement, nav**

`leave/services/serialize.py` `leave_for`: after the pending loop add

```python
    history = Booking.objects.filter(person__in=people, status__in=Booking.ACTIVE, dates_only=True, first_day__lte=last, last_day__gte=first).select_related("type")
    for b in history:          # a past schedule entry has no costed days; it still shows where it was
        p = by_pk[b.person_id]
        for day in b.days():
            if first <= day <= last:
                out.setdefault(p.pk, {}).setdefault(day.isoformat(), _json(b, None, detail_for(p)))
```

`leave/views/list.py` `visible_rows`: the row dict gains `"dates_only": b.dates_only` and `"cost": None if b.dates_only else (…existing…)`; the CSV writes `"dates only" if b.dates_only else (hours.fmt(r["cost"]) if r["cost"] is not None else "")`. `templates/leave/list.html`: the Allowance used cell becomes `{% if r.dates_only %}dates only{% elif r.cost is not None %}{{ r.cost|hm }}{% endif %}`.

`leave/views/report.py` `rows`: each row gains `"instances": len(sickness.instances(p, end))` and `"trigger": sickness.level_label(sickness.level(…))` (import `sickness`); the CSV header gains `"Instances", "Trigger"` and the row the two values; `leave_report` team groups sum `instances`. `templates/leave/report.html`: columns `<th>Instances</th><th>Trigger</th>` after TOIL, cells `<td>{{ r.instances }}</td><td>{{ r.trigger }}</td>`, the tfoot `<td>{{ t.instances }}</td><td></td>`.

`leave/views/statement.py` `statement_context`: add

```python
    n = len(sickness.instances(person))
    …, "sickness_count": n, "sickness_label": sickness.level_label(sickness.level(n)),
```

`templates/leave/_statement.html`: after the `</dl>` add `<p>Sickness: {% if sickness_count %}{{ sickness_count }} instance{{ sickness_count|pluralize }}{% else %}none{% endif %} in the last six months{% if sickness_label %} ({{ sickness_label }}){% endif %}</p>`.

`ui/context_processors.py`: the manager `leave_children` gain `{"label": "Past schedule", "url": "/time-off/past/"}` after Blackouts.

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_absence_views.py tests/test_leave_views.py tests/test_leave_reports.py tests/test_leave_grid.py tests/test_shell.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add absence leave ui templates tests/test_absence_views.py
git commit -m "Absence: the join-on warning with Extend or Record separately, the past schedule section, dates-only entries on the grid and list, Instances on the leave report"
```

---

### Task 5: The leaver flags and the return flag

**Files:**
- Create: `leave/services/leavers.py`, `leave/services/returns.py`
- Modify: `leave/services/notify.py` (`leaving`, `returned`), `people/services/hr_sync.py:76-136` (`_apply` returns the people whose end date changed; `sync` flags them), `people/services/health.py:14-45` (`leaving_soon` carries the figures), `templates/people/_health.html:29-30`, `leave/views/statement.py` (`statement_context` gains the leaver line), `templates/leave/_statement.html`, `leave/views/list.py` and `templates/leave/list.html` ("after leaving date"), `tests/test_staff_page.py:100`
- Test: `tests/test_leave_flags.py`

**Interfaces:**
- Consumes: `balances.statement`, `years.year_of`, `common.recipients/span`, `sickness.is_long`, `notify._link/_send_all`, `hr_sync.sync(client)`.
- Produces: `leavers.WEEK = timedelta(days=7)`, `leavers.figure(person) -> (year, Statement)`, `leavers.after_leaving(person) -> [Booking]`, `leavers.flag(person, base_url="") -> bool`, `leavers.week_flags(today=None, base_url="") -> int`, `leavers.figure_text(statement) -> str` ("18 h 30 min of annual leave remaining" / "11 h 30 min of annual leave over" / "no allowance set for the leaving year"); `returns.CATCH_UP = timedelta(days=14)`, `returns.due(today=None) -> [Booking]`, `returns.send(today=None, base_url="") -> int`; `notify.leaving(person, statement, bookings_after, week=False, base_url="")`, `notify.returned(booking, statement, base_url="")`; `health.figures()["leaving_soon"]` is a list of `{"person", "statement", "text", "after"}`; `statement_context` gains `leaver_text`.

- [ ] **Step 1: Write the failing tests**

`tests/test_leave_flags.py`:

```python
"""LEAVE-14 / NOTIF-06 (the leaver flags) and LEAVE-29 / NOTIF-07 (the
return from a long absence): who is emailed, when, and once."""

import json
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.core import mail
from django.test import Client

from leave.services import bank_holidays, bookings, hours, leavers, returns
from people.models import Person
from people.services import health, hr_sync
from tests import clock
from tests.factories import make_allowance, make_booking, make_entry, make_person, make_sick, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(clock.LATE_2026)]
Y26 = date(2026, 1, 1)
BH_TO_OCT = [date(2026, 1, 1), date(2026, 4, 3), date(2026, 4, 6), date(2026, 5, 4), date(2026, 5, 25), date(2026, 8, 31)]
FIXTURE = Path(__file__).parent / "fixtures" / "hr_people.json"


def h(text):
    return hours.from_hours(Decimal(text))


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss")
    make_user_for(boss, is_all_teams_manager=True)
    return boss


def rota(person, year=2026):
    day = date(year, 1, 1) - timedelta(weeks=4)
    while day.year <= year:
        if day.weekday() < 5:
            make_entry(person, day, start=time(9), finish=time(17), break_minutes=30)
        day += timedelta(days=1)


@pytest.fixture
def leaver(boss):
    """LV-07b: 37.5 h Mon–Fri, leaves Wed 14 Oct 2026; total 138.5 h."""
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), end_date=date(2026, 10, 14), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_user_for(sam)
    rota(sam)
    make_allowance(sam, Y26, Decimal("172.5"), 60)
    for bh in BH_TO_OCT:
        bank_holidays.book(boss.user, sam, bh, h("7.5"))
    return sam


def test_lv_07b_the_flag_names_the_hours_over_or_remaining(boss, leaver):
    bookings.book(boss.user, leaver, make_type("Holiday"), date(2026, 2, 2), date(2026, 2, 27), "whole")     # 20 days = 150 h
    year, s = leavers.figure(leaver)
    assert year == Y26 and s.annual_remaining == -h("11.5") and leavers.figure_text(s) == "11 h 30 min of annual leave over"
    assert leavers.flag(leaver) is True
    assert mail.outbox[-1].subject == "Sam Patel is leaving on 14 Oct 2026" and mail.outbox[-1].to == [boss.email]
    assert "11 h 30 min of annual leave over" in mail.outbox[-1].body
    leaver.refresh_from_db()
    assert leaver.leaver_flagged_for == date(2026, 10, 14) and leaver.leaver_week_flagged_for is None
    assert leavers.flag(leaver) is False and len(mail.outbox) == 1                       # same date: not again


def test_lv_07b_remaining_and_the_bookings_after_the_leaving_date(boss, leaver):
    bookings.book(boss.user, leaver, make_type("Holiday"), date(2026, 2, 2), date(2026, 2, 23), "whole")     # 16 days = 120 h
    after = bookings.book(boss.user, leaver, make_type("Holiday"), date(2026, 10, 19), date(2026, 10, 20), "whole")
    year, s = leavers.figure(leaver)
    assert s.annual_remaining == h("18.5") - h("15") and leavers.after_leaving(leaver) == [after]
    leavers.flag(leaver)
    body = mail.outbox[-1].body
    assert "3 h 30 min of annual leave remaining" in body and "to shorten or cancel" in body and "19–20 Oct 2026" in body


def test_a_date_within_a_week_sends_one_email_that_covers_both(boss):
    sam = make_person(first_name="Sam", end_date=date(2026, 11, 6))
    make_allowance(sam, Y26, Decimal("100"), 0)
    assert leavers.flag(sam) is True
    sam.refresh_from_db()
    assert sam.leaver_week_flagged_for == date(2026, 11, 6) and leavers.week_flags() == 0 and len(mail.outbox) == 1


def test_the_week_reminder_goes_once_seven_days_out(boss):
    sam = make_person(first_name="Sam", end_date=date(2026, 11, 20))
    make_allowance(sam, Y26, Decimal("100"), 0)
    leavers.flag(sam)
    assert leavers.week_flags(today=date(2026, 11, 12)) == 0            # eight days out
    assert leavers.week_flags(today=date(2026, 11, 13)) == 1 and mail.outbox[-1].subject == "Sam Patel leaves in a week, on 20 Nov 2026"
    assert leavers.week_flags(today=date(2026, 11, 14)) == 0
    sam.refresh_from_db()
    assert sam.leaver_week_flagged_for == date(2026, 11, 20)


def test_a_cleared_end_date_resets_the_flags_and_a_changed_one_is_announced_again(boss):
    sam = make_person(first_name="Sam", end_date=date(2026, 12, 18))
    make_allowance(sam, Y26, Decimal("100"), 0)
    leavers.flag(sam)
    sam.end_date = None
    sam.save()
    assert leavers.flag(sam) is False
    sam.refresh_from_db()
    assert sam.leaver_flagged_for is None
    sam.end_date = date(2026, 12, 11)
    sam.save()
    assert leavers.flag(sam) is True and len(mail.outbox) == 2


def test_the_hr_sync_flags_a_leaving_date_when_it_arrives_or_changes(boss):
    payload = json.loads(FIXTURE.read_text())

    class Fake:
        def __init__(self, p):
            self.p = p

        def people(self):
            return self.p["people"]

    hr_sync.sync(Fake(payload))
    sam = Person.objects.get(hr_employee_id=1)
    make_allowance(sam, Y26, Decimal("100"), 0)
    sent = len(mail.outbox)
    for rec in payload["people"]:
        if rec["employee_id"] == 1:
            rec["employment"]["end"] = "2026-12-31"
    hr_sync.sync(Fake(payload))
    assert len(mail.outbox) == sent + 1 and "Sam Patel is leaving on 31 Dec 2026" == mail.outbox[-1].subject
    hr_sync.sync(Fake(payload))
    assert len(mail.outbox) == sent + 1
    sam.refresh_from_db()
    assert sam.leaver_flagged_for == date(2026, 12, 31)


def test_the_statement_and_the_health_card_carry_the_leaver_line(boss, leaver):
    after = bookings.book(boss.user, leaver, make_type("Holiday"), date(2026, 10, 19), date(2026, 10, 19), "whole")
    c = Client()
    c.force_login(boss.user)
    body = c.get(f"/staff/{leaver.pk}/profile/?tab=hours").content.decode()
    assert "Leaves on 14 Oct 2026" in body and "of annual leave remaining" in body
    f = health.figures(boss.user)
    (row,) = [r for r in f["leaving_soon"] if r["person"] == leaver]
    assert row["after"] == 1 and "annual leave remaining" in row["text"]
    body = c.get("/staff/").content.decode()
    assert "Sam Patel" in body and "1 booking after" in body
    body = c.get("/time-off/?from=2026-10-01&to=2026-10-31").content.decode()
    assert "after leaving date" in body


# --- returns ---------------------------------------------------------------------

def test_the_return_flag_goes_the_day_after_a_long_sickness_ends_once(boss):
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(sam, Y26, Decimal("172.5"), 0)
    long = make_sick(sam, date(2026, 9, 1), date(2026, 10, 2))      # 32 days
    make_sick(sam, date(2026, 10, 12), date(2026, 10, 16))          # short: never flagged
    assert returns.due(today=date(2026, 10, 2)) == []
    assert returns.due(today=date(2026, 10, 3)) == [long]
    assert returns.send(today=date(2026, 10, 3)) == 1
    assert mail.outbox[-1].subject == "Sam Patel is back after 5 weeks of Sick leave" and "172 h 30 min" in mail.outbox[-1].body
    assert returns.send(today=date(2026, 10, 4)) == 0
    long.refresh_from_db()
    assert long.return_flagged_at is not None


def test_family_leave_is_flagged_on_return_and_history_is_not(boss):
    sam = make_person(first_name="Sam")
    make_allowance(sam, Y26, Decimal("100"), 0)
    mat = make_booking(sam, date(2026, 3, 2), date(2026, 10, 30), type_name="Maternity")
    old = make_booking(sam, date(2025, 1, 6), date(2025, 9, 26), type_name="Maternity")
    make_sick(sam, date(2026, 8, 3), date(2026, 9, 25), dates_only=True)
    assert set(returns.due(today=date(2026, 11, 2))) == {mat}        # the dates-only one and last year's are not due
    assert returns.send(today=date(2026, 11, 2)) == 1 and "Maternity" in mail.outbox[-1].subject
    old.refresh_from_db()
    assert old.return_flagged_at is None


def test_a_leaver_is_not_flagged_on_return(boss):
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), end_date=date(2026, 10, 2))
    make_sick(sam, date(2026, 9, 1), date(2026, 10, 2))
    assert returns.due(today=date(2026, 10, 3)) == []
```

The HR fixture's record shape is `tests/fixtures/hr_people.json`; the test sets `employment.end` on employee 1 as `hr_sync._parse` reads it (check the fixture's key names before running and match them).

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/bin/python -m pytest tests/test_leave_flags.py -q`
Expected: ImportError on `leave.services.leavers`.

- [ ] **Step 3: `leave/services/leavers.py`**

```python
"""LEAVE-14 and NOTIF-06: when Practice HR gives someone an end date, their
managers are told what leave is left or over as at that day and which
bookings run past it; a week before the day they are told again. Nothing
is cancelled for them: the manager decides."""

from datetime import timedelta

from django.utils import timezone

from leave.models import Booking
from leave.services import balances, hours, notify, years
from people.models import Person

WEEK = timedelta(days=7)


def figure(person):
    """The leaving year and its statement: the pro-rata already stops at the
    end date, so annual_remaining is the figure LEAVE-14 asks for."""
    year = years.year_of(person, person.end_date)
    return year, balances.statement(person, year)


def figure_text(statement):
    if statement.missing:
        return "no allowance set for the leaving year"
    remaining = statement.annual_remaining
    if remaining < 0:
        return f"{hours.fmt(-remaining)} of annual leave over"
    return f"{hours.fmt(remaining)} of annual leave remaining"


def after_leaving(person):
    """Live bookings with a day after the end date, to shorten or cancel."""
    return list(Booking.objects.filter(person=person, status__in=Booking.LIVE, last_day__gt=person.end_date)
                .select_related("type").order_by("first_day", "pk"))


def flag(person, base_url=""):
    """The "date entered" email, once per end date. A cleared date resets
    both flags silently. Within a week of the date the one email covers the
    week's reminder too."""
    if person.end_date is None:
        if person.leaver_flagged_for or person.leaver_week_flagged_for:
            Person.objects.filter(pk=person.pk).update(leaver_flagged_for=None, leaver_week_flagged_for=None)
            person.leaver_flagged_for = person.leaver_week_flagged_for = None
        return False
    if person.leaver_flagged_for == person.end_date:
        return False
    today = timezone.localdate()
    within_week = person.end_date <= today + WEEK
    fields = {"leaver_flagged_for": person.end_date}
    if within_week:
        fields["leaver_week_flagged_for"] = person.end_date
    # Claim first, then send: two syncs seeing the same new date send one email between them.
    if not Person.objects.filter(pk=person.pk).exclude(leaver_flagged_for=person.end_date).update(**fields):
        return False
    for k, v in fields.items():
        setattr(person, k, v)
    _, statement = figure(person)
    notify.leaving(person, statement, after_leaving(person), week=within_week, base_url=base_url)
    return True


def week_flags(today=None, base_url=""):
    """The reminder a week out, for everyone leaving in the next seven days
    not yet reminded for that date. Run daily."""
    today = today or timezone.localdate()
    n = 0
    for p in Person.objects.filter(end_date__gte=today, end_date__lte=today + WEEK).order_by("end_date", "pk"):
        if p.leaver_week_flagged_for == p.end_date:
            continue
        if not Person.objects.filter(pk=p.pk).exclude(leaver_week_flagged_for=p.end_date).update(leaver_week_flagged_for=p.end_date):
            continue           # claimed by a run alongside this one
        _, statement = figure(p)
        notify.leaving(p, statement, after_leaving(p), week=True, base_url=base_url)
        n += 1
    return n
```

- [ ] **Step 4: `leave/services/returns.py`**

```python
"""LEAVE-29 and NOTIF-07: the day after a long sickness, or a booking of a
type that flags the return (maternity, adoption), the managers are told
the person is back and what leave they have, so it can be planned. Once
per booking; a run that missed a day catches up for a fortnight."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from leave.models import Booking
from leave.services import balances, notify, sickness, years

CATCH_UP = timedelta(days=14)


def due(today=None):
    today = today or timezone.localdate()
    rows = (Booking.objects.filter(status__in=Booking.ACTIVE, dates_only=False, return_flagged_at__isnull=True,
                                   last_day__lt=today, last_day__gte=today - CATCH_UP)
            .filter(Q(type__flag_return=True) | Q(type__sickness=True))
            .filter(Q(person__end_date__isnull=True) | Q(person__end_date__gte=today))
            .select_related("person", "type").order_by("last_day", "pk"))
    return [b for b in rows if b.type.flag_return or sickness.is_long(b)]


def send(today=None, base_url=""):
    today = today or timezone.localdate()
    n = 0
    for b in due(today):
        # Claim the row first: a second run alongside this one finds it claimed and sends nothing.
        if not Booking.objects.filter(pk=b.pk, return_flagged_at__isnull=True).update(return_flagged_at=timezone.now()):
            continue
        statement = balances.statement(b.person, years.year_of(b.person, today))
        notify.returned(b, statement, base_url)
        n += 1
    return n
```

- [ ] **Step 5: The two emails**

`leave/services/notify.py`:

```python
def leaving(person, statement, bookings_after, week=False, base_url=""):
    """NOTIF-06, the two leaver emails: the figure as at the leaving date
    (LEAVE-14) and the bookings that run past it."""
    from leave.services import leavers
    when = f"{person.end_date:%-d %b %Y}"
    lines = "".join(f"\n  {b.type.name} {span(b)}" for b in bookings_after)
    body = (f"{person.name} {'leaves in a week' if week else 'is leaving'}, on {when}.\n\n"
            f"As at that day: {leavers.figure_text(statement)}; TOIL remaining {hours.fmt(statement.toil_remaining)}.\n"
            + (f"\nTime off booked after the leaving date, to shorten or cancel:{lines}\n" if bookings_after else "")
            + f"\nProfile: {_link(base_url, f'/staff/{person.pk}/profile/?tab=hours')}\n")
    subject = f"{person.name} leaves in a week, on {when}" if week else f"{person.name} is leaving on {when}"
    return _send_all(recipients(person), subject, body)


def returned(booking, statement, base_url=""):
    """NOTIF-07: back from a long absence, with the leave still to take.
    The allowance was not reduced by the absence (LEAVE-29)."""
    p = booking.person
    weeks = ((booking.last_day - booking.first_day).days + 1) // 7
    body = (f"{p.name} is back after {span(booking)} ({booking.type.name}).\n\n"
            f"Annual leave remaining this leave year: {'not set' if statement.missing else hours.fmt(statement.annual_remaining)}; "
            f"TOIL remaining {hours.fmt(statement.toil_remaining)}. The allowance is a full-year figure and was not reduced by the absence; "
            f"leave that could not be taken may need planning or carrying over.\n\n"
            f"Profile: {_link(base_url, f'/staff/{p.pk}/profile/?tab=hours')}\n")
    return _send_all(recipients(p), f"{p.name} is back after {weeks} week{'' if weeks == 1 else 's'} of {booking.type.name}", body)
```

(`leavers` is imported inside `leaving` because `leavers` imports `notify`.)

- [ ] **Step 6: The HR sync hook**

`people/services/hr_sync.py` `_apply`: collect and return the people whose end date changed. Before the loop `leaving = []`; after `if changes:` (inside it) add `if "end_date" in changes: leaving.append(person)`; end with `return leaving`. In `sync`, change `_apply(records, timezone.now())` to `leaving = _apply(records, timezone.now())` (declare `leaving = []` before the `try`) and, after the `finally` block and before the hours-changes block, add:

```python
    if run.ok:
        from leave.services import leavers       # people → leave only here, at call time
        for person in leaving:
            try:
                leavers.flag(person)
            except Exception:
                log.exception("leaver flag failed for person %s", person.pk)
```

- [ ] **Step 7: Health, statement, list**

`people/services/health.py` `figures`: replace the `leaving_soon` entry with

```python
        "leaving_soon": _leaving(people, today),
```

and add

```python
def _leaving(people, today):
    """Everyone leaving in the next 30 days, with LEAVE-14's figure and the
    count of bookings past the date, for the card's line."""
    from leave.services import leavers
    out = []
    for p in people.filter(end_date__gte=today, end_date__lte=today + LEAVING_WINDOW).order_by("end_date", "last_name"):
        _, statement = leavers.figure(p)
        out.append({"person": p, "statement": statement, "text": leavers.figure_text(statement), "after": len(leavers.after_leaving(p))})
    return out
```

`templates/people/_health.html` lines 29-30 become:

```html
  <div class="health-item{% if health.leaving_soon %} is-warning{% endif %}">Leaving in the next 30 days<strong>{{ health.leaving_soon|length }}</strong>
    {% for r in health.leaving_soon %}<a href="{% url 'profile' r.person.pk %}?tab=hours" data-dialog>{{ r.person.name }}</a> ({{ r.person.end_date|date:"j M" }}, {{ r.text }}{% if r.after %}, {{ r.after }} booking{{ r.after|pluralize }} after{% endif %}){% if not forloop.last %}, {% endif %}{% endfor %}</div>
```

`tests/test_staff_page.py:100` becomes `assert [r["person"].first_name for r in f["leaving_soon"]] == ["Leaving"]`.

`leave/views/statement.py` `statement_context`: add `"leaver_text": leavers.figure_text(leavers.figure(person)[1]) if person.end_date else ""` (import `leavers`). `templates/leave/_statement.html`, before the `<dl>`: `{% if leaver_text %}<p class="flash flash-warning">Leaves on {{ person.end_date|date:"j M Y" }}: {{ leaver_text }}.</p>{% endif %}`.

`leave/views/list.py` `visible_rows`: the row gains `"after_leaving": detail and b.person.end_date is not None and b.last_day > b.person.end_date`; `templates/leave/list.html` Status cell: `{{ r.status }}{% if r.after_leaving %} · after leaving date{% endif %}`.

- [ ] **Step 8: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_leave_flags.py tests/test_staff_page.py tests/test_hr_sync.py tests/test_leave_views.py -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add leave people templates tests/test_leave_flags.py tests/test_staff_page.py
git commit -m "Leave: the leaver flags from the HR sync and a week before, the return flag after a long absence; the leaver's figure on the statement and the Health card"
```

---

### Task 6: The year-end flag, its page and decision, the daily command and its timer

**Files:**
- Create: `leave/services/yearend.py`, `leave/views/yearend.py`, `templates/leave/year_end.html`, `templates/leave/year_end_dialog.html`, `leave/management/commands/daily_flags.py`, `deploy/shift-central-daily-flags.service`, `deploy/shift-central-daily-flags.timer`
- Modify: `leave/forms.py` (`YearEndForm`), `leave/services/notify.py` (`year_end`), `leave/views/__init__.py`, `leave/urls.py`, `people/services/health.py` (`year_end_waiting`), `templates/people/_health.html`, `people/views/activity.py:13` (`PERSON_MODELS`), `ui/context_processors.py` (Year end), `tests/test_deploy_units.py:62-67`
- Test: `tests/test_leave_yearend.py`

**Interfaces:**
- Consumes: `balances.statement`, `years.*`, `adjustments.add`, `common.recipients`, `sickness.is_long`, `leavers.week_flags`, `returns.send`.
- Produces: `yearend.OPEN_WINDOW = timedelta(days=31)`, `yearend.open_due(today=None) -> [YearEnd]`, `yearend.notify_opened(rows, base_url="") -> int` (managers emailed), `yearend.run(today=None, base_url="") -> int`, `yearend.decide(user, row, annual_carry, toil_keep=None, note="") -> YearEnd`, `yearend.long_absence(row) -> bool`, `yearend.open_rows(user) -> [YearEnd]`; `notify.year_end(manager, rows, base_url="")`; URLs `time-off-year-end` (`/time-off/year-end/`), `time-off-year-end-decide` (`/time-off/year-end/<pk>/decide/`); `manage.py daily_flags`; `health.figures()["year_end_waiting"]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_leave_yearend.py`:

```python
"""LEAVE-21, 22, 24 and NOTIF-08: at the start of a leave year the managers
are flagged about everyone with leave or TOIL left; for each they carry it
all, lose it, or carry part, written as Adjustments in the new year."""

from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.core import mail
from django.core.management import call_command
from django.test import Client

from leave.models import Adjustment, YearEnd
from leave.services import adjustments, balances, bookings, hours, yearend
from people.models import AuditEntry
from people.services import health
from tests.factories import make_allowance, make_booking, make_entry, make_person, make_sick, make_team, make_team_manager, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 11, 2))]    # late 2027: the fixtures book 2027 leave
Y27, Y28 = date(2027, 1, 1), date(2028, 1, 1)
J3 = date(2028, 1, 3)                                                           # the flag runs in the new year
ROOT = Path(__file__).resolve().parents[1]


def h(text):
    return hours.from_hours(Decimal(text))


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss")
    make_user_for(boss, is_all_teams_manager=True)
    return boss


@pytest.fixture
def sam(boss):
    """LV-15a's person: 172.5 h for 2027 plus 15 h carried from 2026, 167.5 h
    taken, so 20 h left at the end of 2027. Bank holiday allowance 0 so the
    annual figure is the plain one."""
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_user_for(sam)
    make_allowance(sam, Y27, Decimal("172.5"), 0)
    make_allowance(sam, Y28, Decimal("172.5"), 0)
    adjustments.add(boss.user, sam, Y27, "annual", h("15"), "carried over from FindMyShift 2026")
    day = date(2027, 3, 1)
    for _ in range(22):                       # 22 working days at 7.5 h = 165 h
        while day.weekday() >= 5:
            day += timedelta(days=1)
        make_entry(sam, day, start=time(9), finish=time(17), break_minutes=30)
        bookings.book(boss.user, sam, make_type("Holiday"), day, day, "whole")
        day += timedelta(days=1)
    bookings.book(boss.user, sam, make_type("Holiday"), date(2027, 6, 1), date(2027, 6, 1), "whole", costs={date(2027, 6, 1): h("2.5")})
    assert balances.statement(sam, Y27).annual_remaining == h("20")
    return sam


def test_lv_15a_the_flag_offers_whatever_is_left_and_carry_all_adds_it(boss, sam):
    (row,) = yearend.open_due(today=J3)
    assert (row.person, row.year_ended, row.annual_remaining, row.toil_remaining, row.decided) == (sam, Y27, h("20"), 0, False)
    assert yearend.open_due(today=J3) == []                                           # once
    assert yearend.notify_opened([row]) == 1
    assert mail.outbox[-1].subject == "Year end: 1 person has leave or TOIL left" and "Sam Patel" in mail.outbox[-1].body and "20 h" in mail.outbox[-1].body
    row.refresh_from_db()
    assert row.notified_at is not None
    yearend.decide(boss.user, row, h("20"))
    assert balances.statement(sam, Y28).annual_remaining == h("192.5")
    adj = Adjustment.objects.get(person=sam, leave_year=Y28)
    assert (adj.account, adj.seconds, adj.reason) == ("annual", h("20"), "carried over from 2027")
    row.refresh_from_db()
    assert (row.annual_carried, row.annual_lost, row.toil_lost, row.decided_by) == (h("20"), 0, 0, boss.user)


def test_lv_15b_partial_carry_over_is_logged(boss, sam):
    (row,) = yearend.open_due(today=J3)
    yearend.decide(boss.user, row, h("10"), note="agreed with Sam")
    assert balances.statement(sam, Y28).annual_remaining == h("182.5")
    row.refresh_from_db()
    assert row.annual_carried == h("10") and row.annual_lost == h("10")
    assert AuditEntry.objects.filter(model="leave.yearend", object_id=sam.pk, note="agreed with Sam").exists()
    with pytest.raises(ValueError):
        yearend.decide(boss.user, row, h("5"))                                 # already decided


def test_lv_16_toil_left_is_offered_and_only_a_loss_writes_anything(boss):
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(sam, Y27, Decimal("172.5"), 0)
    make_allowance(sam, Y28, Decimal("172.5"), 0)
    make_entry(sam, date(2027, 10, 11), start=time(17), finish=time(20), break_minutes=0, overtime="toil")      # LV-16 moved a month earlier: TOIL earned counts to today
    make_entry(sam, date(2027, 10, 20), start=time(9), finish=time(11), break_minutes=0)
    bookings.book(boss.user, sam, make_type("TOIL", draws_from="toil"), date(2027, 10, 20), date(2027, 10, 20), "whole")
    assert balances.statement(sam, Y27).toil_remaining == h("1")
    (row,) = yearend.open_due(today=J3)
    assert row.toil_remaining == h("1") and row.annual_remaining == h("172.5")
    yearend.decide(boss.user, row, h("172.5"), toil_keep=h("1"))            # keep all TOIL
    assert not Adjustment.objects.filter(person=sam, account="toil").exists()
    row2 = YearEnd.objects.create(person=make_person(first_name="Tom"), year_ended=Y27, annual_remaining=0, toil_remaining=h("1"))
    yearend.decide(boss.user, row2, 0, toil_keep=0)
    adj = Adjustment.objects.get(person=row2.person, account="toil")
    assert (adj.leave_year, adj.seconds, adj.reason) == (Y28, -h("1"), "TOIL lost at year end 2027")


def test_a_deficit_is_carried_as_a_negative_or_written_off(boss):
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(sam, Y27, Decimal("10"), 0)
    make_allowance(sam, Y28, Decimal("172.5"), 0)
    bookings.book(boss.user, sam, make_type("Holiday"), date(2027, 6, 1), date(2027, 6, 1), "whole", costs={date(2027, 6, 1): h("15")})
    (row,) = yearend.open_due(today=J3)
    assert row.annual_remaining == -h("5")
    with pytest.raises(ValueError):
        yearend.decide(boss.user, row, h("5"))                                 # outside remaining..0
    yearend.decide(boss.user, row, -h("5"))
    assert Adjustment.objects.get(person=sam, leave_year=Y28).reason == "deficit carried over from 2027"
    assert balances.statement(sam, Y28).annual_remaining == h("167.5")


def test_nothing_left_closes_at_once_and_a_missing_year_opens_nothing(boss):
    done = make_person(first_name="Done", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(done, Y27, Decimal("7.5"), 0)
    make_allowance(done, Y28, Decimal("7.5"), 0)
    make_entry(done, date(2027, 6, 1), start=time(9), finish=time(17), break_minutes=30)
    bookings.book(boss.user, done, make_type("Holiday"), date(2027, 6, 1), date(2027, 6, 1), "whole")
    make_person(first_name="New", start_date=date(2027, 11, 1))               # no 2027 allowance: nothing to ask
    assert yearend.run(today=J3) == 0
    row = YearEnd.objects.get(person=done)
    assert row.decided and row.note == "nothing left" and row.decided_by is None and mail.outbox == []
    assert not YearEnd.objects.filter(person__first_name="New").exists()


def test_a_leave_year_starting_in_april_opens_in_april_and_the_window_is_a_month():
    sam = make_person(first_name="Sam", start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5, leave_year_start="04-01")
    make_allowance(sam, date(2027, 4, 1), Decimal("100"), 0)
    make_allowance(sam, date(2028, 4, 1), Decimal("100"), 0)
    assert yearend.open_due(today=date(2028, 1, 3)) == []
    assert yearend.open_due(today=date(2028, 5, 3)) == []                     # more than 31 days in: left alone
    (row,) = yearend.open_due(today=date(2028, 4, 20))
    assert row.year_ended == date(2027, 4, 1) and row.annual_remaining == h("100")


def test_each_manager_gets_one_email_for_their_people(boss):
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_user_for(lead)
    make_team_manager(lead, team)
    rows = []
    for name, t in (("Ann", team), ("Nick", make_team("Nursing"))):
        p = make_person(first_name=name, team=t)
        rows.append(YearEnd.objects.create(person=p, year_ended=Y27, annual_remaining=h("5")))
    assert yearend.notify_opened(rows) == 2
    by_to = {m.to[0]: m for m in mail.outbox}
    assert "Ann" in by_to[lead.email].body and "Nick" not in by_to[lead.email].body
    assert by_to[boss.email].subject == "Year end: 2 people have leave or TOIL left"


def test_the_page_and_the_dialog(boss, sam, today):
    team = make_team("Nursing")
    other = make_person(first_name="Other", team=team)
    lead = make_person(first_name="Lead", team=team)
    make_user_for(lead)
    make_team_manager(lead, team)
    YearEnd.objects.create(person=other, year_ended=Y27, annual_remaining=h("3"))
    make_sick(sam, date(2027, 8, 2), date(2027, 9, 3))                        # long sickness in the year: marked
    today(J3)
    (row,) = yearend.open_due()
    c = Client()
    c.force_login(boss.user)
    body = c.get("/time-off/year-end/").content.decode()
    assert "Sam Patel" in body and "Other" in body and "long absence" in body and "20 h" in body
    assert health.figures(boss.user)["year_end_waiting"] == 2
    body = Client()
    body.force_login(lead.user)
    page = body.get("/time-off/year-end/").content.decode()
    assert "Other" in page and "Sam Patel" not in page
    assert body.get(f"/time-off/year-end/{row.pk}/decide/").status_code == 403
    r = c.post(f"/time-off/year-end/{row.pk}/decide/", {"annual_choice": "part", "annual_hours": "10", "toil_choice": "keep", "toil_hours": "", "note": ""})
    assert r.json() == {"refresh": True}
    row.refresh_from_db()
    assert row.annual_carried == h("10")
    assert "Decided" in c.get("/time-off/year-end/").content.decode()
    staff = Client()
    staff.force_login(sam.user)
    assert staff.get("/time-off/year-end/").status_code == 403
    assert 'href="/time-off/year-end/"' in c.get("/time-off/").content.decode()


def test_the_daily_command_and_its_units(boss, sam, today):
    today(J3)
    call_command("daily_flags")
    assert YearEnd.objects.filter(person=sam).exists()
    unit = (ROOT / "deploy" / "shift-central-daily-flags.service").read_text()
    assert "manage.py daily_flags" in unit
    timer = (ROOT / "deploy" / "shift-central-daily-flags.timer").read_text()
    assert "OnCalendar=*-*-* 08:25:00" in timer and "Persistent=true" in timer
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/bin/python -m pytest tests/test_leave_yearend.py -q`
Expected: ImportError on `leave.services.yearend`.

- [ ] **Step 3: `leave/services/yearend.py`**

```python
"""LEAVE-21, 22 and 24: the year-end flag. When a person's leave year has
just ended, a YearEnd row records what was left; the managers are emailed;
on the page one chooses carry all, lose all or carry part (and keep or
lose TOIL), and the choice is written as Adjustments in the new year with
the reason the statement then shows."""

from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from leave.models import Booking, YearEnd
from leave.services import adjustments, balances, hours, notify, sickness, years
from leave.services.common import recipients
from people.models import Person
from people.services import access, audit

OPEN_WINDOW = timedelta(days=31)


def open_due(today=None):
    """Open a row for each current person whose leave year began within the
    last month and whose ended year has no row yet. A year with no allowance
    (everyone's 2026) opens nothing; nothing left closes at once. Returns
    the rows that need a decision."""
    today = today or timezone.localdate()
    opened = []
    for person in Person.objects.current(on=today).order_by("pk"):
        year = years.year_of(person, today)
        if today - year > OPEN_WINDOW:
            continue
        ended = years.previous_year(year)
        if YearEnd.objects.filter(person=person, year_ended=ended).exists():
            continue
        s = balances.statement(person, ended)
        if s.missing:
            continue
        row = YearEnd(person=person, year_ended=ended, annual_remaining=s.annual_remaining, toil_remaining=s.toil_remaining)
        if s.annual_remaining == 0 and s.toil_remaining <= 0:
            row.decided_at, row.note = timezone.now(), "nothing left"
            row.annual_carried = row.annual_lost = row.toil_lost = 0
        row.save()
        if not row.decided:
            opened.append(row)
    return opened


def notify_opened(rows, base_url=""):
    """One email per manager, naming the people they manage among rows."""
    by_manager = {}
    for row in rows:
        for m in recipients(row.person):
            by_manager.setdefault(m.pk, (m, []))[1].append(row)
    for manager, theirs in by_manager.values():
        notify.year_end(manager, theirs, base_url)
    YearEnd.objects.filter(pk__in=[r.pk for r in rows]).update(notified_at=timezone.now())
    return len(by_manager)


def run(today=None, base_url=""):
    rows = open_due(today)
    if rows:
        notify_opened(rows, base_url)
    return len(rows)


def long_absence(row):
    """Whether a long sickness or a flagged-return booking touched the year
    (LEAVE-29: marked in the year-end flag)."""
    end = years.year_end(row.year_ended)
    rows = Booking.objects.filter(person=row.person, status__in=Booking.ACTIVE, first_day__lte=end, last_day__gte=row.year_ended).select_related("type")
    return any(b.type.flag_return or (b.type.sickness and sickness.is_long(b)) for b in rows)


def open_rows(user):
    return list(YearEnd.objects.filter(person__in=access.managed_people(user), decided_at__isnull=True).select_related("person__team"))


def decide(user, row, annual_carry, toil_keep=None, note=""):
    if not access.can_manage(user, row.person):
        raise PermissionDenied("you don't manage this person")
    with transaction.atomic():
        fresh = YearEnd.objects.select_related("person").get(pk=row.pk)
        if fresh.decided:
            raise ValueError("Already decided")
        remaining = fresh.annual_remaining
        low, high = (remaining, 0) if remaining < 0 else (0, remaining)
        if not (low <= int(annual_carry) <= high):
            raise ValueError(f"Carry between {hours.fmt(low)} and {hours.fmt(high)}")
        toil_keep = fresh.toil_remaining if toil_keep is None else int(toil_keep)
        toil_lost = 0
        if fresh.toil_remaining > 0:
            if not (0 <= toil_keep <= fresh.toil_remaining):
                raise ValueError(f"Keep between 0 min and {hours.fmt(fresh.toil_remaining)} of TOIL")
            toil_lost = fresh.toil_remaining - toil_keep
        new_year = years.next_year(fresh.year_ended)
        label = years.label(fresh.year_ended)
        if annual_carry:
            reason = f"{'deficit ' if annual_carry < 0 else ''}carried over from {label}"
            adjustments.add(user, fresh.person, new_year, "annual", annual_carry, reason)
        if toil_lost:
            adjustments.add(user, fresh.person, new_year, "toil", -toil_lost, f"TOIL lost at year end {label}")
        fresh.annual_carried, fresh.annual_lost, fresh.toil_lost = int(annual_carry), remaining - int(annual_carry), toil_lost
        fresh.decided_by, fresh.decided_at, fresh.note = user, timezone.now(), (note or "").strip()[:300]
        fresh.save()
        audit.record_as(user, "leave.yearend", fresh.person_id,
                        {f"year end {label}": ("", f"carried {hours.fmt(fresh.annual_carried)}, lost {hours.fmt(fresh.annual_lost)}, TOIL lost {hours.fmt(toil_lost)}")},
                        note=fresh.note)
    return fresh
```

`leave/services/notify.py`:

```python
def year_end(manager, rows, base_url=""):
    """NOTIF-08: one email per manager at the start of a leave year."""
    from leave.services import years
    lines = "\n".join(
        f"  {r.person.name} ({years.label(r.year_ended)}): "
        + (f"{hours.fmt(-r.annual_remaining)} over" if r.annual_remaining < 0 else f"{hours.fmt(r.annual_remaining)} of annual leave left")
        + (f", TOIL {hours.fmt(r.toil_remaining)}" if r.toil_remaining > 0 else "") for r in rows)
    n = len(rows)
    body = (f"The leave year has ended for {n} of your people with annual leave or TOIL left over, or over.\n\n{lines}\n\n"
            f"For each, choose carry all, lose all or carry part: {_link(base_url, '/time-off/year-end/')}\n")
    return _send_all([manager], f"Year end: {n} {'person has' if n == 1 else 'people have'} leave or TOIL left", body)
```

- [ ] **Step 4: Form, view, templates**

`leave/forms.py`:

```python
class YearEndForm(forms.Form):
    annual_choice = forms.ChoiceField(choices=[("all", "Carry it all"), ("none", "Lose it all"), ("part", "Carry part")], initial="all")
    annual_hours = forms.CharField(max_length=12, required=False, help_text="Hours to carry, e.g. 10:00")
    toil_choice = forms.ChoiceField(choices=[("keep", "Keep it all"), ("lose", "Lose it all"), ("part", "Keep part")], initial="keep", required=False)
    toil_hours = forms.CharField(max_length=12, required=False)
    note = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, row=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.row = row
        if row is not None and row.annual_remaining < 0:
            self.fields["annual_choice"].choices = [("all", "Carry the deficit into the new year"), ("none", "Write it off")]
        if row is not None and row.toil_remaining <= 0:
            del self.fields["toil_choice"], self.fields["toil_hours"]

    def _part(self, text, limit, what):
        seconds = parse_hours(text)
        if seconds is None:
            raise forms.ValidationError(f"Type the {what} hours")
        if not 0 <= seconds <= limit:
            raise forms.ValidationError(f"Between 0 and {hours.fmt(limit)}")
        return seconds

    def clean(self):
        d = super().clean()
        row = self.row
        if row is None or self.errors:
            return d
        choice = d.get("annual_choice")
        if choice == "all":
            d["annual_carry"] = row.annual_remaining
        elif choice == "none":
            d["annual_carry"] = 0
        else:
            try:
                d["annual_carry"] = self._part(d.get("annual_hours"), row.annual_remaining, "annual leave")
            except forms.ValidationError as e:
                self.add_error("annual_hours", e)
        if "toil_choice" in self.fields:
            tc = d.get("toil_choice") or "keep"
            if tc == "keep":
                d["toil_keep"] = row.toil_remaining
            elif tc == "lose":
                d["toil_keep"] = 0
            else:
                try:
                    d["toil_keep"] = self._part(d.get("toil_hours"), row.toil_remaining, "TOIL")
                except forms.ValidationError as e:
                    self.add_error("toil_hours", e)
        else:
            d["toil_keep"] = None
        return d
```

`leave/views/yearend.py`:

```python
"""The year-end page (LEAVE-21): open flags for the manager's people, each
with a Decide pop-up; decided rows beneath for the record."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from leave.forms import YearEndForm
from leave.models import YearEnd
from leave.services import yearend, years
from people.services import access

REFRESH = {"refresh": True}


def _row(r):
    return {"row": r, "label": years.label(r.year_ended), "long": yearend.long_absence(r), "over": r.annual_remaining < 0}


@login_required
@access.manager_required
def index(request):
    people = access.managed_people(request.user)
    decided = (YearEnd.objects.filter(person__in=people, decided_at__isnull=False).exclude(note="nothing left")
               .select_related("person__team", "decided_by").order_by("-decided_at")[:200])
    return render(request, "leave/year_end.html", {
        "page_title": "Year end", "open": [_row(r) for r in yearend.open_rows(request.user)],
        "decided": [_row(r) for r in decided]})


@login_required
@access.manager_required
def decide(request, pk):
    row = get_object_or_404(YearEnd.objects.select_related("person"), pk=pk)
    if not access.can_manage(request.user, row.person):
        raise PermissionDenied
    form = YearEndForm(request.POST or None, row=row)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            yearend.decide(request.user, row, d["annual_carry"], d["toil_keep"], d["note"])
            return JsonResponse(REFRESH)
        except ValueError as e:
            form.add_error(None, str(e))
    return render(request, "leave/year_end_dialog.html", {"form": form, **_row(row), "new_year": years.label(years.next_year(row.year_ended))})
```

`templates/leave/year_end.html`:

```html
{% extends "base.html" %}
{% load leave_extras %}
{% block title %}Year end · AMG Shift Central{% endblock %}
{% block content %}
<p class="field-help">At the start of each leave year, everyone with annual leave or TOIL left (or over). Carry it all, lose it, or carry part; the carry is written as an adjustment in the new year and shows on the statement.</p>
<h2>Waiting for a decision</h2>
<table class="table">
  <thead><tr><th>Staff</th><th>Team</th><th>Year ended</th><th>Annual leave left</th><th>TOIL left</th><th></th><th></th></tr></thead>
  <tbody>
  {% for r in open %}{% with y=r.row %}
  <tr><td>{{ y.person.name }}</td><td>{{ y.person.team.name|default:"—" }}</td><td>{{ r.label }}</td>
      <td>{% if r.over %}<span class="field-error">{{ y.annual_remaining|hm }} (over)</span>{% else %}{{ y.annual_remaining|hm }}{% endif %}</td>
      <td>{% if y.toil_remaining > 0 %}{{ y.toil_remaining|hm }}{% endif %}</td>
      <td>{% if r.long %}<span class="chip">long absence this year</span>{% endif %}</td>
      <td><a href="{% url 'time-off-year-end-decide' y.pk %}" data-dialog>Decide…</a></td></tr>
  {% endwith %}{% empty %}<tr><td colspan="7">Nothing waiting.</td></tr>{% endfor %}
  </tbody>
</table>
<h2>Decided</h2>
<table class="table">
  <thead><tr><th>Staff</th><th>Year ended</th><th>Was left</th><th>Carried</th><th>Lost</th><th>TOIL lost</th><th>Decided</th><th>Note</th></tr></thead>
  <tbody>
  {% for r in decided %}{% with y=r.row %}
  <tr><td>{{ y.person.name }}</td><td>{{ r.label }}</td><td>{{ y.annual_remaining|hm }}</td><td>{{ y.annual_carried|hm }}</td><td>{{ y.annual_lost|hm }}</td><td>{{ y.toil_lost|hm }}</td>
      <td>{{ y.decided_by.person.name|default:y.decided_by.email|default:"—" }} · {{ y.decided_at|date:"j M Y" }}</td><td>{{ y.note }}</td></tr>
  {% endwith %}{% empty %}<tr><td colspan="8">No decisions yet.</td></tr>{% endfor %}
  </tbody>
</table>
{% endblock %}
```

`templates/leave/year_end_dialog.html`:

```html
{% extends "ui/_dialog.html" %}
{% load leave_extras %}
{% block dialog_title %}Year end · {{ row.person.name }}{% endblock %}
{% block dialog_body %}
<form method="post" action="{% url 'time-off-year-end-decide' row.pk %}" data-dialog-form>
  {% csrf_token %}
  {% for e in form.non_field_errors %}<p class="flash flash-error">{{ e }}</p>{% endfor %}
  <p>At the end of {{ label }}: <strong>{{ row.annual_remaining|hm }}</strong> of annual leave {% if over %}over{% else %}left{% endif %}{% if row.toil_remaining > 0 %}, <strong>{{ row.toil_remaining|hm }}</strong> of TOIL left{% endif %}.{% if long %} A long absence fell in this year.{% endif %}</p>
  <fieldset class="field"><legend>Annual leave into {{ new_year }}</legend>
    {% for radio in form.annual_choice %}<label class="check">{{ radio.tag }} {{ radio.choice_label }}</label>{% endfor %}
    {% if not over %}<div class="field{% if form.annual_hours.errors %} has-error{% endif %}"><label for="id_annual_hours">Hours to carry (for Carry part)</label>{{ form.annual_hours }}{% for e in form.annual_hours.errors %}<p class="field-error">{{ e }}</p>{% endfor %}</div>{% endif %}
  </fieldset>
  {% if form.toil_choice %}
  <fieldset class="field"><legend>TOIL</legend>
    {% for radio in form.toil_choice %}<label class="check">{{ radio.tag }} {{ radio.choice_label }}</label>{% endfor %}
    <div class="field{% if form.toil_hours.errors %} has-error{% endif %}"><label for="id_toil_hours">Hours to keep (for Keep part)</label>{{ form.toil_hours }}{% for e in form.toil_hours.errors %}<p class="field-error">{{ e }}</p>{% endfor %}</div>
  </fieldset>
  {% endif %}
  <div class="field"><label for="id_note">Note</label>{{ form.note }}</div>
  <button class="btn btn-dark">Save decision</button>
</form>
{% endblock %}
```

The form's choice fields render as radios: set `widget=forms.RadioSelect` on `annual_choice` and `toil_choice`.

`leave/views/__init__.py`: `from .yearend import decide as year_end_decide, index as year_end  # noqa: F401`. `leave/urls.py`: `path("time-off/year-end/", views.year_end, name="time-off-year-end")`, `path("time-off/year-end/<int:pk>/decide/", views.year_end_decide, name="time-off-year-end-decide")`. `ui/context_processors.py`: manager `leave_children` gain `{"label": "Year end", "url": "/time-off/year-end/"}` after Past schedule. `people/views/activity.py`: `PERSON_MODELS = ("people.person", "shifts.entry", "leave.booking", "leave.adjustment", "leave.yearend")`. `people/services/health.py` `figures`: `"year_end_waiting": YearEnd.objects.filter(person__in=people, decided_at__isnull=True).count()` (import inside the function from `leave.models`); `_health.html` gains

```html
  <div class="health-item{% if health.year_end_waiting %} is-warning{% endif %}">Year-end decisions waiting<strong>{{ health.year_end_waiting }}</strong>
    {% if health.year_end_waiting %}<a href="{% url 'time-off-year-end' %}">Decide</a>{% endif %}</div>
```

- [ ] **Step 5: The daily command and its units**

`leave/management/commands/daily_flags.py`:

```python
"""The daily flags (spec 4, section 6): the leaver reminder a week out, the
return from a long absence, the year-end flag. Each step fails on its own
so one bad row never stops the others; the command exits 0 regardless so
the timer does not go red for one person. Run by
shift-central-daily-flags.timer at 08:25 every day."""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from leave.services import leavers, returns, yearend

log = logging.getLogger("leave.daily_flags")


class Command(BaseCommand):
    help = "Email managers the leaver, return and year-end flags that fall due today"

    def handle(self, *args, **options):
        base = (settings.CSRF_TRUSTED_ORIGINS or [""])[0]
        steps = (("leaver reminders", lambda: leavers.week_flags(base_url=base)),
                 ("return flags", lambda: returns.send(base_url=base)),
                 ("year-end flags", lambda: yearend.run(base_url=base)))
        for name, step in steps:
            try:
                n = step()
            except Exception:
                log.exception("daily_flags: %s failed", name)
                self.stderr.write(f"{name} failed; see the journal")
                continue
            self.stdout.write(f"{n} {name}")
```

`deploy/shift-central-daily-flags.timer`:

```ini
[Unit]
Description=Email managers the leaver, return and year-end flags, every morning

[Timer]
OnCalendar=*-*-* 08:25:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

`deploy/shift-central-daily-flags.service`: a copy of `deploy/shift-central-leave-reminders.service` with `Description=Email managers the leaver, return and year-end flags` and `ExecStart=/srv/shift-central/.venv/bin/python manage.py daily_flags`; every other directive identical (the sandbox test checks them).

`tests/test_deploy_units.py`: `test_there_are_seven_services` becomes `test_there_are_eight_services` with `"shift-central-daily-flags.service"` inserted after `shift-central-clearsessions.service` in the sorted list, and add

```python
def test_the_daily_flags_run_every_morning():
    (cmd,) = _directives(DEPLOY / "shift-central-daily-flags.service")["ExecStart"]
    assert cmd == "/srv/shift-central/.venv/bin/python manage.py daily_flags"
    text = (DEPLOY / "shift-central-daily-flags.timer").read_text()
    assert "OnCalendar=*-*-* 08:25:00" in text and "Persistent=true" in text
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_leave_yearend.py tests/test_deploy_units.py tests/test_activity.py tests/test_staff_page.py tests/test_shell.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add leave people ui templates deploy tests/test_leave_yearend.py tests/test_deploy_units.py
git commit -m "Leave: the year-end flag, its page and decisions as adjustments; the daily_flags command and timer"
```

---

### Task 7: The export writers (Excel and PDF), GP sessions hidden by leave, Who's in today

**Files:**
- Create: `exports/__init__.py`, `exports/xlsx.py`, `exports/pdf.py`, `leave/services/sessions.py`, `static/img/logo-dark.png` (a copy of `docs/brand/amg-shift-central-logo-dark.png`)
- Modify: `shifts/services/today.py:34-37`
- Test: `tests/test_exports.py`, `tests/test_shifts_today.py`

**Interfaces:**
- Produces: `exports.xlsx.Hours(seconds)` (an `int` subclass written as decimal hours), `exports.xlsx.workbook(sheets) -> bytes` where `sheets = [(title, header_row, rows)]`, `exports.xlsx.response(content, filename) -> HttpResponse`; `exports.pdf.document(title, subtitle, sections, footer) -> bytes` where `sections = [(heading, header_row, rows)]`, `exports.pdf.response(content, filename) -> HttpResponse`, `exports.pdf.LOGO` (the static path); `sessions.HIDES`, `sessions.hidden(people, first, last) -> {(person_id, day): set(parts)}`, `sessions.visible(sessions, hidden) -> [GpSession]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_exports.py`:

```python
"""The two writers every download shares: a workbook whose text cells are
text (a name beginning with = is a name), and a PDF with the logo."""

import io
from datetime import date

from openpyxl import load_workbook

from exports import pdf, xlsx


def test_the_workbook_types_text_as_text_and_hours_as_decimal_hours():
    content = xlsx.workbook([("Payroll", ["Name", "Worked", "Started"],
                              [["=cmd|' /C calc'!A0", xlsx.Hours(27000), date(2027, 1, 4)], ["Sam", xlsx.Hours(0), None]])])
    wb = load_workbook(io.BytesIO(content))
    ws = wb["Payroll"]
    assert ws["A1"].value == "Name" and ws["A1"].font.bold
    assert ws["A2"].value == "=cmd|' /C calc'!A0" and ws["A2"].data_type == "s"
    assert ws["B2"].value == 7.5 and ws["B2"].number_format == "0.00"
    assert ws["C2"].value.date() == date(2027, 1, 4) and ws["C3"].value is None
    r = xlsx.response(content, "payroll-2027-01.xlsx")
    assert r["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert r["Content-Disposition"] == 'attachment; filename="payroll-2027-01.xlsx"'


def test_the_pdf_has_the_title_and_a_table():
    content = pdf.document("Sickness summary", "1 Jul 2026 to 31 Dec 2026", [("Practice", ["People", "Instances"], [["59", "12"]])], "Generated 2 Nov 2026 by Boss")
    assert content.startswith(b"%PDF") and b"Sickness summary" in content and len(content) > 2000
    r = pdf.response(content, "sickness-2026-07-01-2026-12-31.pdf")
    assert r["Content-Type"] == "application/pdf" and 'filename="sickness-2026-07-01-2026-12-31.pdf"' in r["Content-Disposition"]
```

`tests/test_shifts_today.py`, a new test:

```python
def test_a_gp_on_leave_is_off_and_their_sessions_are_not_listed():
    doc = make_person(first_name="Doc", team=make_team("GPs"), is_gp=True)
    make_gp_session(doc, DAY, "AM", site="PMC")
    make_gp_session(doc, DAY, "PM", site="PMC")
    from leave.models import BookingDay
    b = make_booking(doc, DAY, type_name="Holiday", status="approved", part="am")
    BookingDay.objects.create(booking=b, day=DAY, cost_seconds=15000, source="rota", account="annual")
    board = today.board(DAY)
    sites = {s["name"]: s for s in board["sites"]}
    assert sites["PMC"]["teams"][0]["people"][0]["lines"] == ["PM Surgery PMC"]       # the morning is hidden
    assert [x["person"] for x in board["off"]] == [doc]
    b.part = "whole"
    b.save()
    board = today.board(DAY)
    assert "PMC" not in {s["name"] for s in board["sites"]} and [x["person"] for x in board["off"]] == [doc]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/bin/python -m pytest tests/test_exports.py tests/test_shifts_today.py -q`
Expected: ImportError on `exports`; the today test fails on the AM line.

- [ ] **Step 3: `exports/xlsx.py`**

```python
"""Workbooks for the downloads (the payroll report and the two one-pagers).
Every text cell is typed as a string explicitly: openpyxl would otherwise
store a value beginning with = as a formula, and a name or a note typed in
the app can begin with one. Hours are written as decimal hours to two
places, which is what the bureau adds up."""

import io
from datetime import date, datetime
from decimal import Decimal

from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class Hours(int):
    """Seconds that a sheet shows as decimal hours."""

    @property
    def decimal(self):
        return round(int(self) / 3600, 2)


def _put(cell, value):
    if isinstance(value, Hours):
        cell.value, cell.number_format = value.decimal, "0.00"
    elif isinstance(value, bool):
        cell.value, cell.data_type = "Yes" if value else "No", "s"
    elif isinstance(value, (int, float, Decimal)):
        cell.value = value
    elif isinstance(value, (date, datetime)):
        cell.value, cell.number_format = value, "DD/MM/YYYY"
    elif value is None:
        cell.value = None
    else:
        cell.value, cell.data_type = str(value), "s"


def workbook(sheets):
    """sheets: [(title, header_row, rows)] -> the .xlsx bytes."""
    wb = Workbook()
    wb.remove(wb.active)
    for title, header, rows in sheets:
        ws = wb.create_sheet(title=title[:31])
        for col, text in enumerate(header, start=1):
            c = ws.cell(row=1, column=col)
            _put(c, text)
            c.font = Font(bold=True)
        for r, row in enumerate(rows, start=2):
            for col, value in enumerate(row, start=1):
                _put(ws.cell(row=r, column=col), value)
        ws.freeze_panes = "A2"
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def response(content, filename):
    r = HttpResponse(content, content_type=XLSX)
    r["Content-Disposition"] = f'attachment; filename="{filename}"'
    return r
```

- [ ] **Step 4: `exports/pdf.py`**

```python
"""One-page summaries as PDF (REP-04, REP-05): A4 landscape, the logo, a
title and range, one table per section with its header repeated on each
page, page numbers. Every cell is text."""

import io

from django.contrib.staticfiles import finders
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

LOGO = "img/logo-dark.png"
NAVY = colors.HexColor("#143D5C")


def _logo():
    path = finders.find(LOGO)
    if not path:
        return None
    img = Image(path)
    ratio = img.imageWidth / img.imageHeight
    img.drawHeight, img.drawWidth = 10 * mm, 10 * mm * ratio
    img.hAlign = "LEFT"
    return img


def _table(header, rows):
    data = [[str(h) for h in header]] + [["" if v is None else str(v) for v in row] for row in rows]
    t = Table(data, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B0B7C3")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F5F8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return t


def document(title, subtitle, sections, footer):
    """sections: [(heading, header_row, rows)] -> the PDF bytes."""
    styles = getSampleStyleSheet()
    heading = ParagraphStyle("h", parent=styles["Heading2"], textColor=NAVY, spaceBefore=6, spaceAfter=3)
    out = io.BytesIO()

    def page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.drawString(15 * mm, 8 * mm, footer)
        canvas.drawRightString(doc.pagesize[0] - 15 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(out, pagesize=landscape(A4), title=title, author="AMG Shift Central",
                            leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=15 * mm)
    story = []
    logo = _logo()
    if logo is not None:
        story += [logo, Spacer(1, 3 * mm)]
    story += [Paragraph(title, styles["Title"]), Paragraph(subtitle, styles["Normal"]), Spacer(1, 4 * mm)]
    for i, (name, header, rows) in enumerate(sections):
        story += [Paragraph(name, heading), _table(header, rows), Spacer(1, 4 * mm)]
    doc.build(story, onFirstPage=page, onLaterPages=page)
    return out.getvalue()


def response(content, filename):
    r = HttpResponse(content, content_type="application/pdf")
    r["Content-Disposition"] = f'attachment; filename="{filename}"'
    return r
```

(`PageBreak` is imported for a caller that wants one between sections; remove the import if unused, ruff checks it.) Copy the logo: `cp docs/brand/amg-shift-central-logo-dark.png static/img/logo-dark.png`. `finders.find` needs `STATICFILES_DIRS` to include `static/`: it already does for the shell's images.

- [ ] **Step 5: `leave/services/sessions.py` and Who's in today**

```python
"""GP sessions are the rota app's and leave never covers them (leave spec,
Revisit). Where a GP's sessions and their leave are shown or counted
together, the leave hides the sessions it falls on: a whole day hides both,
a morning the AM session, an afternoon the PM one, a timed booking none."""

from datetime import timedelta

from leave.models import Booking

HIDES = {"whole": ("AM", "PM"), "am": ("AM",), "pm": ("PM",), "times": ()}


def hidden(people, first, last):
    """{(person_id, day): {"AM", ...}} for the active, costed bookings of
    `people` between first and last."""
    out = {}
    rows = Booking.objects.filter(person__in=people, status__in=Booking.ACTIVE, dates_only=False,
                                  first_day__lte=last, last_day__gte=first).values_list("person_id", "part", "first_day", "last_day")
    for pid, part, f, l in rows:
        day, stop = max(f, first), min(l, last)
        while day <= stop:
            out.setdefault((pid, day), set()).update(HIDES[part])
            day += timedelta(days=1)
    return out


def visible(sessions, hidden_parts):
    return [s for s in sessions if s.part not in hidden_parts.get((s.person_id, s.day), ())]
```

`shifts/services/today.py` `board`: import `from leave.services import sessions as leave_sessions` and replace the sessions loop's source with

```python
    gp_sessions = leave_sessions.visible(GpSession.objects.filter(person__in=people, day=day).select_related("person__team").order_by("part"),
                                         leave_sessions.hidden(people, day, day))
    for s in gp_sessions:
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_exports.py tests/test_shifts_today.py tests/test_csp.py -q && .venv/bin/ruff check .`
Expected: all pass, ruff clean.

- [ ] **Step 7: Commit**

```bash
git add exports leave/services/sessions.py shifts/services/today.py static/img/logo-dark.png tests/test_exports.py tests/test_shifts_today.py
git commit -m "Shifts: the Excel and PDF writers; a GP's sessions hidden by their leave on Who's in today"
```

---

### Task 8: The payroll report's figures, corrections and Mark as sent

**Files:**
- Create: `payroll/services/report.py`, `payroll/services/runs.py`
- Test: `tests/test_payroll_report.py`

**Interfaces:**
- Consumes: `Entry`, `GpSession`, `BookingDay`, `Booking`, `LeaveType`, `hours.GP_SESSION`, `sessions.hidden/visible`, `leavers.figure`, `access.managed_people/is_all_teams`, `audit.record_as`.
- Produces: `report.FIELDS`, `report.LABELS` (field → column heading), `report.month_of(text) -> date` (raises `ValueError` outside Jan 2026 .. a year ahead), `report.month_end(month) -> date`, `report.people_for(user, month) -> QuerySet`, `report.rows(people, month) -> [Row]`, `Row` fields `person, team, worked, paid_leave, total, paid_overtime, unpaid, sickness, sickness_instances, toil_taken, leave_half_days, types (dict name -> {"days", "seconds"}), started, leaves, leaver_balance, leaver_missing` and `Row.figures() -> dict`, `Row.leave_days_text`; `report.type_names(rows) -> [str]`; `report.corrections(user, month) -> [Correction(month, person, field, label, sent, now, delta)]`; `runs.latest(month) -> PayrollRun | None`, `runs.mark_sent(user, month) -> PayrollRun`, `runs.unsent_due(user, today=None) -> date | None`.

- [ ] **Step 1: Write the failing tests**

`tests/test_payroll_report.py`:

```python
"""PAY-01 to 03: the month's figures per person from the same tables the
statement reads, the days still to come taken from the rota, the snapshot
on Mark as sent and the corrections a later report lists."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied

from leave.services import bookings, hours
from payroll.models import PayrollRun
from payroll.services import report, runs
from people.models import AuditEntry
from shifts.models import Entry
from tests.factories import make_allowance, make_entry, make_gp_session, make_person, make_sick, make_team, make_team_manager, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 1, 15))]     # mid-month: the rest of January is the rota as it stands
JAN = date(2027, 1, 1)
Y27 = JAN


def h(text):
    return hours.from_hours(Decimal(text))


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss")
    make_user_for(boss, is_all_teams_manager=True)
    return boss


def weekdays(first, last):
    d = first
    while d <= last:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


@pytest.fixture
def sam(boss):
    """Mon–Fri 9–17 with 30 min break (7.5 h) through January: 21 working
    days = 157.5 h before any leave."""
    sam = make_person(first_name="Sam", team=make_team("Reception"), start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(sam, Y27, Decimal("172.5"), 60)
    for d in weekdays(JAN, date(2027, 1, 31)):
        make_entry(sam, d, start=time(9), finish=time(17), break_minutes=30)
    return sam


def row_for(user, person, month=JAN):
    return next(r for r in report.rows(report.people_for(user, month), month) if r.person == person)


def test_a_plain_month_is_the_rota_hours(boss, sam):
    r = row_for(boss.user, sam)
    assert (r.worked, r.paid_leave, r.total, r.paid_overtime, r.unpaid, r.sickness, r.toil_taken) == (h("157.5"), 0, h("157.5"), 0, 0, 0, 0)
    assert r.team == "Reception" and r.started is None and r.leaves is None and r.types == {}


def test_each_kind_of_absence_lands_in_its_column(boss, sam):
    bookings.book(boss.user, sam, make_type("Holiday"), date(2027, 1, 4), date(2027, 1, 5), "whole")                       # 15 h paid leave, 2 days
    bookings.book(boss.user, sam, make_type("Compassionate"), date(2027, 1, 6), date(2027, 1, 6), "whole", paid=False)      # LV-25: 7.5 h unpaid
    bookings.book(boss.user, sam, make_type("Sick leave", sickness=True), date(2027, 1, 7), date(2027, 1, 7), "whole")       # 7.5 h sickness
    make_entry(sam, date(2027, 1, 8), start=time(17), finish=time(19), break_minutes=0, overtime="paid")                   # 2 h paid overtime
    make_entry(sam, date(2027, 1, 11), start=time(17), finish=time(20), break_minutes=0, overtime="toil")                  # earns TOIL, not paid
    bookings.book(boss.user, sam, make_type("TOIL"), date(2027, 1, 12), date(2027, 1, 12), "whole")                         # 7.5 h TOIL taken, paid
    bookings.book(boss.user, sam, make_type("Holiday"), date(2027, 1, 13), date(2027, 1, 13), "am")                         # half day: 3.75 h, ½ day; the other 3.75 h worked
    Entry.objects.filter(person=sam, day=date(2027, 1, 14)).delete()                                                       # on maternity that day: no shift
    bookings.book(boss.user, sam, make_type("KIT day"), date(2027, 1, 14), date(2027, 1, 14), "times", time(9), time(15))   # KIT-01: 6 h
    bookings.book(boss.user, sam, make_type("Jury service"), date(2027, 1, 20), date(2027, 1, 21), "whole")                # 15 h reported
    make_sick(sam, date(2026, 7, 6), date(2026, 7, 10), dates_only=True)                                                   # history: nowhere
    r = row_for(boss.user, sam)
    assert r.worked == h("150") - h("7.5") * 7 + h("3.75")                # 20 shifts; 7 whole days covered; the half day's other half worked
    assert r.paid_leave == h("15") + h("7.5") + h("3.75")                 # holiday, TOIL taken, the half day
    assert r.total == r.worked + r.paid_leave
    assert r.paid_overtime == h("2") and r.unpaid == h("7.5") and r.sickness == h("7.5") and r.sickness_instances == 1
    assert r.toil_taken == h("7.5") and r.leave_half_days == 5 and r.leave_days_text == "2½"
    assert r.types == {"KIT day": {"days": 1, "seconds": h("6")}, "Jury service": {"days": 2, "seconds": h("15")}}
    assert report.type_names(report.rows(report.people_for(boss.user, JAN), JAN)) == ["Jury service", "KIT day"]


def test_sickness_instances_count_bookings_that_touch_the_month(boss, sam):
    make_sick(sam, date(2026, 12, 29), date(2027, 1, 2))
    make_sick(sam, date(2027, 1, 25))
    make_sick(sam, date(2027, 2, 1))
    assert row_for(boss.user, sam).sickness_instances == 2


def test_a_gps_sessions_count_as_worked_unless_their_leave_hides_them(boss):
    gp = make_person(first_name="Gail", team=make_team("GPs"), is_gp=True)
    make_allowance(gp, Y27, Decimal("100"), 0)
    for d in (date(2027, 1, 4), date(2027, 1, 5)):
        make_gp_session(gp, d, "AM")
        make_gp_session(gp, d, "PM")
    make_gp_session(gp, date(2027, 1, 6), "AM")
    bookings.book(boss.user, gp, make_type("Holiday"), date(2027, 1, 5), date(2027, 1, 5), "whole")
    bookings.book(boss.user, gp, make_type("Holiday"), date(2027, 1, 6), date(2027, 1, 6), "pm")
    r = row_for(boss.user, gp)
    assert r.worked == 3 * hours.GP_SESSION                                 # 4 Jan both, 6 Jan's morning
    assert r.paid_leave == 2 * hours.GP_SESSION + hours.GP_SESSION // 2    # the whole day, and a half day of the 6 Jan session (half the day's rota)


def test_starters_and_leavers_with_lv_07bs_figure(boss):
    new = make_person(first_name="New", team=make_team("Reception"), start_date=date(2027, 1, 18))
    gone = make_person(first_name="Gone", team=make_team("Reception"), start_date=date(2020, 1, 6), end_date=date(2027, 1, 22),
                       weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(gone, Y27, Decimal("172.5"), 0)
    for d in weekdays(JAN, date(2027, 1, 22)):
        make_entry(gone, d, start=time(9), finish=time(17), break_minutes=30)
    bookings.book(boss.user, gone, make_type("Holiday"), date(2027, 1, 11), date(2027, 1, 15), "whole")     # 37.5 h against 4 weeks' pro-rata
    rows = {r.person: r for r in report.rows(report.people_for(boss.user, JAN), JAN)}
    assert rows[new].started == date(2027, 1, 18) and rows[new].leaves is None
    r = rows[gone]
    assert r.leaves == date(2027, 1, 22) and r.leaver_balance == h("13.5") - h("37.5")        # 172.5 ÷ 52 × 4 = 13.27 → 13.5; 24 h over
    left = make_person(first_name="Left", start_date=date(2020, 1, 6), end_date=date(2026, 12, 31))
    assert left not in rows


def test_people_for_follows_the_managers_reach(boss):
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_user_for(lead)
    make_team_manager(lead, reception)
    ann, nick = make_person(first_name="Ann", team=reception), make_person(first_name="Nick", team=nursing)
    assert set(report.people_for(lead.user, JAN)) == {lead, ann}            # managed_people lists the team's members, the manager among them
    assert {ann, nick, boss, lead} <= set(report.people_for(boss.user, JAN))


def test_month_parsing():
    assert report.month_of("2027-01") == JAN and report.month_end(JAN) == date(2027, 1, 31) and report.month_end(date(2027, 2, 1)) == date(2027, 2, 28)
    assert report.month_of("") == JAN and report.month_of("junk") == JAN            # today's month
    with pytest.raises(ValueError):
        report.month_of("2025-12")
    with pytest.raises(ValueError):
        report.month_of("2028-03")                                                  # more than a year ahead


def test_mark_sent_stores_the_snapshot_and_later_changes_are_corrections(boss, sam):
    dec = date(2026, 12, 1)
    for d in weekdays(dec, date(2026, 12, 31)):
        make_entry(sam, d, start=time(9), finish=time(17), break_minutes=30)
    run = runs.mark_sent(boss.user, dec)
    assert run.month == dec and run.people >= 1 and run.figures["rows"][str(sam.pk)]["worked"] == h("172.5")    # 23 weekdays
    assert AuditEntry.objects.filter(model="payroll.payrollrun", object_id=run.pk, note="marked sent to the bureau").exists()
    assert report.corrections(boss.user, JAN) == []
    make_entry(sam, date(2026, 12, 19), start=time(9), finish=time(12), break_minutes=0)        # a Saturday shift added after the send
    changes = {(c.person, c.field): (c.sent, c.now, c.delta) for c in report.corrections(boss.user, JAN)}
    assert changes[(sam, "worked")] == (h("172.5"), h("175.5"), h("3"))
    assert changes[(sam, "total")] == (h("172.5"), h("175.5"), h("3"))
    assert (sam, "paid_leave") not in changes and all(c.month == dec for c in report.corrections(boss.user, JAN))
    make_sick(sam, date(2026, 12, 23))                                                          # the factory writes no costed day: the count moves, the hours do not
    labels = {c.label for c in report.corrections(boss.user, JAN)}
    assert "Sickness instances" in labels and "Sickness" not in labels
    runs.mark_sent(boss.user, dec)                                                   # sent again: the latest is what was sent
    assert report.corrections(boss.user, JAN) == []


def test_a_new_person_and_a_vanished_one_are_corrections(boss, sam):
    dec = date(2026, 12, 1)
    runs.mark_sent(boss.user, dec)
    late = make_person(first_name="Late", team=sam.team, start_date=date(2026, 12, 1))
    make_entry(late, date(2026, 12, 7), start=time(9), finish=time(12), break_minutes=0)
    fields = {(c.person, c.field) for c in report.corrections(boss.user, JAN)}
    assert (late, "worked") in fields and (late, "total") in fields


def test_only_an_all_teams_manager_marks_sent_and_the_health_line_appears_ten_days_out(boss):
    reception = make_team("Reception")
    lead = make_person(first_name="Lead", team=reception)
    make_user_for(lead)
    make_team_manager(lead, reception)
    with pytest.raises(PermissionDenied):
        runs.mark_sent(lead.user, JAN)
    assert runs.unsent_due(boss.user, today=date(2027, 1, 20)) is None
    assert runs.unsent_due(boss.user, today=date(2027, 1, 21)) == JAN
    assert runs.unsent_due(lead.user, today=date(2027, 1, 21)) is None
    runs.mark_sent(boss.user, JAN)
    assert runs.unsent_due(boss.user, today=date(2027, 1, 25)) is None
    assert runs.latest(JAN).sent_by == boss.user and PayrollRun.objects.count() == 1
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/bin/python -m pytest tests/test_payroll_report.py -q`
Expected: ImportError on `payroll.services.report`.

- [ ] **Step 3: `payroll/services/report.py`**

```python
"""The monthly payroll report (PAY-01): one row per person for a calendar
month, every figure the sum of rows a manager can open (REP-10). Days still
to come are taken from the rota as it stands (PAY-02). The bureau does the
pay; this is the hours."""

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.utils import timezone

from leave.models import Booking, BookingDay
from leave.services import hours, leavers, sessions
from people.models import Person
from people.services import access
from shifts.models import Entry, GpSession

FIELDS = ("worked", "paid_leave", "total", "paid_overtime", "unpaid", "sickness", "sickness_instances", "toil_taken", "leave_half_days")
HOUR_FIELDS = ("worked", "paid_leave", "total", "paid_overtime", "unpaid", "sickness", "toil_taken")
LABELS = {"worked": "Worked", "paid_leave": "Paid leave", "total": "Total to pay", "paid_overtime": "Paid overtime", "unpaid": "Unpaid leave",
          "sickness": "Sickness", "sickness_instances": "Sickness instances", "toil_taken": "TOIL taken", "leave_half_days": "Leave days",
          "started": "Started", "leaves": "Leaves", "leaver_balance": "Leaver's leave remaining"}
EARLIEST = date(2026, 1, 1)


@dataclass
class Row:
    person: Person
    team: str
    worked: int = 0
    paid_leave: int = 0
    total: int = 0
    paid_overtime: int = 0
    unpaid: int = 0
    sickness: int = 0
    sickness_instances: int = 0
    toil_taken: int = 0
    leave_half_days: int = 0
    types: dict = field(default_factory=dict)       # always-reported types present: name -> {"days", "seconds"}
    started: date | None = None
    leaves: date | None = None
    leaver_balance: int | None = None
    leaver_missing: bool = False

    @property
    def leave_days_text(self):
        whole, half = divmod(self.leave_half_days, 2)
        return f"{whole or ''}{'½' if half else ''}" or "0"

    def figures(self):
        out = {f: getattr(self, f) for f in FIELDS}
        out["types"] = {name: dict(v) for name, v in sorted(self.types.items())}
        out["started"] = self.started.isoformat() if self.started else None
        out["leaves"] = self.leaves.isoformat() if self.leaves else None
        out["leaver_balance"] = self.leaver_balance
        return out


def month_of(text):
    """"YYYY-MM" to its first day; blank or unreadable means this month;
    before January 2026 or more than a year ahead raises ValueError."""
    today = timezone.localdate()
    try:
        year, month = (int(x) for x in (text or "").split("-"))
        first = date(year, month, 1)
    except (TypeError, ValueError):
        first = today.replace(day=1)
    if first < EARLIEST or first > date(today.year + 1, today.month, 1):
        raise ValueError("Choose a month from January 2026 to a year ahead")
    return first


def month_end(month):
    return date(month.year, month.month, calendar.monthrange(month.year, month.month)[1])


def people_for(user, month):
    """The viewer's people current on any day of the month, GPs included."""
    end = month_end(month)
    people = Person.objects.all() if access.is_all_teams(user) else access.managed_people(user)
    return (people.filter(start_date__lte=end).exclude(end_date__lt=month).distinct()
            .select_related("team").order_by("team__display_order", "team__name", "last_name", "first_name"))


def _resolved_paid(bd):
    t = bd.booking.type
    return bd.booking.paid if bd.booking.paid is not None else t.default_paid


def rows(people, month):
    first, last = month, month_end(month)
    people = list(people)
    hidden = sessions.hidden(people, first, last)
    out = []
    for p in people:
        r = Row(person=p, team=p.team.name if p.team else "—")
        for e in Entry.objects.filter(person=p, day__range=(first, last), kind=Entry.Kind.SHIFT, covered_by__isnull=True):
            secs = int(e.hours.total_seconds())
            if e.overtime == Entry.Overtime.PAID:
                r.paid_overtime += secs
            elif e.overtime == "":
                r.worked += secs
        if p.is_gp:
            visible = sessions.visible(GpSession.objects.filter(person=p, day__range=(first, last)), hidden)
            r.worked += len(visible) * hours.GP_SESSION
        days = (BookingDay.objects.filter(booking__person=p, booking__status__in=Booking.ACTIVE, booking__dates_only=False, day__range=(first, last))
                .select_related("booking__type"))
        for bd in days:
            t, cost = bd.booking.type, bd.cost_seconds
            if bd.booking.part in (Booking.Part.AM, Booking.Part.PM):
                # A half day covers the whole shift on the grid (leave spec, section 4); the other half was worked.
                covered = sum((e.hours for e in Entry.objects.filter(covered_by=bd, overtime="")), timedelta(0))
                r.worked += max(int(covered.total_seconds()) - cost, 0)
            if bd.account in ("annual", "bank_holiday"):
                r.leave_half_days += 2 if bd.booking.part == Booking.Part.WHOLE else 1
            if bd.account == "toil":
                r.toil_taken += cost
            if not _resolved_paid(bd):
                r.unpaid += cost
            elif t.sickness:
                r.sickness += cost
            elif t.on_payroll == t.Payroll.ALWAYS:
                slot = r.types.setdefault(t.name, {"days": 0, "seconds": 0})
                slot["days"] += 1
                slot["seconds"] += cost
            else:
                r.paid_leave += cost
        r.sickness_instances = Booking.objects.filter(person=p, status__in=Booking.ACTIVE, dates_only=False, type__sickness=True,
                                                      first_day__lte=last, last_day__gte=first).count()
        r.total = r.worked + r.paid_leave
        if first <= p.start_date <= last:
            r.started = p.start_date
        if p.end_date is not None and first <= p.end_date <= last:
            r.leaves = p.end_date
            _, s = leavers.figure(p)
            r.leaver_missing = s.missing
            r.leaver_balance = None if s.missing else s.annual_remaining
        out.append(r)
    return out


def type_names(rows_):
    return sorted({name for r in rows_ for name in r.types})


@dataclass(frozen=True)
class Correction:
    month: date
    person: Person
    field: str
    label: str
    sent: object
    now: object
    delta: object


def _flat(figures):
    """A row's figures as one flat {field: value} for comparing."""
    out = {f: figures.get(f, 0) for f in FIELDS}
    for name, v in (figures.get("types") or {}).items():
        out[f"{name} days"], out[f"{name} hours"] = v["days"], v["seconds"]
    out["started"], out["leaves"], out["leaver_balance"] = figures.get("started"), figures.get("leaves"), figures.get("leaver_balance")
    return out


def _label(field_name):
    return LABELS.get(field_name, field_name)


def corrections(user, month):
    """PAY-02: for each sent month of the previous twelve, what has changed
    since it was sent, for the viewer's people."""
    from payroll.services import runs
    mine = set(access.managed_people(user).values_list("pk", flat=True)) if not access.is_all_teams(user) else None
    out = []
    for back in range(12, 0, -1):
        y, m = month.year, month.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        past = date(y, m, 1)
        run = runs.latest(past)
        if run is None:
            continue
        sent = run.figures.get("rows", {})
        current = Person.objects.filter(start_date__lte=month_end(past)).exclude(end_date__lt=past) | Person.objects.filter(pk__in=[int(k) for k in sent])
        now = {str(r.person.pk): (r.person, _flat(r.figures())) for r in rows(current.distinct().select_related("team"), past)}
        for pk in sorted(set(sent) | set(now), key=int):
            person = now[pk][0] if pk in now else Person.objects.filter(pk=int(pk)).first()
            if person is None or (mine is not None and person.pk not in mine):
                continue
            was, is_now = _flat(sent.get(pk, {})), now[pk][1] if pk in now else _flat({})
            for key in sorted(set(was) | set(is_now)):
                a, b = was.get(key), is_now.get(key)
                if a == b or (not a and not b):
                    continue
                numeric = isinstance(a, int) and isinstance(b, int) and not isinstance(a, bool)
                out.append(Correction(past, person, key, _label(key), a, b, (b - a) if numeric else None))
    return out
```

A note on `_flat` and "total": the test expects `(sam, "total") not in changes` while worked and paid_leave both moved by 15 h; `total` is unchanged, so it is not listed. `sent` and `now` for a vanished type column are `None` and `0`: `not a and not b` skips them.

- [ ] **Step 4: `payroll/services/runs.py`**

```python
"""Mark as sent to the bureau (PAY-02): the snapshot a later report compares
against. All-teams managers only: the bureau's record is the practice's."""

from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from payroll.models import PayrollRun
from payroll.services import report
from people.models import Person
from people.services import access, audit

DUE_DAYS_BEFORE_END = 10


def latest(month):
    return PayrollRun.objects.filter(month=month).order_by("-sent_at", "-pk").first()


def mark_sent(user, month):
    if not access.is_all_teams(user):
        raise PermissionDenied("only an all-teams manager marks the payroll sent")
    people = report.people_for(user, month)
    rows = report.rows(people, month)
    figures = {"generated_at": timezone.now().isoformat(), "rows": {str(r.person.pk): r.figures() for r in rows}}
    with transaction.atomic():
        run = PayrollRun.objects.create(month=month, sent_by=user, people=len(rows), figures=figures)
        audit.record_as(user, "payroll.payrollrun", run.pk, {"sent": ("", f"{month:%B %Y}, {len(rows)} people")}, note="marked sent to the bureau")
    return run


def unsent_due(user, today=None):
    """This month, when it ends within ten days and has not been marked
    sent; for all-teams managers only (the Health card's line)."""
    if not access.is_all_teams(user):
        return None
    today = today or timezone.localdate()
    month = today.replace(day=1)
    if report.month_end(month) - today > timedelta(days=DUE_DAYS_BEFORE_END):
        return None
    return None if latest(month) else month
```

(`Person` is imported for the type of `people_for`'s result; drop the import if ruff flags it unused.)

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_payroll_report.py -q && .venv/bin/ruff check .`
Expected: all pass. The GP test's `paid_leave == 2 * GP_SESSION` relies on `costing.cost` counting a GP's sessions for a whole day (leave spec section 3); the pm booking on a day with only an AM session costs 0 and is listed with no paid leave.

- [ ] **Step 6: Commit**

```bash
git add payroll tests/test_payroll_report.py
git commit -m "Payroll: the month's figures per person, the sent snapshot and the corrections against it"
```

---

### Task 9: The payroll page, the Excel, Mark as sent, the Health line, navigation

**Files:**
- Create: `payroll/views.py`, `payroll/forms.py`, `payroll/services/xlsx.py`, `templates/payroll/report.html`, `templates/payroll/sent_dialog.html`
- Modify: `payroll/urls.py`, `people/services/health.py` (`payroll_unsent`), `templates/people/_health.html`, `people/views/activity.py:18-19` (`LEAVE_SETTING_MODELS`), `ui/context_processors.py:28-30`
- Test: `tests/test_payroll_views.py`

**Interfaces:**
- Consumes: Task 8's `report.*`, `runs.*`; Task 7's `exports.xlsx`.
- Produces: URLs `report-payroll` (`/reports/payroll/?month=YYYY-MM[&download=1]`), `payroll-sent` (`/reports/payroll/sent/?month=`); `payroll.services.xlsx.build(month, rows, type_names, corrections, run) -> bytes`; `health.figures()["payroll_unsent"]` (a month or None).

- [ ] **Step 1: Write the failing tests**

`tests/test_payroll_views.py`:

```python
"""The payroll page by role, the Excel's three sheets, Mark as sent, the
Health card's line, the Reports menu."""

import io
from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from django.test import Client
from openpyxl import load_workbook

from leave.services import bookings
from payroll.models import PayrollRun
from shifts.models import Entry
from tests.factories import make_allowance, make_entry, make_person, make_team, make_team_manager, make_type, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 1, 25))]
JAN = date(2027, 1, 1)


def _client(person, **kw):
    c = Client()
    c.force_login(person.user or make_user_for(person, **kw))
    return c


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss", team=make_team("Management"))
    make_user_for(boss, is_all_teams_manager=True)
    return boss


@pytest.fixture
def staff(boss):
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_user_for(lead)
    make_team_manager(lead, reception)
    ann = make_person(first_name="Ann", last_name="=HYPERLINK(1)", team=reception, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    nick = make_person(first_name="Nick", team=nursing, start_date=date(2020, 1, 6), weekly_hours=Decimal("30"), days_per_week=4)
    for p in (ann, nick):
        make_allowance(p, JAN, Decimal("150"), 0)
        d = JAN
        while d <= date(2027, 1, 31):
            if d.weekday() < 5:
                make_entry(p, d, start=time(9), finish=time(17), break_minutes=30)
            d += timedelta(days=1)
    make_entry(ann, date(2027, 1, 6), start=time(9), finish=time(15), break_minutes=0, kind="shift", overtime="")   # a second shift the same day: 6 h more
    Entry.objects.filter(person=ann, day=date(2027, 1, 13)).delete()                                                # no shift: a KIT day during maternity
    bookings.book(boss.user, ann, make_type("KIT day"), date(2027, 1, 13), date(2027, 1, 13), "times", time(9), time(15))
    return {"lead": lead, "ann": ann, "nick": nick}


def test_the_page_by_role(boss, staff):
    assert _client(staff["ann"]).get("/reports/payroll/").status_code == 403
    body = _client(staff["lead"]).get("/reports/payroll/?month=2027-01").content.decode()
    assert "Ann" in body and "Nick" not in body and "Mark as sent" not in body and "Not yet sent" in body
    body = _client(boss).get("/reports/payroll/?month=2027-01").content.decode()
    assert "Ann" in body and "Nick" in body and "Mark as sent to the bureau" in body and "KIT day" in body
    assert "<th>Total to pay</th>" in body and "Reception total" in body and "Practice total" in body
    assert 'href="/reports/payroll/"' in body


def test_a_bad_month_falls_back_and_an_out_of_range_one_is_a_400(boss):
    c = _client(boss)
    assert c.get("/reports/payroll/?month=junk").status_code == 200 and "January 2027" in c.get("/reports/payroll/?month=junk").content.decode()
    assert c.get("/reports/payroll/?month=2029-01").status_code == 400


def test_the_excel_has_three_sheets_text_cells_and_the_type_columns(boss, staff):
    r = _client(boss).get("/reports/payroll/?month=2027-01&download=1")
    assert r.status_code == 200 and r["Content-Disposition"] == 'attachment; filename="payroll-2027-01.xlsx"'
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Payroll", "Corrections", "Starters and leavers"]
    ws = wb["Payroll"]
    header = [c.value for c in ws[1]]
    assert header[:12] == ["Name", "Team", "Worked", "Paid leave", "Total to pay", "Paid overtime", "Unpaid leave", "Sickness", "Sickness instances",
                           "TOIL taken", "Leave days", "KIT day (days)"]
    assert header[12] == "KIT day (hours)" and header[-3:] == ["Started", "Leaves", "Leaver's leave remaining"]
    ann = next(row for row in ws.iter_rows(min_row=2) if row[0].value.startswith("Ann"))
    assert ann[0].data_type == "s" and ann[0].value == "Ann =HYPERLINK(1)"
    assert ann[2].value == 156.0 and ann[12].value == 6.0 and ann[11].value == 1       # 157.5 − 7.5 + 6 worked; 6 h KIT
    assert ws["A1"].font.bold
    assert wb["Corrections"]["A1"].value == "Month" and wb["Starters and leavers"]["A1"].value == "Name"
    lead = _client(staff["lead"]).get("/reports/payroll/?month=2027-01&download=1")
    names = [row[0].value for row in load_workbook(io.BytesIO(lead.content))["Payroll"].iter_rows(min_row=2)]
    assert any(n.startswith("Ann") for n in names) and not any(n.startswith("Nick") for n in names)


def test_mark_as_sent_is_a_confirm_dialog_for_all_teams_managers(boss, staff):
    c = _client(boss)
    body = c.get("/reports/payroll/sent/?month=2027-01").content.decode()
    assert "January 2027" in body and "people" in body
    r = c.post("/reports/payroll/sent/?month=2027-01")
    assert r.json() == {"refresh": True}
    run = PayrollRun.objects.get()
    assert run.month == JAN and run.sent_by == boss.user
    body = c.get("/reports/payroll/?month=2027-01").content.decode()
    assert "Sent to the bureau on 25 Jan 2027 by Boss" in body and "Draft" not in body
    assert _client(staff["lead"]).post("/reports/payroll/sent/?month=2027-01").status_code == 403
    assert c.post("/reports/payroll/sent/?month=junk").status_code == 400 and c.post("/reports/payroll/sent/").status_code == 400
    assert PayrollRun.objects.count() == 1                                                  # nothing was marked by the bad requests
    page = c.get("/activity/").content.decode()
    assert "Payroll" in page and "January 2027" in page


def test_the_health_line_until_sent(boss, staff):
    c = _client(boss)
    assert "Payroll for January 2027 not yet sent" in c.get("/staff/").content.decode()
    c.post("/reports/payroll/sent/?month=2027-01")
    assert "Payroll for January 2027 not yet sent" not in c.get("/staff/").content.decode()
    assert "Payroll for" not in _client(staff["lead"]).get("/staff/").content.decode()


def test_the_reports_menu(boss, staff):
    body = _client(boss).get("/reports/hours/").content.decode()
    assert 'href="/reports/payroll/"' in body
    assert 'href="/reports/payroll/"' not in _client(staff["ann"]).get("/reports/hours/").content.decode()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/bin/python -m pytest tests/test_payroll_views.py -q`
Expected: 404s on `/reports/payroll/`.

- [ ] **Step 3: The Excel**

`payroll/services/xlsx.py`:

```python
"""The payroll Excel (PAY-03): three sheets from the report's rows. Hours
are decimal hours; names and notes are text cells."""

from exports import xlsx
from payroll.services import report

FIXED = ["Name", "Team", "Worked", "Paid leave", "Total to pay", "Paid overtime", "Unpaid leave", "Sickness", "Sickness instances", "TOIL taken", "Leave days"]


def _hours_field(field_name):
    return field_name in report.HOUR_FIELDS or field_name.endswith(" hours") or field_name == "leaver_balance"


def _cell(value, field_name):
    """A correction's figure: hours as decimal hours, else as it is."""
    if value is None:
        return None
    return xlsx.Hours(value) if _hours_field(field_name) else value


def _row(r, names):
    out = [r.person.name, r.team, xlsx.Hours(r.worked), xlsx.Hours(r.paid_leave), xlsx.Hours(r.total), xlsx.Hours(r.paid_overtime),
           xlsx.Hours(r.unpaid), xlsx.Hours(r.sickness), r.sickness_instances, xlsx.Hours(r.toil_taken), r.leave_half_days / 2]
    for name in names:
        slot = r.types.get(name, {"days": 0, "seconds": 0})
        out += [slot["days"], xlsx.Hours(slot["seconds"])]
    out += [r.started, r.leaves, None if r.leaver_balance is None else xlsx.Hours(r.leaver_balance)]
    return out


def build(month, rows, names, corrections, run):
    header = FIXED + [h for name in names for h in (f"{name} (days)", f"{name} (hours)")] + ["Started", "Leaves", "Leaver's leave remaining"]
    status = f"Sent {run.sent_at:%-d %b %Y}" if run else "Draft"
    payroll = [[f"{month:%B %Y} — {status}"] + [None] * (len(header) - 1)] + [_row(r, names) for r in rows]
    corr = [[c.month.strftime("%B %Y"), c.person.name, c.label, _cell(c.sent, c.field), _cell(c.now, c.field), _cell(c.delta, c.field)] for c in corrections]
    movers = [[r.person.name, r.team, r.started, r.leaves, None if r.leaver_balance is None else xlsx.Hours(r.leaver_balance)]
              for r in rows if r.started or r.leaves]
    return xlsx.workbook([("Payroll", header, payroll), ("Corrections", ["Month", "Name", "Figure", "Sent", "Now", "Difference"], corr),
                          ("Starters and leavers", ["Name", "Team", "Started", "Leaves", "Leave remaining (negative = over)"], movers)])
```

The test reads Ann's row by scanning from row 2: the status line is row 2 and Ann's row follows; `next(... if row[0].value.startswith("Ann"))` skips the status line.

- [ ] **Step 4: Views, form, templates, URLs**

`payroll/forms.py`:

```python
from django import forms


class MonthForm(forms.Form):
    month = forms.CharField(required=False)
```

(kept trivial: `report.month_of` does the parsing.) `payroll/views.py`:

```python
"""The payroll report (PAY-01 to 03): the month on screen for the viewer's
people, the Excel, Mark as sent to the bureau (all-teams managers)."""

import re
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render

from exports import xlsx as exports_xlsx
from payroll.services import report, runs, xlsx
from people.services import access

MONTH = re.compile(r"^\d{4}-\d{2}$")


def _month(request):
    try:
        return report.month_of(request.GET.get("month", ""))
    except ValueError as e:
        return HttpResponseBadRequest(str(e))


def _teams(rows):
    groups = []
    for r in rows:
        if not groups or groups[-1]["team"] != r.team:
            groups.append({"team": r.team, "rows": [], **{f: 0 for f in report.FIELDS}})
        groups[-1]["rows"].append(r)
        for f in report.FIELDS:
            groups[-1][f] += getattr(r, f)
    return groups


@login_required
@access.manager_required
def payroll(request):
    month = _month(request)
    if not hasattr(month, "year"):
        return month
    rows = report.rows(report.people_for(request.user, month), month)
    names = report.type_names(rows)
    corrections = report.corrections(request.user, month)
    run = runs.latest(month)
    if request.GET.get("download"):
        return exports_xlsx.response(xlsx.build(month, rows, names, corrections, run), f"payroll-{month:%Y-%m}.xlsx")
    teams = _teams(rows)
    totals = {f: sum(g[f] for g in teams) for f in report.FIELDS}
    previous = (month - timedelta(days=1)).replace(day=1)
    following = report.month_end(month) + timedelta(days=1)
    return render(request, "payroll/report.html", {
        "page_title": "Payroll", "month": month, "teams": teams, "totals": totals, "type_names": names,
        "corrections": corrections, "movers": [r for r in rows if r.started or r.leaves], "run": run,
        "previous": previous, "following": following, "all_teams": access.is_all_teams(request.user), "people_count": len(rows)})


@login_required
@access.all_teams_required
def mark_sent(request):
    # Never a fallback here: marking "this month" sent because the parameter was unreadable is a wrong record.
    if not MONTH.match(request.GET.get("month", "")):
        return HttpResponseBadRequest("Say which month, as YYYY-MM")
    month = _month(request)
    if not hasattr(month, "year"):
        return month
    if request.method == "POST":
        runs.mark_sent(request.user, month)
        return JsonResponse({"refresh": True})
    count = report.people_for(request.user, month).count()
    return render(request, "payroll/sent_dialog.html", {"month": month, "count": count, "run": runs.latest(month)})
```

`payroll/urls.py`:

```python
from django.urls import path

from payroll import views

urlpatterns = [
    path("reports/payroll/", views.payroll, name="report-payroll"),
    path("reports/payroll/sent/", views.mark_sent, name="payroll-sent"),
]
```

`templates/payroll/report.html`:

```html
{% extends "base.html" %}
{% load leave_extras %}
{% block title %}Payroll · AMG Shift Central{% endblock %}
{% block topbar_actions %}
  <a class="topbar-action" href="?month={{ month|date:'Y-m' }}&amp;download=1">Download Excel</a>
  {% if all_teams %}<a class="topbar-action is-primary" href="{% url 'payroll-sent' %}?month={{ month|date:'Y-m' }}" data-dialog>Mark as sent to the bureau</a>{% endif %}
{% endblock %}
{% block content %}
<form class="filters" method="get">
  <a class="btn btn-quiet" href="?month={{ previous|date:'Y-m' }}" aria-label="Previous month">‹</a>
  <label>Month <input type="month" name="month" value="{{ month|date:'Y-m' }}"></label>
  <a class="btn btn-quiet" href="?month={{ following|date:'Y-m' }}" aria-label="Next month">›</a>
  <button class="btn btn-quiet" type="submit">Show</button>
  <span class="muted">{% if run %}Sent to the bureau on {{ run.sent_at|date:"j M Y" }} by {{ run.sent_by.person.name|default:run.sent_by.email|default:"—" }}{% else %}Not yet sent — a draft until it is marked sent{% endif %}</span>
</form>
<p class="field-help">{{ month|date:"F Y" }}: hours worked from the rota (the days still to come as it stands), paid leave and the rest from the bookings. Hours worked plus paid leave is the total to pay. The bureau does the pay.</p>
{% for t in teams %}
<section class="report-block">
  <h2>{{ t.team }}</h2>
  <table class="table">
    <thead><tr><th>Name</th><th>Worked</th><th>Paid leave</th><th>Total to pay</th><th>Paid overtime</th><th>Unpaid leave</th><th>Sickness</th><th>Instances</th><th>TOIL taken</th><th>Leave days</th>{% for n in type_names %}<th>{{ n }}</th>{% endfor %}<th>Started / leaves</th></tr></thead>
    <tbody>
    {% for r in t.rows %}
    <tr><td>{{ r.person.name }}</td><td>{{ r.worked|hm }}</td><td>{{ r.paid_leave|hm }}</td><td><strong>{{ r.total|hm }}</strong></td><td>{{ r.paid_overtime|hm }}</td><td>{{ r.unpaid|hm }}</td>
        <td>{{ r.sickness|hm }}</td><td>{{ r.sickness_instances }}</td><td>{{ r.toil_taken|hm }}</td><td>{{ r.leave_days_text }}</td>
        {% for n in type_names %}<td>{% with slot=r.types|get_item:n %}{% if slot %}{{ slot.days }} day{{ slot.days|pluralize }}, {{ slot.seconds|hm }}{% endif %}{% endwith %}</td>{% endfor %}
        <td>{% if r.started %}Started {{ r.started|date:"j M" }}{% endif %}{% if r.leaves %}Leaves {{ r.leaves|date:"j M" }}{% if r.leaver_balance is not None %} · {{ r.leaver_balance|hm }}{% if r.leaver_balance < 0 %} over{% else %} remaining{% endif %}{% endif %}{% endif %}</td></tr>
    {% endfor %}
    </tbody>
    <tfoot><tr><td>{{ t.team }} total</td><td>{{ t.worked|hm }}</td><td>{{ t.paid_leave|hm }}</td><td>{{ t.total|hm }}</td><td>{{ t.paid_overtime|hm }}</td><td>{{ t.unpaid|hm }}</td><td>{{ t.sickness|hm }}</td><td>{{ t.sickness_instances }}</td><td>{{ t.toil_taken|hm }}</td><td colspan="{{ type_names|length|add:2 }}"></td></tr></tfoot>
  </table>
</section>
{% empty %}<p>Nobody to report on.</p>{% endfor %}
{% if teams and all_teams %}<p><strong>Practice total</strong>: worked {{ totals.worked|hm }}, paid leave {{ totals.paid_leave|hm }}, to pay {{ totals.total|hm }}, paid overtime {{ totals.paid_overtime|hm }}, unpaid {{ totals.unpaid|hm }}, sickness {{ totals.sickness|hm }}.</p>{% endif %}
{% if corrections %}
<section class="report-block"><h2>Corrections to months already sent</h2>
<table class="table"><thead><tr><th>Month</th><th>Name</th><th>Figure</th><th>Sent</th><th>Now</th><th>Difference</th></tr></thead>
<tbody>{% for c in corrections %}<tr><td>{{ c.month|date:"F Y" }}</td><td>{{ c.person.name }}</td><td>{{ c.label }}</td><td>{{ c.sent|figure:c.field }}</td><td>{{ c.now|figure:c.field }}</td><td>{{ c.delta|figure:c.field }}</td></tr>{% endfor %}</tbody></table>
</section>
{% endif %}
{% if movers %}
<section class="report-block"><h2>Starters and leavers</h2>
<table class="table"><thead><tr><th>Name</th><th>Team</th><th>Started</th><th>Leaves</th><th>Leave remaining (negative = over)</th></tr></thead>
<tbody>{% for r in movers %}<tr><td>{{ r.person.name }}</td><td>{{ r.team }}</td><td>{{ r.started|date:"j M Y"|default:"" }}</td><td>{{ r.leaves|date:"j M Y"|default:"" }}</td><td>{% if r.leaver_balance is not None %}{{ r.leaver_balance|hm }}{% elif r.leaves %}allowance not set{% endif %}</td></tr>{% endfor %}</tbody></table>
</section>
{% endif %}
{% endblock %}
```

Two template filters in `leave/templatetags/leave_extras.py`:

```python
@register.filter
def get_item(mapping, key):
    return (mapping or {}).get(key)


@register.filter
def figure(value, field_name):
    """A correction's figure as the screen shows it: hours for hour fields,
    the number or date otherwise."""
    from payroll.services import report
    if value is None:
        return ""
    if field_name in report.HOUR_FIELDS or str(field_name).endswith(" hours") or field_name == "leaver_balance":
        return hours.fmt(value)
    if field_name == "leave_half_days":
        whole, half = divmod(int(value), 2)
        return f"{whole or ''}{'½' if half else ''}" or "0"
    return value
```

`templates/payroll/sent_dialog.html`:

```html
{% extends "ui/_dialog.html" %}
{% block dialog_title %}Mark as sent to the bureau{% endblock %}
{% block dialog_body %}
<form method="post" action="{% url 'payroll-sent' %}?month={{ month|date:'Y-m' }}" data-dialog-form>
  {% csrf_token %}
  <p>Record that the payroll report for <strong>{{ month|date:"F Y" }}</strong> ({{ count }} people) has been sent. The figures as they stand now are kept, and anything that changes afterwards appears as a correction on later months' reports.</p>
  {% if run %}<p class="flash flash-warning">This month was already marked sent on {{ run.sent_at|date:"j M Y" }}. Marking it again makes today's figures the ones compared against.</p>{% endif %}
  <button class="btn btn-dark">Mark {{ month|date:"F Y" }} as sent</button>
</form>
{% endblock %}
```

- [ ] **Step 5: Health, activity, nav**

`people/services/health.py` `figures`: `"payroll_unsent": runs.unsent_due(user, today)` (import `from payroll.services import runs` inside the function). `templates/people/_health.html` gains

```html
  {% if health.payroll_unsent %}<div class="health-item is-warning">Payroll for {{ health.payroll_unsent|date:"F Y" }} not yet sent<strong>due</strong>
    <a href="{% url 'report-payroll' %}?month={{ health.payroll_unsent|date:'Y-m' }}">Open</a></div>{% endif %}
```

`people/views/activity.py`: `LEAVE_SETTING_MODELS` gains `"payroll.payrollrun": "Payroll"`. `ui/context_processors.py`: the Reports item's children become, for managers, `[Hours, Leave, {"label": "Payroll", "url": "/reports/payroll/"}]` (staff keep Hours and Leave).

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_payroll_views.py tests/test_payroll_report.py tests/test_activity.py tests/test_staff_page.py tests/test_shell.py tests/test_csp.py -q && .venv/bin/ruff check .`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add payroll leave/templatetags people ui templates tests/test_payroll_views.py
git commit -m "Payroll: the monthly report page, its Excel with corrections and starters and leavers, Mark as sent, the Health line"
```

---

### Task 10: The sickness and leave one-pagers (REP-04, REP-05)

**Files:**
- Create: `absence/services/onepager.py`, `absence/views/onepager.py`, `templates/absence/sickness_summary.html`, `leave/services/summary.py`, `leave/views/summary.py`, `templates/leave/summary.html`
- Modify: `absence/views/__init__.py`, `absence/urls.py`, `leave/views/__init__.py`, `leave/urls.py`, `ui/context_processors.py`
- Test: `tests/test_absence_onepager.py`, `tests/test_leave_summary.py`

**Interfaces:**
- Consumes: `sickness.*`, `balances.statement`, `years.*`, `exports.pdf/xlsx`, `access.managed_people`.
- Produces: `onepager.summary(user, start, end) -> {"practice": Totals, "teams": [Totals], "people": [PersonRow]}` with `Totals(name, people, instances, days, seconds, trigger_1, trigger_2, trigger_3)` and `PersonRow(person, team, instances, days, seconds, longest, long, trigger)`; `onepager.sections(summary) -> [(heading, header, rows)]` (text cells, for both writers); URL `report-sickness` (`/reports/sickness/?from&to[&format=pdf|xlsx]`); `summary.summary(user, year) -> {"practice", "teams", "people", "footnotes"}` with `LeaveTotals(name, people, allowance, adjustments, taken, remaining, toil, pending)` and `LeaveRow(person, team, year, missing, allowance, adjustments, taken, remaining, toil, pending)`; `summary.sections(data)`; URL `report-leave-summary` (`/reports/leave-summary/?year=YYYY[&format=pdf|xlsx]`).

- [ ] **Step 1: Write the failing tests**

`tests/test_absence_onepager.py`:

```python
"""REP-04: the sickness one-pager, practice then teams then people, as a
page, a PDF or an Excel file; managers only, their people."""

import io
from datetime import date

import pytest
from django.test import Client
from openpyxl import load_workbook

from absence.services import onepager
from tests.factories import make_person, make_sick, make_team, make_team_manager, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2026, 12, 31))]
START, END = date(2026, 7, 1), date(2026, 12, 31)


def _client(person, **kw):
    c = Client()
    c.force_login(person.user or make_user_for(person, **kw))
    return c


@pytest.fixture
def world():
    boss = make_person(first_name="Boss", team=make_team("Management"))
    make_user_for(boss, is_all_teams_manager=True)
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_user_for(lead)
    make_team_manager(lead, reception)
    ann = make_person(first_name="Ann", team=reception)
    bea = make_person(first_name="Bea", team=reception)
    nick = make_person(first_name="Nick", team=nursing)
    for d in (date(2026, 7, 6), date(2026, 8, 3), date(2026, 9, 7), date(2026, 10, 5)):
        make_sick(ann, d)                                                     # 4 instances: Trigger 2
    make_sick(bea, date(2026, 6, 29), date(2026, 8, 7))                       # 40 days, long; 38 of them in the range
    make_sick(nick, date(2026, 11, 2), date(2026, 11, 3), dates_only=True)
    make_sick(nick, date(2026, 3, 2))                                          # before the range and the window
    return {"boss": boss, "lead": lead, "ann": ann, "bea": bea, "nick": nick}


def test_the_figures(world):
    s = onepager.summary(world["boss"].user, START, END)
    p = s["practice"]
    assert (p.instances, p.days, p.trigger_1, p.trigger_2, p.trigger_3) == (6, 4 + 38 + 2, 0, 1, 0)
    teams = {t.name: t for t in s["teams"]}
    assert (teams["Reception"].instances, teams["Reception"].people, teams["Nursing"].instances) == (5, 3, 1)      # Lead is in Reception too
    people = {r.person.first_name: r for r in s["people"]}
    assert (people["Ann"].instances, people["Ann"].trigger, people["Ann"].days) == (4, "Trigger 2", 4)
    assert (people["Bea"].longest, people["Bea"].long, people["Bea"].days, people["Bea"].instances) == (40, True, 38, 1)
    assert (people["Nick"].instances, people["Nick"].days, people["Nick"].trigger) == (1, 2, "")
    assert people["Nick"].seconds == 0                                        # dates only: no hours
    lead_rows = [r.person.first_name for r in onepager.summary(world["lead"].user, START, END)["people"]]
    assert sorted(lead_rows) == ["Ann", "Bea", "Lead"]


def test_the_page_pdf_and_excel(world):
    c = _client(world["boss"])
    body = c.get("/reports/sickness/?from=2026-07-01&to=2026-12-31").content.decode()
    assert "Sickness summary" in body and "Trigger 2" in body and "Reception" in body and "long" in body
    r = c.get("/reports/sickness/?from=2026-07-01&to=2026-12-31&format=pdf")
    assert r["Content-Type"] == "application/pdf" and r.content.startswith(b"%PDF") and 'filename="sickness-2026-07-01-2026-12-31.pdf"' in r["Content-Disposition"]
    r = c.get("/reports/sickness/?from=2026-07-01&to=2026-12-31&format=xlsx")
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Practice", "Teams", "People"] and wb["People"]["A1"].value == "Name"
    assert _client(world["ann"]).get("/reports/sickness/").status_code == 403
    assert 'href="/reports/sickness/"' in c.get("/reports/hours/").content.decode()


def test_the_default_range_is_the_rolling_six_months(world):
    body = _client(world["boss"]).get("/reports/sickness/").content.decode()
    assert 'value="2026-07-01"' in body and 'value="2026-12-31"' in body
```

`tests/test_leave_summary.py`:

```python
"""REP-05: the leave one-pager for a leave year: taken and remaining per
person with team and practice totals; PDF or Excel."""

import io
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client
from openpyxl import load_workbook

from leave.services import hours, summary
from tests.factories import make_allowance, make_person, make_team, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 6, 1))]
Y27 = date(2027, 1, 1)


def h(text):
    return hours.from_hours(Decimal(text))


@pytest.fixture
def boss():
    boss = make_person(first_name="Boss", team=make_team("Management"))
    make_user_for(boss, is_all_teams_manager=True)
    return boss


def test_the_figures_and_the_footnote_for_another_leave_year_start(boss):
    reception = make_team("Reception")
    ann = make_person(first_name="Ann", team=reception, start_date=date(2020, 1, 6))
    make_allowance(ann, Y27, Decimal("172.5"), 60)
    april = make_person(first_name="Apr", team=reception, start_date=date(2020, 1, 6), leave_year_start="04-01")
    make_allowance(april, date(2026, 4, 1), Decimal("100"), 0)
    make_person(first_name="New", team=reception, start_date=date(2027, 3, 1))     # no allowance: "not set"
    s = summary.summary(boss.user, Y27)
    rows = {r.person.first_name: r for r in s["people"]}
    assert rows["Ann"].allowance == h("232.5") and rows["Ann"].remaining == h("232.5") and not rows["Ann"].missing
    assert rows["Apr"].year == date(2026, 4, 1) and rows["Apr"].allowance == h("100")
    assert rows["New"].missing
    team = next(t for t in s["teams"] if t.name == "Reception")
    assert team.allowance == h("332.5") and team.people == 3
    assert s["practice"].allowance >= h("332.5")
    assert any("2026/27" in f for f in s["footnotes"])


def test_the_page_pdf_and_excel(boss):
    c = Client()
    c.force_login(boss.user)
    ann = make_person(first_name="Ann", team=make_team("Reception"), start_date=date(2020, 1, 6))
    make_allowance(ann, Y27, Decimal("172.5"), 60)
    body = c.get("/reports/leave-summary/?year=2027").content.decode()
    assert "Leave summary" in body and "Ann" in body and "232 h 30 min" in body and "Practice total" in body
    r = c.get("/reports/leave-summary/?year=2027&format=pdf")
    assert r.content.startswith(b"%PDF") and 'filename="leave-summary-2027.pdf"' in r["Content-Disposition"]
    wb = load_workbook(io.BytesIO(c.get("/reports/leave-summary/?year=2027&format=xlsx").content))
    assert wb.sheetnames == ["Practice", "Teams", "People"]
    staff = Client()
    staff.force_login(make_user_for(ann))
    assert staff.get("/reports/leave-summary/").status_code == 403
    assert 'href="/reports/leave-summary/"' in c.get("/reports/hours/").content.decode()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `.venv/bin/python -m pytest tests/test_absence_onepager.py tests/test_leave_summary.py -q`
Expected: ImportErrors.

- [ ] **Step 3: `absence/services/onepager.py`**

```python
"""REP-04: the sickness one-pager. Practice totals, then each team, then
each person: instances in the rolling six months as at the range's end,
time off sick inside the range in days and hours, the longest instance
and whether it was long, the trigger level. Dates-only entries count
their days; they have no hours."""

from dataclasses import dataclass

from django.db.models import Sum
from django.utils import timezone

from leave.models import Booking, BookingDay
from leave.services import hours, sickness
from people.services import access


@dataclass
class Totals:
    name: str
    people: int = 0
    instances: int = 0
    days: int = 0
    seconds: int = 0
    trigger_1: int = 0
    trigger_2: int = 0
    trigger_3: int = 0


@dataclass
class PersonRow:
    person: object
    team: str
    instances: int
    days: int
    seconds: int
    longest: int
    long: bool
    trigger: str
    level: int


def _people(user, start, end):
    return list(access.managed_people(user).filter(start_date__lte=end).exclude(end_date__lt=start)
                .select_related("team").order_by("team__display_order", "team__name", "last_name", "first_name"))


def _in_range(booking, start, end):
    return (min(booking.last_day, end) - max(booking.first_day, start)).days + 1


def _row(person, start, end):
    in_range = list(Booking.objects.filter(person=person, status__in=Booking.ACTIVE, type__sickness=True, first_day__lte=end, last_day__gte=start))
    days = sum(_in_range(b, start, end) for b in in_range)
    seconds = BookingDay.objects.filter(booking__in=in_range, day__range=(start, end)).aggregate(t=Sum("cost_seconds"))["t"] or 0
    longest = max(((b.last_day - b.first_day).days + 1 for b in in_range), default=0)
    as_at = min(end, timezone.localdate())          # a range that runs into the future is read as at today
    level = sickness.level_for(person, as_at)
    return PersonRow(person, person.team.name if person.team else "—", len(sickness.instances(person, as_at)), days, seconds, longest,
                     longest >= sickness.LONG_DAYS, sickness.level_label(level), level)


def _add(t, r, instances):
    t.people += 1
    t.instances += instances
    t.days += r.days
    t.seconds += r.seconds
    if r.level == 1:
        t.trigger_1 += 1
    elif r.level == 2:
        t.trigger_2 += 1
    elif r.level == 3:
        t.trigger_3 += 1


def summary(user, start, end):
    practice, teams, people = Totals("Practice"), {}, []
    for p in _people(user, start, end):
        r = _row(p, start, end)
        people.append(r)
        in_range = Booking.objects.filter(person=p, status__in=Booking.ACTIVE, type__sickness=True, first_day__lte=end, last_day__gte=start).count()
        _add(practice, r, in_range)
        _add(teams.setdefault(r.team, Totals(r.team)), r, in_range)
    return {"practice": practice, "teams": list(teams.values()), "people": people}


def _totals_row(t):
    return [t.name, t.people, t.instances, t.days, hours.fmt(t.seconds), t.trigger_1, t.trigger_2, t.trigger_3]


def sections(data):
    """The three tables as text, for the PDF and the Excel alike."""
    head = ["", "People", "Instances in range", "Days off sick", "Hours off sick", "Trigger 1", "Trigger 2", "Trigger 3+"]
    return [("Practice", head, [_totals_row(data["practice"])]),
            ("Teams", head, [_totals_row(t) for t in data["teams"]]),
            ("People", ["Name", "Team", "Instances (rolling six months)", "Days off sick", "Hours off sick", "Longest instance (days)", "Trigger"],
             [[r.person.name, r.team, r.instances, r.days, hours.fmt(r.seconds), f"{r.longest}{' (long)' if r.long else ''}", r.trigger] for r in data["people"]])]
```

The practice and team "Instances in range" count bookings overlapping the range (a longer view than the rolling window); each person's column is the rolling six months as at the range end, as REP-04 asks. Say so in the page's help text.

- [ ] **Step 4: `absence/views/onepager.py` and its template**

```python
"""The sickness summary (REP-04): screen, PDF or Excel for a range."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from absence.services import onepager
from exports import pdf, xlsx
from leave.services import sickness
from people.services import access
from shifts.services.window import parse_day


def _range(request):
    today = timezone.localdate()
    default_start, default_end = sickness.window(today)
    try:
        start = parse_day(request.GET.get("from", ""))
    except ValueError:
        start = default_start
    try:
        end = parse_day(request.GET.get("to", ""))
    except ValueError:
        end = default_end
    if end < start:
        start, end = end, start
    return start, end


@login_required
@access.manager_required
def sickness_summary(request):
    start, end = _range(request)
    data = onepager.summary(request.user, start, end)
    stem = f"sickness-{start.isoformat()}-{end.isoformat()}"
    fmt = request.GET.get("format")
    me = getattr(request.user, "person", None)
    footer = f"Generated {timezone.localdate():%-d %b %Y} by {me.name if me else request.user.email} · AMG Shift Central"
    if fmt == "pdf":
        return pdf.response(pdf.document("Sickness summary", f"{start:%-d %b %Y} to {end:%-d %b %Y}", onepager.sections(data), footer), f"{stem}.pdf")
    if fmt == "xlsx":
        return xlsx.response(xlsx.workbook([(name, head, rows) for name, head, rows in onepager.sections(data)]), f"{stem}.xlsx")
    return render(request, "absence/sickness_summary.html", {"page_title": "Sickness summary", "start": start, "end": end, **data})
```

`templates/absence/sickness_summary.html`:

```html
{% extends "base.html" %}
{% load leave_extras %}
{% block title %}Sickness summary · AMG Shift Central{% endblock %}
{% block topbar_actions %}
  <a class="topbar-action" href="?from={{ start|date:'Y-m-d' }}&amp;to={{ end|date:'Y-m-d' }}&amp;format=pdf">Download PDF</a>
  <a class="topbar-action" href="?from={{ start|date:'Y-m-d' }}&amp;to={{ end|date:'Y-m-d' }}&amp;format=xlsx">Download Excel</a>
{% endblock %}
{% block content %}
<form class="filters" method="get">
  <label>From <input type="date" name="from" value="{{ start|date:'Y-m-d' }}"></label>
  <label>To <input type="date" name="to" value="{{ end|date:'Y-m-d' }}"></label>
  <button class="btn btn-quiet" type="submit">Refresh</button>
</form>
<p class="field-help">Instances and days off sick inside the range; each person's instances and trigger are the rolling six months as at {{ end|date:"j M Y" }}. Dates-only entries from the past schedule count their days and have no hours.</p>
<section class="report-block"><h2>Practice</h2>
<table class="table"><thead><tr><th>People</th><th>Instances</th><th>Days off sick</th><th>Hours off sick</th><th>Trigger 1</th><th>Trigger 2</th><th>Trigger 3+</th></tr></thead>
<tbody><tr><td>{{ practice.people }}</td><td>{{ practice.instances }}</td><td>{{ practice.days }}</td><td>{{ practice.seconds|hm }}</td><td>{{ practice.trigger_1 }}</td><td>{{ practice.trigger_2 }}</td><td>{{ practice.trigger_3 }}</td></tr></tbody></table></section>
<section class="report-block"><h2>Teams</h2>
<table class="table"><thead><tr><th>Team</th><th>People</th><th>Instances</th><th>Days off sick</th><th>Hours off sick</th><th>Trigger 1</th><th>Trigger 2</th><th>Trigger 3+</th></tr></thead>
<tbody>{% for t in teams %}<tr><td>{{ t.name }}</td><td>{{ t.people }}</td><td>{{ t.instances }}</td><td>{{ t.days }}</td><td>{{ t.seconds|hm }}</td><td>{{ t.trigger_1 }}</td><td>{{ t.trigger_2 }}</td><td>{{ t.trigger_3 }}</td></tr>{% endfor %}</tbody></table></section>
<section class="report-block"><h2>People</h2>
<table class="table"><thead><tr><th>Name</th><th>Team</th><th>Instances (rolling six months)</th><th>Days off sick</th><th>Hours off sick</th><th>Longest instance</th><th>Trigger</th></tr></thead>
<tbody>{% for r in people %}<tr><td>{{ r.person.name }}</td><td>{{ r.team }}</td><td>{{ r.instances }}</td><td>{{ r.days }}</td><td>{{ r.seconds|hm }}</td><td>{% if r.longest %}{{ r.longest }} day{{ r.longest|pluralize }}{% if r.long %} (long){% endif %}{% endif %}</td><td>{{ r.trigger }}</td></tr>
{% empty %}<tr><td colspan="7">Nobody to report on.</td></tr>{% endfor %}</tbody></table></section>
{% endblock %}
```

`absence/views/__init__.py`: `from .onepager import sickness_summary  # noqa: F401`; `absence/urls.py`: `path("reports/sickness/", views.sickness_summary, name="report-sickness")`.

- [ ] **Step 5: `leave/services/summary.py`, its view and template**

```python
"""REP-05: the leave one-pager for a leave year: taken and remaining per
person, with team and practice totals. A person whose leave year starts on
another day is reported for the year of theirs that holds the chosen
year's first day, and a footnote says so."""

from dataclasses import dataclass, field

from leave.services import balances, hours, years
from people.services import access


@dataclass
class LeaveTotals:
    name: str
    people: int = 0
    allowance: int = 0
    adjustments: int = 0
    taken: int = 0
    remaining: int = 0
    toil: int = 0
    pending: int = 0


@dataclass
class LeaveRow:
    person: object
    team: str
    year: object
    missing: bool
    allowance: int = 0
    adjustments: int = 0
    taken: int = 0
    remaining: int = 0
    toil: int = 0
    pending: int = 0
    lines: list = field(default_factory=list)


def _row(person, year):
    own = years.year_of(person, year)
    s = balances.statement(person, own)
    if s.missing:
        return LeaveRow(person, person.team.name if person.team else "—", own, True, toil=s.toil_remaining)
    return LeaveRow(person, person.team.name if person.team else "—", own, False,
                    s.annual_allowance + s.bank_holiday_allowance, s.adjustments["annual"] + s.adjustments["bank_holiday"],
                    s.taken["annual"] + s.taken["bank_holiday"], s.annual_remaining, s.toil_remaining, s.pending["annual"] + s.pending["bank_holiday"])


def _add(t, r):
    t.people += 1
    for f in ("allowance", "adjustments", "taken", "remaining", "toil", "pending"):
        setattr(t, f, getattr(t, f) + getattr(r, f))


def summary(user, year):
    end = years.year_end(year)
    people = (access.managed_people(user).filter(start_date__lte=end).exclude(end_date__lt=year)
              .select_related("team").order_by("team__display_order", "team__name", "last_name", "first_name"))
    practice, teams, rows, other_years = LeaveTotals("Practice"), {}, [], set()
    for p in people:
        r = _row(p, year)
        rows.append(r)
        if r.year != year:
            other_years.add(years.label(r.year))
        _add(practice, r)
        _add(teams.setdefault(r.team, LeaveTotals(r.team)), r)
    footnotes = [f"Reported for leave year {label}, which holds {year:%-d %b %Y}, for those whose leave year starts on another day." for label in sorted(other_years)]
    return {"practice": practice, "teams": list(teams.values()), "people": rows, "footnotes": footnotes}


def _t(t):
    return [t.name, t.people, hours.fmt(t.allowance), hours.fmt(t.adjustments), hours.fmt(t.taken), hours.fmt(t.remaining), hours.fmt(t.toil), hours.fmt(t.pending)]


def sections(data):
    head = ["", "People", "Allowance", "Adjustments", "Taken", "Remaining", "TOIL remaining", "Waiting for approval"]
    return [("Practice", head, [_t(data["practice"])]), ("Teams", head, [_t(t) for t in data["teams"]]),
            ("People", ["Name", "Team", "Leave year", "Allowance", "Adjustments", "Taken", "Remaining", "TOIL remaining", "Waiting for approval"],
             [[r.person.name, r.team, years.label(r.year), "not set" if r.missing else hours.fmt(r.allowance), hours.fmt(r.adjustments), hours.fmt(r.taken),
               "—" if r.missing else hours.fmt(r.remaining), hours.fmt(r.toil), hours.fmt(r.pending)] for r in data["people"]])]
```

`leave/views/summary.py`:

```python
"""The leave summary (REP-05): screen, PDF or Excel for a leave year."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from exports import pdf, xlsx
from leave.services import summary, years
from people.services import access


def _year(request):
    today = timezone.localdate()
    me = getattr(request.user, "person", None)
    default = years.year_of(me, today) if me is not None else date(today.year, 1, 1)
    try:
        y = int(request.GET.get("year", ""))
        return date(y, default.month, default.day) if 2000 <= y <= 2100 else default
    except ValueError:
        return default


@login_required
@access.manager_required
def leave_summary(request):
    year = _year(request)
    data = summary.summary(request.user, year)
    label = years.label(year)
    me = getattr(request.user, "person", None)
    footer = f"Generated {timezone.localdate():%-d %b %Y} by {me.name if me else request.user.email} · AMG Shift Central"
    stem = f"leave-summary-{year.year}"
    fmt = request.GET.get("format")
    if fmt == "pdf":
        return pdf.response(pdf.document("Leave summary", f"Leave year {label}" + (" · " + " ".join(data["footnotes"]) if data["footnotes"] else ""),
                                         summary.sections(data), footer), f"{stem}.pdf")
    if fmt == "xlsx":
        return xlsx.response(xlsx.workbook(summary.sections(data)), f"{stem}.xlsx")
    return render(request, "leave/summary.html", {"page_title": "Leave summary", "year": year, "label": label,
                                                  "previous": year.year - 1, "following": year.year + 1, **data})
```

`templates/leave/summary.html`:

```html
{% extends "base.html" %}
{% load leave_extras %}
{% block title %}Leave summary · AMG Shift Central{% endblock %}
{% block topbar_actions %}
  <a class="topbar-action" href="?year={{ year.year }}&amp;format=pdf">Download PDF</a>
  <a class="topbar-action" href="?year={{ year.year }}&amp;format=xlsx">Download Excel</a>
{% endblock %}
{% block content %}
<form class="filters" method="get">
  <a class="btn btn-quiet" href="?year={{ previous }}" aria-label="Previous year">‹</a>
  <label>Leave year <input type="number" name="year" min="2000" max="2100" value="{{ year.year }}"></label>
  <a class="btn btn-quiet" href="?year={{ following }}" aria-label="Next year">›</a>
  <button class="btn btn-quiet" type="submit">Show</button>
</form>
{% for f in footnotes %}<p class="field-help">{{ f }}</p>{% endfor %}
<section class="report-block"><h2>Practice</h2>
<table class="table"><thead><tr><th></th><th>People</th><th>Allowance</th><th>Adjustments</th><th>Taken</th><th>Remaining</th><th>TOIL remaining</th><th>Waiting for approval</th></tr></thead>
<tbody><tr><td>Practice total</td><td>{{ practice.people }}</td><td>{{ practice.allowance|hm }}</td><td>{{ practice.adjustments|hm }}</td><td>{{ practice.taken|hm }}</td><td>{{ practice.remaining|hm }}</td><td>{{ practice.toil|hm }}</td><td>{{ practice.pending|hm }}</td></tr></tbody></table></section>
<section class="report-block"><h2>Teams</h2>
<table class="table"><thead><tr><th>Team</th><th>People</th><th>Allowance</th><th>Adjustments</th><th>Taken</th><th>Remaining</th><th>TOIL remaining</th><th>Waiting for approval</th></tr></thead>
<tbody>{% for t in teams %}<tr><td>{{ t.name }}</td><td>{{ t.people }}</td><td>{{ t.allowance|hm }}</td><td>{{ t.adjustments|hm }}</td><td>{{ t.taken|hm }}</td><td>{{ t.remaining|hm }}</td><td>{{ t.toil|hm }}</td><td>{{ t.pending|hm }}</td></tr>{% endfor %}</tbody></table></section>
<section class="report-block"><h2>People</h2>
<table class="table"><thead><tr><th>Name</th><th>Team</th><th>Leave year</th><th>Allowance</th><th>Adjustments</th><th>Taken</th><th>Remaining</th><th>TOIL remaining</th><th>Waiting for approval</th></tr></thead>
<tbody>{% for r in people %}<tr><td>{{ r.person.name }}</td><td>{{ r.team }}</td><td>{{ r.year|year_label }}</td>
  <td>{% if r.missing %}<span class="muted">not set</span>{% else %}{{ r.allowance|hm }}{% endif %}</td><td>{{ r.adjustments|hm }}</td><td>{{ r.taken|hm }}</td>
  <td>{% if r.missing %}<span class="muted">—</span>{% else %}{{ r.remaining|hm }}{% endif %}</td><td>{{ r.toil|hm }}</td><td>{{ r.pending|hm }}</td></tr>
{% empty %}<tr><td colspan="9">Nobody to report on.</td></tr>{% endfor %}</tbody></table></section>
{% endblock %}
```

`leave/templatetags/leave_extras.py` gains the filter the leave-year cell uses:

```python
@register.filter
def year_label(value):
    from leave.services import years
    return years.label(value)
```

`leave/views/__init__.py`: `from .summary import leave_summary  # noqa: F401`; `leave/urls.py`: `path("reports/leave-summary/", views.leave_summary, name="report-leave-summary")`. `ui/context_processors.py`: the manager Reports children become `[Hours, Leave, Payroll, {"label": "Sickness summary", "url": "/reports/sickness/"}, {"label": "Leave summary", "url": "/reports/leave-summary/"}]`.

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_absence_onepager.py tests/test_leave_summary.py tests/test_shell.py -q && .venv/bin/ruff check .`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add absence leave ui templates tests/test_absence_onepager.py tests/test_leave_summary.py
git commit -m "Reports: the sickness and leave one-pagers as a page, a PDF or an Excel file"
```

---

### Task 11: The e2e test, the manager's guide, the upgrade checklist, the amendments postscript, the spec's deviations

**Files:**
- Create: `tests/e2e/test_absence.py`, `docs/admin/absence.md`
- Modify: `docs/admin/setup.md:126-182` (the upgrade checklist), `docs/admin/leave.md:519-535` ("What is not here yet"), `docs/admin/people.md` (the leaver line on the statement; the sickness line), `docs/admin/README.md` (the Absence and payroll row), `README.md` (the feature list, the timer), `docs/requirements/2026-10-29-proposed-amendments.md` (a postscript), `docs/superpowers/specs/2026-10-31-leave-design.md` (two Revisit items marked settled), `docs/superpowers/specs/2026-10-31-absence-payroll-design.md` (Status line; the "Deviations recorded during the build" section the controller supplies)

**Interfaces:** none new. Consumes everything above.

- [ ] **Step 1: Write the e2e test**

`tests/e2e/test_absence.py`:

```python
"""A manager records sickness that joins on to an earlier entry, chooses
Extend, and sees one entry; then downloads the payroll Excel. Signs in
with a password as test_grid does."""

from datetime import date, time, timedelta
from decimal import Decimal

import pytest
from playwright.sync_api import expect

from tests import clock
from tests.factories import make_allowance, make_entry, make_person, make_sick, make_team, make_team_manager, make_type, make_user_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.today(clock.LATE_2026)]


@pytest.fixture
def manager(live_server):
    make_type("Holiday")
    make_type("Sick leave", requestable=False, sickness=True)           # a transactional test empties the seeds
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    user = make_user_for(lead, password="pw", is_all_teams_manager=True)
    nina = make_person(first_name="Nina", team=team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
    make_allowance(nina, date(2026, 1, 1), Decimal("172.5"), 60)
    day = date(2026, 10, 5)
    while day <= date(2026, 11, 30):
        if day.weekday() < 5:
            make_entry(nina, day, start=time(9), finish=time(17), break_minutes=30)
        day += timedelta(days=1)
    make_sick(nina, date(2026, 10, 19), date(2026, 10, 23))              # Mon–Fri
    return user


def _sign_in(page, live_server, user, path):
    page.goto(f"{live_server.url}/accounts/login/?next={path}")
    page.fill("input[name=username]", user.email)
    page.fill("input[name=password]", "pw")
    page.click("button[type=submit]")


def test_extend_a_joined_on_entry_then_download_the_payroll(page, live_server, manager):
    _sign_in(page, live_server, manager, "/time-off/")
    page.click("text=Add time off +")
    page.wait_for_selector("#dialog form")
    page.select_option("#dialog select[name=person]", label="Nina Patel")
    page.select_option("#dialog select[name=type]", label="Sick leave")
    page.fill("#dialog input[name=first_day]", "2026-10-26")
    page.fill("#dialog input[name=last_day]", "2026-10-27")
    page.wait_for_selector("#dialog input[name=join]")
    expect(page.locator("#dialog")).to_contain_text("joins on to Sick leave 19 Oct–23 Oct 2026")
    page.click("#dialog button.btn-dark")
    page.wait_for_selector("#dialog", state="hidden")
    rows = page.locator("table.table tbody tr:has-text('Sick leave')")
    expect(rows).to_have_count(1)
    expect(rows.first).to_contain_text("27 Oct 2026")
    page.goto(f"{live_server.url}/reports/payroll/?month=2026-10")
    with page.expect_download() as download:
        page.click("text=Download Excel")
    assert download.value.suggested_filename == "payroll-2026-10.xlsx"
```

Run: `E2E=1 E2E_CHROMIUM=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/e2e/test_absence.py -q` → passes. If the Time off list's default range (the current leave year and the next) does not show October 2026 rows in a way the locator finds, filter with `?from=2026-10-01&to=2026-10-31` in the `goto` after the dialog closes.

- [ ] **Step 2: The manager's guide and the other documents**

`docs/admin/absence.md` sections, in the voice of `docs/admin/leave.md`: **The mental model** (a sickness entry is a booking of Sick leave; one entry is one instance; triggers count the last six months; the system never stores a figure); **Recording sickness** (Add time off, Sick leave, the join-on warning and what Extend does, long sickness at 29 days, the trigger email, editing dates, what colleagues see); **Converting holiday to sickness** (LEAVE-28, where the link is, what comes back); **The past schedule section** (what to type for 2026, dates only, why, how to remove an entry); **Triggers and the sickness summary** (3/4/5+, the rolling window with an example, the one-pager's three tables, PDF or Excel); **Leavers** (the two emails, what the figure means, bookings after the leaving date are flagged not cancelled, the Health card line); **Returning from a long absence** (the email, LEAVE-29); **Year end** (when the flag opens, the email, the page, the three choices, TOIL, deficits, where the carry shows afterwards, the first year end is December 2027); **The payroll report** (the month, each column explained with PAY-01's words, GPs' sessions, the days still to come, Download Excel, Mark as sent and who can, how corrections appear, the Health line from ten days before month end); **The leave summary**; **Emails** (a table of the five); **The daily command** (`shift-central-daily-flags.timer`, 08:25, what to check in the journal); **What is not here yet** (push, the dashboard reports, pay rates, a sickness reason).

`docs/admin/setup.md` upgrade checklist: retitle "Upgrading a box that runs an earlier release" and add the absence and payroll release's steps: step 2 installs `openpyxl` and `reportlab` (pure Python, from `requirements.txt`), step 3's migrate "adds the two leave type flags (Sick leave counts as sickness; Maternity and Adoption flag the return), dates-only bookings, the year-end table, the leaver flag dates and the payroll run table; nothing existing changes", step 4 collectstatic "copies the PDF's logo", step 6 copies `deploy/shift-central-daily-flags.*`, a new step after the reminders timer: "**Enable the daily flags timer once mail works**: run `deploy/manage daily_flags` once (it prints three counts) then `systemctl enable --now shift-central-daily-flags.timer`; it runs at 08:25 every day." Keep every command through `deploy/manage` (the docs test).

`docs/admin/leave.md` "What is not here yet": remove the sickness, convert, year-end, leaver, payroll and one-pager bullets (point to `absence.md`); keep push, repeating time off, the approval variants, imports. `docs/admin/people.md`: the Pay & time off tab's statement now shows a leaver's line and the sickness line. `docs/admin/README.md`: an **Absence and payroll** row linking `absence.md`, and the Leave row's "what is not built yet" phrase updated. `README.md`: the feature list gains the release (sickness and triggers, the past schedule, the flags, the payroll report, the one-pagers), the timers list gains `shift-central-daily-flags.timer`, the dependency note names openpyxl and reportlab, and the "follow in later specs" sentence shrinks to push notifications and spec 5's reports.

`docs/requirements/2026-10-29-proposed-amendments.md`, append:

```
## Postscript, 31 October 2026 (developers), absence and payroll

Built as the pack asks (spec 4): sickness instances and triggers over Sick
leave bookings, the past schedule section for 2026 sickness, the leaver
and year-end flags, the payroll report and the two one-pagers, the last
two ahead of the dates in point 3. Two choices to note: no sickness reason
is recorded (Q-11; the manager note stays the place for anything a manager
wants to keep), and GPs appear on the payroll report with their sessions
counted as hours worked at 4 h 10 min.
```

`docs/superpowers/specs/2026-10-31-leave-design.md` Revisit: the "GP sessions are not covered by leave" item gains "Settled in spec 4: Who's in today and the payroll report hide a GP's sessions under their leave; the grid still shows them." and the "Approved bookings that run past a person's HR finish date" item gains "Settled in spec 4: flagged in the leaver email, on the Health card and on the Time off list; never cancelled automatically."

`docs/superpowers/specs/2026-10-31-absence-payroll-design.md`: the Status line becomes "approved in conversation; built and reviewed, with the deviations recorded at the end" and a "Deviations recorded during the build" section is appended with every ruling the controller ledgered during Tasks 1 to 10 (the controller supplies the list in the task brief; known already: the join-on gap cap of seven days, a half day's other half counted as worked on the payroll report, the "Your time off has been changed" email on conversion, a whole-booking conversion sending the cancel email too, the practice and team "instances" on the sickness one-pager counting the range rather than the window).

- [ ] **Step 3: Run everything**

Run: `.venv/bin/python -m pytest -q`; `E2E=1 E2E_CHROMIUM=/opt/pw-browsers/chromium .venv/bin/python -m pytest tests/e2e -q`; `.venv/bin/ruff check .`; `DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run`; `git status` clean apart from this task's files.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_absence.py docs README.md
git commit -m "Docs: the absence and payroll guide, the upgrade checklist, the amendments postscript, the spec's deviations; an end-to-end sickness test"
```

---

## Self-review notes (plan author)

- **Spec coverage.** Section 2 (models): Task 1. Section 3 (sickness rules, trigger notices, who sees what): Tasks 2 and 4. Section 4 (past schedule): Tasks 2 and 4. Section 5 (convert): Task 3. Section 6 (leaver, return, year end): Tasks 5 and 6. Section 7 (screens, nav, Who's in today): Tasks 3, 4, 6, 7, 9, 10. Section 8 (payroll): Tasks 8 and 9. Section 9 (one-pagers): Tasks 7 and 10. Section 10 (notifications, daily command): Tasks 2, 3, 5, 6. Section 11 (audit): Tasks 2, 3, 6, 8, 9. Section 12 (errors): the services' refusals in Tasks 2, 3, 6, 8 and the views' handling in 3, 4, 6, 9. Section 13 (testing): each task's tests; the e2e in Task 11. Section 14 (deploy, docs): Tasks 1, 6, 7, 11.
- **Names used across tasks:** `sickness.window/instances/level/level_for/level_label/is_long/joins_on/overlaps_window/LONG_DAYS` (2 → 3, 4, 5, 6, 10); `bookings.book(dates_only=)` and `bookings.edit(note=)` (2 → 3, 4); `_sickness_preview` (4 → 4's past view); `leavers.figure/figure_text/after_leaving/flag/week_flags` (5 → 6, 8); `returns.send` (5 → 6); `yearend.run/open_due/decide/open_rows/long_absence` (6); `exports.xlsx.Hours/workbook/response`, `exports.pdf.document/response` (7 → 9, 10); `sessions.hidden/visible` (7 → 8); `report.FIELDS/HOUR_FIELDS/LABELS/month_of/month_end/people_for/rows/type_names/corrections`, `runs.latest/mark_sent/unsent_due` (8 → 9); `Row.leave_days_text` (8 → 9).
- **Known soft spots for the reviewer:** the join-on rule's seven-day cap (a spec deviation, to ledger); `bookings.edit` gaining a `note` parameter while `**fields` are the editable fields (`note` is not in `EDITABLE`, so the two never clash); the GP half-day cost in the payroll test (`costing.cost` halves the day's sessions); the Excel's status line as row 2 of the Payroll sheet; `report.corrections` recomputing up to twelve months on every page view (one practice, fine; a cache is spec 5's if it ever matters); the `today` fixture in the year-end tests moving the clock after the fixtures book 2027 leave.
