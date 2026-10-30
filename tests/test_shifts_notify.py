"""One summary email per person on Notify staff (ROTA-09, NOTIF-02), built
from the DayChange rows; nothing sent twice, nothing sent for a change
undone."""

from datetime import date, timedelta

import pytest
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.utils import timezone

import messaging.services as messaging
from people.models import AuditEntry
from shifts.models import DayChange
from shifts.services import entries, notify
from tests.factories import make_department, make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db
MON, TUE = date(2027, 3, 1), date(2027, 3, 2)
BASE = "https://shift.example"


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
    out = notify.send(u, [nina.pk], BASE)
    assert out["skipped"] == [nina] and not DayChange.objects.exists() and not mail.outbox


def test_send_emails_one_summary_deletes_the_rows_and_audits(world):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")
    entries.set_cell_text(u, nina, TUE, "13:00-17:00")
    out = notify.send(u, [nina.pk], BASE)
    assert out["sent"] == [nina] and len(mail.outbox) == 1
    body = mail.outbox[0].body
    assert mail.outbox[0].subject == "Your rota has changed"
    assert "Mon 1 Mar 2027: 08:00-12:00 (was no shift)" in body and "Tue 2 Mar 2027: 13:00-17:00 (was no shift)" in body
    assert "https://shift.example/rota/?from=2027-03-01" in body
    assert not DayChange.objects.exists()
    row = AuditEntry.objects.get(model="shifts.entry", field="notified")
    assert row.object_id == nina.pk and row.after == "2" and row.actor == u


def test_a_failed_send_keeps_the_rows(world, monkeypatch):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")
    monkeypatch.setattr("messaging.services.send_mail", lambda *a, **kw: (_ for _ in ()).throw(OSError("down")))
    out = notify.send(u, [nina.pk], BASE)
    assert out["failed"] == [nina] and DayChange.objects.count() == 1


def test_people_without_an_email_are_listed_with_the_reason_and_skipped(world):
    u = world["user"]
    quiet = make_person(first_name="Quiet", team=world["team"], email="")
    entries.set_cell_text(u, quiet, MON, "08:00-12:00")
    assert notify.pending(u)[0]["reason"] == "no email"
    assert notify.send(u, [quiet.pk], BASE)["skipped"] == [quiet]


def test_pending_is_scoped_to_the_viewers_teams(world):
    u = world["user"]
    other = make_person(first_name="Other", team=make_team("Nursing"))
    DayChange.objects.create(person=other, day=MON, before="no shift")
    DayChange.objects.create(person=world["nina"], day=MON, before="no shift")
    assert [p["person"] for p in notify.pending(u)] == [world["nina"]]
    with pytest.raises(PermissionDenied):
        notify.send(u, [other.pk], BASE)


def test_the_dialog_lists_ticks_and_sends(world):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")
    c = Client()
    c.force_login(u)
    body = c.get("/rota/notify/").content.decode()
    assert "Nina Patel" in body and "Mon 1 Mar" in body and f'name="people" value="{nina.pk}" checked' in body
    body = c.post("/rota/notify/", {"people": [nina.pk]}).content.decode()
    assert "Sent to Nina Patel" in body and len(mail.outbox) == 1
    assert "http://testserver/rota/?from=2027-03-01" in mail.outbox[0].body and "data-dialog-refresh" in body


def test_a_cancelled_out_person_is_ticked_and_sending_clears_them_without_mail(world):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")
    entries.set_cell_text(u, nina, MON, "")
    DayChange.objects.update(at=timezone.now() - timedelta(days=8))
    assert notify.old_count(u) == 0
    c = Client()
    c.force_login(u)
    body = c.get("/rota/notify/").content.decode()
    assert f'name="people" value="{nina.pk}" checked' in body and "changes cancel out" in body
    c.post("/rota/notify/", {"people": [nina.pk]})
    assert not DayChange.objects.exists() and not mail.outbox


def test_a_person_without_an_email_is_not_ticked(world):
    u = world["user"]
    quiet = make_person(first_name="Quiet", team=world["team"], email="")
    entries.set_cell_text(u, quiet, MON, "08:00-12:00")
    c = Client()
    c.force_login(u)
    body = c.get("/rota/notify/").content.decode()
    assert f'name="people" value="{quiet.pk}" disabled' in body


def test_posting_nothing_ticked_says_so_and_does_not_refresh(world):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")
    c = Client()
    c.force_login(u)
    body = c.post("/rota/notify/", {"people": ["²", "x"]}).content.decode()
    assert "Nothing ticked." in body and "data-dialog-refresh" not in body and not mail.outbox


