"""The open-shifts pages and their pop-ups (spec 5, section 3)."""

import json
from datetime import date, time
from types import SimpleNamespace

import pytest
from django.test import Client

from leave.services import bookings
from shifts.models import Entry, OpenShift, OpenShiftClaim
from shifts.services import open_shifts
from tests.factories import make_claim, make_person, make_team, make_team_manager, make_type, make_user_for

pytestmark = pytest.mark.django_db
DAY = date(2026, 11, 9)


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")

    def staff(first, team, **kw):
        p = make_person(first_name=first, team=team)
        client = Client()
        client.force_login(make_user_for(p, **kw))
        return SimpleNamespace(person=p, client=client)

    lead = staff("Lead", reception)
    make_team_manager(lead.person, reception)
    return SimpleNamespace(reception=reception, nursing=nursing, lead=lead, sam=staff("Sam", reception),
                           nina=staff("Nina", nursing), boss=staff("Boss", reception, is_all_teams_manager=True))


def make_post(c, **kw):
    args = dict(team=c.reception, day=DAY, start=time(9), finish=time(13), audience_teams=[c.reception])
    args.update(kw)
    return open_shifts.post(c.lead.person.user, **args)


def test_the_list_shows_posts_offered_to_you_with_a_claim_button(cast):
    make_post(cast, comment="Front desk")
    body = cast.sam.client.get("/rota/open/").content.decode()
    assert "Mon 9 Nov" in body and "09:00" in body and "Front desk" in body and "Reception" in body
    assert f'/rota/open/{OpenShift.objects.get().pk}/claim/' in body
    assert "Post an open shift" not in body


def test_someone_outside_the_audience_sees_nothing(cast):
    make_post(cast)
    body = cast.nina.client.get("/rota/open/").content.decode()
    assert "Mon 9 Nov" not in body and "Nothing is open" in body


def test_a_manager_sees_the_post_action_and_the_waiting_claims(cast):
    post = make_post(cast)
    open_shifts.claim(cast.sam.person.user, post, note="Keen")
    body = cast.lead.client.get("/rota/open/").content.decode()
    assert "Post an open shift" in body and "Sam Patel" in body and "Keen" in body
    assert "/rota/open/claims/" in body


def test_staff_may_not_open_the_post_dialog_but_a_manager_may(cast):
    assert cast.sam.client.get("/rota/open/post/").status_code == 403
    assert cast.lead.client.get("/rota/open/post/").status_code == 200


def test_posting_from_the_dialog_creates_the_post_and_refreshes(cast):
    r = cast.lead.client.post("/rota/open/post/", {
        "team": cast.reception.pk, "day": "2026-11-10", "start": "09:00", "finish": "13:00", "break_minutes": "0",
        "comment": "Phones", "audience": [cast.reception.pk]})
    assert r.status_code == 200 and json.loads(r.content) == {"refresh": True}
    post = OpenShift.objects.get()
    assert post.day == date(2026, 11, 10) and post.comment == "Phones" and list(post.audience.all()) == [cast.reception]


def test_a_bad_post_shows_the_error_in_the_dialog(cast):
    r = cast.lead.client.post("/rota/open/post/", {
        "team": cast.reception.pk, "day": "2026-10-01", "start": "09:00", "finish": "13:00", "break_minutes": "0",
        "audience": [cast.reception.pk]})
    assert r.status_code == 200 and b"That day has passed" in r.content and OpenShift.objects.count() == 0


def test_the_dialog_only_offers_the_managers_own_team_as_owner(cast):
    body = cast.lead.client.get("/rota/open/post/").content.decode()
    owner = body.split('name="team"')[1].split("</select>")[0]
    assert "Reception" in owner and "Nursing" not in owner


def test_claiming_from_the_dialog(cast):
    post = make_post(cast)
    assert cast.sam.client.get(f"/rota/open/{post.pk}/claim/").status_code == 200
    r = cast.sam.client.post(f"/rota/open/{post.pk}/claim/", {"overtime": "toil", "note": "Yes please"})
    assert json.loads(r.content) == {"refresh": True}
    claim = OpenShiftClaim.objects.get()
    assert claim.person == cast.sam.person and claim.overtime == "toil" and claim.note == "Yes please"


def test_claiming_a_post_you_cannot_see_is_a_404(cast):
    post = make_post(cast)
    assert cast.nina.client.get(f"/rota/open/{post.pk}/claim/").status_code == 404
    assert cast.nina.client.post(f"/rota/open/{post.pk}/claim/", {"overtime": ""}).status_code == 404


