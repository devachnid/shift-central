from django.core.exceptions import PermissionDenied

from leave.models import LeaveSetting
from people.services import access, audit


def get():
    row = LeaveSetting.objects.first()
    return row or LeaveSetting.objects.create()


def _on_off(value):
    return "on" if value else "off"


def update(user, reminder_working_days, allowances_need_checking=None):
    """Any manager sets the reminder. Whether worked-out allowances wait
    for a check (allowance spec, 7.6) is an all-teams manager's; None
    leaves it as it is."""
    if not access.is_manager(user):
        raise PermissionDenied("managers only")
    row = get()
    changes = {}
    if row.reminder_working_days != reminder_working_days:
        changes["reminder_working_days"] = (row.reminder_working_days, reminder_working_days)
        row.reminder_working_days = reminder_working_days
    if allowances_need_checking is not None and row.allowances_need_checking != allowances_need_checking:
        if not access.is_all_teams(user):
            raise PermissionDenied("all-teams managers only")
        changes["allowances_need_checking"] = (_on_off(row.allowances_need_checking), _on_off(allowances_need_checking))
        row.allowances_need_checking = allowances_need_checking
    if changes:
        row.save(update_fields=list(changes))
        audit.record(user, row, changes)
    return row
