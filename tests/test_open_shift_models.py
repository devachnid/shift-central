"""Open shifts: the two tables and their rules (spec 5, section 2)."""

from datetime import date, time

import pytest
from django.db import IntegrityError, transaction

from shifts.models import OpenShift, OpenShiftClaim
from tests.factories import make_claim, make_open_shift, make_person, make_team

pytestmark = pytest.mark.django_db


def test_a_new_post_is_open_and_is_for_its_audience_teams():
    nursing = make_team("Nursing")
    post = make_open_shift(day=date(2026, 11, 9))
    post.audience.add(nursing)
    assert post.state == OpenShift.State.OPEN and list(post.audience.all()) == [nursing]
    assert post.everyone is False and post.filled_by is None and post.entry is None


def test_a_post_whose_day_has_passed_is_expired_not_closed():
    assert make_open_shift(day=date(2026, 11, 1)).expired          # the pin is 2 Nov 2026
    assert not make_open_shift(day=date(2026, 11, 2)).expired      # today is not expired
    assert not make_open_shift(day=date(2026, 11, 3)).expired


def test_a_shift_needs_a_later_finish():
    with pytest.raises(IntegrityError), transaction.atomic():
        make_open_shift(start=time(12), finish=time(12))


def test_one_waiting_claim_per_person_but_a_withdrawn_one_may_be_remade():
    post, sam = make_open_shift(), make_person()
    first = make_claim(post, sam)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_claim(post, sam)
    first.state = OpenShiftClaim.State.WITHDRAWN
    first.save()
    assert make_claim(post, sam).state == OpenShiftClaim.State.WAITING


def test_claims_hang_off_the_post_and_the_person():
    post, sam = make_open_shift(), make_person()
    claim = make_claim(post, sam, overtime="toil", note="Happy to")
    assert list(post.claims.all()) == [claim] and list(sam.open_shift_claims.all()) == [claim]
    assert claim.overtime == "toil" and claim.decided_by is None and claim.decided_at is None