def test_a_change_saved_while_the_mail_was_built_is_kept(world, monkeypatch):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")
    real = notify.send_mail

    def send_and_edit(person, subject, body, connection=None):
        entries.set_cell_text(u, person, TUE, "13:00-17:00")
        return real(person, subject, body, connection=connection)

    monkeypatch.setattr(notify, "send_mail", send_and_edit)
    notify.send(u, [nina.pk], BASE)
    assert list(DayChange.objects.values_list("day", flat=True)) == [TUE]


def test_the_health_card_counts_old_unnotified_changes(world):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")   # a real change, not one that cancels out
    DayChange.objects.update(at=timezone.now() - timedelta(days=8))
    assert notify.old_count(u) == 1
    c = Client()
    c.force_login(u)
    assert "Unnotified rota changes over a week old" in c.get("/staff/").content.decode()


def test_a_day_re_edited_while_its_mail_was_built_keeps_the_newer_change(world, monkeypatch):
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")
    real = notify.send_mail

    def send_and_edit(person, subject, body, connection=None):
        entries.set_cell_text(u, person, MON, "09:00-13:00")
        return real(person, subject, body, connection=connection)

    monkeypatch.setattr(notify, "send_mail", send_and_edit)
    assert notify.send(u, [nina.pk], BASE)["sent"] == [nina]
    change = DayChange.objects.get()
    assert (change.day, change.before) == (MON, "08:00-12:00"), "measured against what was mailed"
    assert notify.lines(nina) == ["Mon 1 Mar 2027: 09:00-13:00 (was 08:00-12:00)"]


def _three(world):
    u = world["user"]
    people = [make_person(first_name=n, team=world["team"]) for n in ("Ann", "Bea", "Cal")]
    for p in people:
        entries.set_cell_text(u, p, MON, "08:00-12:00")
    return u, people


def test_a_batch_is_sent_on_one_connection(world, monkeypatch):
    u, people = _three(world)
    opened, used = [], []
    real_get = notify.get_connection

    def get_connection(*a, **kw):
        opened.append(real_get(*a, **kw))
        return opened[-1]

    real_send = messaging.send_mail

    def spy(*a, connection=None, **kw):
        used.append(connection)
        return real_send(*a, connection=connection, **kw)

    monkeypatch.setattr(notify, "get_connection", get_connection)
    monkeypatch.setattr("messaging.services.send_mail", spy)
    out = notify.send(u, [p.pk for p in people], BASE)
    assert out["sent"] == people and len(mail.outbox) == 3
    assert len(opened) == 1 and used == [opened[0]] * 3


def test_a_relay_failure_fails_the_rest_of_the_batch_without_trying_them(world, monkeypatch):
    import smtplib
    u, people = _three(world)
    calls = []

    def down(*a, **kw):
        calls.append(1)
        raise smtplib.SMTPServerDisconnected("gone")

    monkeypatch.setattr("messaging.services.send_mail", down)
    out = notify.send(u, [p.pk for p in people], BASE)
    assert out["failed"] == people and out["sent"] == [] and len(calls) == 1
    assert DayChange.objects.count() == 3


def test_a_relay_that_cannot_be_reached_is_not_tried_for_anyone(world, monkeypatch):
    u, people = _three(world)

    class Refusing:
        def open(self):
            raise OSError("connection refused")

        def close(self):
            pass

    sent = []
    monkeypatch.setattr(notify, "get_connection", lambda *a, **kw: Refusing())
    monkeypatch.setattr("messaging.services.send_mail", lambda *a, **kw: sent.append(1))
    out = notify.send(u, [p.pk for p in people], BASE)
    assert out["failed"] == people and not sent and DayChange.objects.count() == 3


def test_a_refused_recipient_does_not_stop_the_batch(world, monkeypatch):
    import smtplib
    u, people = _three(world)
    calls = []

    def first_refused(*a, **kw):
        calls.append(1)
        if len(calls) == 1:
            raise smtplib.SMTPRecipientsRefused({"x": (550, b"no")})

    monkeypatch.setattr("messaging.services.send_mail", first_refused)
    out = notify.send(u, [p.pk for p in people], BASE)
    assert out["failed"] == people[:1] and out["sent"] == people[1:] and len(calls) == 3


def test_with_no_mail_relay_nothing_is_tried_and_the_changes_are_kept(world, settings):
    from messaging.models import Outbox
    settings.EMAIL_HOST = ""
    u, nina = world["user"], world["nina"]
    entries.set_cell_text(u, nina, MON, "08:00-12:00")
    out = notify.send(u, [nina.pk], BASE)
    assert out["failed"] == [nina] and not mail.outbox and DayChange.objects.count() == 1
    assert Outbox.objects.get().error == "mail not configured"
