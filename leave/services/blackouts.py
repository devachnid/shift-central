from django.core.exceptions import PermissionDenied
from django.db.models import Q

from leave.models import Blackout
from people.services import access, audit


def blocks(person, day):
    rows = Blackout.objects.filter(first_day__lte=day, last_day__gte=day)
    if person.team_id:
        rows = rows.filter(Q(teams__isnull=True) | Q(teams=person.team_id))
    else:
        rows = rows.filter(teams__isnull=True)
    return rows.exists()


def _manager(user):
    if not access.is_manager(user):
        raise PermissionDenied("managers only")


def add(user, first, last, teams, note=""):
    _manager(user)
    if first > last:
        raise ValueError("The last day is before the first")
    row = Blackout.objects.create(first_day=first, last_day=last, note=(note or "")[:120])
    row.teams.set(teams)
    audit.record(user, row, {"blackout": ("", f"{first}..{last} {note}".strip())})
    return row


def update(user, row, first, last, teams, note=""):
    _manager(user)
    if first > last:
        raise ValueError("The last day is before the first")
    before = f"{row.first_day}..{row.last_day} {row.note}".strip()
    row.first_day, row.last_day, row.note = first, last, (note or "")[:120]
    row.save()
    row.teams.set(teams)
    audit.record(user, row, {"blackout": (before, f"{first}..{last} {note}".strip())})
    return row


def remove(user, row):
    _manager(user)
    audit.record(user, row, {"blackout": (f"{row.first_day}..{row.last_day} {row.note}".strip(), "")})
    row.delete()
