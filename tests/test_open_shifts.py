"""Open shifts: posting, claiming, approving (spec 5, section 3)."""

from datetime import date, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.exceptions import PermissionDenied

from leave.services import bookings
from messaging.models import Outbox
from people.models import AuditEntry
from shifts.models import DayChange, Entry, OpenShift, OpenShiftClaim
from shifts.services import open_shifts
from shifts.services.open_shifts import OpenShiftError
from tests.factories import make_entry, make_person, make_team, make_team_manager, make_type, make_user_for

pytestmark = pytest.mark.django_db
DAY = date(2026, 11, 9)      # the Monday after the pinned Monday 2 Nov 2026


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")

    def staff(first, team, **user_kw):
        p = make_person(first_name=first, team=team, start_date=date(2020, 1, 6), weekly_hours=Decimal("37.5"), days_per_week=5)
        make_user_for(p, **user_kw)
        return p

    lead = staff("Lead", reception)
    make_team_manager(lead, reception)
    nurse_lead = staff("Nurse", nursing)
    make_team_manager(nurse_lead, nursing)
    return SimpleNamespace(
        reception=reception, nursing=nursing, lead=lead, nurse_lead=nurse_lead,
        boss=staff("Boss", reception, is_all_teams_manager=True),
        sam=staff("Sam", reception), ann=staff("Ann", reception), nina=staff("Nina", nursing))


def post(c, **kw):
    args = dict(team=c.reception, day=DAY, start=time(9), finish=time(13), break_minutes=0, department=None,
                comment="", everyone=False, audience_teams=[c.reception])
    args.update(kw)
    return open_shifts.post(c.lead.user, **args)


def subjects(person):
    return list(Outbox.objects.filter(to_person=person).values_list("subject", flat=True))


# --- posting -------------------------------------------------------------------

def test_a_manager_of_the_owning_team_posts_and_the_audience_is_told(cast):
    shift = post(cast, comment="Secret comment")
    assert shift.state == "open" and list(shift.audience.all()) == [cast.reception]
    assert subjects(cast.sam) == ["Open shift: Mon 9 Nov, 09:00–13:00"]
    assert subjects(cast.ann) == subjects(cast.sam)
    assert subjects(cast.nina) == [] and subjects(cast.lead) == []        # other team; the poster
    body = Outbox.objects.get(to_person=cast.sam).body
    assert "Secret comment" not in body and "/rota/open/" in body


def test_everyone_tells_every_current_person_with_a_login(cast):
    shift = post(cast, everyone=True, audience_teams=[])
    assert shift.everyone and shift.audience.count() == 0
    assert subjects(cast.nina) and subjects(cast.sam)


def test_only_a_manager_of_the_owning_team_may_post(cast):
    with pytest.raises(PermissionDenied):
        open_shifts.post(cast.nurse_lead.user, cast.reception, DAY, time(9), time(13), audience_teams=[cast.reception])
    with pytest.raises(PermissionDenied):
        open_shifts.post(cast.sam.user, cast.reception, DAY, time(9), time(13), audience_teams=[cast.reception])
    assert open_shifts.post(cast.boss.user, cast.nursing, DAY, time(9), time(13), audience_teams=[cast.nursing])


@pytest.mark.parametrize("kw, message", [
    ({"day": date(2026, 11, 1)}, "passed"),
    ({"start": time(13), "finish": time(9)}, "later"),
    ({"break_minutes": 20}, "break"),
    ({"audience_teams": []}, "who is offered"),
])
def test_a_bad_post_is_refused_with_a_sentence(cast, kw, message):
    with pytest.raises(OpenShiftError, match=message):
        post(cast, **kw)
    assert OpenShift.objects.count() == 0


def test_posting_is_audited(cast):
    post(cast)
    assert AuditEntry.objects.filter(model="shifts.openshift", field="posted").count() == 1


# --- claiming ------------------------------------------------------------------

def test_an_audience_member_claims_and_the_owning_managers_are_told(cast):
    shift = post(cast, comment="x")
    claim = open_shifts.claim(cast.sam.user, shift, overtime="toil", note="Happy to")
    assert claim.state == "waiting" and claim.overtime == "toil" and claim.person == cast.sam
    assert "Sam Patel has claimed an open shift" in subjects(cast.lead)
    assert "Sam Patel has claimed an open shift" in subjects(cast.boss)
    assert subjects(cast.sam) == ["Open shift: Mon 9 Nov, 09:00–13:00"]     # not told of their own claim
    assert all("Happy to" not in b for b in Outbox.objects.values_list("body", flat=True))


def test_someone_outside_the_audience_cannot_claim(cast):
    shift = post(cast)
    with pytest.raises(PermissionDenied):
        open_shifts.claim(cast.nina.user, shift)


