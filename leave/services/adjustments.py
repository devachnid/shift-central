from django.core.exceptions import PermissionDenied
from django.db import transaction

from leave.models import Adjustment
from leave.services import hours
from people.services import access, audit


def add(user, person, year, account, seconds, reason):
    if not access.can_manage(user, person):
        raise PermissionDenied("you don't manage this person")
    if account not in ("annual", "bank_holiday", "toil"):
        raise ValueError("unknown account")
    if not (reason or "").strip():
        raise ValueError("A reason is needed")
    with transaction.atomic():
        row = Adjustment.objects.create(person=person, leave_year=year, account=account, seconds=int(seconds), reason=reason.strip()[:300], actor=user)
        audit.record_as(user, "leave.adjustment", person.pk, {f"{account} {year.year}": ("", hours.fmt(row.seconds))}, note=row.reason)
    return row
