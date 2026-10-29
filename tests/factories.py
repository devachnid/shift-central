"""Short builders for the suite. Every default is a plausible receptionist."""

from datetime import date

from accounts.models import User
from people.models import Person, Team, TeamManager

_next_id = iter(range(1000, 100000))


def make_team(name="Reception", **kw):
    team, _ = Team.objects.get_or_create(name=name, defaults=kw)
    return team


def make_person(**kw):
    kw.setdefault("hr_employee_id", next(_next_id))
    kw.setdefault("first_name", "Sam")
    kw.setdefault("last_name", "Patel")
    kw.setdefault("name", f"{kw['first_name']} {kw['last_name']}")
    kw.setdefault("email", f"{kw['first_name'].lower()}.{kw['hr_employee_id']}@example.org")
    if "team" not in kw:
        kw["team"] = make_team()
    kw.setdefault("start_date", date(2024, 1, 8))
    return Person.objects.create(**kw)


def make_user_for(person, **kw):
    user = User.objects.create_user(email=person.email, **kw)
    person.user = user
    person.save(update_fields=["user"])
    return user


def make_team_manager(person, team, granted_by=None):
    return TeamManager.objects.create(person=person, team=team, granted_by=granted_by)
