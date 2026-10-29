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