def test_one_waiting_claim_each_and_a_withdrawn_one_can_be_remade(cast):
    shift = post(cast)
    claim = open_shifts.claim(cast.sam.user, shift)
    with pytest.raises(OpenShiftError, match="already"):
        open_shifts.claim(cast.sam.user, shift)
    open_shifts.withdraw_claim(cast.sam.user, claim)
    assert OpenShiftClaim.objects.get(pk=claim.pk).state == "withdrawn"
    assert open_shifts.claim(cast.sam.user, shift).state == "waiting"


def test_nobody_can_withdraw_someone_elses_claim(cast):
    claim = open_shifts.claim(cast.sam.user, post(cast))
    with pytest.raises(PermissionDenied):
        open_shifts.withdraw_claim(cast.ann.user, claim)


def test_a_filled_or_withdrawn_post_cannot_be_claimed(cast, today):
    shift = post(cast)
    open_shifts.withdraw(cast.lead.user, shift)
    with pytest.raises(OpenShiftError, match="no longer open"):
        open_shifts.claim(cast.sam.user, shift)
    again = post(cast)
    today(DAY + timedelta(days=1))
    with pytest.raises(OpenShiftError, match="no longer open"):      # expired
        open_shifts.claim(cast.sam.user, again)


def test_an_invalid_overtime_choice_is_refused(cast):
    with pytest.raises(OpenShiftError, match="Overtime"):
        open_shifts.claim(cast.sam.user, post(cast), overtime="gold")


# --- approving -----------------------------------------------------------------

def test_approving_puts_the_shift_on_the_claimants_rota_beside_their_own(cast):
    make_entry(cast.sam, DAY, start=time(14), finish=time(18))
    shift = post(cast, comment="Cover", break_minutes=0)
    claim = open_shifts.claim(cast.sam.user, shift, overtime="paid")
    open_shifts.approve(cast.lead.user, claim)
    rows = list(Entry.objects.filter(person=cast.sam, day=DAY).order_by("position"))
    assert [(e.start, e.finish, e.overtime, e.text) for e in rows] == [(time(14), time(18), "", ""), (time(9), time(13), "paid", "Cover")]
    shift.refresh_from_db()
    claim.refresh_from_db()
    assert shift.state == "filled" and shift.filled_by == cast.sam and shift.entry == rows[-1]
    assert claim.state == "approved" and claim.decided_by == cast.lead.user and claim.decided_at


def test_the_approver_may_change_the_overtime_choice(cast):
    claim = open_shifts.claim(cast.sam.user, post(cast), overtime="paid")
    open_shifts.approve(cast.lead.user, claim, overtime="")
    assert Entry.objects.get(person=cast.sam, day=DAY).overtime == ""


def test_approving_tells_the_claimant_and_the_others_it_has_gone_and_closes_their_claims(cast):
    shift = post(cast)
    first = open_shifts.claim(cast.sam.user, shift)
    second = open_shifts.claim(cast.ann.user, shift)
    open_shifts.approve(cast.lead.user, first)
    second.refresh_from_db()
    assert second.state == "closed"
    assert "Your open shift claim for Mon 9 Nov is approved" in subjects(cast.sam)
    assert "The open shift on Mon 9 Nov has been filled" in subjects(cast.ann)


def test_approving_does_not_leave_the_day_for_notify_staff(cast):
    claim = open_shifts.claim(cast.sam.user, post(cast))
    open_shifts.approve(cast.lead.user, claim)
    assert not DayChange.objects.filter(person=cast.sam).exists()
    assert AuditEntry.objects.filter(model="shifts.entry", object_id=cast.sam.pk, field="cell").exists()


def test_an_owning_team_manager_approves_a_claimant_from_another_team(cast):
    shift = post(cast, everyone=True, audience_teams=[])
    claim = open_shifts.claim(cast.nina.user, shift)
    open_shifts.approve(cast.lead.user, claim)             # Lead manages Reception, Nina is in Nursing
    assert Entry.objects.filter(person=cast.nina, day=DAY).count() == 1


def test_a_manager_of_another_team_cannot_approve_or_decline(cast):
    claim = open_shifts.claim(cast.sam.user, post(cast))
    with pytest.raises(PermissionDenied):
        open_shifts.approve(cast.nurse_lead.user, claim)
    with pytest.raises(PermissionDenied):
        open_shifts.decline(cast.nurse_lead.user, claim)
    with pytest.raises(PermissionDenied):
        open_shifts.approve(cast.sam.user, claim)


def test_a_claim_already_decided_cannot_be_decided_again(cast):
    shift = post(cast)
    first = open_shifts.claim(cast.sam.user, shift)
    second = open_shifts.claim(cast.ann.user, shift)
    open_shifts.approve(cast.lead.user, first)
    with pytest.raises(OpenShiftError, match="already been decided"):
        open_shifts.approve(cast.lead.user, first)
    with pytest.raises(OpenShiftError, match="already been decided"):
        open_shifts.approve(cast.lead.user, second)           # closed when the first was approved
    assert Entry.objects.filter(day=DAY).count() == 1


