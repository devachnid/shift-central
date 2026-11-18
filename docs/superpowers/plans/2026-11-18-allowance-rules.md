# Allowances Worked Out From Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AMG Shift Central reads each person's contracts and leave terms from Practice HR's staff feed, works their two full-year leave allowances out for this leave year and the next, keeps them in step when a contract changes, and gives managers a page to check the figures on.

**Architecture:** The sync copies each feed record's `contracts` into a new `people.Contract` table and owns `Person.weekly_hours` for anyone whose hours contracts in force add up to more than 0. A new service, `leave/services/entitlement.py`, holds the arithmetic as pure functions over prefetched data, a `refresh()` that reconciles `people.Allowance` rows after every good sync, and a `review()` that builds the manager's four lists on demand. `Allowance` rows gain a source (typed, worked out, copied) and a check, every write to one goes through `people/services/profiles.py` and is audited, and pro-rata is untouched except that a GP's single rounding is to the whole session.

**Tech Stack:** Django 5.2, Python 3.13, SQLite, pytest-django, Playwright for one browser test. Server-rendered templates with `static/js/modal.js` for pop-ups; no new JavaScript. Lint is `ruff check .` (pyflakes rules only).

**Spec:** `docs/superpowers/specs/2026-11-18-allowance-rules-design.md`, part B: sections 5, 6, 6.1, 7, 8, 9, 10 (the Shift Central lines), 11 step 2 and 12. Read sections 5 to 9 before starting. Part A (Practice HR) has its own plan, `docs/superpowers/plans/2026-11-18-leave-terms.md` in `devachnid/practice-hr`, and is already built on that repository's branch.

## Global Constraints

- Branch `claude/hopeful-keller-lankio`, base `main`. One pull request, merge commits, not merged until asked.
- Every write goes through a service; a view never touches a model's fields. Every change is audited with `people.services.audit.record(actor, obj, {field: (before, after)}, note)`; `actor=None` is the app and is stored as `practice-hr` with the note starting `from Practice HR`.
- Every write to an `Allowance` row's figures, source or check goes through `people/services/profiles.py` (`set_allowance`, `add_hours_change`, and from Task 5 `write_allowance`, `add_allowance`, `remove_allowance`).
- Log lines carry ids and counts, never names, figures or terms. `SyncRun.message` never carries a record's values.
- The CSP forbids inline scripts and handlers: no `<script>`, no `onclick`, no `style=` in a new template. Pop-ups use `data-dialog` and `data-dialog-form`; a page's own buttons are plain `<form method="post">`.
- With no copied contract anywhere the app behaves exactly as today: nothing is worked out, nothing is copied forward, the four new Health lines read 0. Every existing test passes untouched. (A trial run of the whole suite with this plan applied passed with no existing test edited; no existing test pins a GP's part-year figure to the half hour.)
- A full-year figure for an hours contract is rounded to the nearest half hour, a quarter hour rounding up. For a sessions contract it is rounded to the nearest whole session, a half rounding up, and stored as sessions × 25 ÷ 6 hours to 4 decimal places. A GP session is 15 000 seconds (`leave.services.hours.GP_SESSION`); `hours.from_hours(Decimal("266.6667"))` is exactly 960 000.
- `Allowance.annual_hours` and `bank_holiday_hours` are `max_digits=8, decimal_places=4`. What a manager types stays at 2 places (the forms and `set_allowance` quantise to 0.01). Show a figure with `hours.plain()` (2 places unless it needs 4) or as hours and minutes with `hours.fmt()`.
- A person's weekly hours are Practice HR's only while their hours contracts in force today (on the start date, for a starter) add up to more than 0: `contracts.hours_from_hr(person)`. Everyone else is typed as today: no copied contract, bank staff on a 0-hour contract, someone between contracts. A GP has no weekly hours.
- A row **needs checking** when `source in ("worked_out", "copied") and checked_at is None`. `checked_at` set with `checked_by` null means the app checked it itself.
- A leave year is named by its first day (`Allowance.leave_year`); the year's first row has `from_day == leave_year`, for a starter in the year too. Refresh covers `years.years_for(person)` less any year that ended before `leave.services.yearend.LAUNCH` (1 January 2027), and never writes to a year that has ended.
- Permissions: a manager action needs `access.can_manage(actor, person)` (nobody manages themselves). Only `access.is_all_teams` changes `LeaveSetting.allowances_need_checking`.
- Seeds send no email and no push. No secret, token or real person's detail goes in a test, a fixture or a doc.
- Tests pin the clock: the suite runs as 2 November 2026 (`tests/clock.py`); a test on another day uses `@pytest.mark.today(date(...))` or the `today` fixture. Bank holidays for 2026 and 2027 are seeded by migration (8 each); 2028 has none unless a test makes them.
- Commands: `.venv/bin/python -m pytest -q` is the whole suite, about 2 minutes (1,189 tests before this plan). Run the named files while working and the whole suite once, in Task 10. Lint: `.venv/bin/ruff check .`. Migrations: `DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run`. Browser tests: `E2E=1 E2E_CHROMIUM=/opt/pw-browsers/chromium .venv/bin/python -m pytest -q tests/e2e` (about 35 seconds; CI runs them without `E2E_CHROMIUM`).
- Commit messages are `Area: what changed` (`People:`, `Leave:`, `Docs:`) and end with the two attribution lines the session provides (attribution lines: `Co-Authored-By:` and `Claude-Session:`). No model name anywhere else in the repository.
- The repository's `CLAUDE.md` asks for `graphify update .` after code changes. Run it after each commit if the command exists (`command -v graphify`); it is not installed in this container, so skip it when the command is missing.
- **How edits are written in this plan.** "Create" gives the whole file. "In `file`, replace: … with: …" swaps the first block, which occurs exactly once, for the second. "Add before the line" puts the block immediately above that line, with two blank lines between when both are top-level Python and none otherwise. "Add after the line" puts it immediately below, with no blank line. "Add to the end of" a Python file leaves two blank lines before the block. "Replace everything from the line A up to, but not including, the line B" removes A and what follows it and puts the block there, with two blank lines before B at the top level of a Python file.

## File Structure

| File | | Responsibility |
|---|---|---|
| `people/models/contract.py` | create | `Contract`: a copy of one contract in Practice HR's feed. |
| `people/models/allowance.py`, `people/models/__init__.py` | modify | `Allowance.source`, `checked_at`, `checked_by`, `needs_checking`; figures widened to 4 places. |
| `leave/models/setting.py` | modify | `LeaveSetting.allowances_need_checking`. |
| `people/migrations/0008_contracts_and_allowance_source.py`, `leave/migrations/0004_allowances_need_checking.py` | create (generated) | The schema. |
| `people/admin.py`, `leave/admin.py` | modify | Contracts shown read-only; the new columns. |
| `leave/services/hours.py`, `leave/templatetags/leave_extras.py` | modify | `plain()`; the `plain_hours` and `hours_hm` filters. |
| `leave/services/prorata.py`, `leave/services/balances.py` | modify | A GP's part-year rounding to the whole session; the statement's wording. |
| `people/services/contracts.py` | create | Which copied contracts are in force on a day and what they add up to. |
| `people/services/hr_sync.py` | modify | Reads `contracts`; owns weekly hours where a contract gives them; calls `entitlement.refresh()`. |
| `people/services/profiles.py` | modify | Weekly hours rule; the row writers; confirm, change, use the worked-out figure. |
| `leave/services/entitlement.py` | create | The arithmetic, `load`, `refresh`, `review`, `shown`, `state`. |
| `leave/services/settings.py`, `leave/forms.py`, `leave/views/settings.py`, `templates/leave/settings.html` | modify | The Leave settings switch. |
| `people/services/health.py`, `templates/people/_health.html` | modify | Four Health lines. |
| `people/views/allowances.py`, `people/urls.py`, `people/views/__init__.py`, `people/forms.py` | create / modify | The page at `/staff/allowances/` and its actions. |
| `templates/people/allowances.html`, `_allowance_confirm_fields.html`, `allowance_change_dialog.html` | create | The page, the hidden fields a confirm posts, the Change pop-up. |
| `ui/context_processors.py` | modify | "Allowances" under Staff in the side panel, for managers. |
| `people/views/profile.py`, `templates/people/_profile_hours.html` | modify | Read-only weekly hours; each row's state, working and buttons. |
| `leave/views/statement.py`, `templates/leave/_statement.html` | modify | The working under the statement, for managers; no Add hours change for a worked-out year. |
| `tests/factories.py` | modify | `make_contract`. |
| `tests/data/people_feed.json` | create | The sample feed, byte for byte the same as Practice HR's. |
| `tests/test_allowance_models.py`, `test_leave_prorata_gp.py`, `test_hr_sync_contracts.py`, `test_entitlement.py`, `test_entitlement_refresh.py`, `test_allowance_actions.py`, `test_allowance_review.py`, `test_allowances_page.py`, `test_allowance_profile.py`, `tests/e2e/test_allowances.py` | create | One file per task. |
| `docs/admin/leave.md`, `people.md`, `sync.md`, `setup.md`, `README.md`; `README.md`; `docs/requirements/04`, `05`, `12`, `2026-10-29-proposed-amendments.md`; the spec | modify | The guide, the requirement changes, the spec's record of what was built. |

**Order of tasks.** The spec's order with two changes, both forced by the code. The models come before the GP rounding (Tasks 1 and 2), because the rounding's tests need a figure stored to four places (66.6667). The Health card's lines arrive with the page (Task 8), not with the lists (Task 7), because each line links to the page.

---

### Task 1: What is stored

**Files:**
- Create: `people/models/contract.py`, `people/migrations/0008_contracts_and_allowance_source.py` (generated), `leave/migrations/0004_allowances_need_checking.py` (generated)
- Modify: `people/models/__init__.py`, `people/models/allowance.py`, `leave/models/setting.py`, `people/admin.py`, `leave/admin.py`, `leave/services/hours.py`, `leave/templatetags/leave_extras.py`, `leave/services/balances.py:127`, `people/services/profiles.py:61-84`, `people/views/profile.py:60-67`, `templates/people/_profile_hours.html`, `tests/factories.py`
- Test: `tests/test_allowance_models.py`

**Interfaces:**
- Consumes: nothing from this plan.
- Produces:
  - `people.models.Contract(person, hr_id, type_name, unit, from_day, to_day, weekly_amount, full_time_weekly, leave_base, leave_steps)`; `Contract.Unit.HOURS == "hours"`, `Contract.Unit.SESSIONS == "sessions"`; related name `person.contracts`, ordered by `from_day`, `hr_id`. `leave_steps` is a list of `[after_years: int, total: str]`.
  - `Allowance.Source.TYPED / WORKED_OUT / COPIED` (values `"typed"`, `"worked_out"`, `"copied"`; labels "typed", "worked out", "copied from last year"); `Allowance.source`, `Allowance.checked_at`, `Allowance.checked_by`; `Allowance.NEEDS_CHECK`; property `Allowance.needs_checking -> bool`.
  - `LeaveSetting.allowances_need_checking` (bool, default True).
  - `leave.services.hours.plain(value) -> str`: `"138.00"` for 138, `"266.6667"` for 266.6667. Template filter `plain_hours` in `leave_extras`.
  - `tests.factories.make_contract(person, weekly="37.5", base="22", steps=(), **kw) -> Contract`.

Widening the two figures to four places changes how a stored figure reads back (`138.0000`), so this task also keeps every place that shows one at two places: the statement line, the audit entry, the profile's boxes and the read-only tab.

- [ ] **Step 1: Write the factory and the failing tests**

In `tests/factories.py`, replace:

```python
from people.models import Allowance, Department, Person, Team, TeamManager
```

with:

```python
from people.models import Allowance, Contract, Department, Person, Team, TeamManager
```

In `tests/factories.py`, add before the line `def client_for(person, **user_kw):`:

```python
def make_contract(person, weekly="37.5", base="22", steps=(), **kw):
    """A copy of a Practice HR contract: hours unless unit="sessions", from
    the person's start date, with leave terms of `base` days (weeks for
    sessions) and `steps` of (after_years, total). base=None is a contract
    with no terms, whose allowances are typed."""
    from decimal import Decimal
    sessions = kw.get("unit") == "sessions"
    kw.setdefault("hr_id", next(_next_id))
    kw.setdefault("unit", "hours")
    kw.setdefault("type_name", "Salaried GP" if sessions else "Reception")
    kw.setdefault("from_day", person.start_date)
    kw.setdefault("full_time_weekly", Decimal("8") if sessions else Decimal("37.5"))
    return Contract.objects.create(person=person, weekly_amount=Decimal(str(weekly)),
                                   leave_base=None if base is None else Decimal(str(base)),
                                   leave_steps=[[after, f"{Decimal(str(total)):.2f}"] for after, total in steps], **kw)
```

Create `tests/test_allowance_models.py`:

```python
"""Allowance spec 2026-11-18, section 5: what is stored."""

from datetime import date
from decimal import Decimal as D

import pytest
from django.db import IntegrityError, transaction

from leave.models import LeaveSetting
from leave.services import balances, hours
from leave.services import settings as leave_settings
from people.models import Allowance, Contract, Person
from tests.factories import client_for, make_allowance, make_contract, make_person

pytestmark = pytest.mark.django_db
Y27 = date(2027, 1, 1)


def test_a_contract_is_a_copy_of_the_feeds_with_one_row_per_hr_id():
    sam = make_person(start_date=date(2025, 6, 1))
    c = make_contract(sam, "22.5", steps=[(1, 23), (5, 25)])
    c.refresh_from_db()
    assert (c.type_name, c.unit, c.from_day, c.to_day) == ("Reception", "hours", date(2025, 6, 1), None)
    assert (c.weekly_amount, c.full_time_weekly, c.leave_base) == (D("22.5"), D("37.5"), D("22"))
    assert c.leave_steps == [[1, "23.00"], [5, "25.00"]]                # totals as strings, so the decimals are exact
    assert str(c) == "Reception, 22.50 hours a week from 1 Jun 2025"
    with pytest.raises(IntegrityError), transaction.atomic():
        make_contract(sam, hr_id=c.hr_id)
    doc = make_person(is_gp=True)
    gp = make_contract(doc, 6, 8, unit="sessions", type_name="Partner")
    assert (gp.unit, gp.full_time_weekly, gp.leave_steps) == ("sessions", D("8"), [])
    assert make_contract(doc, 8, None, unit="sessions").leave_base is None           # no terms: its allowances are typed
    assert [x.hr_id for x in sam.contracts.all()] == [c.hr_id]
    sam.delete()
    assert not Contract.objects.filter(pk=c.pk).exists()


def test_every_existing_allowance_is_typed_and_needs_no_check():
    row = make_allowance(make_person(), Y27, 138, 48)
    row.refresh_from_db()
    assert (row.source, row.checked_at, row.checked_by) == ("typed", None, None) and not row.needs_checking


@pytest.mark.parametrize("source, checked, needs", [("typed", False, False), ("worked_out", False, True), ("copied", False, True),
                                                    ("worked_out", True, False), ("copied", True, False)])
def test_a_worked_out_or_copied_row_needs_checking_until_it_is_checked(source, checked, needs, all_teams_user):
    from django.utils import timezone
    row = make_allowance(make_person(), Y27, 138, 48, source=source, checked_at=timezone.now() if checked else None,
                         checked_by=all_teams_user if checked else None)
    assert row.needs_checking is needs
    assert row.get_source_display() == {"typed": "typed", "worked_out": "worked out", "copied": "copied from last year"}[source]


def test_the_figures_hold_four_places_so_whole_sessions_are_exact():
    row = make_allowance(make_person(is_gp=True), Y27, D("266.6667"), D("66.6667"))
    row.refresh_from_db()
    assert (row.annual_hours, row.bank_holiday_hours) == (D("266.6667"), D("66.6667"))
    assert hours.from_hours(row.annual_hours) == 960000 == 64 * hours.GP_SESSION        # 64 sessions, to the second
    assert hours.from_hours(row.bank_holiday_hours) == 16 * hours.GP_SESSION


def test_a_typed_figure_still_reads_to_two_places():
    assert hours.plain(D("138.0000")) == "138.00" and hours.plain(D("172.5")) == "172.50" and hours.plain(138) == "138.00"
    assert hours.plain(D("266.6667")) == "266.6667"
    sam = make_person(start_date=date(2027, 7, 6))
    make_allowance(sam, Y27, 210, 0)
    texts = [text for kind, text, _ in balances.statement(sam, Y27).lines if kind == "allowance"]
    assert texts[0] == "Annual leave allowance 6 Jul–31 Dec: 26 weeks of 52 at 210.00 h"


def test_worked_out_allowances_need_checking_unless_the_setting_says_otherwise():
    assert leave_settings.get().allowances_need_checking is True
    assert LeaveSetting._meta.get_field("allowances_need_checking").default is True


def test_the_superuser_deletes_a_person_with_a_copied_contract(root_client):
    sam = make_person(end_date=date(2026, 3, 31))
    make_contract(sam)
    make_allowance(sam, Y27, 138, 48)
    assert root_client.get("/admin/people/contract/").status_code == 200
    assert root_client.get("/admin/people/contract/add/").status_code == 403
    r = root_client.post(f"/admin/people/person/{sam.pk}/delete/", {"post": "yes"})
    assert r.status_code == 302 and not Person.objects.filter(pk=sam.pk).exists()
    assert not Contract.objects.exists() and not Allowance.objects.exists()


def test_the_hours_tab_shows_a_stored_figure_to_two_places_and_saves_it_back_untouched(monkeypatch):
    """The boxes take two decimal places; a figure read back from four must not be refused by them."""
    from leave.services import years
    real = years.years_for
    monkeypatch.setattr(years, "years_for", lambda person, today=None: real(person, today or date(2026, 11, 20)))
    nina = make_person(first_name="Nina", weekly_hours=D("30"), days_per_week=4)
    make_allowance(nina, Y27, 138, 48)
    c = client_for(make_person(first_name="Boss"), is_all_teams_manager=True)
    url = f"/staff/{nina.pk}/profile/?tab=hours"
    body = c.get(url).content.decode()
    assert 'name="annual_2027" value="138.00"' in body and 'name="bank_holiday_2027" value="48.00"' in body
    r = c.post(url, {"weekly_hours": "30.00", "days_per_week": "4", "annual_2027": "138.00", "bank_holiday_2027": "48.00", "note": ""})
    assert "Saved." in r.content.decode()
    assert "138.00 h" in client_for(nina).get(url).content.decode()      # and the person reads it as before
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_allowance_models.py -q`
Expected: an error while collecting, `ImportError: cannot import name 'Contract' from 'people.models'`.

- [ ] **Step 3: The models**

Create `people/models/contract.py`:

```python
from django.db import models

from .person import Person


class Contract(models.Model):
    """A copy of one contract in Practice HR's feed (allowance spec, 5.1):
    what the entitlement service works allowances out from. The sync
    replaces a person's rows with what the feed sends; nothing here is
    edited or audited, because Practice HR audits the contract and Shift
    Central audits every allowance figure that results.

    `leave_base` and each step's total are days a year for an hours
    contract and weeks a year for a sessions one; `leave_base` is null when
    the contract has no terms and its allowances are typed. `leave_steps`
    is a list of [after_years, total] pairs, oldest step first, the total a
    string ("23.00") so the decimal is exact."""

    class Unit(models.TextChoices):
        HOURS = "hours"
        SESSIONS = "sessions"

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="contracts")
    hr_id = models.PositiveIntegerField(unique=True)
    type_name = models.CharField(max_length=60)
    unit = models.CharField(max_length=8, choices=Unit.choices)
    from_day = models.DateField()
    to_day = models.DateField(null=True, blank=True)
    weekly_amount = models.DecimalField(max_digits=5, decimal_places=2)
    full_time_weekly = models.DecimalField(max_digits=5, decimal_places=2)
    leave_base = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    leave_steps = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["from_day", "hr_id"]

    def __str__(self):
        return f"{self.type_name}, {self.weekly_amount} {self.unit} a week from {self.from_day:%-d %b %Y}"
```

Replace the whole of `people/models/__init__.py` with:

```python
from .allowance import Allowance
from .audit import AuditEntry
from .contract import Contract
from .department import Department
from .manager import TeamManager
from .person import HEX_COLOUR, Person
from .sync import SyncRun
from .team import Team

__all__ = ["Allowance", "AuditEntry", "Contract", "Department", "HEX_COLOUR", "Person", "SyncRun",
           "Team", "TeamManager"]
```

Replace the whole of `people/models/allowance.py` with:

```python
from django.conf import settings
from django.db import models

from .person import Person


class Allowance(models.Model):
    """The two full-year figures (LEAVE-01), per leave year. `leave_year`
    is the year's first day. The first row of a year has `from_day` =
    `leave_year`; a later row is a dated hours change (PAT-06, LEAVE-12)
    carrying the new full-year figures and, when set, the new weekly hours
    and days per week from that day.

    `source` says where the figures came from: typed by a manager, worked
    out from the person's contract in Practice HR, or copied from last
    year's. A worked-out or copied row needs checking until `checked_at`
    is set; `checked_by` is the manager who confirmed it, or null when the
    app did (the figures a manager typed turned out to be the rule's, or
    Leave settings no longer asks for a check). The figures hold four
    decimal places so that a whole number of GP sessions is exact to the
    second (64 sessions is 266.6667 h); what a manager types stays at two."""

    class Source(models.TextChoices):
        TYPED = "typed", "typed"
        WORKED_OUT = "worked_out", "worked out"
        COPIED = "copied", "copied from last year"

    NEEDS_CHECK = (Source.WORKED_OUT, Source.COPIED)

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="allowances")
    leave_year = models.DateField()
    from_day = models.DateField(editable=False)
    annual_hours = models.DecimalField(max_digits=8, decimal_places=4)
    bank_holiday_hours = models.DecimalField(max_digits=8, decimal_places=4)
    weekly_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    days_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    hours_applied = models.BooleanField(default=False)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.TYPED)
    checked_at = models.DateTimeField(null=True, blank=True)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["person", "leave_year", "from_day"],
                                               name="one_allowance_per_person_year_and_day")]
        ordering = ["leave_year", "from_day"]

    @property
    def needs_checking(self):
        return self.source in self.NEEDS_CHECK and self.checked_at is None

    def save(self, *args, **kwargs):
        if self.from_day is None:
            self.from_day = self.leave_year
        super().save(*args, **kwargs)
```

Replace the whole of `leave/models/setting.py` with:

```python
from django.db import models


class LeaveSetting(models.Model):
    """One row. Read through leave.services.settings.get()."""
    reminder_working_days = models.PositiveSmallIntegerField(default=3)
    # Allowance spec, 7.6: while on, an allowance the app works out from a
    # contract (or copies from last year) waits for a manager to check it.
    allowances_need_checking = models.BooleanField(default=True)

    class Meta:
        verbose_name = "leave settings"
        verbose_name_plural = "leave settings"
```

- [ ] **Step 4: Generate the migrations**

Run: `DEBUG=1 .venv/bin/python manage.py makemigrations people -n contracts_and_allowance_source`
Expected: `people/migrations/0008_contracts_and_allowance_source.py`, listing "Add field checked_at to allowance", "Add field checked_by to allowance", "Add field source to allowance", "Alter field annual_hours on allowance", "Alter field bank_holiday_hours on allowance" and "Create model Contract". Open it and check it holds nothing else.

Run: `DEBUG=1 .venv/bin/python manage.py makemigrations leave -n allowances_need_checking`
Expected: `leave/migrations/0004_allowances_need_checking.py`, "Add field allowances_need_checking to leavesetting".

Existing rows need no data migration: every one becomes `typed` by the field's default, and SQLite rewrites `138.00` as `138.0000` without loss.

- [ ] **Step 5: The admin**

In `people/admin.py`, replace:

```python
its allowances through itself."""
```

with:

```python
its allowances through itself. The copies of Practice HR's contracts are
shown read-only as well and go with their person in the same way."""
```

In `people/admin.py`, replace:

```python
from .models import Allowance, AuditEntry, Department, Person, SyncRun, Team, TeamManager
```

with:

```python
from .models import Allowance, AuditEntry, Contract, Department, Person, SyncRun, Team, TeamManager
```

In `people/admin.py`, replace:

```python
        """The person's allowances go with them, though their admin refuses a delete of one alone."""
        to_delete, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        perms_needed.discard(Allowance._meta.verbose_name)
```

with:

```python
        """The person's allowances and copied contracts go with them, though their admins refuse a delete of one alone."""
        to_delete, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        perms_needed.discard(Allowance._meta.verbose_name)
        perms_needed.discard(Contract._meta.verbose_name)
```

In `people/admin.py`, replace:

```python
    list_display = ("person", "leave_year", "from_day", "annual_hours", "bank_holiday_hours", "weekly_hours", "days_per_week")
```

with:

```python
    list_display = ("person", "leave_year", "from_day", "annual_hours", "bank_holiday_hours", "weekly_hours", "days_per_week",
                    "source", "checked_at")
    list_filter = ("source",)


@admin.register(Contract)
class ContractAdmin(ReadOnlyModelAdmin):
    list_display = ("person", "type_name", "unit", "from_day", "to_day", "weekly_amount", "leave_base", "hr_id")
    search_fields = ("person__name",)
```

In `leave/admin.py`, replace:

```python
    list_display = ("reminder_working_days",)
```

with:

```python
    list_display = ("reminder_working_days", "allowances_need_checking")
```

- [ ] **Step 6: Keep a figure reading at two places**

In `leave/services/hours.py`, add before the line `def fmt(seconds):`:

```python
def plain(value):
    """An allowance figure as it is typed and read back: two decimal places,
    and four only when it needs them (a GP's whole sessions: 266.6667)."""
    value = Decimal(value)
    two = value.quantize(Decimal("0.01"))
    return str(two if two == value else value)
```

In `leave/templatetags/leave_extras.py`, replace:

```python
@register.filter
def get_item(mapping, key):
```

with:

```python
@register.filter
def plain_hours(value):
    return hours.plain(value)


@register.filter
def get_item(mapping, key):
```

In `leave/services/balances.py`, replace:

```python
{ln.weeks} weeks of 52 at {ln.full_hours} h"
```

with:

```python
{ln.weeks} weeks of 52 at {hours.plain(ln.full_hours)} h"
```

In `people/services/profiles.py`, replace:

```python
from leave.services import years
```

with:

```python
from leave.services import hours, years
```

In `people/services/profiles.py`, replace:

```python
        before = getattr(allowance, field)
        if before != after:
            changes[field] = (before, after)
```

with:

```python
        before = getattr(allowance, field)
        if before != after:
            changes[field] = (hours.plain(before), after)
```

In `people/views/profile.py`, replace:

```python
from copy import copy

```

with:

```python
from copy import copy
from decimal import Decimal

```

In `people/views/profile.py`, replace:

```python
        initial[f"annual_{a.leave_year.year}"] = a.annual_hours
        initial[f"bank_holiday_{a.leave_year.year}"] = a.bank_holiday_hours
```

with:

```python
        initial[f"annual_{a.leave_year.year}"] = a.annual_hours.quantize(Decimal("0.01"))
        initial[f"bank_holiday_{a.leave_year.year}"] = a.bank_holiday_hours.quantize(Decimal("0.01"))
```

In `templates/people/_profile_hours.html`, replace:

```html
{% if manages %}
<form method="post" action="{% url 'profile' person.pk %}?tab=hours" data-dialog-form>
```

with:

```html
{% load leave_extras %}
{% if manages %}
<form method="post" action="{% url 'profile' person.pk %}?tab=hours" data-dialog-form>
```

In `templates/people/_profile_hours.html`, replace:

```html
  <dt>Annual leave allowance {{ year.year }}</dt><dd>{% if allowance %}{{ allowance.annual_hours }} h{% else %}—{% endif %}</dd>
  <dt>Bank holiday allowance {{ year.year }}</dt><dd>{% if allowance %}{{ allowance.bank_holiday_hours }} h{% else %}—{% endif %}</dd>
```

with:

```html
  <dt>Annual leave allowance {{ year.year }}</dt><dd>{% if allowance %}{{ allowance.annual_hours|plain_hours }} h{% else %}—{% endif %}</dd>
  <dt>Bank holiday allowance {{ year.year }}</dt><dd>{% if allowance %}{{ allowance.bank_holiday_hours|plain_hours }} h{% else %}—{% endif %}</dd>
```

- [ ] **Step 7: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_allowance_models.py tests/test_admin.py tests/test_profile.py tests/test_leave_prorata.py tests/test_leave_models.py tests/test_leave_examples.py -q`
Expected: all pass. `tests/test_profile.py::test_changing_an_existing_allowance_needs_a_reason` is the one that fails if the audit entry is left reading `138.0000`.

Run: `DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run && .venv/bin/ruff check .`
Expected: "No changes detected"; ruff reports nothing.

- [ ] **Step 8: Commit**

```bash
git add people/models people/migrations/0008_contracts_and_allowance_source.py leave/models/setting.py leave/migrations/0004_allowances_need_checking.py people/admin.py leave/admin.py leave/services/hours.py leave/services/balances.py leave/templatetags/leave_extras.py people/services/profiles.py people/views/profile.py templates/people/_profile_hours.html tests/factories.py tests/test_allowance_models.py
git commit -m "People: a copy of Practice HR's contracts, and where each allowance figure came from"
```

---

### Task 2: A GP's part-year allowance is whole sessions

**Files:**
- Modify: `leave/services/prorata.py`, `leave/services/balances.py:129`
- Test: `tests/test_leave_prorata_gp.py`

**Interfaces:**
- Consumes: the four-place figures of Task 1; `hours.GP_SESSION` (15000), `hours.from_hours(value) -> int`.
- Produces: `prorata.allowance(person, year, account) -> ProRata` with the same signature and fields as before. For `person.is_gp` its `seconds` is a whole number of sessions unless it is the cap. Nothing else calls the two new private helpers.

Spec 6.1. Three things change for a GP, none for anyone else. The single rounding is to the nearest whole session, a half rounding up. A stored figure is taken to the whole second before it is shared out, because 14 sessions is stored as 58.3333 h and 13/52 of that must be exactly 3.5 sessions. And a GP whose shares already reach the largest full-year figure gets that figure: without this, a typed figure that is not a whole number of sessions (55 h is 13.2 sessions) would round down to 13 sessions for someone employed all year, which LEAVE-13 forbids.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_leave_prorata_gp.py`:

```python
"""Spec 2026-11-18, section 6.1: a GP's part-year allowance is rounded once
to the nearest whole session (4 h 10 min), not the half hour. Staff on
hours are untouched."""

from datetime import date
from decimal import Decimal

import pytest

from leave.services import balances, hours, prorata
from tests.factories import make_allowance, make_person

pytestmark = pytest.mark.django_db
Y27 = date(2027, 1, 1)
SALARIED_8 = (Decimal("200"), Decimal("66.6667"))        # 48 and 16 sessions


def test_sixty_four_sessions_is_exact_to_the_second():
    assert hours.from_hours(Decimal("266.6667")) == 960000 == 64 * hours.GP_SESSION


def test_a_gp_starting_on_1_july_gets_whole_sessions():
    gp = make_person(is_gp=True, start_date=date(2027, 7, 1))
    make_allowance(gp, Y27, *SALARIED_8)
    annual, bank = prorata.allowance(gp, Y27, "annual"), prorata.allowance(gp, Y27, "bank_holiday")
    assert annual.lines[0].weeks == 27
    assert annual.seconds == 25 * hours.GP_SESSION and hours.fmt(annual.seconds) == "104 h 10 min"
    assert bank.seconds == 8 * hours.GP_SESSION and hours.fmt(bank.seconds) == "33 h 20 min"


def test_staff_on_hours_with_the_same_figures_still_round_to_the_half_hour():
    sam = make_person(start_date=date(2027, 7, 1))
    make_allowance(sam, Y27, Decimal("200"), Decimal("66.67"))
    assert hours.fmt(prorata.allowance(sam, Y27, "annual").seconds) == "104 h"
    assert hours.fmt(prorata.allowance(sam, Y27, "bank_holiday").seconds) == "34 h 30 min"


def test_half_a_session_rounds_up():
    # 13 weeks of 52 at 50 h is 12.5 h: three sessions exactly. At 58.3333 h (14 sessions)
    # it is 14.58 h, 3.5 sessions, which rounds up to 4.
    gp = make_person(is_gp=True, start_date=date(2027, 10, 2))
    make_allowance(gp, Y27, Decimal("50"), Decimal("58.3333"))
    assert prorata.allowance(gp, Y27, "annual").seconds == 3 * hours.GP_SESSION
    assert prorata.allowance(gp, Y27, "bank_holiday").seconds == 4 * hours.GP_SESSION


def test_a_gp_here_all_year_gets_exactly_the_full_figure():
    gp = make_person(is_gp=True, start_date=date(2020, 1, 6))
    make_allowance(gp, Y27, *SALARIED_8)
    annual, bank = prorata.allowance(gp, Y27, "annual"), prorata.allowance(gp, Y27, "bank_holiday")
    assert (annual.seconds, annual.capped) == (48 * hours.GP_SESSION, True)
    assert (bank.seconds, bank.capped) == (16 * hours.GP_SESSION, True)


def test_a_typed_figure_that_is_not_whole_sessions_is_still_met_in_full_by_a_whole_year():
    # 55 h is 13.2 sessions. 53 weeks of 52 is 56.06 h, 13.45 sessions, which rounds DOWN to
    # 13 sessions (54 h 10 min): without the rule for a GP at the cap, LEAVE-13 would not hold.
    gp = make_person(is_gp=True, start_date=date(2020, 1, 6))
    make_allowance(gp, Y27, Decimal("210"), Decimal("55"))
    assert hours.fmt(prorata.allowance(gp, Y27, "annual").seconds) == "210 h"
    assert hours.fmt(prorata.allowance(gp, Y27, "bank_holiday").seconds) == "55 h"


def test_a_gps_change_of_sessions_is_rounded_once_to_a_whole_session():
    gp = make_person(is_gp=True, start_date=date(2020, 1, 6))
    make_allowance(gp, Y27, Decimal("200"), Decimal("50"))                                   # 6 sessions a week
    make_allowance(gp, Y27, Decimal("266.6667"), Decimal("66.6667"), from_day=date(2027, 7, 1))   # 8 from July
    pr = prorata.allowance(gp, Y27, "annual")
    assert [l.weeks for l in pr.lines] == [26, 27]
    # 200 × 26/52 + 266.6667 × 27/52 = 238.46 h = 57.23 sessions
    assert pr.seconds == 57 * hours.GP_SESSION and not pr.capped


def test_the_statement_says_which_rounding_was_used():
    gp = make_person(is_gp=True, start_date=date(2027, 7, 1))
    make_allowance(gp, Y27, *SALARIED_8)
    texts = [text for kind, text, _ in balances.statement(gp, Y27).lines if kind == "allowance"]
    assert "Annual leave allowance rounded to the whole session" in texts
    sam = make_person(start_date=date(2027, 7, 1))
    make_allowance(sam, Y27, Decimal("200"), Decimal("66.67"))
    texts = [text for kind, text, _ in balances.statement(sam, Y27).lines if kind == "allowance"]
    assert "Annual leave allowance rounded to the half hour" in texts
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_leave_prorata_gp.py -q`
Expected: 4 failed, 4 passed. The part-year GP tests fail on half-hour figures (374400 seconds, 104 h, where 25 sessions are wanted) and the statement test on its wording; the hours person and the two whole-year tests already pass.

- [ ] **Step 3: Round a GP's total to the whole session**

In `leave/services/prorata.py`, replace:

```python
rows, which is also what makes a 53-week whole year exactly the full
allowance (LEAVE-13)."""
```

with:

```python
rows, which is also what makes a 53-week whole year exactly the full
allowance (LEAVE-13).

A GP's allowances are whole sessions: for a GP the one rounding is to the
nearest whole session (4 h 10 min, a half session rounding up) instead of
the half hour, whether the full-year figure was worked out or typed. A GP
whose shares already add up to the full-year figure gets exactly that
figure, so one typed in hours that is not a whole number of sessions is
still met in full by a whole year (LEAVE-13)."""
```

In `leave/services/prorata.py`, replace:

```python
        full = getattr(row, field)
        share = Fraction(full) * weeks / 52
```

with:

```python
        full = getattr(row, field)
        share = _exact(person, full) * weeks / 52
```

In `leave/services/prorata.py`, replace:

```python
    rounded = Fraction(math.floor(total * 2 + Fraction(1, 2)), 2)
    cap = max(Fraction(getattr(r, field)) for r in rows)
    capped = rounded > cap
    return ProRata(hours.from_hours(_decimal(min(rounded, cap))), lines, capped)
```

with:

```python
    cap = max(_exact(person, getattr(r, field)) for r in rows)
    rounded = _round_once(person, total)
    # A GP whose shares already reach the largest full-year figure has all of it,
    # whatever a whole session would round to: a typed 55 h is not 13 sessions.
    capped = rounded > cap or (person.is_gp and total >= cap)
    return ProRata(hours.from_hours(_decimal(cap if capped else rounded)), lines, capped)
```

In `leave/services/prorata.py`, add before the line `def _decimal(value):`:

```python
SESSION = Fraction(hours.GP_SESSION, 3600)        # 4 h 10 min, in hours


def _exact(person, full):
    """A full-year figure as an exact number of hours. A GP's is taken to
    the whole second first: 58.3333 h is stored for 14 sessions, and must
    count as the 58 h 20 min it stands for."""
    return Fraction(hours.from_hours(full), 3600) if person.is_gp else Fraction(full)


def _round_once(person, total):
    """The single rounding of the summed shares, a half rounding up: to the
    half hour, or for a GP to the whole session."""
    step = SESSION if person.is_gp else Fraction(1, 2)
    return math.floor(total / step + Fraction(1, 2)) * step
```

For anyone who is not a GP `_round_once` is the old expression (`floor(total ÷ ½ + ½) × ½`) and `cap if capped else rounded` is the old `min(rounded, cap)`.

- [ ] **Step 4: Say which rounding the statement used**

In `leave/services/balances.py`, replace:

```python
            out.append(("allowance", f"{label} rounded to the half hour{' and capped at the full-year figure' if pr.capped else ''}", pr.seconds))
```

with:

```python
            unit = "whole session" if s.person.is_gp else "half hour"
            out.append(("allowance", f"{label} rounded to the {unit}{' and capped at the full-year figure' if pr.capped else ''}", pr.seconds))
```

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_leave_prorata_gp.py tests/test_leave_prorata.py tests/test_leave_examples.py tests/test_leave_yearend.py tests/test_leave_flags.py tests/test_leave_summary.py tests/test_payroll_report.py -q`
Expected: all pass, with no existing test changed. (No existing test pins a GP's part-year figure: the worked examples in `test_leave_examples.py` that involve a GP cost sessions, they do not pro-rate an allowance.)

- [ ] **Step 6: Commit**

```bash
git add leave/services/prorata.py leave/services/balances.py tests/test_leave_prorata_gp.py
git commit -m "Leave: a GP's part-year allowance is rounded to the whole session"
```

---

### Task 3: The sync reads contracts and owns weekly hours

**Files:**
- Create: `people/services/contracts.py`, `tests/data/people_feed.json`
- Modify: `people/services/hr_sync.py`, `people/services/profiles.py` (`update_hours`, `apply_due_hours_changes`)
- Test: `tests/test_hr_sync_contracts.py`

**Interfaces:**
- Consumes: `Contract`, `make_contract` (Task 1); `audit.record`, `audit.SYNC_NOTE` ("from Practice HR").
- Produces:
  - `people.services.contracts.in_force(contracts, day) -> list`; `weekly_hours_on(contracts, day) -> Decimal | None`; `hours_from_hr(person, today=None) -> bool`: whether the person's hours contracts in force today (on the start date, for a starter) add up to more than 0.
  - `hr_sync.sync(client=None) -> SyncRun` now copies each record's `contracts` and sets weekly hours where `hours_from_hr`. A malformed contract raises `BadRecord("record N in the feed: missing or bad contracts")`.
  - `profiles.update_hours(actor, person, weekly_hours, days_per_week, note="")` ignores `weekly_hours` for a person whose hours are Practice HR's (`hours_from_hr`); `profiles.set_weekly_hours_from_hr(person, weekly_hours) -> list[AuditEntry]`.
  - `tests/data/people_feed.json`: five records, used again in Task 5.

Spec 5.1 and 5.4. The rule for weekly hours is one function, `contracts.hours_from_hr`: they are Practice HR's while the person's hours contracts in force add up to more than 0, and typed exactly as today otherwise. So bank staff on a contract for 0 hours, someone between contracts and someone with no copied contract keep the weekly hours a manager types, and the sync never writes them. The sample file is Practice HR's `tests/data/people_feed.json`, byte for byte: that repository tests that a fixed set of people produces it, this one that the sync reads it. Whoever changes the feed changes the file in both, and the hash in the test here.

- [ ] **Step 1: Add the sample feed**

Create `tests/data/people_feed.json`:

```json
{"people": [
  {"id": 101, "first_name": "Sam", "last_name": "Patel", "name": "Sam Patel", "email": "sam@practice.example",
   "contract_type": "Reception", "unit": "hours",
   "employment": {"start": "2025-06-01", "end": null},
   "positions": [{"title": "Receptionist", "team": "Reception"}],
   "contracts": [
     {"id": 41, "contract_type": "Reception", "unit": "hours", "from": "2025-06-01", "to": "2026-08-31",
      "weekly_amount": "22.50", "full_time_weekly": "37.50",
      "leave": {"base": "22.00", "steps": [{"after_years": 1, "total": "23.00"}, {"after_years": 5, "total": "25.00"}]}},
     {"id": 42, "contract_type": "Reception", "unit": "hours", "from": "2026-09-01", "to": null,
      "weekly_amount": "30.00", "full_time_weekly": "37.50",
      "leave": {"base": "22.00", "steps": [{"after_years": 1, "total": "23.00"}, {"after_years": 5, "total": "25.00"}]}}
   ]},
  {"id": 102, "first_name": "Alex", "last_name": "Morgan", "name": "Alex Morgan", "email": "alex@practice.example",
   "contract_type": "Partner", "unit": "sessions",
   "employment": {"start": "2019-04-01", "end": null},
   "positions": [{"title": "GP Partner", "team": "GPs"}],
   "contracts": [
     {"id": 43, "contract_type": "Partner", "unit": "sessions", "from": "2019-04-01", "to": null,
      "weekly_amount": "6.00", "full_time_weekly": "8.00",
      "leave": {"base": "8.00", "steps": []}}
   ]},
  {"id": 103, "first_name": "Jo", "last_name": "Okafor", "name": "Jo Okafor", "email": "jo@practice.example",
   "contract_type": "Management", "unit": "hours",
   "employment": {"start": "2015-01-05", "end": null},
   "positions": [{"title": "Practice Manager", "team": "Management"}],
   "contracts": [
     {"id": 44, "contract_type": "Management", "unit": "hours", "from": "2015-01-05", "to": null,
      "weekly_amount": "37.50", "full_time_weekly": "37.50",
      "leave": {"base": "27.00", "steps": [{"after_years": 10, "total": "30.00"}]}}
   ]},
  {"id": 104, "first_name": "Riley", "last_name": "Chen", "name": "Riley Chen", "email": "riley@practice.example",
   "contract_type": "GP trainee", "unit": "sessions",
   "employment": {"start": "2026-08-05", "end": null},
   "positions": [{"title": "GP Trainee", "team": "GPs"}],
   "contracts": [
     {"id": 45, "contract_type": "GP trainee", "unit": "sessions", "from": "2026-08-05", "to": null,
      "weekly_amount": "8.00", "full_time_weekly": "8.00",
      "leave": null}
   ]},
  {"id": 105, "first_name": "Casey", "last_name": "Lee", "name": "Casey Lee", "email": "casey@practice.example",
   "contract_type": null, "unit": null,
   "employment": {"start": "2026-10-01", "end": null},
   "positions": [],
   "contracts": []}
]}
```

The file ends with one newline after the last `]}`.

Run: `sha256sum tests/data/people_feed.json`
Expected: `4bf3b639cb705d048a9e9b5aa2c938adcc55ad80d63c563c9f8fccd2d8933940`. Where Practice HR is checked out beside this repository, `cmp tests/data/people_feed.json ../practice-hr/tests/data/people_feed.json` prints nothing.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_hr_sync_contracts.py`:

