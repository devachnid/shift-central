"""Approved GP leave for the rota app (spec section 8). A timed booking is
reported as the half it falls in. Never a description, a note or a pk."""

from datetime import time

from leave.models import Booking

NOON = time(13, 0)


def part_of(b):
    if b.part != "times":
        return b.part
    if b.finish <= NOON:
        return "am"
    if b.start >= NOON:
        return "pm"
    return "whole"


def records(start, end):
    rows = (Booking.objects.filter(person__is_gp=True, status__in=Booking.ACTIVE, first_day__lte=end, last_day__gte=start)
            .exclude(person__email="").select_related("person", "type").order_by("first_day", "person__email", "pk"))
    return [{"email": b.person.email, "first_day": b.first_day.isoformat(), "last_day": b.last_day.isoformat(), "part": part_of(b), "type": b.type.name}
            for b in rows]