def test_approving_is_refused_on_a_whole_day_of_leave_and_changes_nothing(cast):
    bookings.book(cast.boss.user, cast.sam, make_type("Training"), DAY, DAY, "whole")
    shift = post(cast)
    claim = open_shifts.claim(cast.sam.user, shift)
    with pytest.raises(OpenShiftError, match="on leave"):
        open_shifts.approve(cast.lead.user, claim)
    claim.refresh_from_db()
    shift.refresh_from_db()
    assert claim.state == "waiting" and shift.state == "open"
    assert not Entry.objects.filter(person=cast.sam, day=DAY, start=time(9)).exists()


def test_an_overlapping_shift_only_warns(cast):
    make_entry(cast.sam, DAY, start=time(12), finish=time(16))
    claim = open_shifts.claim(cast.sam.user, post(cast))
    assert any("12:00–16:00" in w for w in open_shifts.clashes(claim))
    assert open_shifts.approve(cast.lead.user, claim).state == "approved"


def test_part_day_leave_is_named_by_clashes_and_blocks_approval_that_would_hide_the_shift(cast):
    bookings.book(cast.boss.user, cast.sam, make_type("Training"), DAY, DAY, "pm")
    shift = post(cast)
    claim = open_shifts.claim(cast.sam.user, shift)
    assert any("Training" in w for w in open_shifts.clashes(claim))
    with pytest.raises(OpenShiftError, match="on leave"):
        open_shifts.approve(cast.lead.user, claim)
    claim.refresh_from_db()
    shift.refresh_from_db()
    assert claim.state == "waiting" and shift.state == "open" and shift.entry is None
    assert not Entry.objects.filter(person=cast.sam, day=DAY, start=time(9)).exists()


def test_no_manager_decides_their_own_claim(cast):
    claim = open_shifts.claim(cast.lead.user, post(cast))        # Lead manages Reception and is in its audience
    with pytest.raises(PermissionDenied):
        open_shifts.approve(cast.lead.user, claim)
    with pytest.raises(PermissionDenied):
        open_shifts.decline(cast.lead.user, claim)
    assert OpenShiftClaim.objects.get(pk=claim.pk).state == "waiting"
    assert open_shifts.approve(cast.boss.user, claim).state == "approved"
    assert Entry.objects.filter(person=cast.lead, day=DAY).count() == 1


def test_declining_tells_the_claimant_and_leaves_the_post_open(cast):
    shift = post(cast)
    claim = open_shifts.claim(cast.sam.user, shift)
    open_shifts.decline(cast.lead.user, claim)
    claim.refresh_from_db()
    shift.refresh_from_db()
    assert claim.state == "declined" and shift.state == "open"
    assert "Your open shift claim for Mon 9 Nov was declined" in subjects(cast.sam)


def test_withdrawing_a_post_closes_its_claims_and_tells_the_claimants(cast):
    shift = post(cast)
    claim = open_shifts.claim(cast.sam.user, shift)
    open_shifts.withdraw(cast.lead.user, shift)
    claim.refresh_from_db()
    shift.refresh_from_db()
    assert shift.state == "withdrawn" and claim.state == "closed"
    assert "The open shift on Mon 9 Nov has been withdrawn" in subjects(cast.sam)
    with pytest.raises(PermissionDenied):
        open_shifts.withdraw(cast.nurse_lead.user, post(cast))


# --- who sees what ---------------------------------------------------------------

def test_visible_to(cast):
    reception_only = post(cast)
    nursing_post = open_shifts.post(cast.nurse_lead.user, cast.nursing, DAY, time(9), time(13), audience_teams=[cast.nursing])
    everyone = post(cast, everyone=True, audience_teams=[])
    seen = lambda p: set(open_shifts.visible_to(p.user))                     # noqa: E731
    assert seen(cast.sam) == {reception_only, everyone}
    assert seen(cast.nina) == {nursing_post, everyone}
    assert seen(cast.lead) == {reception_only, everyone}                     # Lead manages Reception; also in its audience
    assert seen(cast.nurse_lead) == {nursing_post, everyone}
    assert seen(cast.boss) == {reception_only, nursing_post, everyone}


def test_waiting_claims_are_those_on_posts_the_user_manages(cast):
    mine = open_shifts.claim(cast.sam.user, post(cast))
    open_shifts.claim(cast.nina.user, open_shifts.post(cast.nurse_lead.user, cast.nursing, DAY, time(9), time(13), audience_teams=[cast.nursing]))
    assert list(open_shifts.waiting_claims(cast.lead.user)) == [mine]
    assert open_shifts.waiting_claims(cast.boss.user).count() == 2
    assert open_shifts.waiting_claims(cast.sam.user).count() == 0
