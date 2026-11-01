"""The Shifts report (REP-07, spec 5 section 9): every shift in a range for
the people the viewer manages, net hours as the Hours report counts them
(finish less start less break), overtime shown apart. Shifts covered by leave
are left out."""

from collections import OrderedDict
from datetime import timedelta

from people.services import access
from shifts.models import Entry

MAX_RANGE = timedelta(days=366)


def report(user, start, end, team=None, department=None, person=None):
    if end < start:
        start, end = end, start
    if end - start > MAX_RANGE:
        start = end - MAX_RANGE
    found = (Entry.objects.filter(person__in=access.managed_people(user), day__range=(start, end), kind=Entry.Kind.SHIFT,
                                  covered_by__isnull=True)
             .select_related("person__team", "department")
             .order_by("person__team__display_order", "person__team__name", "person__display_order", "person__last_name",
                       "person__first_name", "day", "position"))
    if team is not None:
        found = found.filter(person__team=team)
    if department is not None:
        found = found.filter(department=department)
    if person is not None:
        found = found.filter(person=person)
    blocks = OrderedDict()
    for e in found:
        block = blocks.setdefault(e.person_id, {"person": e.person, "rows": [], "total": timedelta(0), "overtime": timedelta(0)})
        block["rows"].append(e)
        block["total"] += e.hours
        if e.overtime:
            block["overtime"] += e.hours
    return {"blocks": list(blocks.values()), "start": start, "end": end,
            "grand_total": sum((b["total"] for b in blocks.values()), timedelta(0)),
            "grand_overtime": sum((b["overtime"] for b in blocks.values()), timedelta(0))}
