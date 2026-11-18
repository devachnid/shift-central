"""The copies of Practice HR's contracts (people.Contract): which are in
force on a day and what they add up to. The sync writes them; the profile,
the sync's weekly hours and leave's entitlement service read them here."""

from django.utils import timezone

from people.models import Contract


def in_force(contracts, day):
    return [c for c in contracts if c.from_day <= day and (c.to_day is None or c.to_day >= day)]


def weekly_hours_on(contracts, day):
    """The sum of the hours contracts in force on the day, or None when
    there is none (a GP, or a day between contracts)."""
    amounts = [c.weekly_amount for c in in_force(contracts, day) if c.unit == Contract.Unit.HOURS]
    return sum(amounts) if amounts else None


def hours_from_hr(person, today=None):
    """Whether the person's weekly hours are Practice HR's (allowance spec,
    5.4): their hours contracts in force today (on the start date, for a
    starter) add up to more than 0. Everyone else is typed here as before:
    no copied contract, bank staff whose only contract in force is for 0
    hours, someone between contracts, and a GP."""
    today = today or timezone.localdate()
    return bool(weekly_hours_on(list(person.contracts.all()), max(today, person.start_date)))
