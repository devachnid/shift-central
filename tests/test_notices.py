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