```python
"""Allowance spec 2026-11-18, sections 5.1 and 5.4: the sync copies each
person's contracts from Practice HR's feed and, for a person with a copied
contract with fixed hours, owns their weekly hours. tests/data/people_feed.json is the same
file, byte for byte, as Practice HR's: that app tests that it produces it,
this one that it reads it."""

import copy
import hashlib
import json
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest

from people.models import AuditEntry, Contract, Person
from people.services import contracts, hr_sync, profiles
from tests.factories import make_allowance, make_contract, make_person

pytestmark = pytest.mark.django_db
SAMPLE = Path(__file__).parent / "data" / "people_feed.json"
SAMPLE_SHA256 = "4bf3b639cb705d048a9e9b5aa2c938adcc55ad80d63c563c9f8fccd2d8933940"


class Feed:
    def __init__(self, people):
        self.records = people

    def people(self):
        return self.records


def _sample():
    return json.loads(SAMPLE.read_text())["people"]


def _person(hr_id):
    return Person.objects.get(hr_employee_id=hr_id)


def test_the_sample_file_is_the_one_practice_hr_produces():
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest() == SAMPLE_SHA256, \
        "tests/data/people_feed.json changed: change it in practice-hr too, then this hash"


def test_the_sync_reads_the_sample_feed():
    run = hr_sync.sync(Feed(_sample()))
    assert run.ok and run.people_seen == 5 and run.message == ""
    sam = _person(101)
    rows = list(sam.contracts.all())
    assert [(c.hr_id, c.type_name, c.unit, c.from_day, c.to_day, c.weekly_amount, c.full_time_weekly, c.leave_base, c.leave_steps) for c in rows] == [
        (41, "Reception", "hours", date(2025, 6, 1), date(2026, 8, 31), D("22.5"), D("37.5"), D("22"), [[1, "23.00"], [5, "25.00"]]),
        (42, "Reception", "hours", date(2026, 9, 1), None, D("30"), D("37.5"), D("22"), [[1, "23.00"], [5, "25.00"]])]
    alex = _person(102).contracts.get()
    assert (alex.unit, alex.weekly_amount, alex.full_time_weekly, alex.leave_base, alex.leave_steps) == ("sessions", D("6"), D("8"), D("8"), [])
    assert _person(103).contracts.get().leave_steps == [[10, "30.00"]]
    riley = _person(104).contracts.get()
    assert (riley.type_name, riley.leave_base, riley.leave_steps) == ("GP trainee", None, [])
    assert not _person(105).contracts.exists()
    assert Contract.objects.count() == 5
    assert not AuditEntry.objects.filter(model="people.contract").exists()       # Practice HR audits the contract


def test_a_second_identical_run_writes_nothing():
    hr_sync.sync(Feed(_sample()))
    ids = list(Contract.objects.values_list("pk", flat=True))
    audited = AuditEntry.objects.count()
    assert hr_sync.sync(Feed(_sample())).ok
    assert list(Contract.objects.values_list("pk", flat=True)) == ids and AuditEntry.objects.count() == audited


def test_a_record_with_no_contracts_key_leaves_the_copy_alone():
    hr_sync.sync(Feed(_sample()))
    older = _sample()
    for record in older:
        del record["contracts"]
    assert hr_sync.sync(Feed(older)).ok
    assert Contract.objects.count() == 5


def test_an_empty_list_empties_the_copy_and_a_changed_one_replaces_it():
    hr_sync.sync(Feed(_sample()))
    feed = _sample()
    feed[0]["contracts"] = []
    feed[1]["contracts"][0]["weekly_amount"] = "7.00"
    feed[2]["contracts"].append({**copy.deepcopy(feed[2]["contracts"][0]), "id": 50, "from": "2027-04-01", "weekly_amount": "30.00"})
    assert hr_sync.sync(Feed(feed)).ok
    assert not _person(101).contracts.exists()
    assert _person(102).contracts.get().weekly_amount == D("7")
    assert [c.hr_id for c in _person(103).contracts.all()] == [44, 50]


def test_a_contract_id_that_moves_to_another_person_moves_here_too():
    hr_sync.sync(Feed(_sample()))
    feed = _sample()
    feed[4]["contracts"] = [feed[0]["contracts"].pop()]          # contract 42 now arrives under Casey, listed after Sam
    feed.reverse()                                               # …and Casey's record comes first
    assert hr_sync.sync(Feed(feed)).ok
    assert [c.hr_id for c in _person(105).contracts.all()] == [42] and [c.hr_id for c in _person(101).contracts.all()] == [41]


@pytest.mark.parametrize("spoil", [
    lambda c: c.pop("from"),
    lambda c: c.update({"from": None}),
    lambda c: c.update({"to": "next year"}),
    lambda c: c.update({"weekly_amount": "lots"}),
    lambda c: c.update({"weekly_amount": 22.5}),
    lambda c: c.update({"weekly_amount": "-1.00"}),
    lambda c: c.update({"full_time_weekly": None}),
    lambda c: c.update({"unit": "days"}),
    lambda c: c.update({"id": "41"}),
    lambda c: c.update({"contract_type": None}),
    lambda c: c.pop("leave"),
    lambda c: c.update({"leave": {"base": "22.00"}}),
    lambda c: c.update({"leave": {"base": "22.00", "steps": [{"after_years": "1", "total": "23.00"}]}}),
    lambda c: c.update({"leave": {"base": "22.00", "steps": [{"after_years": 1}]}}),
])
def test_a_malformed_contract_fails_the_run_and_the_previous_data_stands(spoil):
    hr_sync.sync(Feed(_sample()))
    feed = _sample()
    feed[0]["email"] = "sam.patel@practice.example"
    spoil(feed[2]["contracts"][0])
    run = hr_sync.sync(Feed(feed))
    assert not run.ok and run.message == "record 3 in the feed: missing or bad contracts"
    assert Contract.objects.count() == 5 and _person(101).email == "sam@practice.example"


def test_contracts_that_are_not_a_list_or_repeat_an_id_fail_the_run():
    for bad in (None, {"id": 41}, "none"):
        feed = _sample()
        feed[0]["contracts"] = bad
        assert hr_sync.sync(Feed(feed)).message == "record 1 in the feed: missing or bad contracts"
    feed = _sample()
    feed[0]["contracts"][1]["id"] = 41
    assert hr_sync.sync(Feed(feed)).message == "record 1 in the feed: missing or bad contracts"
    assert Person.objects.count() == 0


def test_a_bank_contract_and_steps_that_do_not_rise_are_copied_as_sent():
    feed = _sample()
    feed[0]["contracts"][1]["weekly_amount"] = "0.00"                                        # bank staff: no fixed hours
    feed[2]["contracts"][0]["leave"]["steps"] = [{"after_years": 10, "total": "20.00"}]      # falls
    assert hr_sync.sync(Feed(feed)).ok
    assert _person(101).contracts.get(hr_id=42).weekly_amount == 0
    assert _person(103).contracts.get().leave_steps == [[10, "20.00"]]


# --- weekly hours are Practice HR's while the hours contracts in force add up to more than 0 (5.4) ---

def test_weekly_hours_are_the_hours_contracts_in_force_today_audited_as_practice_hr():
    hr_sync.sync(Feed(_sample()))                            # the suite's clock: 2 November 2026
    sam = _person(101)
    assert sam.weekly_hours == D("30") and sam.days_per_week is None
    entry = AuditEntry.objects.get(model="people.person", object_id=sam.pk, field="weekly_hours")
    assert (entry.before, entry.after, entry.actor_email, entry.note) == ("", "30.00", "practice-hr", "from Practice HR")
    assert _person(103).weekly_hours == D("37.5")
    assert _person(102).weekly_hours is None and _person(104).weekly_hours is None        # GPs keep none
    assert _person(105).weekly_hours is None                                              # no contract: typed, as today


@pytest.mark.today(date(2026, 8, 31))
def test_weekly_hours_follow_the_contracts_as_the_days_pass(today):
    hr_sync.sync(Feed(_sample()))
    assert _person(101).weekly_hours == D("22.5")
    today(date(2026, 9, 1))
    hr_sync.sync(Feed(_sample()))
    assert _person(101).weekly_hours == D("30")


@pytest.mark.today(date(2026, 7, 1))
def test_a_starters_weekly_hours_are_those_on_their_start_date():
    hr_sync.sync(Feed(_sample()))
    assert _person(104).start_date == date(2026, 8, 5)
    feed = _sample()
    feed[3].update({"unit": "hours", "contract_type": "Reception"})
    feed[3]["contracts"][0].update({"unit": "hours", "contract_type": "Reception", "weekly_amount": "20.00", "full_time_weekly": "37.50"})
    hr_sync.sync(Feed(feed))
    assert _person(104).weekly_hours == D("20")


def test_two_hours_contracts_in_force_are_added_up():
    feed = _sample()
    feed[2]["contracts"].append({**copy.deepcopy(feed[2]["contracts"][0]), "id": 50, "from": "2026-01-01", "weekly_amount": "4.00"})
    hr_sync.sync(Feed(feed))
    assert _person(103).weekly_hours == D("41.5")


def test_a_day_between_contracts_keeps_the_hours_the_person_had():
    feed = _sample()
    del feed[0]["contracts"][1]                              # Sam's only contract ended on 31 August
    hr_sync.sync(Feed(feed))
    sam = _person(101)
    assert sam.weekly_hours is None
    Person.objects.filter(pk=sam.pk).update(weekly_hours=D("22.5"))
    hr_sync.sync(Feed(feed))
    assert _person(101).weekly_hours == D("22.5")


def test_bank_staff_keep_the_weekly_hours_typed_here(all_teams_user):
    feed = _sample()
    feed[0]["contracts"][1]["weekly_amount"] = "0.00"            # Sam's only contract in force is for 0 hours
    hr_sync.sync(Feed(feed))
    sam = _person(101)
    assert sam.weekly_hours is None and not contracts.hours_from_hr(sam)
    assert not AuditEntry.objects.filter(model="people.person", object_id=sam.pk, field="weekly_hours").exists()
    profiles.update_hours(all_teams_user, sam, D("12"), 2)       # typed, exactly as before this release
    hr_sync.sync(Feed(feed))
    sam.refresh_from_db()
    assert (sam.weekly_hours, sam.days_per_week) == (D("12"), 2)
    feed[0]["contracts"].append({**copy.deepcopy(feed[0]["contracts"][1]), "id": 51, "from": "2026-10-01", "weekly_amount": "15.00"})
    hr_sync.sync(Feed(feed))                                     # a fixed contract beside it: 0 + 15 is more than 0
    sam.refresh_from_db()
    assert sam.weekly_hours == D("15") and contracts.hours_from_hr(sam)


def test_in_force_and_weekly_hours_on_a_day():
    sam = make_person(start_date=date(2025, 6, 1))
    old = make_contract(sam, "22.5", to_day=date(2026, 8, 31))
    new = make_contract(sam, "30", from_day=date(2026, 9, 1))
    held = [old, new]
    assert contracts.in_force(held, date(2026, 8, 31)) == [old] and contracts.in_force(held, date(2026, 9, 1)) == [new]
    assert contracts.in_force(held, date(2025, 5, 31)) == []
    assert contracts.weekly_hours_on(held, date(2026, 9, 1)) == D("30") and contracts.weekly_hours_on(held, date(2025, 5, 31)) is None
    doc = make_person(is_gp=True)
    assert contracts.weekly_hours_on([make_contract(doc, 6, 8, unit="sessions")], date(2026, 9, 1)) is None
    assert contracts.hours_from_hr(sam) and not contracts.hours_from_hr(make_person())
    assert contracts.hours_from_hr(sam, date(2025, 5, 31))                # before day one they are read on the start date
    assert not contracts.hours_from_hr(doc)                               # a GP has no weekly hours
    bank = make_person(first_name="Bank")
    make_contract(bank, 0)
    assert contracts.weekly_hours_on(list(bank.contracts.all()), date(2026, 9, 1)) == 0 and not contracts.hours_from_hr(bank)


def test_nothing_else_writes_the_weekly_hours_of_a_person_whose_contract_gives_them(all_teams_user):
    sam = make_person(weekly_hours=D("30"), days_per_week=4)
    make_contract(sam, "30")
    rows = profiles.update_hours(all_teams_user, sam, D("37.5"), 5)
    sam.refresh_from_db()
    assert (sam.weekly_hours, sam.days_per_week) == (D("30"), 5) and [r.field for r in rows] == ["days_per_week"]
    typed = make_person(weekly_hours=D("30"), days_per_week=4)              # no copied contract: typed exactly as before
    profiles.update_hours(all_teams_user, typed, D("37.5"), 5)
    typed.refresh_from_db()
    assert (typed.weekly_hours, typed.days_per_week) == (D("37.5"), 5)


def test_a_due_hours_change_copies_only_days_per_week_for_such_a_person():
    sam = make_person(weekly_hours=D("30"), days_per_week=4)
    make_contract(sam, "30")
    make_allowance(sam, date(2026, 1, 1), 138, 48)
    make_allowance(sam, date(2026, 1, 1), D("172.5"), 60, from_day=date(2026, 7, 1), weekly_hours=D("37.5"), days_per_week=5)
    assert profiles.apply_due_hours_changes() == 1
    sam.refresh_from_db()
    assert (sam.weekly_hours, sam.days_per_week) == (D("30"), 5)
    assert profiles.apply_due_hours_changes() == 0
```

- [ ] **Step 3: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_hr_sync_contracts.py -q`
Expected: an error while collecting, `ImportError: cannot import name 'contracts' from 'people.services'`.

- [ ] **Step 4: The contracts helper**

Create `people/services/contracts.py`:

```python
"""The copies of Practice HR's contracts (people.Contract): which are in
force on a day and what they add up to. The sync writes them; the profile,
the sync's weekly hours and leave's entitlement service read them here."""

from django.utils import timezone

from people.models import Contract


def in_force(contracts, day):
    return [c for c in contracts if c.from_day <= day and (c.to_day is None or c.to_day >= day)]


def weekly_hours_on(contracts, day):
    """The sum of the hours contracts in force on the day, or None when
    there is none (a GP, or a day between contracts)."""
    amounts = [c.weekly_amount for c in in_force(contracts, day) if c.unit == Contract.Unit.HOURS]
    return sum(amounts) if amounts else None


def hours_from_hr(person, today=None):
    """Whether the person's weekly hours are Practice HR's (allowance spec,
    5.4): their hours contracts in force today (on the start date, for a
    starter) add up to more than 0. Everyone else is typed here as before:
    no copied contract, bank staff whose only contract in force is for 0
    hours, someone between contracts, and a GP."""
    today = today or timezone.localdate()
    return bool(weekly_hours_on(list(person.contracts.all()), max(today, person.start_date)))
```

- [ ] **Step 5: Weekly hours are Practice HR's where a contract gives them**

In `people/services/profiles.py`, replace:

```python
from people.services import access, audit
```

with:

```python
from people.services import access, audit, contracts
```

In `people/services/profiles.py`, replace:

```python
                  "show_to_other_staff", "can_see_other_staff")
```

with:

```python
                  "show_to_other_staff", "can_see_other_staff")
TWO_PLACES = Decimal("0.01")
```

In `people/services/profiles.py`, replace:

```python
def update_hours(actor, person, weekly_hours, days_per_week, note=""):
    if person.is_gp:
        raise ValueError("a GP's sessions come from the GP rota")
    weekly_hours = Decimal(weekly_hours).quantize(Decimal("0.01")) if weekly_hours is not None else None
    return _apply(actor, person, {"weekly_hours": weekly_hours, "days_per_week": days_per_week}, note=note)
```

with:

```python
def update_hours(actor, person, weekly_hours, days_per_week, note=""):
    """Weekly hours and days per week, as typed. While the person's hours
    contracts in Practice HR add up to more than 0 their weekly hours are
    HR's (allowance spec, 5.4): only the days per week are written,
    whatever is passed."""
    if person.is_gp:
        raise ValueError("a GP's sessions come from the GP rota")
    if contracts.hours_from_hr(person):
        return _apply(actor, person, {"days_per_week": days_per_week}, note=note)
    weekly_hours = Decimal(weekly_hours).quantize(Decimal("0.01")) if weekly_hours is not None else None
    return _apply(actor, person, {"weekly_hours": weekly_hours, "days_per_week": days_per_week}, note=note)


def set_weekly_hours_from_hr(person, weekly_hours):
    """The sync's write of a person's weekly hours: the sum, more than 0,
    of their hours contracts in force in Practice HR. Nothing else writes
    them for such a person."""
    return _apply(None, person, {"weekly_hours": Decimal(weekly_hours).quantize(TWO_PLACES)}, note=audit.SYNC_NOTE)
```

In `people/services/profiles.py`, replace:

```python
        with transaction.atomic():
            if person.weekly_hours != latest.weekly_hours or person.days_per_week != latest.days_per_week:
                update_hours(None, person, latest.weekly_hours, latest.days_per_week, note="hours change due")
                changed += 1
```

with:

```python
        with transaction.atomic():
            if contracts.hours_from_hr(person, today):       # weekly hours are Practice HR's: only the days are copied
                differs = latest.days_per_week is not None and person.days_per_week != latest.days_per_week
            else:
                differs = person.weekly_hours != latest.weekly_hours or person.days_per_week != latest.days_per_week
            if differs:
                update_hours(None, person, latest.weekly_hours, latest.days_per_week, note="hours change due")
                changed += 1
```

- [ ] **Step 6: The sync copies the contracts**

In `people/services/hr_sync.py`, replace:

```python
never delete. A person absent from the feed keeps their last_seen_from_hr,
which the Health card reads."""

import logging
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from people.models import Person, SyncRun, Team
from people.services import audit, profiles
```

with:

```python
never delete. A person absent from the feed keeps their last_seen_from_hr,
which the Health card reads.

Each record's `contracts` (allowance spec, 5.1) are copied to
people.Contract, replacing the person's rows; a record without the key
leaves the copy alone. A person whose hours contracts in force add up to
more than 0 has their weekly hours from them (5.4)."""

import logging
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from people.models import Contract, Person, SyncRun, Team
from people.services import audit, contracts, profiles
```

In `people/services/hr_sync.py`, add before the line `def _field(record, key, convert=None, *, required=True, position):`:

```python
TWO_PLACES = Decimal("0.01")
CONTRACT_FIELDS = ("hr_id", "type_name", "unit", "from_day", "to_day", "weekly_amount", "full_time_weekly",
                   "leave_base", "leave_steps")


def _amount(value):
    """An amount as Practice HR sends it: a string, "22.50"."""
    if not isinstance(value, str):
        raise ValueError
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ValueError from None
    if not number.is_finite() or not 0 <= number < 1000:
        raise ValueError
    return number.quantize(TWO_PLACES)


def _text(value):
    if not isinstance(value, str) or not value:
        raise ValueError
    return value[:60]


def _contract(raw):
    """One contract of a feed record, as Contract's fields. Anything
    missing or unreadable raises; terms that are readable but cannot be
    worked out (a weekly amount of 0, steps that do not rise) are copied
    as sent, and the entitlement service says so."""
    leave = raw["leave"]
    steps = [] if leave is None else [[_id(step["after_years"]), str(_amount(step["total"]))] for step in leave["steps"]]
    if raw["unit"] not in Contract.Unit.values:
        raise ValueError
    return {"hr_id": _id(raw["id"]), "type_name": _text(raw["contract_type"]), "unit": raw["unit"],
            "from_day": date.fromisoformat(raw["from"]), "to_day": _date(raw["to"]),
            "weekly_amount": _amount(raw["weekly_amount"]), "full_time_weekly": _amount(raw["full_time_weekly"]),
            "leave_base": None if leave is None else _amount(leave["base"]), "leave_steps": steps}


def _contracts(value):
    rows = sorted((_contract(raw) for raw in value), key=lambda c: c["hr_id"])
    if len({c["hr_id"] for c in rows}) != len(rows):
        raise ValueError
    return rows
```

`_contracts` is the converter `_field` runs, so anything it raises (`KeyError`, `TypeError`, `ValueError`) becomes the one message `record N in the feed: missing or bad contracts`, with no value in it.

In `people/services/hr_sync.py`, replace:

```python
        fields["team_name"] = _field(record, "positions", _first_team, position=position)
    return employee_id, fields
```

with:

```python
        fields["team_name"] = _field(record, "positions", _first_team, position=position)
    # None when the key is absent (an older Practice HR): the copy is left alone.
    fields["contracts"] = _field(record, "contracts", _contracts, position=position) if "contracts" in record else None
    return employee_id, fields
```

In `people/services/hr_sync.py`, add before the line `def _team(name, cache):`:

```python
def _copy_contracts(person, rows):
    """Replace the person's copied contracts with the feed's. Unchanged
    rows are left as they are, so a run that brings nothing new writes
    nothing. A contract id held under anyone else goes too: the id is HR's."""
    have = [{name: getattr(c, name) for name in CONTRACT_FIELDS} for c in person.contracts.order_by("hr_id")]
    if have == rows:
        return
    Contract.objects.filter(Q(person=person) | Q(hr_id__in=[c["hr_id"] for c in rows])).delete()
    Contract.objects.bulk_create([Contract(person=person, **c) for c in rows])


def _own_weekly_hours(person, today):
    """Allowance spec, 5.4: a person whose hours contracts in force today
    (on the start date, for a starter) add up to more than 0 has that sum
    as their weekly hours. A GP has none. Bank staff on a 0-hour contract
    and someone between contracts keep the hours typed here."""
    if person.is_gp:
        return
    weekly = contracts.weekly_hours_on(list(person.contracts.all()), max(today, person.start_date))
    if weekly:
        profiles.set_weekly_hours_from_hr(person, weekly)
```

In `people/services/hr_sync.py`, replace everything from the line `def _apply(records, seen_at):` up to, but not including, the line `def sync(client=None):` with:

```python
def _apply(records, seen_at):
    """HR's feed gives today's positions, so a starter whose post begins next
    month has none yet, and nor does someone between posts. A record with no
    position keeps the person's team; a new person with none starts without
    one, for an all-teams manager to see on the Staff list meanwhile."""
    teams = {}
    leaving = []
    today = timezone.localdate()
    for position, record in enumerate(records, start=1):
        employee_id, fields = _parse(record, position)
        team_name = fields.pop("team_name")
        sent = fields.pop("contracts")
        person = Person.objects.filter(hr_employee_id=employee_id).first()
        if team_name is None and person is not None:
            fields["team"] = person.team
        else:
            fields["team"] = _team(team_name, teams)
        if person is None:
            person = Person.objects.create(hr_employee_id=employee_id, last_seen_from_hr=seen_at,
                                           **fields)
            audit.record(None, person, {"created": ("", f"employee {employee_id}")},
                         note=audit.SYNC_NOTE)
        else:
            changes = {}
            for field in HR_FIELDS:
                before, after = getattr(person, field), fields[field]
                if before != after:
                    changes[field] = (before, after)
                    setattr(person, field, after)
            person.last_seen_from_hr = seen_at
            person.save()
            if changes:
                audit.record(None, person, changes,
                             note=audit.SYNC_NOTE)
                if "end_date" in changes:
                    leaving.append(person)
        if sent is not None:
            _copy_contracts(person, sent)
        _own_weekly_hours(person, today)
    return leaving
```

What changed in `_apply`: a new person no longer skips the rest of the loop (the `continue` became an `else`), so every record, new or known, reaches the last two lines.

- [ ] **Step 7: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_hr_sync_contracts.py tests/test_hr_sync.py tests/test_profile.py tests/test_leave_prorata.py tests/test_staff_page.py -q`
Expected: all pass.

