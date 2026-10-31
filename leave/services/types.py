from django.core.exceptions import PermissionDenied

from leave.models import LeaveType
from people.services import access, audit

EDITABLE = ("name", "colour", "requestable", "paid_choice", "default_paid", "display_order", "draws_from", "on_payroll", "archived")
FIXED_ON_SEEDED = ("draws_from", "on_payroll")


def _manager(user):
    if not access.is_manager(user):
        raise PermissionDenied("managers only")


def add(user, name, colour, draws_from, requestable, paid_choice, on_payroll, default_paid=True):
    _manager(user)
    row = LeaveType.objects.create(name=name.strip()[:60], colour=colour, draws_from=draws_from, requestable=requestable,
                                   paid_choice=paid_choice, on_payroll=on_payroll, default_paid=default_paid,
                                   display_order=(LeaveType.objects.order_by("-display_order").values_list("display_order", flat=True).first() or 0) + 10)
    audit.record(user, row, {"name": ("", row.name)})
    return row


def update(user, row, **fields):
    _manager(user)
    unknown = set(fields) - set(EDITABLE)
    if unknown:
        raise ValueError(f"not editable: {sorted(unknown)}")
    if row.seeded and any(k in fields and fields[k] != getattr(row, k) for k in FIXED_ON_SEEDED):
        raise ValueError("A seeded type keeps what it draws from and how it reaches payroll")
    changes = {}
    for k, v in fields.items():
        before = getattr(row, k)
        if before != v:
            changes[k] = (before, v)
            setattr(row, k, v)
    if changes:
        row.save()
        audit.record(user, row, changes)
    return row


def archive(user, row):
    return update(user, row, archived=True) if not row.archived else row
