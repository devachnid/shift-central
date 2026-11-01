"""Leave as the island reads it: one object per covered or requested day."""

from leave.models import Booking, BookingDay
from people.services import access


def _json(booking, bd, detail):
    out = {"id": booking.pk, "type": booking.type.name, "colour": booking.type.colour, "part": booking.part,
           "label": booking.label if detail else booking.type.name, "status": "pending" if booking.status == Booking.Status.PENDING else "approved"}
    if booking.part == "times":
        out["times"] = f"{booking.start:%H:%M}–{booking.finish:%H:%M}"
    if detail:
        out["description"] = booking.description
        out["paid"] = booking.paid
        out["cost"] = bd.cost_seconds if bd is not None else None
    return out


def leave_for(people, first, last, user):
    me = getattr(user, "person", None)
    manager = access.is_manager(user)
    all_teams = access.is_all_teams(user)
    managed = set(access.managed_teams(user).values_list("pk", flat=True)) if manager and not all_teams else set()
    people = list(people)
    by_pk = {p.pk: p for p in people}

    def detail_for(p):
        return (me is not None and me.pk == p.pk) or all_teams or (manager and p.team_id in managed)

    out = {}
    days = (BookingDay.objects.filter(booking__person__in=people, day__range=(first, last), booking__status__in=Booking.ACTIVE)
            .select_related("booking__type"))
    for bd in days:
        p = by_pk[bd.booking.person_id]
        out.setdefault(p.pk, {})[bd.day.isoformat()] = _json(bd.booking, bd, detail_for(p))
    pending = Booking.objects.filter(person__in=people, status=Booking.Status.PENDING, first_day__lte=last, last_day__gte=first).select_related("type")
    for b in pending:
        p = by_pk[b.person_id]
        for day in b.days():
            if first <= day <= last:
                out.setdefault(p.pk, {}).setdefault(day.isoformat(), _json(b, None, detail_for(p)))
    history = Booking.objects.filter(person__in=people, status__in=Booking.ACTIVE, dates_only=True, first_day__lte=last, last_day__gte=first).select_related("type")
    for b in history:          # a past schedule entry has no costed days; it still shows where it was
        p = by_pk[b.person_id]
        for day in b.days():
            if first <= day <= last:
                out.setdefault(p.pk, {}).setdefault(day.isoformat(), _json(b, None, detail_for(p)))
    return out
