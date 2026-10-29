import pytest
from django.test import Client

from people.models import AuditEntry, Department
from people.services import departments
from tests.factories import make_person, make_user_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def boss_client(db):
    c = Client()
    c.force_login(make_user_for(make_person(), is_all_teams_manager=True))
    return c


def test_the_page_lists_departments_with_colours_for_managers(boss_client):
    body = boss_client.get("/departments/").content.decode()
    assert "Reception AG" in body and "#2F6FB3" in body and "Add department +" in body


def test_staff_cannot_open_the_page(db):
    c = Client()
    c.force_login(make_user_for(make_person()))
    assert c.get("/departments/").status_code == 403


def test_add_and_edit_through_the_dialog(boss_client):
    r = boss_client.post("/departments/add/", {"name": "Flu clinic", "colour": "#2A7F62", "display_order": "5"})
    assert r.status_code == 200 and r["Content-Type"].startswith("application/json")
    d = Department.objects.get(name="Flu clinic")
    assert d.colour == "#2A7F62" and d.display_order == 5
    r = boss_client.post(f"/departments/{d.pk}/edit/", {"name": "Flu clinic", "colour": "#C94C4C",
                                                         "display_order": "5", "archived": "on"})
    assert r.status_code == 200
    d.refresh_from_db()
    assert d.colour == "#C94C4C" and d.archived
    assert {a.field for a in AuditEntry.objects.filter(model="people.department", object_id=d.pk)} == {
        "created", "colour", "archived"}


def test_a_duplicate_name_is_refused_in_the_form(boss_client):
    r = boss_client.post("/departments/add/", {"name": "Pharmacy", "colour": "#2A7F62", "display_order": "5"})
    assert r.status_code == 200 and "already exists" in r.content.decode()


def test_archived_departments_are_listed_apart(boss_client):
    d = Department.objects.get(name="Scanning")
    departments.update(None, d, archived=True)
    body = boss_client.get("/departments/").content.decode()
    assert body.index("Archived") < body.index("Scanning")
