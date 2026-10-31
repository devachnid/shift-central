from django.core.exceptions import PermissionDenied

from leave.models import LeaveSetting
from people.services import access, audit


def get():
    row = LeaveSetting.objects.first()
    return row or LeaveSetting.objects.create()


def update(user, reminder_working_days):
    if not access.is_manager(user):
        raise PermissionDenied("managers only")
    row = get()
    before = row.reminder_working_days
    if before != reminder_working_days:
        row.reminder_working_days = reminder_working_days
        row.save(update_fields=["reminder_working_days"])
        audit.record(user, row, {"reminder_working_days": (before, reminder_working_days)})
    return row
