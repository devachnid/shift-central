"""GP sessions are the rota app's and leave never covers them (leave spec,
Revisit). Where a GP's sessions and their leave are shown or counted
together, the leave hides the sessions it falls on: a whole day hides both,
a morning the AM session, an afternoon the PM one, a timed booking none."""

from datetime import timedelta

from leave.models import Booking

HIDES = {"whole": ("AM", "PM"), "am": ("AM",), "pm": ("PM",), "times": ()}


def hidden(people, first, last):
    """{(person_id, day): {"AM", ...}} for the active, costed bookings of
    `people` between first and last."""
    out = {}
    rows = Booking.objects.filter(person__in=people, status__in=Booking.ACTIVE, dates_only=False,
                                  first_day__lte=last, last_day__gte=first).values_list("person_id", "part", "first_day", "last_day")
    for pid, part, f, l in rows:
        day, stop = max(f, first), min(l, last)
        while day <= stop:
            out.setdefault((pid, day), set()).update(HIDES[part])
            day += timedelta(days=1)
    return out


def visible(sessions, hidden_parts):
    return [s for s in sessions if s.part not in hidden_parts.get((s.person_id, s.day), ())]
