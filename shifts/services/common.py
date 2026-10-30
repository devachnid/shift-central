"""Common and Recent shift shapes for the right-click menu (spec, section
5): not stored, computed from recent entries."""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from people.models import Department
from people.services import access
from shifts.models import Entry
from shifts.services import serialize

WINDOW = timedelta(weeks=12)
LIMIT = 10


def _label(start, finish, break_minutes, dept):
    parts = [f"{serialize.time(start)}–{serialize.time(finish)}"]
    if break_minutes == 60:
        parts.append("1 hour break")
    elif break_minutes:
        parts.append(f"{break_minutes} min break")
    if dept is not None:
        parts.append(dept.name)
    return " ".join(parts)


def _shapes(rows):
    depts = {d.pk: d for d in Department.objects.all()}
    out = []
    for r in rows:
        dept = depts.get(r["department_id"])
        out.append({"start": serialize.time(r["start"]), "finish": serialize.time(r["finish"]),
                    "break_minutes": r["break_minutes"], "department": r["department_id"],
                    "label": _label(r["start"], r["finish"], r["break_minutes"], dept)})
    return out


def common(user):
    since = timezone.localdate() - WINDOW
    rows = (Entry.objects.filter(kind=Entry.Kind.SHIFT, day__gte=since, person__in=access.managed_people(user))
            .values("start", "finish", "break_minutes", "department_id")
            .annotate(n=Count("id")).order_by("-n", "start")[:LIMIT])
    return _shapes(rows)


def recent(user):
    seen, rows = set(), []
    for r in (Entry.objects.filter(kind=Entry.Kind.SHIFT, created_by=user).order_by("-created_at")
              .values("start", "finish", "break_minutes", "department_id")[:200]):
        key = (r["start"], r["finish"], r["break_minutes"], r["department_id"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(r)
        if len(rows) == LIMIT:
            break
    return _shapes(rows)
