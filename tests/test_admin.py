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


# --- the leave admin is read-only (S17): the pages are the way to edit, through the audited services

def _leave_rows():
    from datetime import date

    from leave.models import BankHoliday, LeaveSetting, LeaveType
    from leave.services import settings as leave_settings
    from tests.factories import make_booking
    leave_settings.get()
    return {"leavetype": LeaveType.objects.first(), "bankholiday": BankHoliday.objects.first(),
            "leavesetting": LeaveSetting.objects.first(), "booking": make_booking(make_person(), date(2027, 3, 1))}


@pytest.mark.parametrize("model", ["leavetype", "bankholiday", "leavesetting", "booking"])
def test_the_leave_admin_cannot_add_change_or_delete(root_client, model):
    row = _leave_rows()[model]
    assert root_client.get(f"/admin/leave/{model}/add/").status_code == 403
    page = root_client.get(f"/admin/leave/{model}/{row.pk}/change/")
    assert page.status_code == 200 and 'name="_save"' not in page.content.decode()
    assert root_client.get(f"/admin/leave/{model}/{row.pk}/delete/").status_code == 403
    assert root_client.post(f"/admin/leave/{model}/{row.pk}/change/", {"name": "x"}).status_code == 403


def test_an_allowance_row_cannot_be_deleted_on_its_own(root_client):
    """R-A4: deleting a year's first row would turn set_allowance's next
    edit into an edit of the hours-change row. The row still goes with its
    person (the test above)."""
    from datetime import date
    from decimal import Decimal

    from people.models import Allowance
    row = Allowance.objects.create(person=make_person(), leave_year=date(2026, 1, 1), annual_hours=Decimal("187.5"),
                                   bank_holiday_hours=Decimal("60"))
    assert root_client.get(f"/admin/people/allowance/{row.pk}/delete/").status_code == 403
    assert root_client.post(f"/admin/people/allowance/{row.pk}/delete/", {"post": "yes"}).status_code == 403
    r = root_client.post("/admin/people/allowance/", {"action": "delete_selected", "_selected_action": [row.pk], "post": "yes"})
    assert Allowance.objects.filter(pk=row.pk).exists() and r.status_code in (200, 302)
