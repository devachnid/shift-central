"""The admin shows people's data for setup and repair. Every edit is on the
app's own pages, through the services, so it is audited."""

import pytest

from tests.factories import make_person

pytestmark = pytest.mark.django_db


def test_a_person_is_shown_read_only_in_the_admin(root_client):
    p = make_person()
    body = root_client.get(f"/admin/people/person/{p.pk}/change/").content.decode()
    assert 'name="job_title"' not in body


@pytest.mark.parametrize("model", ["allowance", "teammanager", "department", "syncrun"])
def test_the_admin_cannot_add_rows_to_the_audited_models(root_client, model):
    assert root_client.get(f"/admin/people/{model}/add/").status_code == 403


def test_a_person_who_has_left_can_still_be_deleted_in_the_admin(root_client):
    p = make_person()
    assert root_client.get(f"/admin/people/person/{p.pk}/delete/").status_code == 200


def test_the_superuser_deletes_a_person_with_an_allowance_and_a_grant(root_client):
    from datetime import date
    from decimal import Decimal

    from people.models import Allowance, Person, TeamManager
    from tests.factories import make_team, make_team_manager
    p = make_person()
    Allowance.objects.create(person=p, leave_year=date(2026, 1, 1), annual_hours=Decimal("187.5"),
                             bank_holiday_hours=Decimal("60"))
    make_team_manager(p, make_team("Nursing"))
    r = root_client.post(f"/admin/people/person/{p.pk}/delete/", {"post": "yes"})
    assert r.status_code == 302
    assert not Person.objects.filter(pk=p.pk).exists()
    assert not Allowance.objects.exists() and not TeamManager.objects.exists()


@pytest.mark.parametrize("model", ["allowance", "teammanager"])
def test_allowances_and_grants_stay_read_only_in_the_admin(root_client, model):
    from datetime import date
    from decimal import Decimal

    from people.models import Allowance
    from tests.factories import make_team, make_team_manager
    p = make_person()
    row = (Allowance.objects.create(person=p, leave_year=date(2026, 1, 1), annual_hours=Decimal("1"),
                                    bank_holiday_hours=Decimal("1"))
           if model == "allowance" else make_team_manager(p, make_team("Nursing")))
    body = root_client.get(f"/admin/people/{model}/{row.pk}/change/").content.decode()
    assert 'name="_save"' not in body
