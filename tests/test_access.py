"""The one place that answers who may manage whom (spec, section 2)."""

import pytest
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory

from people.models import Team
from people.services import access
from tests.factories import make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(db):
    nursing, reception = make_team("Nursing"), make_team("Reception")
    nurse = make_person(team=nursing)
    lead = make_person(team=nursing, first_name="Lead")
    receptionist = make_person(team=reception)
    boss = make_person(team=make_team("Management"), first_name="Boss")
    users = {
        "u_nurse": make_user_for(nurse), "u_lead": make_user_for(lead),
        "u_receptionist": make_user_for(receptionist),
        "u_boss": make_user_for(boss, is_all_teams_manager=True),
    }
    make_team_manager(lead, nursing)
    return {"nursing": nursing, "reception": reception, "nurse": nurse, "lead": lead,
            "receptionist": receptionist, "boss": boss, **users}


def test_roles(world):
    assert access.role(world["u_nurse"]) == "staff"
    assert access.role(world["u_lead"]) == "team"
    assert access.role(world["u_boss"]) == "all"


def test_managed_teams(world):
    assert list(access.managed_teams(world["u_nurse"])) == []
    assert list(access.managed_teams(world["u_lead"])) == [world["nursing"]]
    assert set(access.managed_teams(world["u_boss"])) == set(Team.objects.all())


def test_can_manage_follows_the_persons_team(world):
    assert access.can_manage(world["u_lead"], world["nurse"])
    assert not access.can_manage(world["u_lead"], world["receptionist"])
    assert access.can_manage(world["u_boss"], world["receptionist"])
    assert not access.can_manage(world["u_nurse"], world["nurse"]), "nobody manages themselves"


def test_a_lead_manages_their_own_team_but_is_self_for_themselves(world):
    assert access.is_self(world["u_lead"], world["lead"])
    assert not access.can_manage(world["u_lead"], world["lead"])


def test_managed_people(world):
    assert set(access.managed_people(world["u_lead"])) == {world["nurse"], world["lead"]}
    assert access.managed_people(world["u_boss"]).count() == 4
    assert not access.managed_people(world["u_nurse"]).exists()


def test_a_person_with_no_team_is_managed_by_all_teams_managers_only(world):
    loose = make_person(team=None)
    assert access.can_manage(world["u_boss"], loose) and not access.can_manage(world["u_lead"], loose)


def test_the_decorators(world):
    rf = RequestFactory()

    @access.manager_required
    def managers_only(request):
        return HttpResponse("ok")

    @access.all_teams_required
    def all_teams_only(request):
        return HttpResponse("ok")

    for user, m, a in ((world["u_nurse"], 403, 403), (world["u_lead"], 200, 403),
                       (world["u_boss"], 200, 200)):
        req = rf.get("/")
        req.user = user
        if m == 200:
            assert managers_only(req).status_code == 200
        else:
            with pytest.raises(PermissionDenied):
                managers_only(req)
        if a == 200:
            assert all_teams_only(req).status_code == 200
        else:
            with pytest.raises(PermissionDenied):
                all_teams_only(req)


def test_a_user_with_no_person_is_staff_and_manages_nobody(staff_user):
    assert access.role(staff_user) == "staff"
    assert not access.managed_people(staff_user).exists()
