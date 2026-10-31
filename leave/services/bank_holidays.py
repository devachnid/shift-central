from django.core.exceptions import PermissionDenied
from django.db import transaction

from leave.models import BankHoliday, LeaveType
from leave.services import bookings, costing
from leave.services.common import LeaveError
from people.models import Person
from people.services import access, audit


def _type():
    """Found by what it draws from, not its name: a manager may rename it."""
    return LeaveType.objects.get(seeded=True, draws_from=LeaveType.Account.BANK_HOLIDAY)


def add(user, day, name):
    if not access.is_manager(user):
        raise PermissionDenied("managers only")
    row, made = BankHoliday.objects.get_or_create(day=day, defaults={"name": (name or "Bank holiday")[:60]})
    if made:
        audit.record(user, row, {"day": ("", f"{day} {row.name}")})
    return row


def remove(user, day):
    if not access.is_manager(user):
        raise PermissionDenied("managers only")
    row = BankHoliday.objects.filter(day=day).first()
    if row:
        audit.record(user, row, {"day": (f"{day} {row.name}", "")})
        row.delete()


def book(user, person, day, seconds):
    """One person's bank holiday at the typed hours (LEAVE-16): a whole-day
    Bank holiday booking whose day is an override noted "bank holiday"."""
    return bookings.book(user, person, _type(), day, day, "whole", note="bank holiday", costs={day: int(seconds)})


def book_many(user, day, hours_by_person):
    booked = skipped = 0
    for pk, seconds in hours_by_person.items():
        person = Person.objects.filter(pk=pk).first()
        if person is None or not access.can_manage(user, person):
            skipped += 1
            continue
        try:
            with transaction.atomic():
                book(user, person, day, seconds)
            booked += 1
        except LeaveError:
            skipped += 1
    return booked, skipped


def suggestions(user, day):
    """[(person, suggested_seconds)] for the manager's current non-GP people, GPs after them at 0."""
    people = access.managed_people(user).current(on=day).filter(display_on_rota=True).order_by("is_gp", "team__display_order", "last_name")
    return [(p, 0 if p.is_gp else costing.suggestion(p, day)) for p in people]
