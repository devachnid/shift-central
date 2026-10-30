"""One summary email per person on Notify staff (ROTA-09, NOTIF-02), built
from the DayChange rows; nothing sent twice, nothing sent for a change
undone."""

from datetime import date, timedelta

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.utils import timezone

from people.models import AuditEntry
from shifts.models import DayChange
from shifts.services import entries, notify
from tests.factories import make_department, make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db
MON, TUE = date(2027, 3, 1), date(2027, 3, 2)


@pytest.fixture
def world():
    team = make_team("Reception")
    lead = make_person(first_name="Lead", team=team)
    make_team_manager(lead, team)
    user = make_user_for(lead)
    nina = make_person(first_name="Nina", team=team)
    pmc = make_department("Reception PMC")
    return {"lead": lead, "user": user, "nina": nina, "pmc": pmc, "team": team}


def test_lines_say_what_each_changed_day_is_now_and_was(world):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "09:00-17:00 Reception PMC")
    DayChange.objects.filter(person=nina).delete()   # as if notified
    entries.set_cell_text(u, nina, MON, "08:00-16:15 1 hour break Reception PMC")
    entries.set_cell_text(u, nina, TUE, "08:00-13:00")
    entries.set_cell_text(u, nina, TUE, "")
    # Tuesday was set and then cleared, so it is back to what it was: no line.
    assert notify.lines(nina) == [
        "Mon 1 Mar 2027: 08:00-16:15 1 hour break Reception PMC (was 09:00-17:00 Reception PMC)"]


def test_a_change_undone_sends_nothing_and_its_row_goes(world):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")
    entries.set_cell_text(u, nina, MON, "")
    assert notify.lines(nina) == []
    assert notify.pending(u)[0]["reason"] == "changes cancel out"
    out = notify.send(u, [nina.pk])
    assert out["skipped"] == [nina] and not DayChange.objects.exists() and not mail.outbox


def test_send_emails_one_summary_deletes_the_rows_and_audits(world):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")
    entries.set_cell_text(u, nina, TUE, "13:00-17:00")
    out = notify.send(u, [nina.pk])
    assert out["sent"] == [nina] and len(mail.outbox) == 1
    body = mail.outbox[0].body
    assert mail.outbox[0].subject == "Your rota has changed"
    assert "Mon 1 Mar 2027: 08:00-12:00 (was no shift)" in body and "Tue 2 Mar 2027: 13:00-17:00 (was no shift)" in body
    assert "/rota/?from=2027-03-01" in body
    assert not DayChange.objects.exists()
    row = AuditEntry.objects.get(model="shifts.entry", field="notified")
    assert row.object_id == nina.pk and row.after == "2" and row.actor == u


def test_a_failed_send_keeps_the_rows(world, monkeypatch):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")
    monkeypatch.setattr("messaging.services.send_mail", lambda *a, **kw: (_ for _ in ()).throw(OSError("down")))
    out = notify.send(u, [nina.pk])
    assert out["failed"] == [nina] and DayChange.objects.count() == 1


def test_people_without_an_email_are_listed_with_the_reason_and_skipped(world):
    u = world["user"]
    quiet = make_person(first_name="Quiet", team=world["team"], email="")
    entries.set_cell_text(u, quiet, MON, "08:00-12:00")
    assert notify.pending(u)[0]["reason"] == "no email"
    assert notify.send(u, [quiet.pk])["skipped"] == [quiet]


def test_pending_is_scoped_to_the_viewers_teams(world):
    u = world["user"]
    other = make_person(first_name="Other", team=make_team("Nursing"))
    DayChange.objects.create(person=other, day=MON, before="no shift")
    DayChange.objects.create(person=world["nina"], day=MON, before="no shift")
    assert [p["person"] for p in notify.pending(u)] == [world["nina"]]
    with pytest.raises(PermissionDenied):
        notify.send(u, [other.pk])


def test_the_dialog_lists_ticks_and_sends(world):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")
    c = Client()
    c.force_login(u)
    body = c.get("/rota/notify/").content.decode()
    assert "Nina Patel" in body and "Mon 1 Mar" in body and f'name="people" value="{nina.pk}" checked' in body
    body = c.post("/rota/notify/", {"people": [nina.pk]}).content.decode()
    assert "Sent to Nina Patel" in body and len(mail.outbox) == 1


def test_the_health_card_counts_old_unnotified_changes(world):
    u, nina = world["user"], world["nina"]
    row = DayChange.objects.create(person=nina, day=MON, before="no shift")
    DayChange.objects.filter(pk=row.pk).update(at=timezone.now() - timedelta(days=8))
    assert notify.old_count(u) == 1
    c = Client()
    c.force_login(u)
    assert "Unnotified rota changes over a week old" in c.get("/staff/").content.decode()