Run: `.venv/bin/ruff check people tests`
Expected: nothing reported.

- [ ] **Step 8: Commit**

```bash
git add people/services/contracts.py people/services/hr_sync.py people/services/profiles.py tests/data/people_feed.json tests/test_hr_sync_contracts.py
git commit -m "People: the sync copies each person's contracts and sets the weekly hours they give"
```

---

### Task 4: The arithmetic

**Files:**
- Create: `leave/services/entitlement.py`
- Test: `tests/test_entitlement.py`

**Interfaces:**
- Consumes: `Contract`, `make_contract`, `make_bank_holiday`; `people.services.contracts.in_force`, `weekly_hours_on` (Task 3); `leave.services.hours.fmt`, `from_hours`, `GP_SESSION`; `leave.services.years.year_end`, `years_for`; `leave.services.yearend.LAUNCH`.
- Produces, all in `leave.services.entitlement`:
  - `service_years(start_date, year) -> int`; `entitled(contract, service) -> Decimal`; `sound(contract) -> bool`.
  - `Period(from_day, annual, bank_holiday, weekly_hours, working)`: `annual` and `bank_holiday` are Decimal hours to 4 places, `weekly_hours` a Decimal or None for a GP, `working` a tuple `(annual leave line, bank holiday line)`.
  - `Worked(periods, reason, gaps, changes)` with property `ok`; all four are tuples or a string, empty by default.
  - `periods(contracts, start_date, end_date, year, bank_holidays) -> Worked`. Pure: no query.
  - The reasons: `NOT_EMPLOYED`, `NO_CONTRACT`, `NOT_IN_FORCE`, `MIXED`, `NO_TERMS`, `NO_HOURS`, `BAD_TERMS` (strings).
  - `Data(contracts, holidays, rows)` with `holidays_in(year) -> int`; `load(people) -> Data` (three queries); `worked(person, year, data) -> Worked`; `worked_for(person, year) -> Worked`; `covered(person, today=None) -> list[date]`.

Spec section 6. The table of worked examples and the service example are the tests, figure for figure. Four points to hold on to:

- The year's first `Period` is always dated the leave year's first day, also for someone who starts later in the year, because the year's first `Allowance` row always is (`from_day == leave_year`); pro-rata cuts it to the start date.
- When no contract is in force on that first day (the start date, for a starter) the year is not worked out, `NOT_IN_FORCE`, and the day is a gap.
- A contract with a weekly amount of 0 is bank staff (`NO_HOURS`): not worked out and nobody's mistake. Steps that do not rise (`BAD_TERMS`) are the only terms that put a person on a list (Task 7), and are said first.
- A contract's dates are read within the person's own: Practice HR does not guarantee a contract sits inside its employment, so one that starts before the start date counts from the start date, and service always runs from the person's start date. `test_a_contract_that_starts_before_the_start_date_counts_from_the_start_date` pins it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_entitlement.py`:

```python
"""Allowance spec 2026-11-18, section 6: full-year allowances worked out
from a person's contracts. The table in the spec and its service example
are these tests, figure for figure."""

from datetime import date
from decimal import Decimal as D

import pytest

from leave.services import entitlement, hours
from tests.factories import make_bank_holiday, make_contract, make_person

pytestmark = pytest.mark.django_db
Y27 = date(2027, 1, 1)
RECEPTION = [(1, 23)]                # 22 days; 23 after 1 year


def _year(person, year=Y27, bank_holidays=8):
    return entitlement.periods(list(person.contracts.all()), person.start_date, person.end_date, year, bank_holidays)


def _one(person, **kw):
    result = _year(person, **kw)
    assert result.ok, result.reason
    (period,) = result.periods
    return period


def _fmt(period):
    return hours.fmt(hours.from_hours(period.annual)), hours.fmt(hours.from_hours(period.bank_holiday))


# --- service ------------------------------------------------------------------------------

def test_service_is_complete_years_on_the_first_day_of_the_leave_year():
    start = date(2025, 6, 1)
    assert entitlement.service_years(start, date(2026, 1, 1)) == 0
    assert entitlement.service_years(start, date(2027, 1, 1)) == 1        # 1 complete year on 1 Jan 2027
    assert entitlement.service_years(start, date(2028, 1, 1)) == 2        # 3 years are reached on 1 June 2028…
    assert entitlement.service_years(start, date(2029, 1, 1)) == 3        # …so a 3-year step applies from 1 Jan 2029
    assert entitlement.service_years(date(2027, 3, 1), Y27) == 0          # a year the person starts in has none
    assert entitlement.service_years(date(2026, 1, 1), Y27) == 1          # a year to the day
    assert entitlement.service_years(date(2026, 4, 1), date(2027, 4, 1)) == 1


def test_the_step_in_force_is_the_highest_one_reached():
    sam = make_person(start_date=date(2021, 6, 1))
    make_contract(sam, steps=[(1, 23), (5, 25), (10, 27)])
    (contract,) = sam.contracts.all()
    assert [entitlement.entitled(contract, n) for n in (0, 1, 4, 5, 9, 10, 30)] == [D("22"), D("23"), D("23"), D("25"), D("25"), D("27"), D("27")]


# --- the spec's table, with 8 bank holidays in the year -----------------------------------

def test_full_time_with_one_complete_year():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "37.5", steps=RECEPTION)
    p = _one(sam)
    assert (p.annual, p.bank_holiday, p.weekly_hours) == (D("172.5"), D("60"), D("37.5"))
    assert _fmt(p) == ("172 h 30 min", "60 h")
    assert p.working == ("23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min",
                         "8 bank holidays × 37.5 h ÷ 5 = 60 h")


def test_part_time_under_a_year():
    sam = make_person(start_date=date(2026, 6, 1))
    make_contract(sam, "22.5", steps=RECEPTION)
    p = _one(sam)
    assert _fmt(p) == ("99 h", "36 h")
    assert p.working[0] == "22 days (no complete years on 1 Jan 2027) × 22.5 h ÷ 5 = 99 h"


def test_a_quarter_hour_rounds_up_to_the_half_hour():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "18.75", steps=RECEPTION)
    p = _one(sam)
    assert _fmt(p) == ("86 h 30 min", "30 h")
    assert p.working[0] == "23 days (1 complete year on 1 Jan 2027) × 18.75 h ÷ 5 = 86 h 15 min, rounded to 86 h 30 min"


def test_under_a_quarter_hour_rounds_down():
    sam = make_person(start_date=date(2026, 6, 1))
    make_contract(sam, "18.8", steps=RECEPTION)          # 22 × 18.8 ÷ 5 = 82.72 h; 8 × 18.8 ÷ 5 = 30.08 h
    assert _fmt(_one(sam)) == ("82 h 30 min", "30 h")


def test_a_partner_on_6_sessions():
    doc = make_person(is_gp=True, start_date=date(2019, 4, 1))
    make_contract(doc, 6, 8, unit="sessions", type_name="Partner")
    p = _one(doc)
    assert (p.annual, p.bank_holiday, p.weekly_hours) == (D("200"), D("50"), None)
    assert p.working == ("8 weeks × 6 sessions = 48 sessions = 200 h",
                         "8 bank holidays × 2 sessions × 6 ÷ 8 = 12 sessions = 50 h")


def test_a_salaried_gp_on_8_sessions():
    doc = make_person(is_gp=True, start_date=date(2022, 9, 1))
    make_contract(doc, 8, 6, unit="sessions")
    p = _one(doc)
    assert (p.annual, p.bank_holiday) == (D("200"), D("66.6667"))
    assert _fmt(p) == ("200 h", "66 h 40 min")
    assert hours.from_hours(p.bank_holiday) == 16 * hours.GP_SESSION


def test_a_fractional_number_of_sessions_rounds_to_the_nearest_whole_one():
    doc = make_person(is_gp=True, start_date=date(2022, 9, 1))
    make_contract(doc, 5, 6, unit="sessions")
    p = _one(doc, bank_holidays=9)
    assert _fmt(p) == ("125 h", "45 h 50 min")            # 30 sessions; 11.25 rounded to 11
    assert p.working == ("6 weeks × 5 sessions = 30 sessions = 125 h",
                         "9 bank holidays × 2 sessions × 5 ÷ 8 = 11.25 sessions, rounded to 11 sessions = 45 h 50 min")


def test_half_a_session_rounds_up():
    doc = make_person(is_gp=True, start_date=date(2022, 9, 1))
    make_contract(doc, 2, 6, unit="sessions")              # 9 × 2 × 2 ÷ 8 = 4.5 sessions
    assert hours.from_hours(_one(doc, bank_holidays=9).bank_holiday) == 5 * hours.GP_SESSION


def test_sixty_four_sessions_is_held_exactly():
    doc = make_person(is_gp=True, start_date=date(2019, 4, 1))
    make_contract(doc, 8, 8, unit="sessions", type_name="Partner")
    p = _one(doc)
    assert p.annual == D("266.6667") and hours.from_hours(p.annual) == 960000


def test_no_bank_holidays_entered_gives_none():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "37.5", steps=RECEPTION)
    p = _one(sam, bank_holidays=0)
    assert p.bank_holiday == 0 and p.working[1] == "0 bank holidays × 37.5 h ÷ 5 = 0 min"


# --- several contracts, and changes in the year -----------------------------------------------

def test_two_contracts_in_force_together_are_each_rounded_then_added():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "18.75", steps=RECEPTION)           # 86.25 → 86.5; 30
    make_contract(sam, "7.5", base=20)                     # 30; 12
    p = _one(sam)
    assert (p.annual, p.bank_holiday, p.weekly_hours) == (D("116.5"), D("42"), D("26.25"))
    assert p.working[0] == ("23 days (1 complete year on 1 Jan 2027) × 18.75 h ÷ 5 = 86 h 15 min, rounded to 86 h 30 min; "
                            "20 days × 7.5 h ÷ 5 = 30 h; together 116 h 30 min")


def test_a_new_contract_in_the_year_starts_a_period_on_its_first_day():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(sam, "30", steps=RECEPTION, from_day=date(2027, 6, 1))
    result = _year(sam)
    assert [(p.from_day, p.annual, p.bank_holiday, p.weekly_hours) for p in result.periods] == [
        (Y27, D("103.5"), D("36"), D("22.5")), (date(2027, 6, 1), D("138"), D("48"), D("30"))]
    assert result.changes == (date(2027, 6, 1),) and result.gaps == ()


def test_a_second_contract_ending_starts_a_period_the_day_after():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "22.5", steps=RECEPTION)
    make_contract(sam, "7.5", steps=RECEPTION, to_day=date(2027, 3, 31))
    assert [(p.from_day, p.weekly_hours) for p in _year(sam).periods] == [(Y27, D("30")), (date(2027, 4, 1), D("22.5"))]


def test_a_renewal_on_the_same_terms_starts_no_period():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(sam, "22.5", steps=RECEPTION, from_day=date(2027, 6, 1))
    result = _year(sam)
    assert len(result.periods) == 1 and result.changes == ()


def test_a_starter_in_the_year_is_worked_out_from_the_contract_on_their_start_date():
    sam = make_person(start_date=date(2027, 7, 1))
    make_contract(sam, "30", steps=RECEPTION)
    p = _one(sam)
    assert (p.from_day, p.annual) == (Y27, D("132"))        # the year's first row is dated the year's first day; pro-rata does the rest


def test_a_contract_that_starts_before_the_start_date_counts_from_the_start_date():
    """Practice HR does not guarantee a contract sits inside its employment."""
    sam = make_person(start_date=date(2027, 7, 1))
    make_contract(sam, "22.5", steps=RECEPTION, from_day=date(2027, 3, 1), to_day=date(2027, 8, 31))
    make_contract(sam, "30", steps=RECEPTION, from_day=date(2027, 9, 1))
    result = _year(sam)
    assert [(p.from_day, p.weekly_hours) for p in result.periods] == [(Y27, D("22.5")), (date(2027, 9, 1), D("30"))]
    assert result.gaps == () and result.changes == (date(2027, 9, 1),)    # 1 March is before they start: no period, no change
    early = make_person(first_name="Early", start_date=date(2027, 7, 1))
    make_contract(early, "30", steps=RECEPTION, from_day=date(2026, 11, 1))
    p = _one(early)
    assert (p.from_day, p.annual) == (Y27, D("132"))                      # 22 days: service runs from the start date, not the contract's
    ended = make_person(first_name="Ended", start_date=date(2027, 7, 1))
    make_contract(ended, "30", steps=RECEPTION, from_day=date(2027, 3, 1), to_day=date(2027, 6, 30))      # over before they start
    assert _year(ended).reason == entitlement.NOT_IN_FORCE


def test_changes_after_the_end_date_are_ignored():
    sam = make_person(start_date=date(2025, 6, 1), end_date=date(2027, 5, 31))
    make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    result = _year(sam)
    assert len(result.periods) == 1 and result.gaps == ()


def test_a_day_with_no_contract_starts_no_period_and_is_a_gap():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 6, 30))
    result = _year(sam)
    assert result.ok and len(result.periods) == 1 and result.gaps == (date(2027, 7, 1),)


def test_a_step_reached_in_the_year_waits_for_the_next_leave_year():
    sam = make_person(start_date=date(2026, 6, 1))
    make_contract(sam, "37.5", steps=RECEPTION)
    assert _one(sam).annual == D("165")                      # 22 days all of 2027, though a year is reached on 1 June
    assert _one(sam, year=date(2028, 1, 1)).annual == D("172.5")


# --- not worked out ------------------------------------------------------------------------

def test_each_reason_a_year_is_not_worked_out():
    nobody = make_person(first_name="Nobody")
    assert _year(nobody).reason == entitlement.NO_CONTRACT

    trainee = make_person(first_name="Trainee", is_gp=True)
    make_contract(trainee, 8, None, unit="sessions", type_name="GP trainee")
    assert _year(trainee).reason == entitlement.NO_TERMS

    bank = make_person(first_name="Bank")
    make_contract(bank, 0, steps=RECEPTION)                     # a bank contract: no fixed hours, so nothing to multiply
    assert _year(bank).reason == entitlement.NO_HOURS

    both = make_person(first_name="Both", start_date=date(2025, 6, 1))
    make_contract(both, "22.5", steps=RECEPTION)
    make_contract(both, 0, steps=RECEPTION, from_day=date(2027, 6, 1))        # a bank contract beside a fixed one
    assert _year(both).reason == entitlement.NO_HOURS

    falling = make_person(first_name="Falling")
    make_contract(falling, steps=[(1, 23), (5, 23)])
    assert _year(falling).reason == entitlement.BAD_TERMS

    backwards = make_person(first_name="Backwards")
    make_contract(backwards, 0, steps=[(5, 25), (1, 23)])       # steps that do not rise are said first, whatever else is true
    assert _year(backwards).reason == entitlement.BAD_TERMS

    mixed = make_person(first_name="Mixed", start_date=date(2025, 6, 1))
    make_contract(mixed, "22.5", to_day=date(2027, 5, 31))
    make_contract(mixed, 4, 6, unit="sessions", from_day=date(2027, 6, 1))
    result = _year(mixed)
    assert result.reason == entitlement.MIXED and result.changes == (date(2027, 6, 1),)
    assert _year(mixed, year=date(2028, 1, 1)).ok                 # the next year holds only sessions

    late = make_person(first_name="Late", start_date=date(2025, 6, 1))
    make_contract(late, from_day=date(2027, 2, 1))
    result = _year(late)
    assert result.reason == entitlement.NOT_IN_FORCE and result.gaps == (Y27,)

    gone = make_person(first_name="Gone", start_date=date(2020, 1, 6), end_date=date(2026, 10, 14))
    make_contract(gone)
    assert _year(gone).reason == entitlement.NOT_EMPLOYED


def test_a_year_that_is_not_worked_out_has_no_periods():
    trainee = make_person(is_gp=True)
    make_contract(trainee, 8, None, unit="sessions")
    result = _year(trainee)
    assert not result.ok and result.periods == ()


# --- loading ----------------------------------------------------------------------------------

def test_the_bank_holidays_counted_are_the_rows_in_the_leave_year():
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "37.5", steps=RECEPTION)
    data = entitlement.load([sam])
    assert data.holidays_in(Y27) == 8                      # seeded
    make_bank_holiday(date(2027, 6, 14), "An extra bank holiday")
    data = entitlement.load([sam])
    assert data.holidays_in(Y27) == 9
    assert entitlement.worked(sam, Y27, data).periods[0].bank_holiday == D("67.5")
    assert entitlement.worked_for(sam, Y27).periods[0].bank_holiday == D("67.5")
    assert data.holidays_in(date(2029, 1, 1)) == 0


def test_the_arithmetic_runs_no_queries(django_assert_num_queries):
    people = [make_person(first_name=f"P{n}", start_date=date(2025, 6, 1)) for n in range(5)]
    for p in people:
        make_contract(p, "30", steps=RECEPTION)
    with django_assert_num_queries(3):
        data = entitlement.load(people)
    with django_assert_num_queries(0):
        assert all(entitlement.worked(p, Y27, data).ok for p in people)


@pytest.mark.today(date(2026, 11, 2))
def test_the_years_covered_leave_out_one_that_ended_before_launch():
    sam = make_person()
    assert entitlement.covered(sam) == [Y27]
    assert entitlement.covered(sam, date(2027, 1, 1)) == [Y27, date(2028, 1, 1)]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_entitlement.py -q`
Expected: an error while collecting, `ImportError: cannot import name 'entitlement' from 'leave.services'`.

- [ ] **Step 3: Write the service**

Create `leave/services/entitlement.py`:

```python
"""Full-year allowances worked out from the contracts Practice HR sends
(allowance spec 2026-11-18, sections 6 to 8).

The arithmetic (service_years, periods and what they call) is pure: it is
given a person's copied contracts, their dates, the leave year and the
number of bank holidays in it, and runs no query. load() does the queries
for any number of people at once, so the Health card can work everyone out
for the price of three queries. Every figure here is a FULL-YEAR one;
starters, leavers and changes are pro-rated in prorata.py as before.

refresh() keeps the Allowance rows in step after each read of Practice HR;
review() builds the lists a manager works through. Nothing extra is stored."""

import math
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from leave.models import BankHoliday
from leave.services import hours, years
from leave.services.yearend import LAUNCH
from people.models import Allowance, Contract
from people.services import contracts as held

FOUR_PLACES = Decimal("0.0001")
HALF = Fraction(1, 2)
SESSION_HOURS = Fraction(hours.GP_SESSION, 3600)      # 4 h 10 min

# Why a leave year is not worked out.
NOT_EMPLOYED = "not employed in this leave year"
NO_CONTRACT = "no contract from Practice HR"
NOT_IN_FORCE = "no contract in force on the first day"
MIXED = "hours and sessions contracts in the same leave year"
NO_TERMS = "a contract with no leave terms"
NO_HOURS = "a contract with no fixed weekly amount"       # bank staff: typed, and nobody's mistake
BAD_TERMS = "leave terms that cannot be worked out"       # steps that do not rise: a contract to look at


@dataclass(frozen=True)
class Period:
    """The full-year figures in force from a day of the leave year."""
    from_day: object
    annual: Decimal             # hours, to four places
    bank_holiday: Decimal
    weekly_hours: object        # the hours contracts added up; None for a GP
    working: tuple              # (the annual leave line, the bank holiday line)


@dataclass(frozen=True)
class Worked:
    """A person's leave year from their contracts: its periods, or the
    reason it is not worked out. `gaps` are the days from which no contract
    is in force while the person is still employed; `changes` the days
    after the first on which the weekly amount in force changes."""
    periods: tuple = ()
    reason: str = ""
    gaps: tuple = ()
    changes: tuple = ()

    @property
    def ok(self):
        return not self.reason


# --- the arithmetic -----------------------------------------------------------

def service_years(start_date, year):
    """Complete years from the start date to the leave year's first day: 0
    for a year the person starts in. Fixed for the whole leave year, so a
    step up always starts with a leave year."""
    if start_date >= year:
        return 0
    return year.year - start_date.year - ((year.month, year.day) < (start_date.month, start_date.day))


def _steps(contract):
    return [(int(after), Decimal(total)) for after, total in contract.leave_steps]


def entitled(contract, service):
    """Days (weeks for a GP) a year: the base, or the total of the highest
    step whose years are not more than the service."""
    reached = [total for after, total in _steps(contract) if after <= service]
    return reached[-1] if reached else contract.leave_base


def sound(contract):
    """Whether a contract's terms can be worked out: a base above nothing
    and steps that rise. Practice HR refuses to save terms that cannot, so
    this is a guard (spec 5.1). A contract with no terms is not asked."""
    if contract.leave_base <= 0:
        return False
    if contract.unit == Contract.Unit.SESSIONS and contract.full_time_weekly <= 0:
        return False
    years_before, total_before = 0, contract.leave_base
    for after, total in _steps(contract):
        if after <= years_before or total <= total_before:
            return False
        years_before, total_before = after, total
    return True


def _round(value, step):
    """To the nearest whole `step`, a half rounding up."""
    return math.floor(value / step + HALF) * step


def _n(number):
    """22.00 as "22", 37.50 as "37.5", 11.25 as it is."""
    number = Decimal(number.numerator) / number.denominator if isinstance(number, Fraction) else Decimal(number)
    text = f"{number.normalize():f}"
    return text if "." not in text or len(text.split(".")[1]) <= 2 else f"{number:.2f}"


def _count(number, word):
    return f"{_n(number)} {word}" if number == 1 else f"{_n(number)} {word}s"


def _time(hours_):
    return hours.fmt(round(hours_ * 3600))


def _hours_figure(raw):
    """(hours as a Decimal, how the working ends) for an hours contract:
    the nearest half hour, a quarter hour rounding up."""
    rounded = _round(raw, HALF)
    text = _time(rounded) if rounded == raw else f"{_time(raw)}, rounded to {_time(rounded)}"
    return (Decimal(rounded.numerator) / rounded.denominator).quantize(FOUR_PLACES), text


def _sessions_figure(raw):
    """The same for a sessions contract: the nearest whole session, a half
    rounding up, held as sessions × 4 h 10 min."""
    rounded = _round(raw, 1)
    as_hours = (Decimal(rounded) * 25 / 6).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
    said = _count(rounded, "session") if rounded == raw else f"{_n(raw)} sessions, rounded to {_count(rounded, 'session')}"
    return as_hours, f"{said} = {_time(rounded * SESSION_HOURS)}"


def _figure(contract, service, year, bank_holidays):
    """One contract's two full-year figures, each with its working:
    ((annual hours, text), (bank holiday hours, text))."""
    total, weekly = Fraction(entitled(contract, service)), Fraction(contract.weekly_amount)
    stepped = f" ({'no' if service == 0 else service} complete year{'' if service == 1 else 's'} on {year:%-d %b %Y})" if contract.leave_steps else ""
    holidays = _count(bank_holidays, "bank holiday")
    if contract.unit == Contract.Unit.SESSIONS:
        annual, said = _sessions_figure(total * weekly)
        bank, bank_said = _sessions_figure(Fraction(bank_holidays) * 2 * weekly / Fraction(contract.full_time_weekly))
        return ((annual, f"{_count(total, 'week')}{stepped} × {_count(weekly, 'session')} = {said}"),
                (bank, f"{holidays} × 2 sessions × {_n(weekly)} ÷ {_n(contract.full_time_weekly)} = {bank_said}"))
    annual, said = _hours_figure(total * weekly / 5)
    bank, bank_said = _hours_figure(Fraction(bank_holidays) * weekly / 5)
    return ((annual, f"{_count(total, 'day')}{stepped} × {_n(weekly)} h ÷ 5 = {said}"),
            (bank, f"{holidays} × {_n(weekly)} h ÷ 5 = {bank_said}"))


def _together(figures):
    """Several contracts in force together: each worked out and rounded,
    then added."""
    total = sum(amount for amount, _ in figures)
    if len(figures) == 1:
        return total, figures[0][1]
    return total, "; ".join(text for _, text in figures) + f"; together {hours.fmt(hours.from_hours(total))}"


def periods(contracts, start_date, end_date, year, bank_holidays):
    """The leave year `year` (its first day) as a Worked: one Period from
    the year's first day, worked out from the contracts in force on it (on
    the start date, for someone who starts in the year), then one from each
    later day on which the contracts in force change, up to the end date.
    A period equal to the one before is dropped. A day from which no
    contract is in force starts no period: the earlier figures carry on,
    and the day is a gap. A contract's dates are read within the person's
    own: Practice HR does not promise a contract sits inside its
    employment, so one that starts before the start date counts from the
    start date. No queries: `contracts` are the person's copied contracts
    and `bank_holidays` the number of bank holidays in the year."""
    last = years.year_end(year)
    if end_date is not None and end_date < last:
        last = end_date
    first = max(year, start_date)
    if first > last:
        return Worked(reason=NOT_EMPLOYED)
    if not contracts:
        return Worked(reason=NO_CONTRACT)
    in_year = [c for c in contracts if c.from_day <= last and (c.to_day is None or c.to_day >= first)]
    days = {first} | {c.from_day for c in in_year if c.from_day > first}
    days |= {c.to_day + timedelta(days=1) for c in in_year if c.to_day is not None and c.to_day < last}
    live = {day: held.in_force(in_year, day) for day in sorted(days)}
    gaps = tuple(day for day, on in live.items() if not on)
    changes, amount = [], None
    for day, on in live.items():
        if on:
            now = sum(c.weekly_amount for c in on)
            if amount is not None and now != amount:
                changes.append(day)
            amount = now
    found = {"gaps": gaps, "changes": tuple(changes)}
    if not live[first]:
        return Worked(reason=NOT_IN_FORCE, **found)
    if len({c.unit for c in in_year}) > 1:
        return Worked(reason=MIXED, **found)
    if not all(sound(c) for c in in_year if c.leave_base is not None):
        return Worked(reason=BAD_TERMS, **found)
    if any(c.leave_base is None for c in in_year):
        return Worked(reason=NO_TERMS, **found)
    if any(c.weekly_amount <= 0 for c in in_year):
        return Worked(reason=NO_HOURS, **found)
    service = service_years(start_date, year)
    out = []
    for day, on in live.items():
        if not on:
            continue
        figures = [_figure(c, service, year, bank_holidays) for c in on]
        (annual, annual_text), (bank, bank_text) = _together([f[0] for f in figures]), _together([f[1] for f in figures])
        weekly = held.weekly_hours_on(on, day)
        if out and (out[-1].annual, out[-1].bank_holiday, out[-1].weekly_hours) == (annual, bank, weekly):
            continue
        out.append(Period(year if day == first else day, annual, bank, weekly, (annual_text, bank_text)))
    return Worked(periods=tuple(out), **found)


# --- loading --------------------------------------------------------------------

@dataclass
class Data:
    contracts: dict         # person id -> [Contract], oldest first
    holidays: list          # every bank holiday on the list
    rows: dict              # (person id, leave year) -> [Allowance], oldest first

    def holidays_in(self, year):
        end = years.year_end(year)
        return sum(1 for day in self.holidays if year <= day <= end)


def load(people):
    """Everything the arithmetic needs for these people, in three queries."""
    ids = [p.pk for p in people]
    contracts, rows = {}, {}
    for c in Contract.objects.filter(person__in=ids):
        contracts.setdefault(c.person_id, []).append(c)
    for a in Allowance.objects.filter(person__in=ids).select_related("checked_by__person"):
        rows.setdefault((a.person_id, a.leave_year), []).append(a)
    return Data(contracts, list(BankHoliday.objects.values_list("day", flat=True)), rows)


def worked(person, year, data):
    return periods(data.contracts.get(person.pk, []), person.start_date, person.end_date, year, data.holidays_in(year))


def worked_for(person, year):
    """worked() for one person, doing its own loading."""
    return worked(person, year, load([person]))


def covered(person, today=None):
    """The leave years refresh keeps in step: the person's current one and
    the next, less a year that ended before launch (2026 is never worked out)."""
    return [year for year in years.years_for(person, today) if years.year_end(year) >= LAUNCH]
```

How the rounding is kept exact: every product is a `Fraction` until it is rounded (`_round`), so a quarter hour or half a session is a true tie and goes up. An hours figure is then a whole number of half hours; a sessions figure is `sessions × 25 ÷ 6` hours to four places, which `hours.from_hours` turns back into exactly `sessions × 15000` seconds.

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_entitlement.py -q && .venv/bin/ruff check leave tests`
Expected: all pass; ruff reports nothing.

- [ ] **Step 5: Commit**

```bash
git add leave/services/entitlement.py tests/test_entitlement.py
git commit -m "Leave: full-year allowances worked out from a person's contracts"
```

---

### Task 5: Refresh, run by the sync

**Files:**
- Modify: `leave/services/entitlement.py`, `people/services/profiles.py`, `people/services/contracts.py`, `people/services/hr_sync.py`
- Test: `tests/test_entitlement_refresh.py`

**Interfaces:**
- Consumes: `entitlement.periods`, `load`, `worked`, `covered`, `Period`, the reasons (Task 4); `Allowance.source`, `checked_at`, `checked_by`, `needs_checking`; `LeaveSetting.allowances_need_checking` through `leave.services.settings.get()`; `hours.plain`; `audit.record`, `audit.SYNC_NOTE`.
- Produces:
  - `profiles.write_allowance(actor, row, fields, note="") -> list[AuditEntry]`: set `fields` (a dict of Allowance field names) on a row, save, audit what changed.
  - `profiles.add_allowance(actor, person, leave_year, from_day, annual_hours, bank_holiday_hours, source, note, **fields) -> Allowance`.
  - `profiles.remove_allowance(actor, row, note) -> list[AuditEntry]`: deletes a dated row; `ValueError` for a year's first row.
  - `profiles.checked_text(row) -> str`: `""`, `"by <email>"` or `"automatically"`.
  - `people.services.contracts.any_copied() -> bool`.
  - `entitlement.refresh(today=None) -> Refreshed`, with `Refreshed.written` and `Refreshed.failed` (ints); `entitlement.note(period, prefix="from Practice HR") -> str`; `entitlement.current_and_starting(people, today) -> QuerySet`; `entitlement.Source` (alias of `Allowance.Source`).
  - `hr_sync.sync()` runs `refresh()` after a good read, before `profiles.apply_due_hours_changes()`; a failure adds `allowances failed; see the journal` to `SyncRun.message`.

Spec section 7. Audit fields written for an allowance row: `annual_hours`, `bank_holiday_hours`, `weekly_hours`, `days_per_week`, `source`, `checked` and, for a new dated row, `from_day`. The note is `from Practice HR: <annual working>; <bank holiday working>`.

Two rows of 7.2 to read carefully. A `copied` row whose figures are what the contract now gives becomes `worked_out` and its check is left exactly as it is (still waiting, or still checked by whoever checked it). A `typed` row with the same figures becomes `worked_out` and is checked by the app. And 7.5: nothing is copied forward until Practice HR has sent someone a contract (`contracts.any_copied()`); from then it applies to everyone whose year is not worked out, people with no contract included.

Two choices the spec leaves open, both tested below:

- **A dated row made by refresh is marked `hours_applied`.** Its weekly hours are Practice HR's and its days per week are a copy of those in force, so there is nothing for `apply_due_hours_changes` to copy; left unmarked, it would put a stale copy of the days back over a later edit to the profile.
- **A removed dated row is audited against the person** (`allowance from 1 Jun 2027`), so the line stays in their History after the row has gone.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_entitlement_refresh.py`:

