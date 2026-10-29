"""People come from Practice HR: upsert by employee id, never delete, HR's
fields overwritten, the typed fields untouched, every change audited."""

import io
import json
import urllib.error
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.utils import timezone

from people.models import AuditEntry, Person, SyncRun, Team
from people.services import hr_sync
from people.services.hr_client import HRClient, HRError

pytestmark = pytest.mark.django_db
FIXTURE = Path(__file__).parent / "fixtures" / "hr_people.json"


class FakeClient:
    def __init__(self, payload=None, error=None):
        self.payload = payload if payload is not None else json.loads(FIXTURE.read_text())
        self.error = error

    def people(self):
        if self.error:
            raise self.error
        return self.payload["people"]


def test_a_feed_of_six_makes_six_people_and_their_teams():
    run = hr_sync.sync(FakeClient())
    assert run.ok and run.people_seen == 6 and run.finished_at
    assert Person.objects.count() == 6
    assert set(Team.objects.values_list("name", flat=True)) == {
        "Reception", "Nursing", "GPs", "Admin/Secretarial", "Management"}
    sam = Person.objects.get(hr_employee_id=1)
    assert (sam.name, sam.email, sam.team.name) == ("Sam Patel", "sam@example.org", "Reception")
    assert sam.start_date == date(2024, 1, 8) and sam.end_date is None and not sam.is_gp
    assert Person.objects.get(hr_employee_id=3).is_gp
    assert Person.objects.get(hr_employee_id=4).end_date == date(2026, 10, 14)
    assert Person.objects.get(hr_employee_id=5).team is None
    assert all(p.last_seen_from_hr for p in Person.objects.all())


def test_a_second_identical_run_changes_nothing_and_audits_nothing():
    hr_sync.sync(FakeClient())
    before = AuditEntry.objects.count()
    hr_sync.sync(FakeClient())
    assert AuditEntry.objects.count() == before


def test_the_first_run_audits_nothing_but_creation():
    hr_sync.sync(FakeClient())
    assert AuditEntry.objects.filter(field="created").count() == 6


def test_changes_from_hr_are_applied_and_audited_as_practice_hr():
    hr_sync.sync(FakeClient())
    payload = json.loads(FIXTURE.read_text())
    sam = payload["people"][0]
    sam["email"] = "sam.patel@example.org"
    sam["employment"]["end"] = "2026-12-31"
    sam["positions"][0]["team"] = "Admin/Secretarial"
    hr_sync.sync(FakeClient(payload))
    p = Person.objects.get(hr_employee_id=1)
    assert p.email == "sam.patel@example.org" and p.end_date == date(2026, 12, 31)
    assert p.team.name == "Admin/Secretarial"
    rows = AuditEntry.objects.filter(object_id=p.pk, model="people.person").exclude(field="created")
    assert {r.field for r in rows} == {"email", "end_date", "team"}
    assert all(r.actor_email == "practice-hr" and r.note == "from Practice HR" for r in rows)
    assert rows.get(field="end_date").before == ""


def test_typed_fields_survive_a_sync():
    hr_sync.sync(FakeClient())
    p = Person.objects.get(hr_employee_id=1)
    p.job_title, p.weekly_hours, p.days_per_week, p.name_colour = "Receptionist", Decimal("22.5"), 3, "#AA0000"
    p.save()
    hr_sync.sync(FakeClient())
    p.refresh_from_db()
    assert (p.job_title, p.weekly_hours, p.days_per_week, p.name_colour) == (
        "Receptionist", Decimal("22.50"), 3, "#AA0000")


def test_a_person_missing_from_the_feed_is_kept():
    hr_sync.sync(FakeClient())
    payload = json.loads(FIXTURE.read_text())
    del payload["people"][0]
    first = Person.objects.get(hr_employee_id=1).last_seen_from_hr
    hr_sync.sync(FakeClient(payload))
    p = Person.objects.get(hr_employee_id=1)
    assert p.last_seen_from_hr == first and Person.objects.count() == 6


def _a_while_ago(days=3):
    """Move every sighting and run back, as if the syncs so far had run days ago."""
    then = timezone.now() - timedelta(days=days)
    Person.objects.update(last_seen_from_hr=then)
    SyncRun.objects.update(started_at=then, finished_at=then)


def test_a_person_a_good_run_left_out_is_not_seen():
    hr_sync.sync(FakeClient())
    _a_while_ago()
    payload = json.loads(FIXTURE.read_text())
    del payload["people"][0]
    hr_sync.sync(FakeClient(payload))
    assert [p.hr_employee_id for p in hr_sync.not_seen_recently()] == [1]


def test_failed_runs_after_a_good_one_list_nobody_as_not_seen():
    """A day of failures advances nobody's sighting; measured by the clock
    that was everyone. Measured by the last good run, it is no one."""
    hr_sync.sync(FakeClient())
    _a_while_ago(days=1.25)
    for _ in range(2):
        assert not hr_sync.sync(FakeClient(error=HRError("Practice HR unreachable"))).ok
    assert not hr_sync.not_seen_recently().exists()


def test_a_person_left_out_an_hour_ago_is_not_yet_not_seen():
    """The card says "for a day": one run without someone is not news yet."""
    hr_sync.sync(FakeClient())
    payload = json.loads(FIXTURE.read_text())
    del payload["people"][0]
    hr_sync.sync(FakeClient(payload))
    assert not hr_sync.not_seen_recently().exists()


