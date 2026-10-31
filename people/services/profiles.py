"""Every write to a person's typed fields and allowances (spec, sections 3
and 6). Each change is audited per field; an allowance that already
exists needs a typed reason to change (LEAVE-31)."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from leave.services import years
from people.models import Allowance
from people.services import access, audit

DISPLAY_FIELDS = ("job_title", "name_colour", "display_order", "display_on_rota",
                  "show_to_other_staff", "can_see_other_staff")


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


def update_hours(actor, person, weekly_hours, days_per_week, note=""):
    if person.is_gp:
        raise ValueError("a GP's sessions come from the GP rota")
    weekly_hours = Decimal(weekly_hours).quantize(Decimal("0.01")) if weekly_hours is not None else None
    return _apply(actor, person, {"weekly_hours": weekly_hours, "days_per_week": days_per_week}, note=note)


def update_leave_year_start(actor, person, text):
    """The month and day the person's leave year starts (LEAVE-03). It cannot
    move once the person has an allowance or a live booking: those are filed
    under the years the old date made."""
    from leave.models import Booking
    try:
        years.parse_start(text)
    except ValueError:
        raise ValueError("That is not a date; type the month and day as MM-DD, e.g. 04-01") from None
    if text == person.leave_year_start:
        return []
    if person.allowances.exists() or Booking.objects.filter(person=person).exclude(status__in=("declined", "cancelled")).exists():
        raise ValueError(f"{person.name} already has allowances or bookings; the leave year cannot move")
    return _apply(actor, person, {"leave_year_start": text})


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


def reorder(actor, ids):
    """The grid's "sort staff": display_order 10, 20, 30… for the ids in the
    order given; people not listed keep theirs. Managers only. An id the
    actor may not manage (another team's person, or the actor themselves,
    as everywhere in the Foundation) is skipped, not refused: the numbering
    counts only the people kept. One transaction, so a failure leaves the
    order as it was."""
    if not access.is_manager(actor):
        raise PermissionDenied("only a manager can sort the staff")
    ids = [int(pk) for pk in ids]
    from people.models import Person
    people = {p.pk: p for p in Person.objects.filter(pk__in=ids)}
    kept = [people[pk] for pk in dict.fromkeys(ids)
            if pk in people and access.can_manage(actor, people[pk])]
    with transaction.atomic():
        for n, person in enumerate(kept, start=1):
            _apply(actor, person, {"display_order": n * 10})


def add_hours_change(actor, person, from_day, weekly_hours, days_per_week, annual_hours, bank_holiday_hours, note):
    """A dated change of contract (PAT-06, LEAVE-12): a second Allowance row
    for the year from `from_day`, carrying the new full-year figures and the
    new weekly hours and days. The year's first row must exist; the first
    day itself is set_allowance's. When the day has arrived the hours go on
    the person now; otherwise apply_due_hours_changes() copies them on the day."""
    if not note or not note.strip():
        raise ValueError("A reason is needed for an hours change")
    year = years.year_of(person, from_day)
    if from_day == year:
        raise ValueError("Set the year's allowance on the Pay & time off tab; a change starts after the year's first day")
    if not Allowance.objects.filter(person=person, leave_year=year, from_day=year).exists():
        raise ValueError(f"Set the {year.year} allowance first")
    if Allowance.objects.filter(person=person, leave_year=year, from_day=from_day).exists():
        raise ValueError("There is already a change from that day")
    weekly_hours = Decimal(weekly_hours).quantize(Decimal("0.01")) if weekly_hours is not None else None
    copy_now = from_day <= timezone.localdate() and not person.is_gp and weekly_hours is not None
    with transaction.atomic():
        row = Allowance.objects.create(person=person, leave_year=year, from_day=from_day,
                                       annual_hours=Decimal(annual_hours).quantize(Decimal("0.01")),
                                       bank_holiday_hours=Decimal(bank_holiday_hours).quantize(Decimal("0.01")),
                                       weekly_hours=weekly_hours, days_per_week=days_per_week,
                                       hours_applied=copy_now)
        audit.record(actor, row, {"annual_hours": ("", str(row.annual_hours)), "bank_holiday_hours": ("", str(row.bank_holiday_hours)),
                                  "weekly_hours": ("", str(weekly_hours or "")), "days_per_week": ("", str(days_per_week or "")),
                                  "from_day": ("", from_day.isoformat())}, note=note.strip())
        if copy_now:
            update_hours(actor, person, weekly_hours, days_per_week, note=note.strip())
    return row


def apply_due_hours_changes(today=None):
    """Copy each person's latest due hours change onto the person, once. A
    change is due from its day and is marked hours_applied when copied, so
    a manager's later edit to the profile is not overwritten by the next
    sync. Run by hr_sync after each good run; returns how many people changed."""
    today = today or timezone.localdate()
    due = {}
    for row in (Allowance.objects.filter(from_day__lte=today, weekly_hours__isnull=False, hours_applied=False)
                .select_related("person").order_by("from_day", "pk")):
        due.setdefault(row.person_id, []).append(row)
    changed = 0
    for rows in due.values():
        latest = rows[-1]
        person = latest.person
        if person.is_gp:
            continue
        with transaction.atomic():
            if person.weekly_hours != latest.weekly_hours or person.days_per_week != latest.days_per_week:
                update_hours(None, person, latest.weekly_hours, latest.days_per_week, note="hours change due")
                changed += 1
            Allowance.objects.filter(pk__in=[r.pk for r in rows]).update(hours_applied=True)
    return changed