```python
"""Allowance spec 2026-11-18, section 7: refresh keeps the Allowance rows in
step with the contracts after each read of Practice HR. The table in 7.2 is
tested row by row."""

import json
import logging
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from django.utils import timezone

from leave.models import BankHoliday
from leave.services import entitlement
from leave.services import settings as leave_settings
from people.models import Allowance, AuditEntry, Person
from people.services import hr_sync, profiles
from tests.factories import make_allowance, make_bank_holiday, make_contract, make_person

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2026, 11, 2))]
Y26, Y27, Y28 = date(2026, 1, 1), date(2027, 1, 1), date(2028, 1, 1)
JUNE = date(2027, 6, 1)
RECEPTION = [(1, 23)]
SAMPLE = Path(__file__).parent / "data" / "people_feed.json"


def _sam(weekly="37.5", **kw):
    """Full time since June 2025: 23 days in 2027, so 172 h 30 min and 60 h."""
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D(weekly), days_per_week=5, **kw)
    make_contract(sam, weekly, steps=RECEPTION)
    return sam


def _rows(person, year=Y27):
    return list(Allowance.objects.filter(person=person, leave_year=year).order_by("from_day"))


def _figures(person, year=Y27):
    return [(r.from_day, r.annual_hours, r.bank_holiday_hours, r.source, r.checked_at is not None) for r in _rows(person, year)]


def _audit(row):
    return {a.field: (a.before, a.after) for a in AuditEntry.objects.filter(model="people.allowance", object_id=row.pk)}


def _check(row, user):
    """As a manager's Confirm leaves a row."""
    profiles.write_allowance(user, row, {"checked_at": timezone.now(), "checked_by": user}, note="allowance checked")


# --- 7.2, row by row ---------------------------------------------------------------------------

def test_no_row_creates_one_worked_out_and_waiting():
    sam = _sam()
    result = entitlement.refresh()
    assert (result.written, result.failed) == (1, 0)
    assert _figures(sam) == [(Y27, D("172.5"), D("60"), "worked_out", False)]
    (row,) = _rows(sam)
    assert row.needs_checking and row.checked_by is None and row.weekly_hours is None
    assert _audit(row) == {"annual_hours": ("", "172.50"), "bank_holiday_hours": ("", "60.00"), "source": ("", "worked_out")}
    entry = AuditEntry.objects.filter(model="people.allowance", object_id=row.pk).first()
    assert entry.actor is None and entry.actor_email == "practice-hr"
    assert entry.note == ("from Practice HR: 23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min; "
                          "8 bank holidays × 37.5 h ÷ 5 = 60 h")
    assert not Allowance.objects.filter(leave_year=Y26).exists()          # 2026 ended before launch: never worked out


def test_a_worked_out_row_with_the_same_figures_is_left_alone(all_teams_user):
    sam = _sam()
    entitlement.refresh()
    _check(_rows(sam)[0], all_teams_user)
    audited = AuditEntry.objects.count()
    assert entitlement.refresh().written == 0
    (row,) = _rows(sam)
    assert row.checked_by == all_teams_user and AuditEntry.objects.count() == audited


def test_a_worked_out_row_with_different_figures_is_rewritten_and_waits_again(all_teams_user):
    sam = _sam()
    entitlement.refresh()
    _check(_rows(sam)[0], all_teams_user)
    make_bank_holiday(date(2027, 6, 14), "An extra bank holiday")           # nine in the year now
    AuditEntry.objects.all().delete()
    assert entitlement.refresh().written == 1
    (row,) = _rows(sam)
    assert (row.bank_holiday_hours, row.source, row.checked_at, row.checked_by) == (D("67.5"), "worked_out", None, None)
    assert _audit(row) == {"bank_holiday_hours": ("60.00", "67.50"), "checked": (f"by {all_teams_user.email}", "")}


def test_a_copied_row_with_different_figures_becomes_worked_out():
    sam = _sam()
    make_allowance(sam, Y27, 150, 60, source="copied")
    entitlement.refresh()
    assert _figures(sam) == [(Y27, D("172.5"), D("60"), "worked_out", False)]


def test_a_copied_row_with_the_same_figures_becomes_worked_out_and_its_check_is_left_as_it_is(all_teams_user):
    waiting = _sam(first_name="Waiting")
    row = make_allowance(waiting, Y27, D("172.5"), 60, source="copied")
    checked = _sam(first_name="Checked")
    _check(make_allowance(checked, Y27, D("172.5"), 60, source="copied"), all_teams_user)
    AuditEntry.objects.all().delete()
    assert entitlement.refresh().written == 2
    assert _figures(waiting) == [(Y27, D("172.5"), D("60"), "worked_out", False)]         # still "not yet checked"
    assert _audit(row) == {"source": ("copied", "worked_out")}
    (kept,) = _rows(checked)
    assert (kept.source, kept.checked_by) == ("worked_out", all_teams_user) and not kept.needs_checking
    assert entitlement.refresh().written == 0


def test_a_typed_row_with_the_same_figures_follows_the_contract_from_now_on():
    sam = _sam()
    make_allowance(sam, Y27, D("172.50"), D("60.00"))
    assert entitlement.refresh().written == 1
    (row,) = _rows(sam)
    assert (row.source, row.checked_by) == ("worked_out", None) and row.checked_at is not None and not row.needs_checking
    assert _audit(row) == {"source": ("typed", "worked_out"), "checked": ("", "automatically")}


def test_a_typed_row_with_different_figures_is_never_changed():
    sam = _sam()
    make_allowance(sam, Y27, 180, 60)
    assert entitlement.refresh().written == 0
    assert _figures(sam) == [(Y27, D("180"), D("60"), "typed", False)]
    assert not AuditEntry.objects.filter(model="people.allowance").exists()


# --- 7.3: changes during the year ---------------------------------------------------------------

def _part_time_then_30_from_june():
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=3)
    old = make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    new = make_contract(sam, "30", steps=RECEPTION, from_day=JUNE)
    return sam, old, new


def test_a_mid_year_contract_adds_a_dated_row_with_the_hours_and_the_days_then_in_force():
    sam, _, _ = _part_time_then_30_from_june()
    assert entitlement.refresh().written == 2
    assert _figures(sam) == [(Y27, D("103.5"), D("36"), "worked_out", False), (JUNE, D("138"), D("48"), "worked_out", False)]
    dated = _rows(sam)[1]
    assert (dated.weekly_hours, dated.days_per_week, dated.hours_applied) == (D("30"), 3, True)
    assert _audit(dated) == {"annual_hours": ("", "138.00"), "bank_holiday_hours": ("", "48.00"), "weekly_hours": ("", "30.00"),
                             "days_per_week": ("", "3"), "source": ("", "worked_out"), "from_day": ("", "2027-06-01")}


def test_the_days_then_in_force_come_from_the_row_before_when_it_carries_them():
    sam, _, new = _part_time_then_30_from_june()
    new.to_day = date(2027, 8, 31)
    new.save()
    make_contract(sam, "37.5", steps=RECEPTION, from_day=date(2027, 9, 1))
    entitlement.refresh()
    june = _rows(sam)[1]
    june.days_per_week = 4
    june.save()
    Allowance.objects.filter(person=sam, from_day=date(2027, 9, 1)).delete()
    entitlement.refresh()
    assert [r.days_per_week for r in _rows(sam)] == [None, 4, 4]


def test_a_typed_dated_row_on_the_same_day_is_kept_and_a_typed_one_that_matches_is_adopted():
    sam, _, _ = _part_time_then_30_from_june()
    make_allowance(sam, Y27, D("103.5"), 36)
    make_allowance(sam, Y27, 140, 48, from_day=JUNE, weekly_hours=D("30"), days_per_week=4)
    entitlement.refresh()
    assert _figures(sam) == [(Y27, D("103.5"), D("36"), "worked_out", True), (JUNE, D("140"), D("48"), "typed", False)]


def test_a_corrected_contract_date_moves_the_dated_row(all_teams_user):
    sam, old, new = _part_time_then_30_from_june()
    entitlement.refresh()
    old.to_day, new.from_day = date(2027, 6, 30), date(2027, 7, 1)        # Practice HR corrects the date
    old.save()
    new.save()
    AuditEntry.objects.all().delete()
    assert entitlement.refresh().written == 2
    assert [r.from_day for r in _rows(sam)] == [Y27, date(2027, 7, 1)]
    gone = AuditEntry.objects.get(model="people.person", object_id=sam.pk)
    assert (gone.field, gone.before, gone.after) == ("allowance from 1 Jun 2027", "138.00 h and 48.00 h", "")
    assert gone.note == "from Practice HR: the contracts no longer change on this day"


def test_a_typed_dated_row_is_never_deleted():
    sam = _sam()
    make_allowance(sam, Y27, D("172.5"), 60)
    make_allowance(sam, Y27, 138, 48, from_day=JUNE, weekly_hours=D("30"), days_per_week=4)
    entitlement.refresh()
    assert [(r.from_day, r.source) for r in _rows(sam)] == [(Y27, "worked_out"), (JUNE, "typed")]


def test_a_change_to_the_terms_alters_every_period_and_they_wait_again(all_teams_user):
    sam, old, new = _part_time_then_30_from_june()
    entitlement.refresh()
    for row in _rows(sam):
        _check(row, all_teams_user)
    for contract in (old, new):
        contract.leave_base, contract.leave_steps = D("25"), []
        contract.save()
    assert entitlement.refresh().written == 2
    assert _figures(sam) == [(Y27, D("112.5"), D("36"), "worked_out", False), (JUNE, D("150"), D("48"), "worked_out", False)]


# --- 7.6: the setting ----------------------------------------------------------------------------

def test_with_the_setting_off_rows_are_written_already_checked_and_waiting_ones_are_left():
    waiting = _sam(first_name="Waiting")
    entitlement.refresh()
    setting = leave_settings.get()
    setting.allowances_need_checking = False
    setting.save()
    new = _sam(first_name="New")
    make_bank_holiday(date(2027, 6, 14), "An extra bank holiday")           # changes Waiting's row as well
    entitlement.refresh()
    (row,) = _rows(new)
    assert row.checked_at is not None and row.checked_by is None and not row.needs_checking
    assert _audit(row)["checked"] == ("", "automatically")
    (changed,) = _rows(waiting)
    assert changed.bank_holiday_hours == D("67.5") and not changed.needs_checking

    untouched = _sam(first_name="Untouched")
    make_allowance(untouched, Y27, D("172.5"), D("67.5"), source="worked_out")     # waiting since before, and still right
    entitlement.refresh()
    assert _rows(untouched)[0].needs_checking


# --- 7.1 and 7.4: which years ---------------------------------------------------------------------

def test_before_1_january_only_next_year_is_worked_out_and_from_1_january_both(today):
    sam = _sam()
    entitlement.refresh()
    assert not _rows(sam, Y26) and len(_rows(sam, Y27)) == 1 and not _rows(sam, Y28)
    for day in BankHoliday.objects.filter(day__year=2027):
        make_bank_holiday(day.day.replace(year=2028), day.name)
    today(date(2027, 1, 1))
    entitlement.refresh()
    assert _figures(sam, Y27) == [(Y27, D("172.5"), D("60"), "worked_out", False)]
    assert _figures(sam, Y28) == [(Y28, D("172.5"), D("60"), "worked_out", False)]      # next year's exists from the first day of this one


def test_a_step_is_reached_for_the_next_leave_year(today):
    sam = make_person(start_date=date(2026, 6, 1), weekly_hours=D("37.5"), days_per_week=5)
    make_contract(sam, "37.5", steps=RECEPTION)
    today(date(2027, 1, 1))
    entitlement.refresh()
    assert _rows(sam, Y27)[0].annual_hours == D("165") and _rows(sam, Y28)[0].annual_hours == D("172.5")


def test_a_finished_year_is_never_written(today):
    sam, old, new = _part_time_then_30_from_june()
    today(date(2027, 3, 1))
    entitlement.refresh()
    before = _figures(sam, Y27)
    today(date(2028, 1, 1))
    old.to_day, new.from_day = date(2027, 6, 30), date(2027, 7, 1)        # a change dated inside the year that has ended
    old.save()
    new.save()
    entitlement.refresh()
    assert _figures(sam, Y27) == before


def test_a_year_the_person_is_not_employed_in_gets_nothing():
    sam = _sam(end_date=date(2026, 12, 31))
    assert entitlement.refresh().written == 0 and not Allowance.objects.filter(person=sam).exists()


def test_someone_who_has_left_is_not_refreshed():
    sam = _sam(end_date=date(2026, 10, 14))
    assert entitlement.refresh().written == 0 and not Allowance.objects.filter(person=sam).exists()


def test_a_starter_is_worked_out_before_day_one():
    sam = make_person(start_date=date(2027, 3, 1))
    make_contract(sam, "30", steps=RECEPTION)
    entitlement.refresh()
    assert _figures(sam) == [(Y27, D("132"), D("48"), "worked_out", False)]


# --- 7.5: a year that is not worked out -----------------------------------------------------------

def _trainee():
    doc = make_person(first_name="Riley", is_gp=True, start_date=date(2026, 8, 5))
    make_contract(doc, 8, None, unit="sessions", type_name="GP trainee")
    return doc


def test_next_year_is_copied_from_this_years_last_row_and_waits(today):
    doc = _trainee()
    assert entitlement.refresh().written == 0                             # nothing typed yet: nothing to copy
    today(date(2027, 2, 1))
    make_allowance(doc, Y27, 250, D("66.6667"))
    make_allowance(doc, Y27, 200, 50, from_day=date(2027, 8, 4))
    assert entitlement.refresh().written == 1
    assert _figures(doc, Y28) == [(Y28, D("200"), D("50"), "copied", False)]
    (row,) = _rows(doc, Y28)
    assert row.needs_checking
    assert AuditEntry.objects.filter(model="people.allowance", object_id=row.pk).first().note == "from Practice HR: copied from 2027"
    assert entitlement.refresh().written == 0                             # once only
    assert _figures(doc, Y27) == [(Y27, D("250"), D("66.6667"), "typed", False), (date(2027, 8, 4), D("200"), D("50"), "typed", False)]


def test_nothing_is_copied_until_practice_hr_has_sent_someone_a_contract(today):
    today(date(2027, 2, 1))
    plain = make_person(first_name="Plain")
    make_allowance(plain, Y27, 138, 48)
    assert entitlement.refresh().written == 0 and not _rows(plain, Y28)          # exactly as before this release


def test_nothing_is_copied_over_a_year_that_has_rows_or_for_a_leaver(today):
    today(date(2027, 2, 1))
    doc = _trainee()
    make_allowance(doc, Y27, 250, 60)
    make_allowance(doc, Y28, 260, 60)
    plain = make_person(first_name="Plain")                               # no contract in Practice HR yet: copied too (7.5)
    make_allowance(plain, Y27, 138, 48)
    leaver = make_person(first_name="Leaver", end_date=date(2027, 6, 30))
    make_allowance(leaver, Y27, 138, 48)
    entitlement.refresh()
    assert _figures(doc, Y28) == [(Y28, D("260"), D("60"), "typed", False)]
    assert _figures(plain, Y28) == [(Y28, D("138"), D("48"), "copied", False)]
    assert not _rows(leaver, Y28)


def test_bank_staff_are_typed_and_copied_forward_like_anyone_whose_year_is_not_worked_out(today):
    today(date(2027, 2, 1))
    bank = make_person(first_name="Bank", start_date=date(2025, 6, 1))
    make_contract(bank, 0, steps=RECEPTION)                               # a weekly amount of 0
    make_allowance(bank, Y27, 40, 0)
    assert entitlement.refresh().written == 1
    assert _figures(bank, Y27) == [(Y27, D("40"), D("0"), "typed", False)]
    assert _figures(bank, Y28) == [(Y28, D("40"), D("0"), "copied", False)]


def test_a_worked_out_year_is_copied_into_a_next_year_with_no_contract(today):
    today(date(2027, 2, 1))
    sam = make_person(start_date=date(2025, 6, 1))
    make_contract(sam, "37.5", steps=RECEPTION, to_day=date(2027, 12, 31))           # nothing after it
    entitlement.refresh()
    assert _figures(sam, Y28) == [(Y28, D("172.5"), D("60"), "copied", False)]


# --- failures, and the sync -----------------------------------------------------------------------

def test_one_persons_failure_is_logged_by_id_and_the_rest_are_done(monkeypatch, caplog):
    bad, good = _sam(first_name="Bad"), _sam(first_name="Good")
    real = entitlement._refresh_person

    def flaky(person, *args):
        if person.pk == bad.pk:
            Allowance.objects.create(person=person, leave_year=Y27, annual_hours=1, bank_holiday_hours=1)
            raise RuntimeError("boom")
        return real(person, *args)
    monkeypatch.setattr(entitlement, "_refresh_person", flaky)
    with caplog.at_level(logging.INFO, logger="leave.entitlement"):
        result = entitlement.refresh()
    assert (result.written, result.failed) == (1, 1)
    assert not _rows(bad) and len(_rows(good)) == 1                       # the failed person's half-written row is rolled back
    assert f"allowances: person {bad.pk}" in caplog.text
    assert "Bad" not in caplog.text and "172" not in caplog.text


class Feed:
    def people(self):
        return json.loads(SAMPLE.read_text())["people"]


def test_the_sync_works_the_sample_feed_out():
    run = hr_sync.sync(Feed())
    assert run.ok and run.message == ""
    by_id = {p.hr_employee_id: p for p in Person.objects.all()}
    assert _figures(by_id[101]) == [(Y27, D("138"), D("48"), "worked_out", False)]            # 23 days at 30 h
    assert _figures(by_id[102]) == [(Y27, D("200"), D("50"), "worked_out", False)]            # 8 weeks at 6 sessions
    assert _figures(by_id[103]) == [(Y27, D("225"), D("60"), "worked_out", False)]            # 30 days after 10 years
    assert not _rows(by_id[104]) and not _rows(by_id[105])                                    # no terms; no contract
    assert hr_sync.sync(Feed()).ok and Allowance.objects.count() == 3


def test_a_failed_refresh_is_on_the_runs_message_and_the_people_stand(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")
    monkeypatch.setattr(entitlement, "refresh", boom)
    run = hr_sync.sync(Feed())
    run.refresh_from_db()
    assert run.ok and run.message == "allowances failed; see the journal" and Person.objects.count() == 5


def test_one_persons_failure_is_on_the_runs_message_too(monkeypatch):
    monkeypatch.setattr(entitlement, "refresh", lambda today=None: entitlement.Refreshed(written=2, failed=1))
    run = hr_sync.sync(Feed())
    run.refresh_from_db()
    assert run.ok and run.message == "allowances failed; see the journal"


def test_refresh_runs_before_the_due_hours_changes(monkeypatch):
    order = []
    monkeypatch.setattr(entitlement, "refresh", lambda today=None: order.append("allowances") or entitlement.Refreshed(0, 0))
    monkeypatch.setattr(profiles, "apply_due_hours_changes", lambda today=None: order.append("hours"))
    hr_sync.sync(Feed())
    assert order == ["allowances", "hours"]
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_entitlement_refresh.py -q`
Expected: 30 failed, most with `AttributeError: module 'leave.services.entitlement' has no attribute 'refresh'`.

- [ ] **Step 3: The writers of an allowance row**

In `people/services/profiles.py`, replace:

```python
and 6). Each change is audited per field; an allowance that already
exists needs a typed reason to change (LEAVE-31)."""
```

with:

```python
and 6). Each change is audited per field; an allowance that already
exists needs a typed reason to change (LEAVE-31).

Allowance spec 2026-11-18: an allowance row is typed, worked out from the
person's contract or copied from last year's (Allowance.source), and the
last two wait for a manager's check. write_allowance, add_allowance and
remove_allowance are the only writers of a row's figures, source and check:
the manager's actions below use them, and so does leave's entitlement
service when it keeps the figures in step with Practice HR."""
```

In `people/services/profiles.py`, add before the line `NOTES_BEFORE = "(notes)"`:

```python
# --- an allowance row's figures, source and check (allowance spec, 5.2 and 7) ----

def checked_text(row):
    """How a row's check reads in the audit trail."""
    if row.checked_at is None:
        return ""
    return f"by {row.checked_by.email}" if row.checked_by_id else "automatically"


def _audited(row):
    return {"annual_hours": hours.plain(row.annual_hours), "bank_holiday_hours": hours.plain(row.bank_holiday_hours),
            "weekly_hours": None if row.weekly_hours is None else str(Decimal(row.weekly_hours).quantize(TWO_PLACES)),
            "days_per_week": row.days_per_week,
            "source": row.source, "checked": checked_text(row)}


def write_allowance(actor, row, fields, note=""):
    """Set fields on an Allowance row and audit what changed. `actor` None
    is the app, keeping the figures in step with Practice HR."""
    before = _audited(row)
    for name, value in fields.items():
        setattr(row, name, value)
    row.save(update_fields=list(fields))
    after = _audited(row)
    return audit.record(actor, row, {name: (before[name], after[name]) for name in after}, note=note)


def add_allowance(actor, person, leave_year, from_day, annual_hours, bank_holiday_hours, source, note, **fields):
    """A new Allowance row that is not a manager's typing: worked out from
    a contract, or copied from last year's. `fields` are the row's others
    (checked_at, weekly_hours, days_per_week, hours_applied)."""
    row = Allowance.objects.create(person=person, leave_year=leave_year, from_day=from_day, annual_hours=annual_hours,
                                   bank_holiday_hours=bank_holiday_hours, source=source, **fields)
    after = _audited(row)
    after["from_day"] = from_day.isoformat() if from_day != leave_year else ""
    audit.record(actor, row, {name: ("", value) for name, value in after.items()}, note=note)
    return row


def remove_allowance(actor, row, note):
    """Delete a dated row. Audited against the person, so the line stays in
    their History after the row has gone."""
    if row.from_day == row.leave_year:
        raise ValueError("The year's first allowance is changed, not removed")
    gone = f"{hours.plain(row.annual_hours)} h and {hours.plain(row.bank_holiday_hours)} h"
    entries = audit.record(actor, row.person, {f"allowance from {row.from_day:%-d %b %Y}": (gone, "")}, note=note)
    row.delete()
    return entries
```

Add to the end of `people/services/contracts.py`:

```python
def any_copied():
    """Whether Practice HR has sent anyone a contract yet. Until it has,
    nothing is copied forward and nobody is listed for a missing contract."""
    return Contract.objects.exists()
```

- [ ] **Step 4: Refresh**

In `leave/services/entitlement.py`, replace:

```python
import math
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from leave.models import BankHoliday
from leave.services import hours, years
from leave.services.yearend import LAUNCH
from people.models import Allowance, Contract
from people.services import contracts as held

FOUR_PLACES = Decimal("0.0001")
```

with:

```python
import logging
import math
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from django.db import transaction
from django.utils import timezone

from leave.models import BankHoliday
from leave.services import hours, years
from leave.services import settings as leave_settings
from leave.services.yearend import LAUNCH
from people.models import Allowance, Contract, Person
from people.services import audit, profiles
from people.services import contracts as held

log = logging.getLogger("leave.entitlement")

FOUR_PLACES = Decimal("0.0001")
```

In `leave/services/entitlement.py`, replace:

```python
BAD_TERMS = "leave terms that cannot be worked out"       # steps that do not rise: a contract to look at
```

with:

```python
BAD_TERMS = "leave terms that cannot be worked out"       # steps that do not rise: a contract to look at

Source = Allowance.Source
```

`people.services.profiles` imports nothing from `leave.services.entitlement` at module level (Task 6 imports it inside two functions), so this import is not a circle.

Add to the end of `leave/services/entitlement.py`:

```python
# --- refresh (spec section 7) -----------------------------------------------------

def note(period, prefix=audit.SYNC_NOTE):
    """The audit note for a figure written from a period: where it came
    from, then the working."""
    return f"{prefix}: {period.working[0]}; {period.working[1]}"[:300]


def current_and_starting(people, today):
    """Current people and starters, as the Health card counts them."""
    return (people.current(on=today) | people.filter(start_date__gt=today)).distinct()


@dataclass(frozen=True)
class Refreshed:
    written: int
    failed: int


def refresh(today=None):
    """Bring every current person's and starter's allowance rows into step
    with their contracts (spec section 7). Run by hr_sync after each good
    read, inside a transaction of the caller's. One person's failure is
    logged by id and skipped; `failed` counts them."""
    today = today or timezone.localdate()
    people = list(current_and_starting(Person.objects.all(), today))
    data = load(people)
    need_check = leave_settings.get().allowances_need_checking
    copying = held.any_copied()
    written = failed = 0
    for person in people:
        try:
            with transaction.atomic():
                written += _refresh_person(person, today, data, need_check, copying)
        except Exception:
            log.exception("allowances: person %s", person.pk)
            failed += 1
    if written or failed:
        log.info("allowances: %s rows written, %s people skipped", written, failed)
    return Refreshed(written, failed)


def _refresh_person(person, today, data, need_check, copying):
    """`copying` is off until Practice HR has sent anyone a contract: before
    that nothing is worked out and nothing is copied, exactly as it was."""
    this, following = years.years_for(person, today)
    written = 0
    for year in covered(person, today):
        result = worked(person, year, data)
        rows = data.rows.setdefault((person.pk, year), [])
        if result.ok:
            written += _reconcile(person, year, result, rows, need_check)
        elif copying and year == following and not rows and result.reason != NOT_EMPLOYED:
            written += _copy_forward(person, this, following, data, need_check)
    return written


def _days_in_force(person, rows, day):
    """The days per week in force just before `day`: the latest earlier row
    of the year that carries them, else the person's."""
    earlier = [r.days_per_week for r in rows if r.from_day < day and r.days_per_week]
    return earlier[-1] if earlier else person.days_per_week


def _reconcile(person, year, result, rows, need_check):
    """The table in spec 7.2. `rows` is the year's rows, oldest first, kept
    in step with what is written."""
    now = timezone.now()
    checked_at = None if need_check else now
    by_day = {r.from_day: r for r in rows}
    written = 0
    for period in result.periods:
        row = by_day.get(period.from_day)
        dated = period.from_day != year
        if row is None:
            extra = {"weekly_hours": period.weekly_hours, "days_per_week": _days_in_force(person, rows, period.from_day),
                     "hours_applied": True} if dated else {}
            rows.append(profiles.add_allowance(None, person, year, period.from_day, period.annual, period.bank_holiday,
                                               Source.WORKED_OUT, note(period), checked_at=checked_at, **extra))
            rows.sort(key=lambda r: r.from_day)
            written += 1
            continue
        same = (row.annual_hours, row.bank_holiday_hours) == (period.annual, period.bank_holiday)
        if row.source == Source.TYPED:
            if same:        # the manager typed what the contract gives: it follows the contract from now on
                profiles.write_allowance(None, row, {"source": Source.WORKED_OUT, "checked_at": now, "checked_by": None}, note(period))
                written += 1
        elif same:
            if row.source == Source.COPIED:     # last year's figures turned out to be the contract's: its check is left as it is
                profiles.write_allowance(None, row, {"source": Source.WORKED_OUT}, note(period))
                written += 1
        else:
            fields = {"annual_hours": period.annual, "bank_holiday_hours": period.bank_holiday, "source": Source.WORKED_OUT,
                      "checked_at": checked_at, "checked_by": None}
            if dated:
                fields["weekly_hours"] = period.weekly_hours
            profiles.write_allowance(None, row, fields, note(period))
            written += 1
    starts = {period.from_day for period in result.periods}
    for row in [r for r in rows if r.from_day != year and r.source == Source.WORKED_OUT and r.from_day not in starts]:
        profiles.remove_allowance(None, row, f"{audit.SYNC_NOTE}: the contracts no longer change on this day")
        rows.remove(row)
        written += 1
    return written


def _copy_forward(person, this, following, data, need_check):
    """Spec 7.5: a year that is not worked out and has no rows yet starts
    with the full-year figures of this year's last row, to be checked."""
    earlier = data.rows.get((person.pk, this), [])
    if not earlier:
        return 0
    last = earlier[-1]
    row = profiles.add_allowance(None, person, following, following, last.annual_hours, last.bank_holiday_hours, Source.COPIED,
                                 f"{audit.SYNC_NOTE}: copied from {years.label(this)}",
                                 checked_at=None if need_check else timezone.now())
    data.rows[(person.pk, following)].append(row)
    return 1
```

Each person is refreshed inside their own `transaction.atomic()`, a savepoint of the caller's transaction, so one person's failure rolls back only what was half-written for them.

- [ ] **Step 5: Run refresh from the sync**

In `people/services/hr_sync.py`, replace:

```python
leaves the copy alone. A person whose hours contracts in force add up to
more than 0 has their weekly hours from them (5.4)."""
```

with:

```python
leaves the copy alone. A person whose hours contracts in force add up to
more than 0 has their weekly hours from them (5.4). After a good run the
allowances are worked out from the copies
(leave.services.entitlement.refresh)."""
```

In `people/services/hr_sync.py`, replace:

```python
        from leave.services import leavers       # people → leave only here, at call time
```

with:

```python
        from leave.services import entitlement, leavers       # people → leave only here, at call time
```

In `people/services/hr_sync.py`, replace:

```python
            run.save(update_fields=["message"])
        try:
            with transaction.atomic():
                profiles.apply_due_hours_changes()
```

with:

```python
            run.save(update_fields=["message"])
        try:
            with transaction.atomic():      # allowance spec, section 7: before the due hours changes, so today's new rows are seen
                allowances_failed = entitlement.refresh().failed > 0
        except Exception:
            log.exception("allowances failed")
            allowances_failed = True
        if allowances_failed:
            run.message = (run.message + "; " if run.message else "") + "allowances failed; see the journal"
            run.save(update_fields=["message"])
        try:
            with transaction.atomic():
                profiles.apply_due_hours_changes()
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_entitlement_refresh.py tests/test_entitlement.py tests/test_hr_sync_contracts.py tests/test_hr_sync.py tests/test_profile.py tests/test_staff_page.py -q`
Expected: all pass. `tests/test_hr_sync.py` passing untouched is the check that a feed with no contracts changes nothing.

Run: `.venv/bin/ruff check .`
Expected: nothing reported.

- [ ] **Step 7: Commit**

```bash
git add leave/services/entitlement.py people/services/profiles.py people/services/contracts.py people/services/hr_sync.py tests/test_entitlement_refresh.py
git commit -m "Leave: allowances are kept in step with the contracts after each read of Practice HR"
```

---

### Task 6: What a manager does to a row

**Files:**
- Modify: `people/services/profiles.py`
- Test: `tests/test_allowance_actions.py`

**Interfaces:**
- Consumes: `profiles.write_allowance`, `remove_allowance` (Task 5); `entitlement.worked_for(person, year) -> Worked`, `entitlement.note(period, prefix)`, `entitlement.refresh()`; `access.can_manage(user, person)`.
- Produces, all in `people.services.profiles`, all raising `PermissionDenied` unless `access.can_manage(actor, row.person)`:
  - `confirm_allowance(actor, row, days_per_week=None) -> list[AuditEntry]`.
  - `confirm_allowances(actor, items) -> (confirmed: int, skipped: int)`; `items` is a list of `(row_id: int, annual_hours: Decimal, bank_holiday_hours: Decimal, days_per_week: int | None)`.
  - `change_allowance(actor, row, annual_hours, bank_holiday_hours, note, days_per_week=None) -> list[AuditEntry]`; `ValueError` without a reason. Changed figures make the row `typed`; changed days per week alone leave the figures, the source and the check as they are.
  - `takes_days(row) -> bool` (no permission check): a dated row that carries weekly hours, the only kind whose days per week can be corrected.
  - `use_worked_out(actor, row) -> list[AuditEntry]`; `ValueError` when the year is not worked out or has ended.
  - `set_allowance(...)`, unchanged in signature, now makes an existing row `typed` when its figures change, and treats figures equal at two places as no change.
  - `add_hours_change(...)` raises `ValueError("Enter the new contract in Practice HR")` for a year that is worked out.

Spec 7.7 and 7.3. Until this task `set_allowance` could only change the year's first row; `change_allowance` takes any row. Days per week on a dated row can be corrected in two places: beside Confirm, and with Change at any time afterwards. Either way the same helper writes them (`_correct_days`): the row's figures, source and check are not touched, the change is audited with the reason, and the days go onto the person at once if the row's day has come and no later change is in force, or on the day otherwise.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_allowance_actions.py`:

