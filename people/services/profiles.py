"""Every write to a person's typed fields and allowances (spec, sections 3
and 6). Each change is audited per field; an allowance that already
exists needs a typed reason to change (LEAVE-31)."""

from datetime import date
from decimal import Decimal

from django.utils import timezone

from people.models import Allowance
from people.services import audit

DISPLAY_FIELDS = ("job_title", "name_colour", "display_order", "display_on_rota",
                  "show_to_other_staff", "can_see_other_staff")


def leave_years(today=None):
    today = today or timezone.localdate()
    return [date(today.year, 1, 1), date(today.year + 1, 1, 1)]


def _apply(actor, person, fields, note=""):
    changes = {}
    for name, after in fields.items():
        before = getattr(person, name)
        if before != after:
            changes[name] = (before, after)
            setattr(person, name, after)
    if changes:
        person.save(update_fields=list(changes))
    return audit.record(actor, person, changes, note=note)


def update_display(actor, person, **fields):
    unknown = set(fields) - set(DISPLAY_FIELDS)
    if unknown:
        raise ValueError(f"not display fields: {sorted(unknown)}")
    return _apply(actor, person, fields)


def update_hours(actor, person, weekly_hours, days_per_week):
    if person.is_gp:
        raise ValueError("a GP's sessions come from the GP rota")
    weekly_hours = Decimal(weekly_hours).quantize(Decimal("0.01")) if weekly_hours is not None else None
    return _apply(actor, person, {"weekly_hours": weekly_hours, "days_per_week": days_per_week})


def set_allowance(actor, person, leave_year, annual_hours, bank_holiday_hours, note=""):
    annual_hours = Decimal(annual_hours).quantize(Decimal("0.01"))
    bank_holiday_hours = Decimal(bank_holiday_hours).quantize(Decimal("0.01"))
    allowance = Allowance.objects.filter(person=person, leave_year=leave_year).first()
    if allowance is None:
        allowance = Allowance.objects.create(person=person, leave_year=leave_year,
                                             annual_hours=annual_hours,
                                             bank_holiday_hours=bank_holiday_hours)
        return audit.record(actor, allowance, {"annual_hours": ("", str(annual_hours)),
                                               "bank_holiday_hours": ("", str(bank_holiday_hours))},
                            note=note or f"allowance set for {leave_year.year}")
    changes = {}
    for field, after in (("annual_hours", annual_hours), ("bank_holiday_hours", bank_holiday_hours)):
        before = getattr(allowance, field)
        if before != after:
            changes[field] = (before, after)
    if not changes:
        return []
    if not note.strip():
        raise ValueError("A reason is needed to change an allowance that is already set")
    for field, (_, after) in changes.items():
        setattr(allowance, field, after)
    allowance.save(update_fields=list(changes))
    return audit.record(actor, allowance, changes, note=note.strip())


NOTES_BEFORE = "(notes)"
NOTES_AFTER = "(notes changed)"


def set_notes(actor, person, notes):
    """Notes are audited as changed, by whom and when, but never their text.
    The Activity log is scoped by access.managed_people, which includes a
    manager's own person, so a lead nurse would otherwise read what was
    written about her (ACC-04: the person never sees their notes)."""
    before = person.notes
    if before == notes:
        return []
    person.notes = notes
    person.save(update_fields=["notes"])
    return audit.record(actor, person, {"notes": (NOTES_BEFORE if before else "", NOTES_AFTER)})
