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


def test_a_team_manager_does_not_see_rows_to_other_managers_except_their_own(cast):
    """Privacy: a sickness-trigger email to the all-teams manager names a person
    in the manager's own team; the team lead must not read it. A row to the
    lead themself, and to staff, stays visible."""
    to_staff, to_lead, to_boss = row(cast.sam), row(cast.lead), row(cast.boss, subject="Nina has reached Trigger 1")
    other_lead = make_person(first_name="Other", team=cast.sam.team)
    make_team_manager(other_lead, cast.sam.team)
    to_other_lead = row(other_lead)
    assert set(outbox.scope(cast.lead.user)) == {to_staff, to_lead}
    assert to_boss not in outbox.scope(cast.lead.user) and to_other_lead not in outbox.scope(cast.lead.user)
    assert set(outbox.scope(cast.boss.user)) == {to_staff, to_lead, to_boss, to_other_lead}
    assert outbox.scope(cast.sam.user).count() == 0
    assert set(outbox.rows(cast.lead.user, person=cast.boss)) == set()


def test_the_failure_count_does_not_count_rows_to_other_managers(cast):
    row(cast.boss, "failed", error="OSError")
    row(cast.sam, "failed", error="OSError")
    assert outbox.failure_count(cast.lead.user) == 1
    assert outbox.failure_count(cast.boss.user) == 2