```python
"""Allowance spec 2026-11-18, section 7.7: what a manager does to an
allowance row. Whoever manages the person may; nobody manages themselves."""

from datetime import date
from decimal import Decimal as D

import pytest
from django.core.exceptions import PermissionDenied

from leave.services import entitlement
from people.models import Allowance, AuditEntry
from people.services import profiles
from tests.factories import make_allowance, make_contract, make_person, make_team, make_team_manager, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 2, 1))]
Y27, Y28 = date(2027, 1, 1), date(2028, 1, 1)
JUNE = date(2027, 6, 1)
RECEPTION = [(1, 23)]


@pytest.fixture
def boss(all_teams_user):
    return all_teams_user


def _sam(weekly="37.5", **kw):
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D(weekly), days_per_week=5, **kw)
    make_contract(sam, weekly, steps=RECEPTION)
    return sam


def _worked_out(person, year=Y27, from_day=None):
    entitlement.refresh()
    return Allowance.objects.get(person=person, leave_year=year, from_day=from_day or year)


def _audit(row, note):
    return {a.field: (a.before, a.after) for a in AuditEntry.objects.filter(model="people.allowance", object_id=row.pk, note=note)}


# --- confirm ---------------------------------------------------------------------------------

def test_confirm_sets_who_and_when_and_is_audited(boss):
    row = _worked_out(_sam())
    entries = profiles.confirm_allowance(boss, row)
    row.refresh_from_db()
    assert row.checked_by == boss and row.checked_at is not None and not row.needs_checking and row.source == "worked_out"
    assert [(e.field, e.before, e.after, e.note, e.actor) for e in entries] == [("checked", "", f"by {boss.email}", "allowance checked", boss)]
    assert profiles.confirm_allowance(boss, row) == []                  # already checked: nothing to do


def test_only_someone_who_manages_the_person_confirms_and_never_themselves(boss):
    nursing = make_team("Nursing")
    lead = make_person(first_name="Lead", team=nursing, start_date=date(2025, 6, 1))
    make_contract(lead, "30", steps=RECEPTION)
    make_team_manager(lead, nursing)
    lead_user = make_user_for(lead)
    nurse = _sam(first_name="Nina", team=nursing)
    rec = _sam(first_name="Rec")
    entitlement.refresh()
    rows = {r.person_id: r for r in Allowance.objects.filter(leave_year=Y27)}
    profiles.confirm_allowance(lead_user, rows[nurse.pk])
    for person in (rec, lead):                                          # another team's; her own
        with pytest.raises(PermissionDenied):
            profiles.confirm_allowance(lead_user, rows[person.pk])
    for action in (profiles.use_worked_out, lambda user, row: profiles.change_allowance(user, row, 1, 1, "x")):
        with pytest.raises(PermissionDenied):
            action(lead_user, rows[lead.pk])
    profiles.confirm_allowance(boss, rows[lead.pk])                     # another manager checks hers


def _dated(days=3):
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=days)
    make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(sam, "30", steps=RECEPTION, from_day=JUNE)
    return sam, _worked_out(sam, from_day=JUNE)


def test_days_per_week_corrected_on_a_future_dated_row_wait_for_the_day(boss):
    sam, row = _dated()
    entries = profiles.confirm_allowance(boss, row, days_per_week=4)
    row.refresh_from_db()
    sam.refresh_from_db()
    assert (row.days_per_week, row.hours_applied, sam.days_per_week) == (4, False, 3)
    assert {(e.field, e.before, e.after) for e in entries} == {("checked", "", f"by {boss.email}"), ("days_per_week", "3", "4")}
    assert profiles.apply_due_hours_changes(today=JUNE) == 1            # the sync copies them on the day…
    sam.refresh_from_db()
    assert (sam.days_per_week, sam.weekly_hours) == (4, D("22.5"))      # …and never the weekly hours, which are Practice HR's


def test_days_per_week_corrected_on_a_row_already_in_force_go_on_the_person_now(boss, today):
    sam, row = _dated()
    today(date(2027, 7, 1))
    profiles.confirm_allowance(boss, row, days_per_week=4)
    row.refresh_from_db()
    sam.refresh_from_db()
    assert (row.days_per_week, row.hours_applied, sam.days_per_week) == (4, True, 4)
    assert AuditEntry.objects.filter(model="people.person", object_id=sam.pk, field="days_per_week", note="days per week corrected").exists()


def test_days_are_not_taken_for_a_years_first_row_or_when_unchanged(boss):
    sam, dated = _dated()
    first = Allowance.objects.get(person=sam, leave_year=Y27, from_day=Y27)
    profiles.confirm_allowance(boss, first, days_per_week=4)
    first.refresh_from_db()
    assert first.days_per_week is None
    entries = profiles.confirm_allowance(boss, dated, days_per_week=3)
    assert [e.field for e in entries] == ["checked"]


# --- confirm all shown ----------------------------------------------------------------------

def test_confirm_all_skips_a_row_whose_figures_changed_and_says_how_many(boss):
    a, b, c = _sam(first_name="A"), _sam(first_name="B", weekly="30"), _sam(first_name="C")
    entitlement.refresh()
    rows = {r.person_id: r for r in Allowance.objects.filter(leave_year=Y27)}
    items = [(r.pk, r.annual_hours, r.bank_holiday_hours, None) for r in rows.values()]
    Allowance.objects.filter(pk=rows[b.pk].pk).update(annual_hours=D("150"))       # changed since the page was drawn
    profiles.confirm_allowance(boss, rows[c.pk])                                   # someone else got there first
    assert profiles.confirm_allowances(boss, items + [(999999, D("1"), D("1"), None)]) == (1, 3)
    assert not Allowance.objects.get(pk=rows[a.pk].pk).needs_checking
    assert Allowance.objects.get(pk=rows[b.pk].pk).needs_checking


def test_confirm_all_skips_a_row_the_actor_does_not_manage():
    nursing = make_team("Nursing")
    lead = make_person(first_name="Lead", team=nursing)
    make_team_manager(lead, nursing)
    row = _worked_out(_sam(first_name="Rec"))
    assert profiles.confirm_allowances(make_user_for(lead), [(row.pk, row.annual_hours, row.bank_holiday_hours, None)]) == (0, 1)


# --- change ----------------------------------------------------------------------------------

def test_change_types_both_figures_with_a_reason_and_the_row_becomes_typed(boss):
    row = _worked_out(_sam())
    profiles.confirm_allowance(boss, row)
    with pytest.raises(ValueError, match="reason"):
        profiles.change_allowance(boss, row, D("180"), D("60"), " ")
    entries = profiles.change_allowance(boss, row, D("180"), D("60"), "contract says 24 days")
    row.refresh_from_db()
    assert (row.annual_hours, row.bank_holiday_hours, row.source, row.checked_at, row.checked_by) == (D("180"), D("60"), "typed", None, None)
    assert {(e.field, e.before, e.after) for e in entries} == {
        ("annual_hours", "172.50", "180.00"), ("source", "worked_out", "typed"), ("checked", f"by {boss.email}", "")}
    assert {e.note for e in entries} == {"contract says 24 days"}
    assert entitlement.refresh().written == 0                           # a typed row is kept
    row.refresh_from_db()
    assert row.annual_hours == D("180")


def test_change_works_on_a_dated_row(boss):
    _, row = _dated()
    profiles.change_allowance(boss, row, D("140"), D("48"), "agreed with the practice manager")
    row.refresh_from_db()
    assert (row.annual_hours, row.source, row.from_day) == (D("140"), "typed", JUNE)


def test_days_per_week_change_at_any_time_and_leave_a_worked_out_row_worked_out(boss):
    sam, row = _dated()
    profiles.confirm_allowance(boss, row)                               # checked weeks ago; the days turn out wrong
    with pytest.raises(ValueError, match="reason"):
        profiles.change_allowance(boss, row, row.annual_hours, row.bank_holiday_hours, "", days_per_week=4)
    entries = profiles.change_allowance(boss, row, D("138.00"), D("48.00"), "works four days from June", days_per_week=4)
    row.refresh_from_db()
    assert (row.days_per_week, row.source, row.checked_by, row.annual_hours) == (4, "worked_out", boss, D("138"))
    assert [(e.field, e.before, e.after, e.note) for e in entries] == [("days_per_week", "3", "4", "works four days from June")]
    assert entitlement.refresh().written == 0                           # still what the contract gives
    assert profiles.change_allowance(boss, row, D("138"), D("48"), "again", days_per_week=4) == []


def test_days_per_week_and_figures_changed_together_make_the_row_typed(boss):
    _, row = _dated()
    entries = profiles.change_allowance(boss, row, D("140"), D("48"), "agreed", days_per_week=4)
    row.refresh_from_db()
    assert (row.annual_hours, row.days_per_week, row.source) == (D("140"), 4, "typed")
    assert {e.field for e in entries} == {"annual_hours", "source", "days_per_week"}


def test_days_per_week_are_not_taken_by_change_for_a_years_first_row(boss):
    sam, _ = _dated()
    first = Allowance.objects.get(person=sam, leave_year=Y27, from_day=Y27)
    assert not profiles.takes_days(first)
    assert profiles.change_allowance(boss, first, first.annual_hours, first.bank_holiday_hours, "x", days_per_week=4) == []
    first.refresh_from_db()
    assert first.days_per_week is None


def test_the_same_figures_to_two_places_are_no_change(boss):
    doc = make_person(is_gp=True, start_date=date(2022, 9, 1))
    make_contract(doc, 8, 6, unit="sessions")
    row = _worked_out(doc)                                              # 200 h and 66.6667 h
    assert profiles.change_allowance(boss, row, D("200.00"), D("66.67"), "") == []
    assert profiles.set_allowance(boss, doc, Y27, D("200"), D("66.67"), note="") == []      # the profile's boxes, saved untouched
    row.refresh_from_db()
    assert (row.bank_holiday_hours, row.source) == (D("66.6667"), "worked_out")


def test_the_profiles_boxes_make_a_worked_out_row_typed(boss):
    sam = _sam()
    row = _worked_out(sam)
    profiles.set_allowance(boss, sam, Y27, D("180"), D("60"), note="contract says 24 days")
    row.refresh_from_db()
    assert (row.annual_hours, row.source) == (D("180"), "typed")


# --- use the worked-out figure ------------------------------------------------------------------

def test_use_the_worked_out_figure_on_a_typed_row_that_differs(boss):
    sam = _sam()
    row = make_allowance(sam, Y27, 180, 60)
    entries = profiles.use_worked_out(boss, row)
    row.refresh_from_db()
    assert (row.annual_hours, row.bank_holiday_hours, row.source, row.checked_by) == (D("172.5"), D("60"), "worked_out", boss)
    assert not row.needs_checking
    assert {(e.field, e.before, e.after) for e in entries} == {
        ("annual_hours", "180.00", "172.50"), ("source", "typed", "worked_out"), ("checked", "", f"by {boss.email}")}
    assert entries[0].note == ("worked-out figure used: 23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min; "
                               "8 bank holidays × 37.5 h ÷ 5 = 60 h")


def test_use_the_worked_out_figure_removes_a_typed_dated_row_the_contracts_have_no_change_for(boss):
    sam = _sam()
    make_allowance(sam, Y27, D("172.5"), 60)
    row = make_allowance(sam, Y27, 138, 48, from_day=JUNE, weekly_hours=D("30"), days_per_week=4)
    profiles.use_worked_out(boss, row)
    assert not Allowance.objects.filter(pk=row.pk).exists()
    gone = AuditEntry.objects.get(model="people.person", object_id=sam.pk, field="allowance from 1 Jun 2027")
    assert (gone.before, gone.after, gone.note, gone.actor) == ("138.00 h and 48.00 h", "", "the contracts have no change on this day", boss)


def test_use_the_worked_out_figure_is_refused_where_there_is_none(boss, today):
    typed = make_person(first_name="Typed")
    row = make_allowance(typed, Y27, 138, 48)
    with pytest.raises(ValueError, match="not worked out"):
        profiles.use_worked_out(boss, row)
    sam = _sam()
    old = make_allowance(sam, Y27, 180, 60)
    today(date(2028, 1, 4))
    with pytest.raises(ValueError, match="has ended"):
        profiles.use_worked_out(boss, old)


def test_the_years_first_row_is_never_removed(boss):
    row = make_allowance(_sam(), Y27, 180, 60)
    with pytest.raises(ValueError):
        profiles.remove_allowance(boss, row, "x")


# --- add hours change ---------------------------------------------------------------------------

def test_add_hours_change_is_refused_for_a_year_that_is_worked_out(boss):
    sam = _sam()
    entitlement.refresh()
    with pytest.raises(ValueError) as e:
        profiles.add_hours_change(boss, sam, JUNE, D("30"), 4, 138, 48, "going part time")
    assert str(e.value) == "Enter the new contract in Practice HR"


def test_add_hours_change_still_works_where_allowances_are_typed(boss):
    doc = make_person(is_gp=True, start_date=date(2026, 8, 5))
    make_contract(doc, 8, None, unit="sessions", type_name="GP trainee")           # no terms: typed
    make_allowance(doc, Y27, 250, 60)
    row = profiles.add_hours_change(boss, doc, JUNE, None, 5, 200, 50, "six sessions from June")
    assert (row.source, row.from_day) == ("typed", JUNE)
    plain = make_person(weekly_hours=D("37.5"), days_per_week=5)                   # no copied contract: exactly as before
    make_allowance(plain, Y27, D("172.5"), 60)
    assert profiles.add_hours_change(boss, plain, JUNE, D("30"), 4, 138, 48, "part time").weekly_hours == D("30")
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_allowance_actions.py -q`
Expected: 18 failed, 2 passed, most failures `AttributeError: module 'people.services.profiles' has no attribute 'confirm_allowance'`. (`test_add_hours_change_still_works_where_allowances_are_typed` and `test_the_years_first_row_is_never_removed` already pass.)

- [ ] **Step 3: The actions**

In `people/services/profiles.py`, replace:

```python
TWO_PLACES = Decimal("0.01")
```

with:

```python
TWO_PLACES = Decimal("0.01")
Source = Allowance.Source
```

In `people/services/profiles.py`, replace:

```python
    changes = {}
    for field, after in (("annual_hours", annual_hours), ("bank_holiday_hours", bank_holiday_hours)):
        before = getattr(allowance, field)
        if before != after:
            changes[field] = (hours.plain(before), after)
    if not changes:
        return []
    if not note.strip():
        raise ValueError("A reason is needed to change an allowance that is already set")
    for field, (_, after) in changes.items():
        setattr(allowance, field, after)
    allowance.save(update_fields=list(changes))
    return audit.record(actor, allowance, changes, note=note.strip())
```

with:

```python
    return _change(actor, allowance, annual_hours, bank_holiday_hours, note)
```

In `people/services/profiles.py`, add before the line `NOTES_BEFORE = "(notes)"`:

```python
def _check_manager(actor, person):
    if not access.can_manage(actor, person):
        raise PermissionDenied("you don't manage this person")


def _change(actor, row, annual_hours, bank_holiday_hours, note):
    """A manager's own figures on a row that exists: it becomes typed and
    needs a reason. The boxes hold two decimal places, so figures equal to
    the row's at two places are no change: a worked-out 266.6667 shown as
    266.67 and saved untouched stays worked out."""
    annual_hours = Decimal(annual_hours).quantize(TWO_PLACES)
    bank_holiday_hours = Decimal(bank_holiday_hours).quantize(TWO_PLACES)
    fields = {}
    if Decimal(row.annual_hours).quantize(TWO_PLACES) != annual_hours:
        fields["annual_hours"] = annual_hours
    if Decimal(row.bank_holiday_hours).quantize(TWO_PLACES) != bank_holiday_hours:
        fields["bank_holiday_hours"] = bank_holiday_hours
    if not fields:
        return []
    if not (note or "").strip():
        raise ValueError("A reason is needed to change an allowance that is already set")
    return write_allowance(actor, row, {**fields, "source": Source.TYPED, "checked_at": None, "checked_by": None},
                           note=note.strip())


def change_allowance(actor, row, annual_hours, bank_holiday_hours, note, days_per_week=None):
    """Allowance spec, 7.7 Change: type both figures of any row, the
    year's first or a dated one, with a reason; the row becomes typed. On
    a dated row that carries hours the days per week can be changed too,
    at any time: changing only them leaves the figures, the source and the
    check as they are. Either change needs the reason."""
    _check_manager(actor, row.person)
    new_days = days_per_week is not None and takes_days(row) and days_per_week != row.days_per_week
    with transaction.atomic():
        entries = _change(actor, row, annual_hours, bank_holiday_hours, note)
        if new_days:
            if not (note or "").strip():
                raise ValueError("A reason is needed to change an allowance that is already set")
            entries += _correct_days(actor, row, days_per_week, note.strip())
    return entries


def takes_days(row):
    """Whether a row carries days per week that can be corrected: a dated
    row with weekly hours (costing reads its average day from such a row)."""
    return row.from_day != row.leave_year and row.weekly_hours is not None


def _correct_days(actor, row, days_per_week, note="days per week corrected"):
    """The days per week on a dated row, corrected as it is confirmed or
    with Change. The figures, the source and the check are not touched.
    When the row's day has come the days go on the person now, unless a
    later change is already in force; before it, the sync copies them on
    the day."""
    today = timezone.localdate()
    person = row.person
    due = row.from_day <= today
    superseded = due and Allowance.objects.filter(person=person, weekly_hours__isnull=False,
                                                  from_day__gt=row.from_day, from_day__lte=today).exists()
    entries = write_allowance(actor, row, {"days_per_week": days_per_week, "hours_applied": due}, note=note)
    if due and not superseded and not person.is_gp:
        entries += _apply(actor, person, {"days_per_week": days_per_week}, note=note)
    return entries


def confirm_allowance(actor, row, days_per_week=None):
    """Allowance spec, 7.7 Confirm: the manager has checked a worked-out or
    copied row. A row that is not waiting is left as it is. On a dated row
    that carries hours the days per week can be corrected at the same time."""
    _check_manager(actor, row.person)
    entries = []
    with transaction.atomic():
        if row.needs_checking:
            entries += write_allowance(actor, row, {"checked_at": timezone.now(), "checked_by": actor},
                                       note="allowance checked")
        if days_per_week is not None and takes_days(row) and days_per_week != row.days_per_week:
            entries += _correct_days(actor, row, days_per_week)
    return entries


def confirm_allowances(actor, items):
    """"Confirm all shown". `items` are (row id, annual hours, bank holiday
    hours, days per week or None) as the page drew them. A row that has
    gone, is no longer waiting, is not the actor's to manage, or whose
    figures have changed since the page was drawn is skipped. Returns
    (confirmed, skipped)."""
    rows = {r.pk: r for r in Allowance.objects.filter(pk__in=[item[0] for item in items]).select_related("person__team")}
    confirmed = skipped = 0
    for pk, annual_hours, bank_holiday_hours, days_per_week in items:
        row = rows.get(pk)
        if (row is None or not row.needs_checking or not access.can_manage(actor, row.person)
                or (row.annual_hours, row.bank_holiday_hours) != (annual_hours, bank_holiday_hours)):
            skipped += 1
            continue
        confirm_allowance(actor, row, days_per_week)
        confirmed += 1
    return confirmed, skipped


def use_worked_out(actor, row):
    """Allowance spec, 7.7 Use the worked-out figure, on a typed row that
    differs from what the contracts give: write those figures, worked out
    and checked by this manager. A typed dated row on a day the contracts
    do not change is removed instead."""
    _check_manager(actor, row.person)
    from leave.services import entitlement       # people → leave at call time, as in hr_sync
    if years.year_end(row.leave_year) < timezone.localdate():
        raise ValueError("That leave year has ended; put it right with an adjustment")
    worked = entitlement.worked_for(row.person, row.leave_year)
    if not worked.ok:
        raise ValueError("This leave year is not worked out from a contract")
    period = next((p for p in worked.periods if p.from_day == row.from_day), None)
    with transaction.atomic():
        if period is None:
            return remove_allowance(actor, row, note="the contracts have no change on this day")
        fields = {"annual_hours": period.annual, "bank_holiday_hours": period.bank_holiday, "source": Source.WORKED_OUT,
                  "checked_at": timezone.now(), "checked_by": actor}
        if row.from_day != row.leave_year:
            fields["weekly_hours"] = period.weekly_hours
        return write_allowance(actor, row, fields, note=entitlement.note(period, "worked-out figure used"))
```

In `people/services/profiles.py`, replace:

```python
    if year not in years.correctable(person):
        raise ValueError("An hours change can start in the previous leave year, this one or the next")
```

with:

```python
    if year not in years.correctable(person):
        raise ValueError("An hours change can start in the previous leave year, this one or the next")
    from leave.services import entitlement       # people → leave at call time, as in hr_sync
    if entitlement.worked_for(person, year).ok:
        raise ValueError("Enter the new contract in Practice HR")
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_allowance_actions.py tests/test_entitlement_refresh.py tests/test_profile.py tests/test_leave_prorata.py tests/test_leave_views.py -q`
Expected: all pass. `tests/test_profile.py::test_changing_an_existing_allowance_needs_a_reason` still sees exactly one audit entry, `("annual_hours", "138.00", "140.00", …)`: a typed row that stays typed records nothing about its source.

Run: `.venv/bin/ruff check .`
Expected: nothing reported.

- [ ] **Step 5: Commit**

```bash
git add people/services/profiles.py tests/test_allowance_actions.py
git commit -m "People: confirm an allowance, change it, or take the worked-out figure"
```

---

### Task 7: The four lists

**Files:**
- Modify: `leave/services/entitlement.py`
- Test: `tests/test_allowance_review.py`

**Interfaces:**
- Consumes: `entitlement.load`, `worked`, `covered`, `current_and_starting`, the reasons, `LAUNCH` (Tasks 4 and 5); `contracts.any_copied`, `contracts.in_force`; `profiles.takes_days(row)` (Task 6); `access.managed_people(user)`, `access.can_manage(user, person)`; `profiles.confirm_allowance`, `use_worked_out`, `add_hours_change` (in the tests).
- Produces, all in `leave.services.entitlement`:
  - `state(row) -> str`: "typed", "worked out, not yet checked", "worked out, checked by Lead Patel on 1 Feb 2027", "worked out, checked automatically on 1 Feb 2027", "copied from last year, not yet checked".
  - `Shown(row, state, working, rule, orphan)` with properties `dated`, `takes_days` (`profiles.takes_days(row)`) and `differs`. `working` is `(annual line, bank holiday line)` when the row's figures are what the contracts give; `rule` is the `Period` the contracts give when the row is typed and differs; `orphan` is a typed dated row on a day the contracts do not change.
  - `shown(person, year_list, data=None) -> list[Shown]`.
  - `Item(person, year, text, can_act, shown)`; `Review(to_check, differ, bank_holidays, contracts)`: three lists of `Item` and a list of leave years (dates).
  - `review(user, team=None, today=None) -> Review`; `FINISHED` (the text for a finished year).

Spec section 8. Nothing is stored: the lists are built from the rows and the copied contracts each time. "Bank holidays not entered" and "Contracts to look at in Practice HR" are both empty until Practice HR has sent someone a contract, and the first two can hold nothing before then, so with no copied contract anywhere all four are empty. One person appears at most once on "Contracts to look at in Practice HR", with the first thing wrong: no contract at all, none in force today (on the start date, for a starter), "no contract from 1 July 2027", or steps that do not rise. A contract with no terms (a GP trainee) or with no fixed hours (bank staff) is not something to look at.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_allowance_review.py`:

```python
"""Allowance spec 2026-11-18, section 8: the four lists, built on demand
for the people a manager manages, and their counts on the Health card."""

from datetime import date
from decimal import Decimal as D

import pytest

from leave.models import BankHoliday
from leave.services import entitlement
from people.services import profiles
from tests.factories import make_allowance, make_bank_holiday, make_contract, make_person, make_team, make_team_manager, make_user_for

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 2, 1))]
Y26, Y27, Y28 = date(2026, 1, 1), date(2027, 1, 1), date(2028, 1, 1)
JUNE = date(2027, 6, 1)
RECEPTION = [(1, 23)]


@pytest.fixture(autouse=True)
def bank_holidays_2028(db):
    """2026 and 2027 are seeded; give 2028 its eight too, so only the test
    about a year with none has one."""
    for row in BankHoliday.objects.filter(day__year=2027):
        make_bank_holiday(row.day.replace(year=2028), row.name)


@pytest.fixture
def boss(all_teams_user):
    return all_teams_user


def _sam(weekly="37.5", **kw):
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D(weekly), days_per_week=5, **kw)
    make_contract(sam, weekly, steps=RECEPTION)
    return sam


def _lines(items):
    return [(i.person.first_name, i.year, i.text) for i in items]


def test_with_no_contracts_anywhere_every_list_is_empty(boss):
    plain = make_person(weekly_hours=D("30"), days_per_week=4)
    make_allowance(plain, Y27, 138, 48)
    BankHoliday.objects.filter(day__year=2028).delete()                # a year with none is not news either, yet
    entitlement.refresh()
    r = entitlement.review(boss)
    assert (r.to_check, r.differ, r.bank_holidays, r.contracts) == ([], [], [], [])
    assert not plain.allowances.filter(leave_year=Y28).exists()         # and nothing was copied forward


def test_rows_that_need_checking_are_listed_until_confirmed(boss):
    sam = _sam()
    entitlement.refresh()
    r = entitlement.review(boss)
    assert _lines(r.to_check) == [("Sam", Y27, "worked out, not yet checked"), ("Sam", Y28, "worked out, not yet checked")]
    first = r.to_check[0]
    assert first.can_act and first.shown.row.leave_year == Y27 and not first.shown.dated
    assert first.shown.working == ("23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min", "8 bank holidays × 37.5 h ÷ 5 = 60 h")
    for item in r.to_check:
        profiles.confirm_allowance(boss, item.shown.row)
    assert entitlement.review(boss).to_check == []
    assert sam.allowances.count() == 2


def test_a_copied_row_is_listed_to_check(boss):
    doc = make_person(first_name="Riley", is_gp=True, start_date=date(2026, 8, 5))
    make_contract(doc, 8, None, unit="sessions", type_name="GP trainee")
    make_allowance(doc, Y27, 250, 60)
    entitlement.refresh()
    r = entitlement.review(boss)
    assert _lines(r.to_check) == [("Riley", Y28, "copied from last year, not yet checked")]
    assert r.to_check[0].shown.working is None and r.contracts == []    # a contract with no terms is not one to look at


def test_a_change_of_hours_in_a_typed_year_is_listed_until_the_hours_change_is_added(boss):
    doc = make_person(first_name="Riley", is_gp=True, start_date=date(2026, 8, 5))
    make_contract(doc, 8, None, unit="sessions", type_name="GP trainee", to_day=date(2027, 5, 31))
    make_contract(doc, 6, None, unit="sessions", type_name="GP trainee", from_day=JUNE)
    make_allowance(doc, Y27, 250, 60)
    make_allowance(doc, Y28, 200, 50)
    r = entitlement.review(boss)
    assert _lines(r.to_check) == [("Riley", Y27, "sessions changed on 1 June; add the hours change")]
    assert r.to_check[0].shown is None
    profiles.add_hours_change(boss, doc, JUNE, None, 5, 200, 50, "six sessions from June")
    assert entitlement.review(boss).to_check == []


def test_typed_figures_that_differ_are_listed_with_what_the_contract_gives(boss):
    sam = _sam()
    make_allowance(sam, Y27, 180, 60)
    make_allowance(sam, Y28, D("172.5"), 60)
    entitlement.refresh()
    r = entitlement.review(boss)
    assert _lines(r.differ) == [("Sam", Y27, "typed figures that are not the contract's")]
    item = r.differ[0]
    assert (item.shown.row.annual_hours, item.shown.rule.annual, item.shown.orphan) == (D("180"), D("172.5"), False)
    assert r.to_check == []                                             # the 2028 figures matched, and were adopted as checked
    profiles.use_worked_out(boss, item.shown.row)
    assert entitlement.review(boss).differ == []


def test_a_typed_dated_row_on_a_day_the_contracts_do_not_change_is_listed(boss):
    sam = _sam()
    make_allowance(sam, Y27, D("172.5"), 60)
    make_allowance(sam, Y27, 138, 48, from_day=JUNE, weekly_hours=D("30"), days_per_week=4)
    make_allowance(sam, Y28, D("172.5"), 60)
    entitlement.refresh()
    r = entitlement.review(boss)
    assert _lines(r.differ) == [("Sam", Y27, "the contracts do not change on this day")]
    assert r.differ[0].shown.orphan and r.differ[0].shown.rule is None