def test_claiming_twice_shows_the_sentence(cast):
    post = make_post(cast)
    cast.sam.client.post(f"/rota/open/{post.pk}/claim/", {"overtime": ""})
    r = cast.sam.client.post(f"/rota/open/{post.pk}/claim/", {"overtime": ""})
    assert r.status_code == 200 and b"already claimed" in r.content


def test_withdrawing_your_own_claim_redirects_to_the_list(cast):
    claim = open_shifts.claim(cast.sam.person.user, make_post(cast))
    r = cast.sam.client.post(f"/rota/open/claims/{claim.pk}/withdraw/")
    assert r.status_code == 302 and r["Location"] == "/rota/open/"
    claim.refresh_from_db()
    assert claim.state == "withdrawn"
    assert cast.sam.client.get(f"/rota/open/claims/{claim.pk}/withdraw/").status_code == 405


def test_the_decide_dialog_approves_with_a_changed_overtime_choice(cast):
    claim = open_shifts.claim(cast.sam.person.user, make_post(cast), overtime="paid")
    page = cast.lead.client.get(f"/rota/open/claims/{claim.pk}/decide/").content.decode()
    assert "Sam Patel" in page and "Approve" in page and "Decline" in page
    r = cast.lead.client.post(f"/rota/open/claims/{claim.pk}/decide/", {"action": "approve", "overtime": ""})
    assert json.loads(r.content) == {"refresh": True}
    assert Entry.objects.get(person=cast.sam.person, day=DAY).overtime == ""


def test_the_decide_dialog_declines(cast):
    claim = open_shifts.claim(cast.sam.person.user, make_post(cast))
    r = cast.lead.client.post(f"/rota/open/claims/{claim.pk}/decide/", {"action": "decline", "overtime": ""})
    assert json.loads(r.content) == {"refresh": True}
    claim.refresh_from_db()
    assert claim.state == "declined"


def test_staff_and_other_teams_cannot_open_the_decide_dialog(cast):
    claim = open_shifts.claim(cast.sam.person.user, make_post(cast))
    assert cast.sam.client.get(f"/rota/open/claims/{claim.pk}/decide/").status_code == 404
    assert cast.nina.client.post(f"/rota/open/claims/{claim.pk}/decide/", {"action": "approve", "overtime": ""}).status_code == 404


def test_the_detail_page_is_for_the_owning_managers_only(cast):
    post = make_post(cast)
    open_shifts.claim(cast.sam.person.user, post)
    assert cast.lead.client.get(f"/rota/open/{post.pk}/").status_code == 200
    assert cast.boss.client.get(f"/rota/open/{post.pk}/").status_code == 200
    assert cast.sam.client.get(f"/rota/open/{post.pk}/").status_code == 404


def test_withdrawing_a_post(cast):
    post = make_post(cast)
    r = cast.lead.client.post(f"/rota/open/{post.pk}/withdraw/")
    assert r.status_code == 302
    post.refresh_from_db()
    assert post.state == "withdrawn"
    assert cast.sam.client.post(f"/rota/open/{post.pk}/withdraw/").status_code in (403, 404)


def test_the_rota_menu_has_open_shifts_for_everyone(cast):
    for who in (cast.sam, cast.lead):
        body = who.client.get("/rota/").content.decode()
        assert 'href="/rota/open/"' in body


def test_closed_posts_from_the_last_month_are_listed_apart(cast):
    post = make_post(cast)
    open_shifts.withdraw(cast.lead.person.user, post)
    body = cast.lead.client.get("/rota/open/").content.decode()
    assert "Filled and past" in body and "withdrawn" in body


def test_approving_a_claimant_on_leave_shows_the_sentence_in_the_dialog(cast):
    claim = open_shifts.claim(cast.sam.person.user, make_post(cast))
    bookings.book(cast.boss.person.user, cast.sam.person, make_type("Training"), DAY, DAY, "whole")
    r = cast.lead.client.post(f"/rota/open/claims/{claim.pk}/decide/", {"action": "approve", "overtime": ""})
    assert r.status_code == 200 and b"is on leave that day" in r.content
    assert not Entry.objects.filter(person=cast.sam.person, day=DAY).exists()


def test_a_manager_cannot_decide_their_own_claim(cast):
    own = make_claim(make_post(cast), cast.lead.person)
    r = cast.lead.client.post(f"/rota/open/claims/{own.pk}/decide/", {"action": "approve", "overtime": ""})
    assert r.status_code == 403
    own.refresh_from_db()
    assert own.state == "waiting"
