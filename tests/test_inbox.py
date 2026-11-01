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