def test_a_finished_year_whose_rows_are_not_what_the_contracts_now_give_is_listed(boss, today):
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=3)
    old = make_contract(sam, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    new = make_contract(sam, "30", steps=RECEPTION, from_day=JUNE)
    entitlement.refresh()
    today(date(2028, 1, 10))
    for row in BankHoliday.objects.filter(day__year=2027):
        make_bank_holiday(row.day.replace(year=2029), row.name)
    entitlement.refresh()
    for row in sam.allowances.all():
        profiles.confirm_allowance(boss, row)
    assert entitlement.review(boss).differ == []
    old.to_day, new.from_day = date(2027, 6, 30), date(2027, 7, 1)      # a change dated inside 2027, made in 2028
    old.save()
    new.save()
    entitlement.refresh()
    r = entitlement.review(boss)
    assert _lines(r.differ) == [("Sam", Y27, entitlement.FINISHED)] and r.differ[0].shown is None
    assert [a.from_day for a in sam.allowances.filter(leave_year=Y27)] == [Y27, JUNE]      # the finished year is not rewritten


def test_a_leave_year_with_no_bank_holidays_is_listed(boss):
    _sam()
    BankHoliday.objects.filter(day__year=2028).delete()
    r = entitlement.review(boss)
    assert r.bank_holidays == [Y28]
    entitlement.refresh()
    row = entitlement.review(boss).to_check[1].shown
    assert row.row.bank_holiday_hours == 0 and row.working[1] == "0 bank holidays × 37.5 h ÷ 5 = 0 min"


def test_contracts_to_look_at(boss):
    _sam(first_name="Fine")
    make_person(first_name="None")                                       # nothing from Practice HR
    ended = make_person(first_name="Ended", start_date=date(2025, 6, 1))
    make_contract(ended, "30", steps=RECEPTION, to_day=date(2027, 1, 31))
    gap = make_person(first_name="Gap", start_date=date(2025, 6, 1))
    make_contract(gap, "30", steps=RECEPTION, to_day=date(2027, 6, 30))
    bad = make_person(first_name="Bad")
    make_contract(bad, steps=[(1, 23), (5, 23)])                         # steps that do not rise
    bank = make_person(first_name="Bank")                                # no fixed hours: typed, and not one to look at
    make_contract(bank, 0, steps=RECEPTION)
    starter = make_person(first_name="Starter", start_date=date(2027, 4, 1))
    make_contract(starter, "30", from_day=date(2027, 5, 1))
    left = make_person(first_name="Left", end_date=date(2027, 1, 15))    # not current: not listed
    make_contract(left, "30", to_day=date(2026, 12, 31))
    assert {(i.person.first_name, i.text) for i in entitlement.review(boss).contracts} == {
        ("None", "no contract from Practice HR"), ("Ended", "no contract in force today"), ("Gap", "no contract from 1 July 2027"),
        ("Bad", "leave terms that cannot be worked out"), ("Starter", "no contract in force on the start date")}


def test_a_team_manager_sees_only_their_teams_and_cannot_act_on_their_own():
    nursing = make_team("Nursing")
    lead = make_person(first_name="Lead", team=nursing, start_date=date(2025, 6, 1))
    make_contract(lead, "30", steps=RECEPTION)
    make_team_manager(lead, nursing)
    _sam(first_name="Nina", team=nursing)
    _sam(first_name="Rec")
    entitlement.refresh()
    r = entitlement.review(make_user_for(lead))
    assert {(i.person.first_name, i.can_act) for i in r.to_check} == {("Lead", False), ("Nina", True)}


def test_the_team_box_narrows_the_lists(boss):
    nursing = make_team("Nursing")
    _sam(first_name="Nina", team=nursing)
    _sam(first_name="Rec")
    entitlement.refresh()
    assert {i.person.first_name for i in entitlement.review(boss, team=nursing).to_check} == {"Nina"}


def test_the_review_costs_the_same_queries_however_many_people(boss, django_assert_max_num_queries):
    for n in range(12):
        _sam(first_name=f"P{n}")
    entitlement.refresh()
    with django_assert_max_num_queries(8):
        assert len(entitlement.review(boss).to_check) == 24
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_allowance_review.py -q`
Expected: 12 failed with `AttributeError: module 'leave.services.entitlement' has no attribute 'review'`.

- [ ] **Step 3: The lists**

In `leave/services/entitlement.py`, replace:

```python
from people.services import audit, profiles
```

with:

```python
from people.services import access, audit, profiles
```

Add to the end of `leave/services/entitlement.py`:

```python
# --- what a manager is shown (spec section 8) -------------------------------------

def state(row):
    """How a row's figures came about, as the profile says it."""
    if row.source == Source.TYPED:
        return "typed"
    what = row.get_source_display()
    if row.checked_at is None:
        return f"{what}, not yet checked"
    on = f"{timezone.localtime(row.checked_at):%-d %b %Y}"
    if row.checked_by_id is None:
        return f"{what}, checked automatically on {on}"
    who = getattr(getattr(row.checked_by, "person", None), "name", "") or row.checked_by.email
    return f"{what}, checked by {who} on {on}"


@dataclass
class Shown:
    """One Allowance row beside what the contracts give for its day."""
    row: object
    state: str
    working: object = None      # (annual line, bank holiday line) when the row's figures are the contracts'
    rule: object = None         # the Period the contracts give, when the row is typed and differs from it
    orphan: bool = False        # a typed dated row on a day the contracts do not change

    @property
    def dated(self):
        return self.row.from_day != self.row.leave_year

    @property
    def takes_days(self):
        return profiles.takes_days(self.row)

    @property
    def differs(self):
        return self.rule is not None or self.orphan


def _shown(row, result):
    out = Shown(row, state(row))
    if not result.ok:
        return out
    period = next((p for p in result.periods if p.from_day == row.from_day), None)
    if period is not None and (row.annual_hours, row.bank_holiday_hours) == (period.annual, period.bank_holiday):
        out.working = period.working
    elif row.source == Source.TYPED:
        out.rule, out.orphan = period, period is None and out.dated
    return out


def shown(person, year_list, data=None):
    """The person's rows for these leave years, oldest first, each with its
    state, its working and what the contracts give instead (the profile)."""
    data = data or load([person])
    return [_shown(row, worked(person, year, data)) for year in year_list for row in data.rows.get((person.pk, year), [])]


@dataclass
class Item:
    """One line of a review list."""
    person: object
    year: object
    text: str
    can_act: bool = False       # the viewer manages this person (nobody acts on their own)
    shown: object = None        # the row, where the line is about one


@dataclass
class Review:
    to_check: list
    differ: list
    bank_holidays: list         # leave years refresh covers with no bank holiday on the list
    contracts: list


FINISHED = "the contracts now give different figures for this year, which has ended; put it right with an adjustment"


def review(user, team=None, today=None):
    """The four lists of spec section 8, for the people the user manages
    (current people and starters), optionally one team's. Built on demand
    from the rows and the copied contracts; nothing is stored."""
    today = today or timezone.localdate()
    people = current_and_starting(access.managed_people(user), today)
    if team is not None:
        people = people.filter(team=team)
    people = list(people.select_related("team").order_by("name"))
    data = load(people)
    listing_contracts = held.any_copied()       # the last two lists stay empty until Practice HR has sent a contract
    out, empty = Review([], [], [], []), set()
    for person in people:
        can_act = access.can_manage(user, person)
        look = ""
        for year in covered(person, today):
            result = worked(person, year, data)
            rows = data.rows.get((person.pk, year), [])
            if data.holidays_in(year) == 0:
                empty.add(year)
            for one in (_shown(row, result) for row in rows):
                if one.row.needs_checking:
                    out.to_check.append(Item(person, year, one.state, can_act, one))
                elif one.differs:
                    text = "the contracts do not change on this day" if one.orphan else "typed figures that are not the contract's"
                    out.differ.append(Item(person, year, text, can_act, one))
            if not result.ok and rows:
                have = {r.from_day for r in rows}
                what = "sessions" if person.is_gp else "hours"
                out.to_check += [Item(person, year, f"{what} changed on {day:%-d %B}; add the hours change", can_act)
                                 for day in result.changes if day not in have]
            if not look and result.reason == BAD_TERMS:
                look = BAD_TERMS
            if not look and result.gaps:
                look = f"no contract from {result.gaps[0]:%-d %B %Y}"
        previous = years.previous_year(years.year_of(person, today))
        if years.year_end(previous) >= LAUNCH:
            result, rows = worked(person, previous, data), data.rows.get((person.pk, previous), [])
            out.to_check += [Item(person, previous, state(row), can_act, Shown(row, state(row))) for row in rows if row.needs_checking]
            if result.ok and rows and ({(r.from_day, r.annual_hours, r.bank_holiday_hours) for r in rows}
                                       != {(p.from_day, p.annual, p.bank_holiday) for p in result.periods}):
                out.differ.append(Item(person, previous, FINISHED, can_act))
        if listing_contracts:
            mine = data.contracts.get(person.pk, [])
            if not mine:
                look = NO_CONTRACT
            elif not held.in_force(mine, max(today, person.start_date)):
                look = "no contract in force today" if person.start_date <= today else "no contract in force on the start date"
            if look:
                out.contracts.append(Item(person, None, look))
    out.bank_holidays = sorted(empty) if listing_contracts else []
    return out
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_allowance_review.py tests/test_entitlement.py tests/test_entitlement_refresh.py -q && .venv/bin/ruff check .`
Expected: all pass; ruff reports nothing.

- [ ] **Step 5: Commit**

```bash
git add leave/services/entitlement.py tests/test_allowance_review.py
git commit -m "Leave: the lists of allowances to check, figures that differ and contracts to look at"
```

---

### Task 8: The Allowances page and the Health card's lines

**Files:**
- Create: `people/views/allowances.py`, `templates/people/allowances.html`, `templates/people/_allowance_confirm_fields.html`, `templates/people/allowance_change_dialog.html`
- Modify: `people/urls.py`, `people/views/__init__.py`, `people/forms.py`, `leave/templatetags/leave_extras.py`, `people/services/health.py`, `templates/people/_health.html`, `ui/context_processors.py`
- Test: `tests/test_allowances_page.py`

**Interfaces:**
- Consumes: `entitlement.review(user, team)`, `entitlement.state(row)`, `Item`, `Shown` (Task 7); `profiles.confirm_allowances`, `use_worked_out`, `change_allowance(actor, row, annual_hours, bank_holiday_hours, note, days_per_week=None)`, `takes_days(row)` (Task 6); `access.manager_required`, `access.managed_teams`, `access.can_manage`; `filters.chosen(request, choices, "team")`, `filters.query(team=team)`; `templates/ui/_team_filter.html` (needs `team_choices` and `team`); `templates/ui/_field.html`; the `plain_hours` filter (Task 1).
- Produces:
  - URLs: `allowances` (`/staff/allowances/`), `allowances-confirm` (`/staff/allowances/confirm/`, POST), `allowance-use` (`/staff/allowances/<pk>/use/`, POST), `allowance-change` (`/staff/allowances/<pk>/change/`, a pop-up).
  - The confirm post: one `row` field per row with `annual_<id>` and `bank_holiday_<id>` (the figures as drawn, from `plain_hours`) and optionally `days_<id>`.
  - `people.forms.AllowanceChangeForm(..., with_days=False)`: `annual_hours`, `bank_holiday_hours`, `note`, and `days_per_week` (optional) only when `with_days`.
  - Template filter `hours_hm` (Decimal hours to "172 h 30 min").
  - `health.figures(user)["allowances"]`, a `Review`.
  - Anchors on the page: `#to-check`, `#differ`, `#bank-holidays`, `#contracts`.

Spec section 8. The page's buttons are ordinary forms that post and redirect back, as the Bank holidays and Blackouts pages do; only Change… is a pop-up. On a dated row that carries hours the pop-up also offers the days per week, whether or not the row has been confirmed. The forms post to `…?team=<id>` so that the Team box survives the redirect. The Health lines come in this task because each links to the page.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_allowances_page.py`:

```python
"""Allowance spec 2026-11-18, section 8: the page at /staff/allowances/."""

import re
from datetime import date
from decimal import Decimal as D

import pytest

from leave.models import BankHoliday
from leave.services import entitlement
from people.models import Allowance
from people.services import health
from tests.factories import (client_for, make_allowance, make_bank_holiday, make_contract, make_person, make_team,
                             make_team_manager)

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 2, 1))]
Y27, Y28 = date(2027, 1, 1), date(2028, 1, 1)
JUNE = date(2027, 6, 1)
RECEPTION = [(1, 23)]
URL = "/staff/allowances/"


@pytest.fixture(autouse=True)
def bank_holidays_2028(db):
    for row in BankHoliday.objects.filter(day__year=2027):
        make_bank_holiday(row.day.replace(year=2028), row.name)


def _sam(weekly="37.5", **kw):
    sam = make_person(start_date=date(2025, 6, 1), weekly_hours=D(weekly), days_per_week=5, **kw)
    make_contract(sam, weekly, steps=RECEPTION)
    return sam


@pytest.fixture
def world(db):
    """Boss manages everyone; Lead manages Nursing (Nina, and herself for
    the list but not for the buttons); Rec is in Reception."""
    nursing = make_team("Nursing")
    boss = _sam(first_name="Boss", team=make_team("Management"))
    lead = _sam(first_name="Lead", team=nursing, weekly="30")
    make_team_manager(lead, nursing)
    nina, rec = _sam(first_name="Nina", team=nursing), _sam(first_name="Rec")
    entitlement.refresh()
    return {"boss": boss, "lead": lead, "nina": nina, "rec": rec, "nursing": nursing,
            "c_boss": client_for(boss, is_all_teams_manager=True), "c_lead": client_for(lead), "c_rec": client_for(rec)}


def _row(person, year=Y27, from_day=None):
    return Allowance.objects.get(person=person, leave_year=year, from_day=from_day or year)


def _post(row, **extra):
    return {"row": row.pk, f"annual_{row.pk}": str(row.annual_hours), f"bank_holiday_{row.pk}": str(row.bank_holiday_hours), **extra}


def test_the_page_is_for_managers(world):
    assert world["c_rec"].get(URL).status_code == 403
    assert world["c_rec"].post(URL + "confirm/", _post(_row(world["nina"]))).status_code == 403
    assert _row(world["nina"]).needs_checking
    assert world["c_lead"].get(URL).status_code == 200
    from django.test import Client
    assert Client().get(URL).status_code == 302


def test_the_page_lists_each_row_with_its_figures_working_and_buttons(world):
    body = world["c_boss"].get(URL).content.decode()
    assert "<h2 id=\"to-check\">Allowances to check</h2>" in body and "Contracts to look at in Practice HR" in body
    row = _row(world["nina"])
    assert "Nina Patel" in body and "172 h 30 min" in body and "worked out, not yet checked" in body
    assert "23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min" in body
    assert f'name="row" value="{row.pk}"' in body and f'name="annual_{row.pk}" value="172.50"' in body
    assert f'href="/staff/allowances/{row.pk}/change/"' in body
    assert "Confirm all shown (6)" in body                              # Lead, Nina and Rec, two years each; never Boss's own
    own = _row(world["boss"])
    assert "Boss Patel" in body and f'name="row" value="{own.pk}"' not in body
    assert "<script" not in body.split("<main")[1] and "onclick" not in body


def test_a_team_manager_sees_only_their_team_and_no_buttons_on_their_own_rows(world):
    body = world["c_lead"].get(URL).content.decode()
    assert "Nina Patel" in body and "Lead Patel" in body and "Rec Patel" not in body
    assert f'name="row" value="{_row(world["nina"]).pk}"' in body
    assert f'name="row" value="{_row(world["lead"]).pk}"' not in body
    assert "Confirm all shown (2)" in body


def test_confirm_one_row(world):
    row = _row(world["nina"])
    r = world["c_lead"].post(URL + "confirm/", _post(row), follow=True)
    assert r.redirect_chain == [(URL, 302)] and "1 allowance confirmed." in r.content.decode()
    row.refresh_from_db()
    assert not row.needs_checking and row.checked_by == world["lead"].user


def test_nobody_confirms_their_own_or_another_teams(world):
    for person in (world["lead"], world["rec"]):
        r = world["c_lead"].post(URL + "confirm/", _post(_row(person)), follow=True)
        assert "1 skipped" in r.content.decode() and _row(person).needs_checking


def test_confirm_all_shown_skips_a_row_that_changed_after_the_page_was_drawn(world):
    body = world["c_boss"].get(URL).content.decode()
    form = body.split("Confirm all shown")[0].rsplit("<form", 1)[1]
    data = dict(re.findall(r'name="((?:annual|bank_holiday)_\d+)" value="([^"]+)"', form))
    data["row"] = re.findall(r'name="row" value="(\d+)"', form)
    assert len(data["row"]) == 6
    Allowance.objects.filter(pk=_row(world["rec"]).pk).update(annual_hours=D("150"))       # a contract changed meanwhile
    r = world["c_boss"].post(URL + "confirm/", data, follow=True)
    body = r.content.decode()
    assert "5 allowances confirmed." in body and "1 skipped: its figures changed after this page was drawn." in body
    assert _row(world["rec"]).needs_checking and not _row(world["nina"]).needs_checking
    assert "Confirm all shown (1)" in body


def test_confirm_all_as_filtered_keeps_the_team_box(world):
    nursing = world["nursing"]
    body = world["c_boss"].get(f"{URL}?team={nursing.pk}").content.decode()
    assert "Confirm all shown (4)" in body and "Rec Patel" not in body
    assert f'action="/staff/allowances/confirm/?team={nursing.pk}"' in body
    r = world["c_boss"].post(f"{URL}confirm/?team={nursing.pk}", _post(_row(world["nina"])))
    assert r.status_code == 302 and r["Location"] == f"{URL}?team={nursing.pk}"


def test_days_per_week_can_be_corrected_as_a_dated_row_is_confirmed(world):
    part = make_person(first_name="Part", start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=3)
    make_contract(part, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(part, "30", steps=RECEPTION, from_day=JUNE)
    entitlement.refresh()
    row = _row(part, from_day=JUNE)
    body = world["c_boss"].get(URL).content.decode()
    assert f'name="days_{row.pk}" min="1" max="7" value="3"' in body
    assert f'name="days_{_row(part).pk}"' not in body                    # not on the year's first row
    world["c_boss"].post(URL + "confirm/", _post(row, **{f"days_{row.pk}": "4"}))
    row.refresh_from_db()
    assert (row.days_per_week, row.needs_checking) == (4, False)


def test_a_bad_post_confirms_nothing(world):
    row = _row(world["nina"])
    for data in ({"row": "x"}, {"row": row.pk}, _post(row, **{f"annual_{row.pk}": "lots"}), _post(row, **{f"days_{row.pk}": "9"})):
        assert world["c_boss"].post(URL + "confirm/", data).status_code == 302
    assert _row(world["nina"]).needs_checking
    assert world["c_boss"].get(URL + "confirm/").status_code == 405


def test_use_the_worked_out_figure_from_the_second_list(world):
    typed = _sam(first_name="Typed")
    row = make_allowance(typed, Y27, 180, 60)
    make_allowance(typed, Y28, D("172.5"), 60)
    body = world["c_boss"].get(URL).content.decode()
    differ = body.split('id="differ"')[1].split('id="bank-holidays"')[0]
    assert "Typed Patel" in differ and "180 h and 60 h" in differ and "172 h 30 min and 60 h" in differ
    assert f'action="/staff/allowances/{row.pk}/use/"' in differ and "Use the worked-out figure" in differ
    assert world["c_rec"].post(f"{URL}{row.pk}/use/").status_code == 403
    assert world["c_lead"].post(f"{URL}{row.pk}/use/").status_code == 403        # another team's
    r = world["c_boss"].post(f"{URL}{row.pk}/use/", follow=True)
    assert "Typed Patel: the worked-out figure is in use." in r.content.decode()
    row.refresh_from_db()
    assert (row.annual_hours, row.source) == (D("172.5"), "worked_out")


def test_remove_a_typed_change_the_contracts_do_not_have(world):
    sam = world["rec"]
    row = make_allowance(sam, Y27, 138, 48, from_day=JUNE, weekly_hours=D("30"), days_per_week=4)
    body = world["c_boss"].get(URL).content.decode()
    assert "Remove this change" in body and "the contracts do not change on this day" in body
    r = world["c_boss"].post(f"{URL}{row.pk}/use/", follow=True)
    assert "Rec Patel: the change is removed." in r.content.decode() and not Allowance.objects.filter(pk=row.pk).exists()


def test_a_refusal_is_shown_on_the_page(world):
    plain = make_person(first_name="Plain")
    row = make_allowance(plain, Y27, 138, 48)
    r = world["c_boss"].post(f"{URL}{row.pk}/use/", follow=True)
    assert "This leave year is not worked out from a contract" in r.content.decode()


def test_the_change_dialog_types_both_figures_with_a_reason(world):
    row = _row(world["nina"])
    url = f"{URL}{row.pk}/change/"
    body = world["c_lead"].get(url).content.decode()
    assert 'name="annual_hours" value="172.50"' in body and "worked out, not yet checked" in body and "data-dialog-form" in body
    r = world["c_lead"].post(url, {"annual_hours": "180", "bank_holiday_hours": "60", "note": ""})
    assert r.status_code == 200 and "field-error" in r.content.decode()
    r = world["c_lead"].post(url, {"annual_hours": "180", "bank_holiday_hours": "60", "note": "contract says 24 days"})
    assert r.json() == {"refresh": True}
    row.refresh_from_db()
    assert (row.annual_hours, row.source) == (D("180"), "typed")
    assert world["c_lead"].get(f"{URL}{_row(world['lead']).pk}/change/").status_code == 403      # her own
    assert world["c_rec"].get(url).status_code == 403


def test_the_change_dialog_takes_days_per_week_on_a_dated_row_at_any_time(world):
    part = make_person(first_name="Part", start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=3)
    make_contract(part, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(part, "30", steps=RECEPTION, from_day=JUNE)
    entitlement.refresh()
    row = _row(part, from_day=JUNE)
    world["c_boss"].post(URL + "confirm/", _post(row))                   # already checked: Change is still there
    assert 'name="days_per_week"' not in world["c_boss"].get(f"{URL}{_row(part).pk}/change/").content.decode()
    url = f"{URL}{row.pk}/change/"
    body = world["c_boss"].get(url).content.decode()
    assert 'name="days_per_week" value="3"' in body and "Changing only the days per week leaves the figures as they are." in body
    figures = {"annual_hours": "138.00", "bank_holiday_hours": "48.00"}
    r = world["c_boss"].post(url, {**figures, "days_per_week": "4", "note": ""})
    assert r.status_code == 200 and "field-error" in r.content.decode()
    assert world["c_boss"].post(url, {**figures, "days_per_week": "8", "note": "x"}).status_code == 200
    r = world["c_boss"].post(url, {**figures, "days_per_week": "4", "note": "works four days from June"})
    assert r.json() == {"refresh": True}
    row.refresh_from_db()
    assert (row.days_per_week, row.source, row.needs_checking) == (4, "worked_out", False)


def test_the_other_lists_and_their_empty_states(world):
    body = world["c_boss"].get(URL).content.decode()
    assert "Every typed figure is what its contract gives." in body and "Nothing to look at." in body
    assert "Every leave year being worked out has its bank holidays." in body
    BankHoliday.objects.filter(day__year=2028).delete()
    make_person(first_name="None")
    body = world["c_boss"].get(URL).content.decode()
    assert '<a href="/time-off/bank-holidays/?year=2028">2028</a>' in body
    assert "None Patel" in body and "no contract from Practice HR" in body


def test_the_sidebar_offers_the_page_to_managers_only(world):
    assert 'href="/staff/allowances/"' in world["c_lead"].get("/staff/").content.decode()
    assert 'href="/staff/allowances/"' not in world["c_rec"].get("/staff/").content.decode()


# --- the Health card ------------------------------------------------------------------------------

def test_the_health_card_counts_the_four_lists_and_links_to_the_page(all_teams_user):
    sam = _sam()
    make_allowance(sam, Y27, 180, 60)
    make_person(first_name="None")
    BankHoliday.objects.filter(day__year=2028).delete()
    entitlement.refresh()
    a = health.figures(all_teams_user)["allowances"]
    assert (len(a.to_check), len(a.differ), a.bank_holidays, len(a.contracts)) == (1, 1, [Y28], 1)
    body = client_for(make_person(first_name="Boss"), is_all_teams_manager=True).get("/staff/").content.decode()       # Boss has no contract either
    for line in ("Allowances to check<strong>1</strong>", "Allowances that differ from the contract<strong>1</strong>",
                 "Bank holidays not entered<strong>1</strong>", "Contracts to look at in Practice HR<strong>2</strong>"):
        assert line in body, line
    assert 'href="/staff/allowances/#to-check"' in body


def test_the_health_card_shows_zeros_before_practice_hr_sends_any_contract():
    make_allowance(make_person(weekly_hours=D("30"), days_per_week=4), Y27, 138, 48)
    BankHoliday.objects.filter(day__year=2028).delete()
    body = client_for(make_person(first_name="Boss"), is_all_teams_manager=True).get("/staff/").content.decode()
    for line in ("Allowances to check<strong>0</strong>", "Allowances that differ from the contract<strong>0</strong>",
                 "Bank holidays not entered<strong>0</strong>", "Contracts to look at in Practice HR<strong>0</strong>"):
        assert line in body, line
    assert "/staff/allowances/#" not in body
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_allowances_page.py -q`
Expected: 18 failed: the page's tests on a 404, the Health tests on `KeyError: 'allowances'` or a missing line.

- [ ] **Step 3: The filter and the form**

In `leave/templatetags/leave_extras.py`, replace:

```python
@register.filter
def get_item(mapping, key):
```

with:

```python
@register.filter
def hours_hm(value):
    """Decimal hours (an allowance figure) as hours and minutes."""
    return hours.fmt(hours.from_hours(value))


@register.filter
def get_item(mapping, key):
```

In `people/forms.py`, add before the line `class NotesForm(forms.Form):`:

```python
class AllowanceChangeForm(forms.Form):
    """A manager's own figures for one allowance row, the year's first or a
    dated one (allowance spec, 7.7 Change). A dated row that carries hours
    also offers its days per week."""
    annual_hours = forms.DecimalField(max_digits=6, decimal_places=2, min_value=0, label="Annual leave allowance (full year, hours)")
    bank_holiday_hours = forms.DecimalField(max_digits=6, decimal_places=2, min_value=0, label="Bank holiday allowance (full year, hours)")
    days_per_week = forms.IntegerField(min_value=1, max_value=7, required=False, label="Days per week from this day")
    note = forms.CharField(max_length=300, label="Reason for the change")

    def __init__(self, *args, with_days=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not with_days:
            del self.fields["days_per_week"]
```

- [ ] **Step 4: The views and their addresses**

Create `people/views/allowances.py`:

```python
"""The Allowances page (allowance spec 2026-11-18, section 8): the four
lists a manager works through, and what they do to a row. Managers only;
each list holds only the people the viewer manages, and nobody acts on
their own row (the services refuse)."""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from leave.services import entitlement
from people.forms import AllowanceChangeForm
from people.models import Allowance
from people.services import access, filters, profiles

LIST = "/staff/allowances/"
REFRESH = {"refresh": True}


def _teams(request):
    return list(access.managed_teams(request.user).filter(active=True))


def _query(team):
    """"?team=3" when a team is chosen, for the forms' actions and the way back."""
    query = filters.query(team=team)
    return "?" + query[1:] if query else ""


def _back(request):
    """The list, with the Team box as it was (the forms post to ?team=)."""
    return redirect(LIST + _query(filters.chosen(request, _teams(request), "team")))


def _row(request, pk):
    row = get_object_or_404(Allowance.objects.select_related("person__team", "checked_by"), pk=pk)
    if not access.can_manage(request.user, row.person):
        raise PermissionDenied
    return row


@login_required
@access.manager_required
def index(request):
    choices = _teams(request)
    team = filters.chosen(request, choices, "team")
    review = entitlement.review(request.user, team)
    return render(request, "people/allowances.html", {
        "page_title": "Allowances", "review": review, "team_choices": choices, "team": team,
        "back_query": _query(team),
        "confirmable": [item for item in review.to_check if item.shown and item.can_act]})


def _posted(request):
    """[(row id, annual, bank holiday, days per week or None)] from the
    page's hidden fields; a row whose fields do not read is left out."""
    items = []
    for value in request.POST.getlist("row"):
        try:
            pk = int(value)
            days = request.POST.get(f"days_{pk}", "").strip()
            items.append((pk, Decimal(request.POST[f"annual_{pk}"]), Decimal(request.POST[f"bank_holiday_{pk}"]),
                          int(days) if days else None))
        except (KeyError, ValueError, InvalidOperation):
            continue
    return [item for item in items if item[3] is None or 1 <= item[3] <= 7]


@login_required
@access.manager_required
@require_POST
def confirm(request):
    """Confirm one row or all shown. Each row arrives with the figures the
    page drew; one whose figures have changed since is skipped."""
    confirmed, skipped = profiles.confirm_allowances(request.user, _posted(request))
    if confirmed:
        messages.success(request, f"{confirmed} allowance{'' if confirmed == 1 else 's'} confirmed.")
    if skipped:
        messages.warning(request, f"{skipped} skipped: {'its' if skipped == 1 else 'their'} figures changed after this page was drawn. "
                                  "Check what is listed now.")
    return _back(request)


@login_required
@access.manager_required
@require_POST
def use(request, pk):
    row = _row(request, pk)
    try:
        profiles.use_worked_out(request.user, row)
        removed = not Allowance.objects.filter(pk=pk).exists()
        messages.success(request, f"{row.person.name}: {'the change is removed' if removed else 'the worked-out figure is in use'}.")
    except ValueError as e:
        messages.error(request, str(e))
    return _back(request)


@login_required
@access.manager_required
def change(request, pk):
    row = _row(request, pk)
    form = AllowanceChangeForm(request.POST or None, with_days=profiles.takes_days(row), initial={
        "annual_hours": row.annual_hours.quantize(Decimal("0.01")), "bank_holiday_hours": row.bank_holiday_hours.quantize(Decimal("0.01")),
        "days_per_week": row.days_per_week})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            profiles.change_allowance(request.user, row, d["annual_hours"], d["bank_holiday_hours"], d["note"], d.get("days_per_week"))
            return JsonResponse(REFRESH)
        except ValueError as e:
            form.add_error(None, str(e))
    return render(request, "people/allowance_change_dialog.html", {"row": row, "form": form, "state": entitlement.state(row)})
```

In `people/views/__init__.py`, replace:

```python
from . import dashboard, departments  # noqa: F401
```

with:

```python
from . import allowances, dashboard, departments  # noqa: F401
```

In `people/urls.py`, add after the line `    path("staff/add/", views.add_staff, name="staff-add"),`:

```python
    path("staff/allowances/", views.allowances.index, name="allowances"),
    path("staff/allowances/confirm/", views.allowances.confirm, name="allowances-confirm"),
    path("staff/allowances/<int:pk>/use/", views.allowances.use, name="allowance-use"),
    path("staff/allowances/<int:pk>/change/", views.allowances.change, name="allowance-change"),
```

- [ ] **Step 5: The templates**

Create `templates/people/_allowance_confirm_fields.html` (one line):

```html
{% load leave_extras %}<input type="hidden" name="row" value="{{ r.pk }}"><input type="hidden" name="annual_{{ r.pk }}" value="{{ r.annual_hours|plain_hours }}"><input type="hidden" name="bank_holiday_{{ r.pk }}" value="{{ r.bank_holiday_hours|plain_hours }}">
```

Create `templates/people/allowances.html`:

```html
{% extends "base.html" %}
{% load leave_extras %}
{% block title %}Allowances · AMG Shift Central{% endblock %}
{% block content %}
<p class="field-help">Full-year allowances are worked out from each person's contract in Practice HR, for this leave year and the next, at every read of Practice HR. A worked-out figure counts straight away; it stays on the first list until a manager has checked it.</p>
{% if team_choices %}<form class="filters" method="get">{% include "ui/_team_filter.html" %}<button class="btn btn-quiet" type="submit">Show</button></form>{% endif %}

<h2 id="to-check">Allowances to check</h2>
<table class="table">
  <thead><tr><th>Staff</th><th>Leave year</th><th>From</th><th>Annual leave</th><th>Bank holidays</th><th>How it was worked out</th><th></th></tr></thead>
  <tbody>
  {% for i in review.to_check %}
  <tr>
    <td><a href="{% url 'profile' i.person.pk %}?tab=hours" data-dialog>{{ i.person.name }}</a></td><td>{{ i.year|year_label }}</td>
    {% if i.shown %}{% with r=i.shown.row %}
    <td>{{ r.from_day|date:"j M Y" }}</td><td>{{ r.annual_hours|hours_hm }}</td><td>{{ r.bank_holiday_hours|hours_hm }}</td>
    <td>{{ i.text }}{% if i.shown.working %}<br><span class="field-help">{{ i.shown.working.0 }}<br>{{ i.shown.working.1 }}</span>{% endif %}</td>
    <td>{% if i.can_act %}
      <form method="post" action="{% url 'allowances-confirm' %}{{ back_query }}" class="inline-form">{% csrf_token %}
        {% include "people/_allowance_confirm_fields.html" %}
        {% if i.shown.takes_days %}<label>Days per week <input type="number" name="days_{{ r.pk }}" min="1" max="7" value="{{ r.days_per_week|default_if_none:'' }}"></label>{% endif %}
        <button class="btn btn-quiet" aria-label="Confirm {{ i.person.name }}, {{ r.from_day|date:'j M Y' }}">Confirm</button>
      </form>
      <a href="{% url 'allowance-change' r.pk %}" data-dialog>Change…</a>
    {% endif %}</td>
    {% endwith %}{% else %}
    <td colspan="4">{{ i.text }}</td>
    <td>{% if i.can_act %}<a href="{% url 'leave-hours-change' i.person.pk %}" data-dialog>Add hours change…</a>{% endif %}</td>
    {% endif %}
  </tr>
  {% empty %}<tr><td colspan="7">Nothing to check.</td></tr>{% endfor %}
  </tbody>
</table>
{% if confirmable %}
<form method="post" action="{% url 'allowances-confirm' %}{{ back_query }}">{% csrf_token %}
  {% for i in confirmable %}{% with r=i.shown.row %}{% include "people/_allowance_confirm_fields.html" %}{% endwith %}{% endfor %}
  <button class="btn btn-dark">Confirm all shown ({{ confirmable|length }})</button>
</form>
{% endif %}

<h2 id="differ">Allowances that differ from the contract</h2>
<table class="table">
  <thead><tr><th>Staff</th><th>Leave year</th><th>From</th><th>Typed</th><th>The contract gives</th><th></th><th></th></tr></thead>
  <tbody>
  {% for i in review.differ %}
  <tr>
    <td><a href="{% url 'profile' i.person.pk %}?tab=hours{% if i.year %}&amp;year={{ i.year|date:'Y-m-d' }}{% endif %}" data-dialog>{{ i.person.name }}</a></td><td>{{ i.year|year_label }}</td>
    {% if i.shown %}{% with r=i.shown.row rule=i.shown.rule %}
    <td>{{ r.from_day|date:"j M Y" }}</td>
    <td>{{ r.annual_hours|hours_hm }} and {{ r.bank_holiday_hours|hours_hm }}</td>
    <td>{% if rule %}{{ rule.annual|hours_hm }} and {{ rule.bank_holiday|hours_hm }}<br><span class="field-help">{{ rule.working.0 }}<br>{{ rule.working.1 }}</span>{% else %}no change on this day{% endif %}</td>
    <td>{{ i.text }}</td>
    <td>{% if i.can_act %}
      <form method="post" action="{% url 'allowance-use' r.pk %}{{ back_query }}" class="inline-form">{% csrf_token %}
        <button class="btn btn-quiet" aria-label="{% if rule %}Use the worked-out figure for{% else %}Remove the change for{% endif %} {{ i.person.name }}, {{ r.from_day|date:'j M Y' }}">{% if rule %}Use the worked-out figure{% else %}Remove this change{% endif %}</button>
      </form>
    {% endif %}</td>
    {% endwith %}{% else %}
    <td colspan="5">{{ i.text }}</td>
    {% endif %}
  </tr>
  {% empty %}<tr><td colspan="7">Every typed figure is what its contract gives.</td></tr>{% endfor %}
  </tbody>
</table>

<h2 id="bank-holidays">Bank holidays not entered</h2>
{% if review.bank_holidays %}
<p>No bank holidays are on the list for {% for y in review.bank_holidays %}<a href="{% url 'bank-holidays' %}?year={{ y.year }}">{{ y|year_label }}</a>{% if not forloop.last %}, {% endif %}{% endfor %}. Until they are, the bank holiday allowance worked out for that year is nothing, and nothing is deducted either.</p>
{% else %}<p class="muted">Every leave year being worked out has its bank holidays.</p>{% endif %}

<h2 id="contracts">Contracts to look at in Practice HR</h2>
<table class="table">
  <thead><tr><th>Staff</th><th>Team</th><th>What to look at</th></tr></thead>
  <tbody>
  {% for i in review.contracts %}
  <tr><td><a href="{% url 'profile' i.person.pk %}?tab=hours" data-dialog>{{ i.person.name }}</a></td><td>{{ i.person.team.name|default:"—" }}</td><td>{{ i.text }}</td></tr>
  {% empty %}<tr><td colspan="3">Nothing to look at.</td></tr>{% endfor %}
  </tbody>
</table>
{% endblock %}
```

Create `templates/people/allowance_change_dialog.html`:

```html
{% extends "ui/_dialog.html" %}
{% load leave_extras %}
{% block dialog_title %}Change allowance — {{ row.person.name }}{% endblock %}
{% block dialog_body %}
<form method="post" action="{% url 'allowance-change' row.pk %}" data-dialog-form>
  {% csrf_token %}
  {% for e in form.non_field_errors %}<p class="flash flash-error">{{ e }}</p>{% endfor %}
  <p class="field-help">Leave year {{ row.leave_year|year_label }}, from {{ row.from_day|date:"j M Y" }}: {{ state }}. Figures typed here are kept as typed, and are listed while they differ from what the contract gives.{% if form.days_per_week %} Changing only the days per week leaves the figures as they are.{% endif %}</p>
  {% for f in form %}{% include "ui/_field.html" with field=f %}{% endfor %}
  <button class="btn btn-dark">Change allowance</button>
</form>
{% endblock %}
```

- [ ] **Step 6: The side panel**

In `ui/context_processors.py`, replace:

```python
              "active": path.startswith("/staff/"), "children": []}]
```

with:

```python
              "active": path.startswith("/staff/"),
              "children": [{"label": "Allowances", "url": "/staff/allowances/"}] if role != "staff" else []}]
```

- [ ] **Step 7: The Health card**

In `people/services/health.py`, replace:

```python
    from payroll.services import runs
```

with:

```python
    from leave.services import entitlement
    from payroll.services import runs
```

In `people/services/health.py`, replace:

```python
        "push": push_status,
```

with:

```python
        "push": push_status,
        "allowances": entitlement.review(user, today=today),
```

In `templates/people/_health.html`, replace:

```html
<section class="health" aria-label="Health">
```

with:

```html
{% load leave_extras %}
<section class="health" aria-label="Health">
```

In `templates/people/_health.html`, add before the line `  <div class="health-item{% if health.waiting %} is-warning{% endif %}">Requests waiting<strong>{{ health.waiting }}</strong>`:

```html
  {% with a=health.allowances %}
  <div class="health-item{% if a.to_check %} is-warning{% endif %}">Allowances to check<strong>{{ a.to_check|length }}</strong>
    {% if a.to_check %}<a href="{% url 'allowances' %}#to-check">Check</a>{% endif %}</div>
  <div class="health-item{% if a.differ %} is-warning{% endif %}">Allowances that differ from the contract<strong>{{ a.differ|length }}</strong>
    {% if a.differ %}<a href="{% url 'allowances' %}#differ">Look</a>{% endif %}</div>
  <div class="health-item{% if a.bank_holidays %} is-warning{% endif %}">Bank holidays not entered<strong>{{ a.bank_holidays|length }}</strong>
    {% if a.bank_holidays %}<a href="{% url 'allowances' %}#bank-holidays">{% for y in a.bank_holidays %}{{ y|year_label }}{% if not forloop.last %}, {% endif %}{% endfor %}</a>{% endif %}</div>
  <div class="health-item{% if a.contracts %} is-warning{% endif %}">Contracts to look at in Practice HR<strong>{{ a.contracts|length }}</strong>
    {% if a.contracts %}<a href="{% url 'allowances' %}#contracts">Look</a>{% endif %}</div>
  {% endwith %}
```

- [ ] **Step 8: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_allowances_page.py tests/test_allowance_review.py tests/test_staff_page.py tests/test_shell.py tests/test_csp.py tests/test_permissions.py tests/test_report_filters.py -q`
Expected: all pass.

Run: `.venv/bin/ruff check .`
Expected: nothing reported.

- [ ] **Step 9: Look at the page**

Run: `DEBUG=1 .venv/bin/python manage.py runserver 8011`, sign in as a superuser who is an all-teams manager (the README's "Develop" section says how to make one) and open `/staff/allowances/` and `/staff/`. With no contracts copied, the four lists are empty and the four Health lines read 0. Stop the server.

- [ ] **Step 10: Commit**

```bash
git add people/views/allowances.py people/views/__init__.py people/urls.py people/forms.py people/services/health.py leave/templatetags/leave_extras.py templates/people/allowances.html templates/people/_allowance_confirm_fields.html templates/people/allowance_change_dialog.html templates/people/_health.html ui/context_processors.py tests/test_allowances_page.py
git commit -m "People: the Allowances page, and its four lines on the Health card"
```

---

### Task 9: The profile, the statement and the Leave settings switch

**Files:**
- Modify: `people/views/profile.py`, `people/forms.py` (`HoursForm`), `templates/people/_profile_hours.html`, `leave/views/statement.py`, `templates/leave/_statement.html`, `leave/forms.py` (`SettingsForm`), `leave/services/settings.py`, `leave/views/settings.py`, `templates/leave/settings.html`
- Test: `tests/test_allowance_profile.py`

**Interfaces:**
- Consumes: `entitlement.shown(person, year_list, data=None) -> list[Shown]`, `entitlement.load`, `entitlement.worked` (Tasks 4 and 7); `profiles.confirm_allowance`, `use_worked_out` (Task 6); `contracts.hours_from_hr(person)` (Task 3); the `allowance-change` pop-up and the `hours_hm` filter (Task 8); `access.is_all_teams(user)`; the template context's `is_all_teams` (from `ui.context_processors.shell`).
- Produces:
  - The Pay & time off tab accepts a second kind of post: `allowance_action` (`confirm` or `use`), `row` (an Allowance id of that person) and optionally `days_per_week`.
  - `HoursForm(..., hours_from_hr=False)`: with it on, the form has no `weekly_hours` field.
  - `statement_context(...)` adds `workings`: `[(from_day, annual line, bank holiday line)]`, empty unless `manages`; and `hours_from_contract` (bool, False unless `manages`): the statement's year is worked out from the person's contracts.
  - `leave.services.settings.update(user, reminder_working_days, allowances_need_checking=None) -> LeaveSetting`; `SettingsForm.allowances_need_checking` (a choice, "yes" or "no", cleaned to True, False or None).

Spec section 8 "The profile", 5.4, 7.3 and 7.6. Where the statement's leave year is worked out, managers are not offered "Add hours change…": in its place the statement says "Hours changes come from Practice HR." The service's refusal (Task 6) stays as the backstop and stays tested. Weekly hours are read-only "from Practice HR" exactly where `contracts.hours_from_hr(person)` says so; bank staff and people with no contract in force keep the box. Two things found in the existing tab are put right here because worked-out rows would trip over them. The year boxes took their starting values from the year's **last** row while saving to its **first**, so someone with an hours change could not save the tab untouched; they now show the first row. And the setting is a choice, not a tick box, so that a post without it (a team manager's form, which does not offer it) leaves it as it is.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_allowance_profile.py`:

```python
"""Allowance spec 2026-11-18, section 8: the profile's Pay & time off tab,
the statement and the Leave settings switch."""

import re
from datetime import date
from decimal import Decimal as D

import pytest
from django.core.exceptions import PermissionDenied

from leave.models import LeaveSetting
from leave.services import entitlement
from leave.services import settings as leave_settings
from people.models import Allowance, AuditEntry
from people.services import profiles
from tests.factories import client_for, make_allowance, make_contract, make_person, make_team, make_team_manager

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2027, 2, 1))]
Y27, Y28 = date(2027, 1, 1), date(2028, 1, 1)
JUNE = date(2027, 6, 1)
RECEPTION = [(1, 23)]
WORKING = "23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min"


@pytest.fixture
def world(db):
    nursing = make_team("Nursing")
    boss = make_person(first_name="Boss", team=make_team("Management"))
    lead = make_person(first_name="Lead", team=nursing)
    make_team_manager(lead, nursing)
    nina = make_person(first_name="Nina", team=nursing, start_date=date(2025, 6, 1), weekly_hours=D("37.5"), days_per_week=5)
    make_contract(nina, "37.5", steps=RECEPTION)
    entitlement.refresh()
    return {"boss": boss, "lead": lead, "nina": nina,
            "c_boss": client_for(boss, is_all_teams_manager=True), "c_lead": client_for(lead), "c_nina": client_for(nina)}


def _tab(client, person, **query):
    return client.get(f"/staff/{person.pk}/profile/", {"tab": "hours", **query}).content.decode()


def _row(person, year=Y27, from_day=None):
    return Allowance.objects.get(person=person, leave_year=year, from_day=from_day or year)


# --- the figures, their state, working and buttons ---------------------------------------------

def test_a_manager_sees_each_years_state_working_and_buttons(world):
    body = _tab(world["c_lead"], world["nina"])
    row = _row(world["nina"])
    assert "Where the allowances come from" in body and body.count("worked out, not yet checked") == 2
    assert WORKING in body and "8 bank holidays × 37.5 h ÷ 5 = 60 h" in body
    assert f'name="row" value="{row.pk}"' in body and 'name="allowance_action" value="confirm"' in body
    assert f'href="/staff/allowances/{row.pk}/change/"' in body
    assert 'name="annual_2027" value="172.50"' in body                  # two places in the box, whatever is stored


def test_staff_see_their_figures_with_no_state_no_working_and_no_buttons(world):
    body = _tab(world["c_nina"], world["nina"])
    assert "172.50 h" in body and "60.00 h" in body
    for hidden in ("worked out,", "not yet checked", "Where the allowances come from", WORKING, "allowance_action", "from the contract in Practice HR"):
        assert hidden not in body, hidden


def test_confirm_from_the_profile(world):
    row = _row(world["nina"])
    r = world["c_lead"].post(f"/staff/{world['nina'].pk}/profile/?tab=hours", {"allowance_action": "confirm", "row": row.pk})
    body = r.content.decode()
    assert r.status_code == 200 and "Saved." in body and "worked out, checked by Lead Patel on 1 Feb 2027" in body
    row.refresh_from_db()
    assert row.checked_by == world["lead"].user
    assert world["c_nina"].post(f"/staff/{world['nina'].pk}/profile/?tab=hours", {"allowance_action": "confirm", "row": row.pk}).status_code == 403


def test_a_row_of_someone_else_or_an_unknown_action_is_not_found(world):
    other = make_allowance(make_person(first_name="Other"), Y27, 138, 48, source="worked_out")
    url = f"/staff/{world['nina'].pk}/profile/?tab=hours"
    assert world["c_boss"].post(url, {"allowance_action": "confirm", "row": other.pk}).status_code == 404
    assert world["c_boss"].post(url, {"allowance_action": "delete", "row": _row(world["nina"]).pk}).status_code == 404
    assert other.needs_checking


def test_a_typed_figure_that_differs_shows_what_the_contract_gives_and_can_take_it(world):
    nina = world["nina"]
    row = _row(nina)
    profiles.change_allowance(world["boss"].user, row, D("180"), D("60"), "contract says 24 days")
    body = _tab(world["c_lead"], nina)
    assert "typed" in body and "The contract gives 172 h 30 min and 60 h: " + WORKING in body and "Use the worked-out figure" in body
    r = world["c_lead"].post(f"/staff/{nina.pk}/profile/?tab=hours", {"allowance_action": "use", "row": row.pk})
    assert "worked out, checked by Lead Patel on 1 Feb 2027" in r.content.decode()
    row.refresh_from_db()
    assert (row.annual_hours, row.source) == (D("172.5"), "worked_out")


def test_a_refused_action_is_said_above_the_list(world):
    plain = make_person(first_name="Plain", team=world["nina"].team)
    row = make_allowance(plain, Y27, 138, 48)
    r = world["c_lead"].post(f"/staff/{plain.pk}/profile/?tab=hours", {"allowance_action": "use", "row": row.pk})
    assert "This leave year is not worked out from a contract" in r.content.decode() and "Saved." not in r.content.decode()


def test_a_figure_checked_by_the_app_and_a_copied_one_say_so(world):
    typed = make_person(first_name="Typed", team=world["nina"].team, start_date=date(2025, 6, 1))
    make_contract(typed, "37.5", steps=RECEPTION)
    make_allowance(typed, Y27, D("172.5"), 60)
    make_allowance(typed, Y28, 150, 60, source="copied")
    entitlement.refresh()
    Allowance.objects.filter(person=typed, leave_year=Y28).update(source="copied")          # as copied before the contract arrived
    body = _tab(world["c_lead"], typed)
    assert "worked out, checked automatically on 1 Feb 2027" in body and "copied from last year, not yet checked" in body


# --- weekly hours are Practice HR's ------------------------------------------------------------

def test_weekly_hours_are_read_only_from_practice_hr_and_days_stay_typed(world):
    nina = world["nina"]
    body = _tab(world["c_lead"], nina)
    assert 'name="weekly_hours"' not in body and 'name="days_per_week"' in body
    assert "37.50 <span class=\"field-help\">from Practice HR</span>" in body
    r = world["c_lead"].post(f"/staff/{nina.pk}/profile/?tab=hours", {"weekly_hours": "20", "days_per_week": "4", "leave_year_start": "01-01"})
    assert "Saved." in r.content.decode()
    nina.refresh_from_db()
    assert (nina.weekly_hours, nina.days_per_week) == (D("37.5"), 4)


def test_bank_staff_on_a_contract_for_no_hours_are_typed_exactly_as_before(world):
    bank = make_person(first_name="Bank", team=world["nina"].team)
    make_contract(bank, 0, steps=RECEPTION)
    body = _tab(world["c_lead"], bank)
    assert 'name="weekly_hours"' in body and "from Practice HR" not in body
    world["c_lead"].post(f"/staff/{bank.pk}/profile/?tab=hours", {"weekly_hours": "12", "days_per_week": "2"})
    bank.refresh_from_db()
    assert (bank.weekly_hours, bank.days_per_week) == (D("12"), 2)


def test_someone_with_no_copied_contract_is_typed_exactly_as_before(world):
    plain = make_person(first_name="Plain", team=world["nina"].team)
    body = _tab(world["c_lead"], plain)
    assert 'name="weekly_hours"' in body and "from Practice HR" not in body and "Where the allowances come from" not in body
    world["c_lead"].post(f"/staff/{plain.pk}/profile/?tab=hours", {"weekly_hours": "20", "days_per_week": "4", "annual_2027": "92", "bank_holiday_2027": "32"})
    plain.refresh_from_db()
    assert plain.weekly_hours == D("20") and _row(plain).source == "typed"
    assert "typed" in _tab(world["c_lead"], plain)


def test_saving_the_tab_untouched_leaves_a_worked_out_gp_figure_alone(world):
    doc = make_person(first_name="Doc", is_gp=True, team=world["nina"].team, start_date=date(2022, 9, 1))
    make_contract(doc, 8, 6, unit="sessions")
    entitlement.refresh()
    body = _tab(world["c_lead"], doc)
    assert 'name="bank_holiday_2027" value="66.67"' in body and "66 h 40 min" in body
    assert "8 bank holidays × 2 sessions × 8 ÷ 8 = 16 sessions = 66 h 40 min" in body
    boxes = dict(re.findall(r'name="((?:annual|bank_holiday)_20\d\d)" value="([^"]+)"', body))
    assert boxes == {"annual_2027": "200.00", "bank_holiday_2027": "66.67", "annual_2028": "200.00", "bank_holiday_2028": "0.00"}
    r = world["c_lead"].post(f"/staff/{doc.pk}/profile/?tab=hours", {**boxes, "note": ""})       # 2028 has no bank holidays entered yet
    assert "Saved." in r.content.decode()
    row = _row(doc)
    assert (row.bank_holiday_hours, row.source) == (D("66.6667"), "worked_out")


def test_the_year_boxes_hold_the_years_first_row_not_a_dated_one(world):
    part = make_person(first_name="Part", team=world["nina"].team, start_date=date(2025, 6, 1), weekly_hours=D("22.5"), days_per_week=3)
    make_contract(part, "22.5", steps=RECEPTION, to_day=date(2027, 5, 31))
    make_contract(part, "30", steps=RECEPTION, from_day=JUNE)
    entitlement.refresh()
    body = _tab(world["c_lead"], part)
    assert 'name="annual_2027" value="103.50"' in body                  # not June's 138
    assert 'name="days_per_week" min="1" max="7" value="3"' in body     # beside the dated row's Confirm
    dated = _row(part, from_day=JUNE)
    world["c_lead"].post(f"/staff/{part.pk}/profile/?tab=hours", {"allowance_action": "confirm", "row": dated.pk, "days_per_week": "4"})
    dated.refresh_from_db()
    assert (dated.days_per_week, dated.needs_checking) == (4, False)


# --- the statement ---------------------------------------------------------------------------

def test_the_statement_gains_the_working_for_managers_only(world):
    nina = world["nina"]
    body = _tab(world["c_lead"], nina, year="2027-01-01")
    assert "Full-year figures, from the contract in Practice HR" in body
    assert f"From 1 Jan 2027, annual leave: {WORKING}" in body
    mine = world["c_nina"].get("/time-off/mine/").content.decode()
    assert "Annual leave allowance" in mine and "Full-year figures" not in mine and WORKING not in mine


def test_add_hours_change_is_not_offered_for_a_year_that_is_worked_out(world):
    nina = world["nina"]
    body = _tab(world["c_lead"], nina)
    assert "Hours changes come from Practice HR." in body and "Add hours change" not in body and "Adjust…" in body
    plain = make_person(first_name="Plain", team=nina.team)
    make_allowance(plain, Y27, 138, 48)
    body = _tab(world["c_lead"], plain)
    assert f'href="/staff/{plain.pk}/leave/hours-change/"' in body and "Hours changes come from Practice HR." not in body
    assert "Hours changes come from Practice HR." not in _tab(world["c_nina"], nina)      # staff never had the link


def test_add_hours_change_is_still_refused_by_its_dialog(world):
    nina = world["nina"]
    r = world["c_lead"].post(f"/staff/{nina.pk}/leave/hours-change/", {
        "from_day": "2027-06-01", "weekly_hours": "30", "days_per_week": "4", "annual_hours": "138", "bank_holiday_hours": "48", "note": "x"})
    assert r.status_code == 200 and "Enter the new contract in Practice HR" in r.content.decode()


# --- Leave settings ------------------------------------------------------------------------------

def test_an_all_teams_manager_turns_checking_off_and_it_is_audited(world):
    c = world["c_boss"]
    body = c.get("/settings/leave/").content.decode()
    assert '<select name="allowances_need_checking"' in body and '<option value="yes" selected>' in body
    r = c.post("/settings/leave/", {"reminder_working_days": "3", "allowances_need_checking": "no"})
    assert "Saved." in r.content.decode() and '<option value="no" selected>' in r.content.decode()
    assert LeaveSetting.objects.get().allowances_need_checking is False
    entry = AuditEntry.objects.get(model="leave.leavesetting", field="allowances_need_checking")
    assert (entry.before, entry.after, entry.actor) == ("on", "off", world["boss"].user)
    c.post("/settings/leave/", {"reminder_working_days": "5"})          # a post without the choice leaves it alone
    setting = LeaveSetting.objects.get()
    assert (setting.reminder_working_days, setting.allowances_need_checking) == (5, False)


def test_other_managers_see_the_setting_and_cannot_change_it(world):
    c = world["c_lead"]
    body = c.get("/settings/leave/").content.decode()
    assert 'name="allowances_need_checking"' not in body and "Wait for a manager to check them" in body
    assert "An all-teams manager changes this." in body
    r = c.post("/settings/leave/", {"reminder_working_days": "4", "allowances_need_checking": "no"})
    assert "Saved." in r.content.decode()
    setting = LeaveSetting.objects.get()
    assert (setting.reminder_working_days, setting.allowances_need_checking) == (4, True)
    with pytest.raises(PermissionDenied):
        leave_settings.update(world["lead"].user, 4, allowances_need_checking=False)
    assert leave_settings.update(world["lead"].user, 4, allowances_need_checking=True).allowances_need_checking      # no change: allowed
```

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_allowance_profile.py -q`
Expected: 14 failed, 3 passed (the three that pass are about people nothing is worked out for and the refused dialog, which already behave).

- [ ] **Step 3: The Pay & time off tab**

In `people/forms.py`, replace:

```python
    def __init__(self, *args, years, is_gp=False, **kwargs):
        super().__init__(*args, **kwargs)
        if is_gp:
            del self.fields["weekly_hours"], self.fields["days_per_week"]
```

with:

```python
    def __init__(self, *args, years, is_gp=False, hours_from_hr=False, **kwargs):
        super().__init__(*args, **kwargs)
        if is_gp:
            del self.fields["weekly_hours"], self.fields["days_per_week"]
        elif hours_from_hr:      # weekly hours are Practice HR's: shown, not typed
            del self.fields["weekly_hours"]
```

In `people/views/profile.py`, replace:

```python
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from leave.services import years as leave_years
from leave.views.statement import statement_context
from people.forms import DisplayForm, HoursForm, NotesForm
from people.models import AuditEntry, Person
from people.services import access, profiles
```

with:

```python
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from leave.services import entitlement
from leave.services import years as leave_years
from leave.views.statement import statement_context
from people.forms import DisplayForm, HoursForm, NotesForm
from people.models import AuditEntry, Person
from people.services import access, contracts, profiles
```

In `people/views/profile.py`, replace:

```python
    for a in person.allowances.filter(leave_year__in=years):
```

with:

```python
    # The year's first row: it is the one these boxes change. A dated row
    # is changed from the list beneath. Two places, as the boxes take them.
    for a in person.allowances.filter(leave_year__in=years, from_day=F("leave_year")):
```

In `people/views/profile.py`, add before the line `def _posted_years(person, start):`:

```python
def _allowance_action(request, person, context):
    """The buttons beside each figure: Confirm, and Use the worked-out
    figure (allowance spec, 7.7). A refusal is shown above the list."""
    action, row_id = request.POST["allowance_action"], request.POST.get("row", "")
    if action not in ("confirm", "use") or not row_id.isascii() or not row_id.isdigit():
        raise Http404
    row = get_object_or_404(person.allowances.select_related("person__team", "checked_by"), pk=int(row_id))
    days = request.POST.get("days_per_week", "")
    try:
        if action == "use":
            profiles.use_worked_out(request.user, row)
        else:
            profiles.confirm_allowance(request.user, row, int(days) if days in list("1234567") else None)
        context["saved"] = True
    except ValueError as e:
        context["allowance_error"] = str(e)
```

In `people/views/profile.py`, replace everything from the line `def _hours(request, person, context):` up to, but not including, the line `def _notes(request, person, context):` with:

```python
def _hours(request, person, context):
    year_list = leave_years.years_for(person)
    from_hr = contracts.hours_from_hr(person)
    form = None
    if request.method == "POST" and "allowance_action" in request.POST:
        _allowance_action(request, person, context)
    elif request.method == "POST":
        year_list = _posted_years(person, request.POST.get("leave_year_start", ""))
        form = HoursForm(request.POST, years=year_list, is_gp=person.is_gp, hours_from_hr=from_hr)
        if form.is_valid():
            field = "leave_year_start"
            try:
                with transaction.atomic():      # a refused allowance leaves the hours unchanged too
                    if form.cleaned_data["leave_year_start"]:
                        profiles.update_leave_year_start(request.user, person, form.cleaned_data["leave_year_start"])
                    field = "note"
                    if not person.is_gp:
                        profiles.update_hours(request.user, person, form.cleaned_data.get("weekly_hours"),
                                              form.cleaned_data["days_per_week"])
                    for year, annual, bank in form.allowances():
                        profiles.set_allowance(request.user, person, year, annual, bank,
                                               note=form.cleaned_data["note"])
                context["saved"] = True
            except ValueError as e:
                person.refresh_from_db()
                if field == "leave_year_start":      # the year did not move: show the fields for the years it has
                    form = HoursForm(request.POST, years=leave_years.years_for(person), is_gp=person.is_gp, hours_from_hr=from_hr)
                    form.full_clean()
                form.add_error(field, str(e))
    year_list = leave_years.years_for(person)
    if form is None or context["saved"]:
        form = HoursForm(initial=_stored(person, year_list), years=year_list, is_gp=person.is_gp, hours_from_hr=from_hr)
    existing = {a.leave_year: a for a in person.allowances.filter(leave_year__in=year_list)}
    context.update({"form": form, "allowance_rows": [(y, existing.get(y)) for y in year_list], "hours_from_hr": from_hr,
                    # Managers only: staff see their figures with no state and no working.
                    "figures": entitlement.shown(person, year_list) if context["manages"] else []})
    context.update(statement_context(person, request.GET.get("year"), manages=context["manages"], in_dialog=True))
```

What changed in `_hours`: the `allowance_action` branch; `hours_from_hr` (from `contracts.hours_from_hr(person)`) passed to each `HoursForm`; `cleaned_data.get("weekly_hours")`, because the field may be gone; and `hours_from_hr` and `figures` in the context. `profile()` already refuses any post from someone who does not manage the person.

In `templates/people/_profile_hours.html`, replace:

```html
  <div class="field{% if form.weekly_hours.errors %} has-error{% endif %}">
    <label for="id_weekly_hours">Weekly hours</label>
    {{ form.weekly_hours }}
    {% for e in form.weekly_hours.errors %}<p class="field-error">{{ e }}</p>{% endfor %}
  </div>
```

with:

```html
  {% if hours_from_hr %}
  <div class="field">
    <label>Weekly hours</label>
    <p>{{ person.weekly_hours|default_if_none:"—" }} <span class="field-help">from Practice HR</span></p>
  </div>
  {% else %}
  <div class="field{% if form.weekly_hours.errors %} has-error{% endif %}">
    <label for="id_weekly_hours">Weekly hours</label>
    {{ form.weekly_hours }}
    {% for e in form.weekly_hours.errors %}<p class="field-error">{{ e }}</p>{% endfor %}
  </div>
  {% endif %}
```

In `templates/people/_profile_hours.html`, replace:

```html
  <button class="btn btn-dark">Update profile</button>
</form>
```

with:

```html
  <button class="btn btn-dark">Update profile</button>
</form>
{% if figures %}
<h3>Where the allowances come from</h3>
{% if allowance_error %}<p class="flash flash-error">{{ allowance_error }}</p>{% endif %}
<table class="table">
  <thead><tr><th>Leave year</th><th>From</th><th>Annual leave</th><th>Bank holidays</th><th>How it was worked out</th><th></th></tr></thead>
  <tbody>
  {% for f in figures %}{% with r=f.row %}
  <tr>
    <td>{{ r.leave_year|year_label }}</td><td>{{ r.from_day|date:"j M Y" }}</td>
    <td>{{ r.annual_hours|hours_hm }}</td><td>{{ r.bank_holiday_hours|hours_hm }}</td>
    <td>{{ f.state }}
      {% if f.working %}<br><span class="field-help">{{ f.working.0 }}<br>{{ f.working.1 }}</span>{% endif %}
      {% if f.rule %}<br><span class="field-help">The contract gives {{ f.rule.annual|hours_hm }} and {{ f.rule.bank_holiday|hours_hm }}: {{ f.rule.working.0 }}; {{ f.rule.working.1 }}</span>{% endif %}
      {% if f.orphan %}<br><span class="field-help">The contracts in Practice HR do not change on this day.</span>{% endif %}</td>
    <td>
      {% if r.needs_checking %}
      <form method="post" action="{% url 'profile' person.pk %}?tab=hours" data-dialog-form class="inline-form">{% csrf_token %}
        <input type="hidden" name="allowance_action" value="confirm"><input type="hidden" name="row" value="{{ r.pk }}">
        {% if f.takes_days %}<label>Days per week <input type="number" name="days_per_week" min="1" max="7" value="{{ r.days_per_week|default_if_none:'' }}"></label>{% endif %}
        <button class="btn btn-quiet" aria-label="Confirm the figures from {{ r.from_day|date:'j M Y' }}">Confirm</button>
      </form>
      {% endif %}
      {% if f.differs %}
      <form method="post" action="{% url 'profile' person.pk %}?tab=hours" data-dialog-form class="inline-form">{% csrf_token %}
        <input type="hidden" name="allowance_action" value="use"><input type="hidden" name="row" value="{{ r.pk }}">
        <button class="btn btn-quiet">{% if f.rule %}Use the worked-out figure{% else %}Remove this change{% endif %}</button>
      </form>
      {% endif %}
      <a href="{% url 'allowance-change' r.pk %}" data-dialog>Change…</a>
    </td>
  </tr>
  {% endwith %}{% endfor %}
  </tbody>
</table>
{% endif %}
```

The new table sits inside `{% if manages %}`, after the form: a person reading their own tab gets the read-only list below it, with no state and no working.

- [ ] **Step 4: The statement**

In `leave/views/statement.py`, replace:

```python
from leave.services import adjustments, balances, leavers, notify, sickness, years
```

with:

```python
from leave.services import adjustments, balances, entitlement, leavers, notify, sickness, years
```

In `leave/views/statement.py`, replace:

```python
    n = len(sickness.instances(person))
    return {"statement": _statement_for(person, year_text), "person": person, "manages": manages, "in_dialog": in_dialog,
```

with:

```python
    n = len(sickness.instances(person))
    statement = _statement_for(person, year_text)
    # Managers only (allowance spec, sections 7.3 and 8): the working behind each full-year figure the
    # contracts give, and no Add hours change for a year that is worked out from them.
    workings, from_contract = [], False
    if manages:
        data = entitlement.load([person])
        workings = [(s.row.from_day, *s.working) for s in entitlement.shown(person, [statement.year], data) if s.working]
        from_contract = entitlement.worked(person, statement.year, data).ok
    return {"statement": statement, "workings": workings, "hours_from_contract": from_contract,
            "person": person, "manages": manages, "in_dialog": in_dialog,
```

In `templates/leave/_statement.html`, replace:

```html
    <a href="{% url 'leave-hours-change' person.pk %}" data-dialog>Add hours change…</a>
```

with:

```html
    {% if hours_from_contract %}<span>Hours changes come from Practice HR.</span>{% else %}<a href="{% url 'leave-hours-change' person.pk %}" data-dialog>Add hours change…</a>{% endif %}
```

In `templates/leave/_statement.html`, add before the line `  {% if s.no_allowance_lines %}`:

```html
  {% if manages and workings %}
  <table class="table">
    <thead><tr><th>Full-year figures, from the contract in Practice HR</th></tr></thead>
    <tbody>
    {% for day, annual, bank_holiday in workings %}<tr class="statement-working"><td>From {{ day|date:"j M Y" }}, annual leave: {{ annual }}<br>Bank holidays: {{ bank_holiday }}</td></tr>{% endfor %}
    </tbody>
  </table>
  {% endif %}
```

- [ ] **Step 5: The Leave settings switch**

In `leave/forms.py`, add after the line `    reminder_working_days = forms.IntegerField(min_value=1, max_value=30, label="Remind the managers when a request has waited this many working days")`:

```python
    # A choice, not a tick box: a post without the field (another manager's
    # form, which does not offer it) leaves the setting as it is.
    allowances_need_checking = forms.TypedChoiceField(
        choices=[("yes", "Wait for a manager to check them"), ("no", "Count as checked straight away")],
        coerce=lambda value: value == "yes", empty_value=None, required=False,
        label="Allowances worked out from a contract")
```

Replace the whole of `leave/services/settings.py` with:

```python
from django.core.exceptions import PermissionDenied

from leave.models import LeaveSetting
from people.services import access, audit


def get():
    row = LeaveSetting.objects.first()
    return row or LeaveSetting.objects.create()


def _on_off(value):
    return "on" if value else "off"


def update(user, reminder_working_days, allowances_need_checking=None):
    """Any manager sets the reminder. Whether worked-out allowances wait
    for a check (allowance spec, 7.6) is an all-teams manager's; None
    leaves it as it is."""
    if not access.is_manager(user):
        raise PermissionDenied("managers only")
    row = get()
    changes = {}
    if row.reminder_working_days != reminder_working_days:
        changes["reminder_working_days"] = (row.reminder_working_days, reminder_working_days)
        row.reminder_working_days = reminder_working_days
    if allowances_need_checking is not None and row.allowances_need_checking != allowances_need_checking:
        if not access.is_all_teams(user):
            raise PermissionDenied("all-teams managers only")
        changes["allowances_need_checking"] = (_on_off(row.allowances_need_checking), _on_off(allowances_need_checking))
        row.allowances_need_checking = allowances_need_checking
    if changes:
        row.save(update_fields=list(changes))
        audit.record(user, row, changes)
    return row
```

In `leave/views/settings.py`, replace everything from the line `    current = leave_settings_service.get()` up to, but not including, the line `    return render(request, "leave/settings.html", {"page_title": "Leave settings", "form": form, "saved": saved})` with:

```python
    current = leave_settings_service.get()
    form = SettingsForm(request.POST or None, initial={"reminder_working_days": current.reminder_working_days,
                                                       "allowances_need_checking": "yes" if current.allowances_need_checking else "no"})
    saved = False
    if request.method == "POST" and form.is_valid():
        # Only an all-teams manager is offered the allowances choice; from anyone else it is not read.
        checking = form.cleaned_data["allowances_need_checking"] if access.is_all_teams(request.user) else None
        current = leave_settings_service.update(request.user, form.cleaned_data["reminder_working_days"], checking)
        saved = True
```

In `leave/views/settings.py`, replace:

```python
    return render(request, "leave/settings.html", {"page_title": "Leave settings", "form": form, "saved": saved})
```

with:

```python
    return render(request, "leave/settings.html", {"page_title": "Leave settings", "form": form, "saved": saved,
                                                   "need_checking": current.allowances_need_checking})
```

In `templates/leave/settings.html`, add before the line `  <button class="btn btn-dark">Save</button>`:

```html
  <div class="field{% if form.allowances_need_checking.errors %} has-error{% endif %}">
    <label for="id_allowances_need_checking">{{ form.allowances_need_checking.label }}</label>
    {% if is_all_teams %}{{ form.allowances_need_checking }}{% else %}<p id="id_allowances_need_checking">{% if need_checking %}Wait for a manager to check them{% else %}Count as checked straight away{% endif %}</p>{% endif %}
    <span class="field-help">An allowance worked out from a contract in Practice HR, or copied from last year's, counts as soon as it is made. While this is set to wait, each one stays on Staff › Allowances until a manager has checked it. Typed figures that differ from the contract are listed either way.{% if not is_all_teams %} An all-teams manager changes this.{% endif %}</span>
    {% for e in form.allowances_need_checking.errors %}<p class="field-error">{{ e }}</p>{% endfor %}
  </div>
```

- [ ] **Step 6: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_allowance_profile.py tests/test_allowance_models.py tests/test_profile.py tests/test_leave_views.py tests/test_leave_reports.py tests/test_leave_notify.py tests/test_absence_views.py tests/test_csp.py -q`
Expected: all pass.

Run: `.venv/bin/ruff check .`
Expected: nothing reported.

- [ ] **Step 7: Commit**

```bash
git add people/views/profile.py people/forms.py templates/people/_profile_hours.html leave/views/statement.py templates/leave/_statement.html leave/forms.py leave/services/settings.py leave/views/settings.py templates/leave/settings.html tests/test_allowance_profile.py
git commit -m "People: each allowance's state, working and buttons on the profile; Leave: the checking switch"
```

---

### Task 10: The browser test, the guide, the requirement changes and the pull request

**Files:**
- Create: `tests/e2e/test_allowances.py`
- Modify: `docs/admin/leave.md`, `docs/admin/people.md`, `docs/admin/sync.md`, `docs/admin/setup.md`, `docs/admin/README.md`, `README.md`, `docs/requirements/05-leave-policy.md`, `docs/requirements/04-contracts-and-working-patterns.md`, `docs/requirements/12-decisions-and-open-questions.md`, `docs/requirements/2026-10-29-proposed-amendments.md`, `docs/superpowers/specs/2026-11-18-allowance-rules-design.md`

**Interfaces:**
- Consumes: everything above. Produces: one browser test and documentation.

- [ ] **Step 1: Write the browser test**

It needs no new code, so it should pass at once; it is the check that the page's forms and the Change pop-up work in a real browser under the CSP. Browser tests run only with `E2E=1` (`tests/e2e/conftest.py`), sign in with a password and use `live_server`, as `tests/e2e/test_leave.py` does.

Create `tests/e2e/test_allowances.py`:

```python
"""A manager confirms a worked-out allowance on the Allowances page, then
changes one in its pop-up. Signs in with a password as test_grid does."""

from datetime import date
from decimal import Decimal

import pytest
from playwright.sync_api import expect

from tests import clock
from tests.factories import make_bank_holiday, make_contract, make_person, make_team, make_team_manager, make_user_for

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.today(clock.LATE_2026)]


@pytest.fixture
def manager(live_server):
    from leave.services import entitlement
    # A transactional test empties the tables when it ends, the seeded bank
    # holidays included, so this one makes the eight it counts.
    for month, day in ((1, 1), (3, 26), (3, 29), (5, 3), (5, 31), (8, 30), (12, 27), (12, 28)):
        make_bank_holiday(date(2027, month, day))
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    user = make_user_for(lead, password="pw")
    for name, weekly in (("Nina", "37.5"), ("Omar", "30")):
        person = make_person(first_name=name, team=team, start_date=date(2025, 6, 1), weekly_hours=Decimal(weekly), days_per_week=5)
        make_contract(person, weekly, steps=[(1, 23)])
    entitlement.refresh()
    return user


def test_confirm_a_worked_out_figure_and_change_another(page, live_server, manager):
    page.goto(f"{live_server.url}/accounts/login/?next=/staff/allowances/")
    page.fill("input[name=username]", manager.email)
    page.fill("input[name=password]", "pw")
    page.click("button[type=submit]")
    nina = page.locator("tr:has-text('Nina Patel')")
    expect(nina).to_contain_text("172 h 30 min")
    expect(nina).to_contain_text("worked out, not yet checked")
    expect(nina).to_contain_text("23 days (1 complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min")
    nina.get_by_role("button", name="Confirm").click()
    expect(page.locator(".flash")).to_have_text("1 allowance confirmed.")
    expect(page.locator("#to-check ~ table").first.locator("tr:has-text('Nina Patel')")).to_have_count(0)

    omar = page.locator("tr:has-text('Omar Patel')")
    omar.get_by_role("link", name="Change…").click()
    page.wait_for_selector("#dialog form")
    page.fill("#dialog input[name=annual_hours]", "150")
    page.fill("#dialog input[name=note]", "contract says 25 days")
    page.click("#dialog button.btn-dark")
    differ = page.locator("#differ ~ table").first.locator("tr:has-text('Omar Patel')")
    expect(differ).to_contain_text("150 h and 48 h")
    expect(differ).to_contain_text("138 h and 48 h")
    differ.get_by_role("button", name="Use the worked-out figure").click()
    expect(page.locator(".flash")).to_have_text("Omar Patel: the worked-out figure is in use.")
    expect(page.locator("text=Nothing to check.")).to_be_visible()
    expect(page.locator("text=Every typed figure is what its contract gives.")).to_be_visible()
```

- [ ] **Step 2: Run it**

Run: `E2E=1 E2E_CHROMIUM=/opt/pw-browsers/chromium .venv/bin/python -m pytest -q tests/e2e/test_allowances.py`
Expected: 1 passed (about 20 seconds). If Playwright is not installed in `.venv`: `.venv/bin/pip install -r requirements-dev.txt`. Outside this container leave `E2E_CHROMIUM` out and run `.venv/bin/python -m playwright install chromium` first.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_allowances.py
git commit -m "People: a browser test that confirms an allowance and changes one"
```

- [ ] **Step 4: The guide, `docs/admin/leave.md`**

In `docs/admin/leave.md`, replace:

```markdown
profile, Pay & time off tab. Everyone uses Time off; the approving, booking and
```

with:

```markdown
profile, Pay & time off tab. Staff › Allowances (`/staff/allowances/`, managers) lists the
allowance figures to check. Everyone uses Time off; the approving, booking and
```

In `docs/admin/leave.md`, replace:

```markdown
**Where:** profile › Pay & time off. The fields are in [People](people.md#typed-here-the-pay--time-off-tab).
Allowances are typed in **hours**, for each of the two leave years, one pair (annual
leave and bank holiday) per year.
```

with:

```markdown
**Where:** profile › Pay & time off, and Staff › Allowances. The fields are in [People](people.md#typed-here-the-pay--time-off-tab).
Each person has two full-year allowances in **hours** for each of the two leave years: annual
leave and bank holiday. Where the person's contract in Practice HR carries leave terms they are
[worked out from the contract](#allowances-worked-out-from-the-contract) and a manager checks
them; where it does not, a manager types them.
```

In `docs/admin/leave.md`, replace:

```markdown
  never exceeds the full-year figure. That second rule is why a person who is here for
  the whole of a 53-week year still gets exactly their allowance.
```

with:

```markdown
  never exceeds the full-year figure. That second rule is why a person who is here for
  the whole of a 53-week year still gets exactly their allowance.
- **For a GP the one rounding is to the nearest whole session** (4 h 10 min; half a session
  rounds up), not the half hour, whether the full-year figure was worked out or typed. A
  salaried GP on 200 h a year who starts on 1 July gets 27/52 of it, 103 h 51 min, which is
  25 sessions: 104 h 10 min.
```

In `docs/admin/leave.md`, replace:

```markdown
**A change of hours part-way through a year** is entered with **Add hours change…**,
under the statement on the Pay & time off tab (managers; not for yourself):
```

with:

```markdown
**A change of hours part-way through a year**, for a person whose allowances are typed, is
entered with **Add hours change…**, under the statement on the Pay & time off tab (managers;
not for yourself). Where the leave year shown is worked out from the person's contract the
link is not there: the statement says "Hours changes come from Practice HR." instead, because
a new contract there starts a new allowance from its date by itself.
```

In `docs/admin/leave.md`, add before the line `## What a day costs`:

```markdown
## Allowances worked out from the contract

**Where:** Staff › Allowances (`/staff/allowances/`, managers); each person's profile › Pay &
time off; the four allowance boxes on the Health card. The contract and its leave terms are
entered in Practice HR, on the contract type or on the contract itself.

**The contract is typed once, in Practice HR, and Shift Central does the arithmetic.**
Practice HR holds each contract's weekly hours (or sessions, for a GP) and its annual leave
terms: days a year for staff on hours, weeks a year for GPs, with any steps for length of
service ("23 after 1 year"). At every read of Practice HR, every fifteen minutes, Shift Central
works out both full-year allowances for the person's current leave year and the next, and
keeps them in step when the contract changes. Next year's allowance therefore exists from the
first day of this year, so leave can be booked ahead at any time.

**A worked-out figure counts straight away, and waits for a manager to check it.** Staff can
book against it at once. It shows as "worked out, not yet checked" and stays on the
*Allowances to check* list until a manager presses **Confirm**. Nobody is emailed.

How the figures are worked out. Each line of this is shown beside the figure, as "23 days (1
complete year on 1 Jan 2027) × 37.5 h ÷ 5 = 172 h 30 min":

| | Staff on hours | GPs (sessions) |
|---|---|---|
| **Annual leave** | days × weekly hours ÷ 5 | weeks × sessions a week |
| **Bank holidays** | bank holidays in the leave year × weekly hours ÷ 5 | bank holidays in the year × 2 sessions × sessions a week ÷ the full-time week (8) |
| **Rounding** | each to the nearest half hour, a quarter hour rounding up | each to the nearest whole session, half a session rounding up; a session is 4 h 10 min |

- **Service** is complete years from the person's start date to the first day of the leave
  year. It is fixed for the whole year, so a step up always starts with a leave year: someone
  who started on 1 June 2025 has one complete year on 1 January 2027 and is on the 1-year
  figure for all of 2027.
- **The bank holidays counted are the ones on the [Bank holidays](#bank-holidays) list** for
  that leave year, so an extra bank holiday added there is included at the next read. A year
  with none on the list gives a bank holiday allowance of nothing; the Health card says so
  (*Bank holidays not entered*).
- Two contracts in force together are each worked out and rounded, then added.
- These are **full-year** figures. A starter, a leaver and a change part-way through the year
  are pro-rated from them exactly as [above](#allowances-and-hours-changes).

**What changes a figure, and what never does:**

| What happens in Practice HR | What Shift Central does |
|---|---|
| A new contract, or a change of weekly hours or sessions | Adds a new allowance from the contract's start date, with the new weekly hours. This is what **Add hours change…** does by hand. The days per week are copied from the ones in force; if the new contract changes them, correct them in the box beside **Confirm**, or at any time afterwards with **Change…**. |
| The leave terms change | Every figure in the two leave years is worked out again and goes back to "not yet checked". |
| A contract's date is corrected | The allowance moves to the corrected date. |
| A bank holiday is added or removed here | The bank holiday allowance is worked out again at the next read and goes back to "not yet checked". |

- **A figure a manager typed is never overwritten.** If it is what the contract gives, it
  becomes "worked out" and follows the contract from then on. If it differs it is kept, and
  listed under *Allowances that differ from the contract* with both figures until a manager
  either presses **Use the worked-out figure** or leaves it as it is.
- **A leave year that has ended is never rewritten.** If a contract is changed with a date
  inside last year, the person is listed, for a manager to put the difference right with an
  [adjustment](#adjustments).
- **Nothing booked is ever cancelled** because a figure went down. The person appears on the
  Health card's *Negative leave balances* list like anyone else below zero.

**Who is not worked out.** A year is left as typed, and the profile says nothing about a
working, when the person has no contract in Practice HR yet; when their contract has no leave
terms (set to "Not worked out" there, or a type with none: **GP trainees**, whose allowance
NWSSP tells the practice); when the contract has no fixed weekly hours (bank staff); or when
the person moves between hours and sessions inside the year. For these people a manager types
the figures as before, and adds any hours change by hand. One thing is done for them: once
this year has figures and next year has none, next year starts with a copy of this year's,
marked "copied from last year, not yet checked". If the person's contract later gains terms,
a copied figure that is what the contract gives simply becomes "worked out" (checked or not,
as it was), and one that is not is replaced by the worked-out figure.

**The Allowances page** has a Team box and four lists, each also a box on the Health card:

| List | Who is on it | What to do |
|---|---|---|
| **Allowances to check** | Every worked-out or copied figure nobody has checked. Also "hours changed on 1 June; add the hours change" for a typed person whose contract changed in the year. | Read the working. **Confirm** if it is right; **Change…** to type your own figures with a reason (the row becomes typed), or, on an allowance from a later date, to correct only its days per week (the figures stay worked out); **Add hours change…** for the second kind. **Confirm all shown** confirms every row listed, as filtered by the Team box. |
| **Allowances that differ from the contract** | Typed figures that are not what the contract gives, with both shown; a typed hours change on a day the contracts do not change; a finished year whose figures the contracts no longer give. | **Use the worked-out figure**, or **Remove this change**, or leave it: a typed figure is a manager's decision. For a finished year, an adjustment. |
| **Bank holidays not entered** | A leave year being worked out with no bank holiday on the list. Empty until Practice HR has sent its first contract. | Add them under Time off › Bank holidays. |
| **Contracts to look at in Practice HR** | Someone with no contract in force today, or none from a day in the year ("no contract from 1 July 2027"), or whose steps do not rise. Empty until Practice HR has sent its first contract. | Put the contract right in Practice HR. Until then the earlier figures carry on. |

- A team manager sees their own team. **Nobody confirms or changes their own figures**: a
  manager's own rows are listed without buttons, for another manager.
- **Confirm all shown** sends each row with the figures the page showed. If a figure changed
  in the meantime (a read of Practice HR happened), that row is skipped and the page says "1
  skipped: its figures changed after this page was drawn", so nothing is confirmed unseen.
- The same state, working and buttons are beside each figure on the person's
  [Pay & time off tab](people.md#typed-here-the-pay--time-off-tab). Staff see their figures as
  before, with no state and no working.
- Every figure written, confirmed, changed or removed is in the Activity log and the person's
  History. The app's own writes are by `practice-hr`, with the working as the reason.

**Once the first year has been checked**, an all-teams manager can turn the checking off:
Settings › Leave settings › **Allowances worked out from a contract** › *Count as checked
straight away*. Figures made or changed after that no longer wait; ones already waiting still
do; typed figures that differ are listed either way.

```

In `docs/admin/leave.md`, replace:

```markdown
(`/settings/leave/`) holds the one setting, **Remind the managers when a request has waited this
many working days** (3 to start; 1 to 30).
```

with:

```markdown
(`/settings/leave/`) holds two settings. **Remind the managers when a request has waited this
many working days** (3 to start; 1 to 30) is any manager's. **Allowances worked out from a
contract** (*Wait for a manager to check them*, to start, or *Count as checked straight away*)
is an all-teams manager's; other managers see it and cannot change it. See
[Allowances worked out from the contract](#allowances-worked-out-from-the-contract).
```

In `docs/admin/leave.md`, replace:

```markdown
- A GP is on the Staff list with **no weekly hours**; allowances are typed in the same way
  as for anyone else. A GP is never on the Health card's *Needs hours and allowances* or
  *Negative leave balances* lists.
```

with:

```markdown
- A GP is on the Staff list with **no weekly hours**. A partner's or a salaried GP's
  allowances are [worked out from their contract](#allowances-worked-out-from-the-contract)
  in whole sessions (8 weeks at 6 sessions a week is 48 sessions, 200 h); a GP trainee's are
  typed, in the same way as for anyone else. A part-year figure for any GP is rounded to the
  whole session. A GP is never on the Health card's *Needs hours and allowances* or
  *Negative leave balances* lists.
```

- [ ] **Step 5: The guide, `docs/admin/people.md`**

In `docs/admin/people.md`, replace:

```markdown
the fault is the contract in HR. |
```

with:

```markdown
the fault is the contract in HR. |
| **Contracts** | Every contract of the person's employment in HR: its dates, weekly hours or sessions, and annual leave terms. Not shown as a field; they are what **Weekly hours** below and the [worked-out allowances](leave.md#allowances-worked-out-from-the-contract) come from. A person with none in force is listed on Staff › Allowances under *Contracts to look at in Practice HR*. |
```

In `docs/admin/people.md`, replace:

```markdown
| **Weekly hours** | Contracted hours a week, to two decimal places, 0 to 999.99.
```

with:

```markdown
| **Weekly hours** | **While the person has a contract with fixed hours in force in Practice HR this is read-only and says "from Practice HR"**: it is the hours of their contracts in force today (on the start date, for a starter), set at each sync, and is changed by entering a new contract there. For everyone else it is typed, as before: someone with no contract in Practice HR yet, bank staff whose contract is for 0 hours, and someone between contracts. Typed, it is contracted hours a week, to two decimal places, 0 to 999.99.
```

In `docs/admin/people.md`, replace:

```markdown
for **each of two leave years: the current one and the next**.
```

with:

```markdown
for **each of two leave years: the current one and the next**. Where the person's contract in Practice HR carries leave terms the figures are worked out for you and the boxes show them (to two places); typing a different figure, with a reason, makes it a typed figure, which is kept.
```

In `docs/admin/people.md`, replace:

```markdown
**Below the form is the person's leave statement**, which the person sees too:
```

with:

```markdown
**Under the form, managers see "Where the allowances come from"**: one line for each allowance
of the two leave years, the year's first and any from a later date, with its state ("worked
out, not yet checked", "worked out, checked by … on …", "typed" or "copied from last year, not
yet checked"), the working, and the buttons **Confirm**, **Use the worked-out figure** and
**Change…**. The boxes in the form are the year's first allowance; a later one is changed from
this list, and its **Change…** also takes the days per week from that date, at any time. The person does not see this list. See
[Leave](leave.md#allowances-worked-out-from-the-contract).

**Below that is the person's leave statement**, which the person sees too:
```

In `docs/admin/people.md`, replace:

```markdown
| Pay & time off | Reads their own hours, allowances and statement | Edits the form; Adjust and Add hours change | Cannot open |
```

with:

```markdown
| Pay & time off | Reads their own hours, allowances and statement | Edits the form; confirms and changes allowance figures; Adjust, and Add hours change where the year is typed | Cannot open |
```

- [ ] **Step 6: The guide, `docs/admin/sync.md`, `setup.md` and `README.md`**

In `docs/admin/sync.md`, replace:

```markdown
their name, email, team, start and finish dates and whether they are a GP. This
app adds what HR does not hold (see [People](people.md)).
```

with:

```markdown
their name, email, team, start and finish dates, whether they are a GP and, once
contracts are entered there, their contracted hours or sessions and annual leave terms. This
app adds what HR does not hold (see [People](people.md)).
```

In `docs/admin/sync.md`, replace:

```markdown
- The run is recorded: when it started and finished, whether it worked, how many
  people the feed held, and, if it failed, a message.

**Never fetched:** date of birth, gender, phone numbers, address, NI number, pay,
patterns, contracts and absences. HR holds them; this app does not need them.
```

with:

```markdown
- **Each record's contracts are copied**: dates, weekly hours or sessions, the type's
  full-time week and the annual leave terms in force. The copy replaces what was held for
  that person. A feed that does not carry contracts (an older Practice HR) leaves the copy
  alone. The copy is not in the Activity log: Practice HR records who changed a contract,
  and every allowance figure that results is recorded here.
- **A person with a contract for fixed hours in force has their weekly hours set from it**:
  the hours of the contracts in force today, or on the start date for a starter, when they
  add up to more than 0. GPs have none. Bank staff on a contract for 0 hours, and someone
  between contracts, keep the hours typed here. It is recorded like any other change "from
  Practice HR". Days per week are still typed here.
- The run is recorded: when it started and finished, whether it worked, how many
  people the feed held, and, if it failed, a message.

After a good read, and outside that transaction, the sync **works the allowances out** for
everyone whose contract carries leave terms
([Leave](leave.md#allowances-worked-out-from-the-contract)), then copies any hours change that
has fallen due. Either step failing leaves the people read as they were and adds a few words
to the run's message.

**Never fetched:** date of birth, gender, phone numbers, address, NI number, pay,
patterns and absences. HR holds them; this app does not need them.
```

In `docs/admin/sync.md`, replace:

```markdown
It names the place and the field, never the value. |
```

with:

```markdown
It names the place and the field, never the value. `missing or bad contracts` is a contract of that person with a date, an amount or a leave step that cannot be read. |
| `allowances failed; see the journal` (after a good read) | The people were read, but working the allowances out failed, for everyone or for one person, who is skipped. The figures already held stand. `journalctl -u shift-central-hr-sync` names the person by number, never by name. The next run tries again. |
```

In `docs/admin/sync.md`, replace:

```markdown
30 days and the leave boxes (Requests waiting, Leave costs to check, Negative leave
```

with:

```markdown
30 days, the four allowance boxes and the leave boxes (Requests waiting, Leave costs to check, Negative leave
```

In `docs/admin/sync.md`, replace:

```markdown
**Requests waiting** is the number of leave requests and cancellation requests waiting for a
```

with:

```markdown
**Allowances to check**, **Allowances that differ from the contract**, **Bank holidays not
entered** and **Contracts to look at in Practice HR** are counts, each with a link to
Staff › Allowances, where the lists themselves are. All four read 0, and link nowhere, until
Practice HR sends its first contract.

- *What to do:* open the page and work down it; what each list holds and what its buttons do
  is in [Leave](leave.md#allowances-worked-out-from-the-contract). None of them blocks
  anything: a figure waiting to be checked already counts.

**Requests waiting** is the number of leave requests and cancellation requests waiting for a
```

In `docs/admin/setup.md`, replace:

```markdown
   reason the first time, but a reason is demanded for every later change, so
   check them as you enter them.
```

with:

```markdown
   reason the first time, but a reason is demanded for every later change, so
   check them as you enter them. **For anyone whose contract and leave terms are already in
   Practice HR**, the weekly hours and both allowances are filled in for you: type only the
   days per week, then check the figures on Staff › Allowances
   ([Leave](leave.md#allowances-worked-out-from-the-contract)).
```

In `docs/admin/setup.md`, add before the line `## Backups`:

```markdown
**The allowances release (November 2026)** needs no new setting, unit or timer: `git pull`,
`deploy/manage migrate` (it adds the copy of Practice HR's contracts, marks every allowance
already held as typed, and widens the two figures to four decimal places without changing any
of them), `deploy/manage collectstatic --noinput`, `systemctl restart shift-central`.

**Before it goes on the production box, Practice HR must hold the practice's real contracts
and none of its dummy data.** From the first read after the release, anyone with a contract
for fixed hours in Practice HR has their weekly hours set from it, so a dummy contract would overwrite hours
a manager typed, and its leave terms would be worked into allowances. Check in Practice HR
first; then, after the first sync, check the Health card's four allowance boxes and Staff ›
Allowances. Set each contract type's usual leave terms in Practice HR before loading staff,
and leave GP trainee blank.

```

In `docs/admin/README.md`, replace:

```markdown
from Practice HR every fifteen minutes and cannot be edited here. Job title,
colour, hours, days per week, leave allowances and notes are typed here and are
never touched by the feed. A mistake in the first group is put right in
Practice HR; a mistake in the second, on the profile.
```

with:

```markdown
from Practice HR every fifteen minutes and cannot be edited here. Job title,
colour, days per week and notes are typed here and are never touched by the
feed. Weekly hours and the leave allowances are typed here too until the
person's contract is in Practice HR; from then the hours come from the contract
and the allowances are worked out from it, for a manager to check. A mistake in
what Practice HR owns is put right in Practice HR; a mistake in the rest, on
the profile.
```

In `README.md`, replace:

```markdown
- **Leave**, in hours, for everyone (GPs included): allowances pro-rated by the weeks a
```

with:

```markdown
- **Leave**, in hours, for everyone (GPs included): allowances worked out from each
  person's contract and leave terms in Practice HR and checked by a manager (typed where a
  contract has no terms), pro-rated by the weeks a
```

In `README.md`, replace:

```markdown
[docs/superpowers/specs/2026-11-01-engagement-design.md](docs/superpowers/specs/2026-11-01-engagement-design.md);
```

with:

```markdown
[docs/superpowers/specs/2026-11-01-engagement-design.md](docs/superpowers/specs/2026-11-01-engagement-design.md);
allowances worked out from contracts, with what was decided while it was built, in
[docs/superpowers/specs/2026-11-18-allowance-rules-design.md](docs/superpowers/specs/2026-11-18-allowance-rules-design.md);
```

- [ ] **Step 7: The requirement changes**

In `docs/requirements/05-leave-policy.md`, replace:

```markdown
**LEAVE-01** — Each person has two allowances, both **full-year figures in hours, typed in by a manager** from their contract: an **annual leave allowance** and a **bank holiday allowance**. The system does not work them out from service, role or contract.
*Why:* entitlements vary by individual contract (e.g. 23 days for one person, 285 h for another).
*Tests:* LV-01, LV-02, LV-03. *HR design:* **differs** — the HR design calculates entitlement as weeks × weekly hours with service steps.
```

with:

```markdown
**LEAVE-01** — Each person has two allowances, both **full-year figures in hours**: an **annual leave allowance** and a **bank holiday allowance**. They are **worked out from the person's contract and its leave terms, held in Practice HR, and a manager checks them**; where a contract has no terms a manager types them. *(Amended November 2026; see D-34 to D-39.)*
*Why:* entitlements vary by individual contract (e.g. 23 days for one person, 8 weeks for a partner), so the terms are entered once, with the contract, and the arithmetic is done the same way for everyone.
*Tests:* LV-01, LV-02, LV-03. *HR design:* **differs** — Practice HR holds the terms; AMG Shift Central works out the hours and is the record of them.
```

In `docs/requirements/05-leave-policy.md`, replace:

```markdown
**A part week counts as a whole week.** The result is **rounded once, to the nearest 0.5 h**.
```

with:

```markdown
**A part week counts as a whole week.** The result is **rounded once, to the nearest 0.5 h**. For a GP the single rounding is to the nearest whole session (4 h 10 min), not the nearest half hour *(amended November 2026)*.
```

In `docs/requirements/05-leave-policy.md`, replace:

```markdown
**LEAVE-11** — The **bank holiday allowance is pro-rated the same way** (LEAVE-10).
```

with:

```markdown
**LEAVE-11** — The **bank holiday allowance is pro-rated the same way** (LEAVE-10), a GP's to the nearest whole session.
```

In `docs/requirements/05-leave-policy.md`, replace:

```markdown
and the **total is rounded once** to the nearest 0.5 h. Leave already booked after the change costs whatever the rota shows on the day.
```

with:

```markdown
and the **total is rounded once** to the nearest 0.5 h, or for a GP to the nearest whole session (4 h 10 min). Leave already booked after the change costs whatever the rota shows on the day.
```

In `docs/requirements/04-contracts-and-working-patterns.md`, replace:

```markdown
**PAT-06** — Contract hours change rarely and always **from a future date**. A manager enters the new weekly hours and the new full-year allowances with the date they take effect. The leave effect is in LEAVE-12.

**PAT-07** — The **new system is the master** for weekly hours, days per week and leave. Practice HR's contract details are kept for HR records only; the two are not linked, and Practice HR's built-in leave design is not used.
*Why:* the practice manager will type details into the new system directly.
```

with:

```markdown
**PAT-06** — A change of hours is entered as a **new contract in Practice HR from its date**; AMG Shift Central works out the new allowances from that date. Where allowances are typed, the manager adds the hours change as before. The leave effect is in LEAVE-12. *(Amended November 2026.)*

**PAT-07** — **Practice HR is the master for contracts, weekly hours or sessions, and leave terms. AMG Shift Central is the master for days per week, allowances, leave and balances.** Practice HR's built-in leave design is not used. *(Amended November 2026.)*
*Why:* a contract is entered once, where it is kept; the practice manager's written answers of November 2026.
```

In `docs/requirements/12-decisions-and-open-questions.md`, replace:

```markdown
All decisions were made by the practice manager during the interview on **29 October 2026**.
```

with:

```markdown
All decisions were made by the practice manager during the interview on **29 October 2026**, except D-34 to D-39, from her written answers of **November 2026** to "Hours and leave allowances: questions for the practice manager". Those six replace D-10 and D-12 where they differ.
```

In `docs/requirements/12-decisions-and-open-questions.md`, replace:

```markdown
| D-32 | All documents and worked examples (incl. LV-22 to LV-25) approved by the practice manager | Review complete | All |
```

with:

```markdown
| D-32 | All documents and worked examples (incl. LV-22 to LV-25) approved by the practice manager | Review complete | All |
| D-34 | Annual leave terms are held **per contract**, in Practice HR: **days** a year (weeks for a GP), with steps for complete years of service counted **from the start date**; continuous service is not recognised | Terms differ by contract; one place to type | LEAVE-01, PAT-07 |
| D-35 | A step up in entitlement applies **from the next leave year** | Practice manager's answer | LEAVE-01 |
| D-36 | Bank holidays: **one day each**, any additional bank holiday included; for a GP **2 sessions each**, pro rata on a full-time week of **8 sessions** | Practice manager's answer | LEAVE-01, 11 |
| D-37 | A worked-out allowance **counts at once** and is listed until a manager has checked it; checking can be made automatic later by a setting | Staff can book straight away; a manager sees every figure in the first year | LEAVE-01 |
| D-38 | **Next year's allowance exists from the first day of this year** | Leave can be booked ahead at any time | LEAVE-01 |
| D-39 | A GP's allowances are **whole sessions**, part-year figures included | Half-hour rounding would leave a GP minutes short of a session | LEAVE-10–12 |
```

Add to the end of `docs/requirements/2026-10-29-proposed-amendments.md`:

```markdown

## Postscript, 18 November 2026 (developers), allowances

Built on your written answers of November 2026 (spec of 18 November):
contracted hours, sessions and annual leave terms are typed once, on the
contract in Practice HR, and Shift Central works both allowances out for
this leave year and the next. This changes LEAVE-01, PAT-06 and PAT-07, and
LEAVE-10 to 12 for GPs; the decisions are D-34 to D-39. What to know:

- **A worked-out figure counts straight away** and is listed on Staff ›
  Allowances until a manager confirms it. A figure a manager typed is
  never overwritten: if it differs from the contract it is listed with
  both figures, which is the comparison of the December figures you asked
  for.
- **A GP's allowance is always whole sessions**, including for a GP who
  starts or leaves in the year, as you confirmed on 18 November.
- **GP trainees, bank staff and anyone whose contract has no leave terms
  are typed as before**, and next year starts with a copy of this year's
  figures for a manager to check.
- **Days per week are still typed in Shift Central.** Weekly hours come
  from the contract once it is in Practice HR; bank staff, whose contract
  is for no fixed hours, keep the hours a manager types.
- **Before this goes live, Practice HR must hold the real contracts and
  none of its dummy data**, because hours are taken from it from the
  first read.
- One question, not blocking: a GP's bank holiday figure that is not a
  whole number of sessions (11.25 for a 5-session GP in a year with nine
  bank holidays) is rounded to the nearest session, 11. Say if it should
  always round up.
```

- [ ] **Step 8: Record in the spec what was decided while building**

Add to the end of `docs/superpowers/specs/2026-11-18-allowance-rules-design.md`:

```markdown

## 15. As built (Shift Central, part B)

Built as designed, with these choices where the text above left room or met the code.

- **The year's first figures are always dated the leave year's first day** (6, Periods), for someone who starts later in the year too: the year's first Allowance row always is, and pro-rata cuts it to the start date. When no contract is in force on that first day (the start date, for a starter) the year is not worked out and the person is listed with "no contract from …".
- **A GP whose weekly shares already reach the largest full-year figure gets exactly that figure** (6.1). Without it a typed figure that is not a whole number of sessions (55 h is 13.2 sessions) would round down for someone employed all year, against LEAVE-13. A GP's stored figure is also read to the whole second before it is shared out, so 58.3333 h is the 14 sessions it stands for and half a session is a true tie.
- **A dated row made by refresh is marked as already applied** (5.4, 7.2): its weekly hours are Practice HR's and its days per week are a copy, so `apply_due_hours_changes` has nothing to copy from it. Days corrected on a dated row, beside Confirm or with Change, go onto the person at once if the row's day has come and no later change is in force, and on the day otherwise. Only a dated row that carries weekly hours takes days per week: costing reads its average day from such a row.
- **A removed dated row is audited against the person**, as "allowance from 1 Jun 2027", so the line stays in their History.
- **Weekly hours are typed whenever no hours contract is in force** (5.4), not only for bank staff: someone between contracts keeps the box too, and the sync leaves their hours alone until a contract for more than 0 hours is in force again.
- **"Add hours change" is hidden by the leave year the statement is showing** (7.3): where that year is worked out the statement says "Hours changes come from Practice HR."; on a year that is not (a year typed before the contract arrived) the link is still offered, and the service refuses a day in a worked-out year whichever way it is reached.
- **The profile's year boxes show the year's first row.** They used to start from the year's last row while saving to its first, which a refresh-made dated row would have tripped over. A stored four-place figure is shown to two places in the boxes, and saving it back untouched is no change.
- **The setting is a choice, not a tick box** (7.6), so a post that does not carry it leaves it alone.
- **A finished year is compared, never written** (7.4): the previous leave year is listed when its rows are not the periods the contracts now give, and a row of it still waiting can still be confirmed. "Use the worked-out figure" is refused for a year that has ended.
- **Order of tasks**: models before the GP rounding (its tests need 66.6667 stored), and the Health card's lines with the page they link to.
```

- [ ] **Step 9: Check the docs and commit**

There is no docs test in this repository, so check the links by hand: the new heading in `docs/admin/leave.md` is "Allowances worked out from the contract", its anchor is `#allowances-worked-out-from-the-contract`, and `leave.md`, `people.md`, `sync.md` and `setup.md` link to it.

Run: `grep -c "allowances-worked-out-from-the-contract" docs/admin/leave.md docs/admin/people.md docs/admin/sync.md docs/admin/setup.md`
Expected: `docs/admin/leave.md:3`, `docs/admin/people.md:2`, `docs/admin/sync.md:2`, `docs/admin/setup.md:1` (lines that hold the link).

Run: `grep -rnE "D-3[4-9]" docs/requirements | wc -l`
Expected: 9 (six rows, the heading sentence, LEAVE-01 and the postscript).

```bash
git add docs README.md
git commit -m "Docs: allowances worked out from the contract, the guide and the requirement changes"
```

- [ ] **Step 10: Run everything**

Run in the background (about 2 minutes): `.venv/bin/python -m pytest -q -p no:cacheprovider`
Expected: `1363 passed, 4 skipped`: the 1,189 from before this plan, none of them edited, and 174 new ones. Fix anything that fails before going on.

Run: `E2E=1 E2E_CHROMIUM=/opt/pw-browsers/chromium .venv/bin/python -m pytest -q tests/e2e`
Expected: 19 passed (about 35 seconds).

Run: `.venv/bin/ruff check . && DEBUG=1 .venv/bin/python manage.py makemigrations --check --dry-run`
Expected: nothing from ruff; "No changes detected".

Run: `git status --short`
Expected: nothing. (`graphify update .` is skipped here: `command -v graphify` finds nothing in this container. Where it is installed, run it now and commit `graphify-out/` only if that folder is tracked; it is git-ignored in this repository.)

- [ ] **Step 11: Push and open the pull request**

```bash
git push -u origin claude/hopeful-keller-lankio
```

Open a pull request against `main`, titled "Allowances worked out from contracts held in Practice HR". No pull request template exists in this repository. The body says, in this order:

1. **What it does.** Shift Central reads each person's contracts and leave terms from Practice HR's feed (the `contracts` field Practice HR's own pull request added), works both full-year allowances out for this leave year and the next, keeps them in step, and lists them on Staff › Allowances for a manager to check. A GP's part-year allowance is now whole sessions.
2. **Before this is deployed to production: Practice HR must hold the practice's real contracts and none of its dummy data.** From the first read, anyone with a copied contract for fixed hours has their weekly hours set from it, so a dummy contract would overwrite hours a manager typed. The same line is in `docs/admin/setup.md`, "Upgrading a box that runs an earlier release".
3. **What does not change.** With no contracts in the feed nothing is worked out or copied, the four new Health lines read 0 and link nowhere; every existing test passes unedited. Typed figures are never overwritten. No new setting, unit or timer; two migrations, neither changing a stored figure.
4. **Choices made while building**, pointing at section 15 of the spec.
5. **Tests.** The suite's count, the browser tests, `ruff`, `makemigrations --check`.

Merge commits are this repository's rule. Do not merge until asked.

---

## Self-Review

- **Spec 5.1 (the copy of contracts):** Tasks 1 and 3. **5.2 (source, check, four places):** Task 1. **5.3 (the setting):** Tasks 1 and 9. **5.4 (weekly hours):** Task 3 (the sync, `update_hours`, `apply_due_hours_changes`) and Task 9 (read-only on the profile).
- **6 (the arithmetic, the working, periods, not worked out):** Task 4, with the table and the service example as tests. **6.1 (a GP's part-year figure):** Task 2, with its table as a test and an hours person unchanged.
- **7 (refresh):** Task 5: 7.1 which years, 7.2 the table row by row, 7.3 a mid-year contract, a corrected date and changed terms, 7.4 a finished year, 7.5 copy-forward, 7.6 the setting; the sync wiring and its failure message. **7.3's refusal of Add hours change and 7.7 (confirm, change with days per week at any time, use the worked-out figure):** Task 6; the link not being offered, Task 9.
- **8 (the lists, the Health card, the page, the profile, the statement, staff):** Task 7 (lists), Task 8 (page and Health card), Task 9 (profile, statement).
- **9 (when things go wrong):** unreachable or bad feed, Task 3; no `contracts`, Tasks 3 and 5; no bank holidays, Tasks 4, 5 and 7; a contract ending with nothing after it, steps that do not rise, bank staff, hours to sessions in a year, Tasks 4 and 7; one person failing, Task 5. "A figure drops below what is booked" needs no code: nothing cancels, and the existing *Negative leave balances* line reads the same statement.
- **10 (testing):** each line of the Shift Central list has its test file; "one browser test that confirms a figure" is Task 10. **11 step 2 and its production line:** Task 10, steps 6 and 11. **12 (requirement changes):** Task 10, step 7.
- **Names used across tasks:** `Contract`, `Allowance.Source`, `needs_checking`, `hours.plain`, `make_contract` (1); `contracts.in_force / weekly_hours_on / hours_from_hr`, `profiles.set_weekly_hours_from_hr` (3); `entitlement.periods / Period / Worked / load / worked / worked_for / covered` and the reasons (4); `profiles.write_allowance / add_allowance / remove_allowance / checked_text`, `contracts.any_copied`, `entitlement.refresh / Refreshed / note / current_and_starting` (5); `profiles.confirm_allowance / confirm_allowances / change_allowance / use_worked_out / takes_days` (6); `entitlement.state / Shown / shown / Item / Review / review / FINISHED` (7); URL names `allowances`, `allowances-confirm`, `allowance-use`, `allowance-change`, `AllowanceChangeForm`, `hours_hm`, `health.figures()["allowances"]` (8); `HoursForm(hours_from_hr=)`, `statement_context()["workings"]` and `["hours_from_contract"]`, `settings.update(user, reminder_working_days, allowances_need_checking=None)` (9).
- **Not in this plan, by the spec:** anything in Practice HR (part A, built); deriving days per week from working patterns; any other change to pro-rata, costing, carry-over or year end; the go-live checklist line of section 11 step 3 beyond the upgrade note in `docs/admin/setup.md`.
