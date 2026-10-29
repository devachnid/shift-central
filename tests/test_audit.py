import pytest

from people.models import AuditEntry
from people.services import audit
from tests.factories import make_person

pytestmark = pytest.mark.django_db


def test_record_writes_one_row_per_changed_field(all_teams_user):
    p = make_person()
    rows = audit.record(all_teams_user, p, {"job_title": ("", "Receptionist"),
                                            "weekly_hours": (None, "22.50"),
                                            "display_order": (100, 100)}, note="first fill")
    assert len(rows) == 2
    row = AuditEntry.objects.get(field="job_title")
    assert row.actor == all_teams_user and row.actor_email == "boss@example.org"
    assert row.model == "people.person" and row.object_id == p.pk
    assert (row.before, row.after, row.note) == ("", "Receptionist", "first fill")
    assert row.kind == AuditEntry.Kind.CHANGE


def test_the_sync_writes_as_practice_hr(db):
    p = make_person()
    audit.record(None, p, {"end_date": (None, "2026-12-31")}, note=audit.SYNC_NOTE)
    row = AuditEntry.objects.get()
    assert row.actor is None and row.actor_email == audit.SYNC_ACTOR_EMAIL
    assert row.before == "" and row.after == "2026-12-31"
    assert row.note == "from Practice HR"


def test_nothing_changed_writes_nothing(all_teams_user):
    assert audit.record(all_teams_user, make_person(), {"job_title": ("a", "a")}) == []
    assert not AuditEntry.objects.exists()
