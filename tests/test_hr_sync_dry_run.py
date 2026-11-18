"""`hr_sync --dry-run`: what a run would change, counted, and nothing kept."""

import io
import json
from datetime import date
from decimal import Decimal as D
from pathlib import Path

import pytest
from django.core import mail
from django.core.management import CommandError, call_command

from people.models import Allowance, AuditEntry, Contract, Person, SyncRun
from people.services import hr_sync
from people.services.hr_client import HRClient, HRError
from tests.factories import make_allowance, make_person

pytestmark = [pytest.mark.django_db, pytest.mark.today(date(2026, 11, 2))]
SAMPLE = Path(__file__).parent / "data" / "people_feed.json"
Y27 = date(2027, 1, 1)


class Feed:
    def __init__(self, error=None):
        self.error = error

    def people(self):
        if self.error:
            raise self.error
        return json.loads(SAMPLE.read_text())["people"]


@pytest.fixture
def typed():
    """Employee 101 is here already, with typed hours and the contract's
    2027 figures typed in: a run takes the row over as worked out."""
    person = make_person(hr_employee_id=101, first_name="Typed", weekly_hours=D("20"), days_per_week=4, start_date=date(2019, 4, 1))
    make_allowance(person, Y27, D("138"), D("48"))
    return person


def _state():
    return {"people": list(Person.objects.order_by("pk").values()), "contracts": Contract.objects.count(),
            "allowances": list(Allowance.objects.order_by("pk").values()), "audit": AuditEntry.objects.count(),
            "runs": SyncRun.objects.count()}


def test_a_dry_run_counts_what_a_run_would_do_and_leaves_nothing_behind(typed):
    before = _state()
    seen = hr_sync.preview(Feed())
    assert seen == {"message": "", "people": 5, "weekly_hours": 2, "created": 2, "changed": 0, "adopted": 1, "removed": 0,
                    "allowances_failed": False}
    assert _state() == before and mail.outbox == []
    typed.refresh_from_db()
    assert typed.weekly_hours == D("20")

    last = AuditEntry.objects.order_by("-pk").values_list("pk", flat=True).first() or 0
    assert hr_sync.sync(Feed()).ok                                      # the real run does what was counted
    entries = AuditEntry.objects.filter(pk__gt=last)
    assert entries.filter(model="people.person", field="weekly_hours").values("object_id").distinct().count() == 2
    assert Allowance.objects.count() == 3 and Contract.objects.exists()
    row = Allowance.objects.get(person=typed)
    assert (row.source, row.annual_hours) == ("worked_out", D("138"))
    typed.refresh_from_db()
    assert typed.weekly_hours == D("30")


def test_a_second_dry_run_after_the_real_one_counts_nothing_to_do(typed):
    hr_sync.sync(Feed())
    seen = hr_sync.preview(Feed())
    assert (seen["weekly_hours"], seen["created"], seen["changed"], seen["adopted"], seen["removed"]) == (0, 0, 0, 0, 0)


def test_the_command_prints_counts_only(typed, settings, monkeypatch):
    settings.PRACTICE_HR_URL, settings.HR_API_TOKEN = "https://hr.example", "t0k"
    monkeypatch.setattr(HRClient, "from_settings", classmethod(lambda cls: Feed()))
    out = io.StringIO()
    call_command("hr_sync", "--dry-run", stdout=out)
    text = out.getvalue()
    assert text.splitlines() == ["Dry run: nothing has been changed.", "5 people in the feed",
                                 "2 people whose weekly hours would be set from a contract", "2 allowance rows would be created",
                                 "0 allowance rows would be changed", "1 typed allowance rows would be taken over as worked out",
                                 "0 allowance rows would be removed", "Working out the allowances would not fail for anyone"]
    names = [p["name"] for p in Feed().people()]
    assert not any(name in text for name in names) and "138" not in text and "Typed" not in text
    assert SyncRun.objects.count() == 0 and Contract.objects.count() == 0


def test_a_feed_error_is_reported_as_a_run_reports_it(settings, monkeypatch):
    settings.PRACTICE_HR_URL, settings.HR_API_TOKEN = "https://hr.example", "t0k"
    monkeypatch.setattr(HRClient, "from_settings", classmethod(lambda cls: Feed(HRError("Practice HR answered 503"))))
    with pytest.raises(CommandError, match="^hr_sync failed: Practice HR answered 503$"):
        call_command("hr_sync", "--dry-run")
    bad = Feed()
    records = bad.people()
    del records[1]["employment"]
    assert hr_sync.preview(type("F", (), {"people": lambda self: records})())["message"] == "record 2 in the feed: missing or bad employment"
    assert SyncRun.objects.count() == 0 and Person.objects.count() == 0