def test_an_error_leaves_the_data_untouched_and_records_a_failed_run():
    hr_sync.sync(FakeClient())
    run = hr_sync.sync(FakeClient(error=HRError("Practice HR returned 500 for people")))
    assert not run.ok and run.message == "Practice HR returned 500 for people"
    assert Person.objects.count() == 6 and SyncRun.objects.count() == 2


def test_a_malformed_record_fails_the_run_without_values_in_the_message():
    payload = {"people": [{"id": 1, "first_name": "Sam", "email": "sam@example.org"}]}
    run = hr_sync.sync(FakeClient(payload))
    assert not run.ok and "sam" not in run.message.lower()
    assert "record 1 in the feed" in run.message and "last_name" in run.message
    assert Person.objects.count() == 0


def test_a_bad_id_is_named_but_its_value_is_not_in_the_message():
    payload = json.loads(FIXTURE.read_text())
    payload["people"][0]["id"] = "sam@example.org"
    run = hr_sync.sync(FakeClient(payload))
    assert not run.ok and "sam@example.org" not in run.message and "id" in run.message
    assert Person.objects.count() == 0


def test_a_boolean_or_fractional_id_is_not_an_employee_id():
    for bad in (True, 1.9):
        payload = json.loads(FIXTURE.read_text())
        payload["people"][0]["id"] = bad
        run = hr_sync.sync(FakeClient(payload))
        assert not run.ok and "record 1 in the feed" in run.message and "id" in run.message
    assert Person.objects.count() == 0


def test_a_bad_date_is_named_but_its_value_is_not_in_the_message():
    payload = json.loads(FIXTURE.read_text())
    payload["people"][1]["employment"]["start"] = "Sam Patel"
    run = hr_sync.sync(FakeClient(payload))
    assert not run.ok and "Sam Patel" not in run.message
    assert "record 2 in the feed" in run.message and "start" in run.message
    assert Person.objects.count() == 0


def test_a_database_error_is_a_failed_run_not_an_exception():
    payload = json.loads(FIXTURE.read_text())
    payload["people"][0]["name"] = None
    run = hr_sync.sync(FakeClient(payload))
    assert not run.ok and run.finished_at
    assert run.message == "unexpected error; see the journal"
    assert Person.objects.count() == 0


def test_a_record_with_no_position_keeps_the_persons_team():
    """HR sends today's positions: someone between posts, or a starter
    whose post begins later, has none, and keeps the team they had."""
    hr_sync.sync(FakeClient())
    payload = json.loads(FIXTURE.read_text())
    payload["people"][0]["positions"] = []
    assert hr_sync.sync(FakeClient(payload)).ok
    sam = Person.objects.get(hr_employee_id=1)
    assert sam.team.name == "Reception"
    assert not AuditEntry.objects.filter(object_id=sam.pk, field="team").exists()


def test_a_new_person_with_no_position_starts_without_a_team():
    payload = json.loads(FIXTURE.read_text())
    hr_sync.sync(FakeClient(payload))
    assert Person.objects.get(hr_employee_id=5).team is None
    payload["people"][4]["positions"] = [{"title": "Nurse", "team": "Nursing"}]
    hr_sync.sync(FakeClient(payload))
    assert Person.objects.get(hr_employee_id=5).team.name == "Nursing"


def test_a_team_rename_in_hr_makes_a_new_team_and_moves_the_person():
    hr_sync.sync(FakeClient())
    payload = json.loads(FIXTURE.read_text())
    payload["people"][1]["positions"][0]["team"] = "Nursing team"
    hr_sync.sync(FakeClient(payload))
    assert Person.objects.get(hr_employee_id=2).team.name == "Nursing team"
    assert Team.objects.filter(name="Nursing").exists(), "the old team is kept, not deleted"


# --- the client ------------------------------------------------------------------

def _opener(status=200, body=b'{"people": []}'):
    calls = []

    def open_(req):
        calls.append(req)
        if status != 200:
            raise urllib.error.HTTPError(req.full_url, status, "x", {}, io.BytesIO(b"boom"))
        return io.BytesIO(body)
    open_.calls = calls
    return open_


def test_the_client_gets_people_with_a_bearer_token():
    op = _opener()
    assert HRClient("https://hr.example", "t0k", opener=op).people() == []
    req = op.calls[0]
    assert req.full_url == "https://hr.example/api/v1/people" and req.get_method() == "GET"
    assert req.get_header("Authorization") == "Bearer t0k"


def test_an_http_error_is_an_hrerror_without_the_token_in_it():
    with pytest.raises(HRError) as e:
        HRClient("https://hr.example", "t0k", opener=_opener(500)).people()
    assert "500" in str(e.value) and "t0k" not in str(e.value)


def test_a_non_json_body_is_an_hrerror():
    with pytest.raises(HRError):
        HRClient("https://hr.example", "t0k", opener=_opener(body=b"<html>")).people()


def test_the_token_is_not_sent_over_plain_http(settings):
    settings.DEBUG = False
    op = _opener()
    with pytest.raises(HRError):
        HRClient("http://hr.example", "t0k", opener=op).people()
    assert op.calls == []


def test_the_command_refuses_without_a_token(settings, capsys):
    from django.core.management import CommandError, call_command
    settings.PRACTICE_HR_URL, settings.HR_API_TOKEN = "https://hr.example", ""
    with pytest.raises(CommandError, match="HR_API_TOKEN"):
        call_command("hr_sync")
