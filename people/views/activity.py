from datetime import date

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from accounts.models import LoginEvent, User
from people.models import Allowance, AuditEntry
from people.services import access


def _pk(value):
    """A filter's id, or None. isdigit() alone admits superscripts and
    circled digits that int() refuses."""
    return int(value) if value and value.isascii() and value.isdigit() else None


def _day(value):
    """A filter's ISO date, or None: a date that does not parse is ignored,
    as a blank one is."""
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _between(rows, request):
    """Rows whose `at` falls on or between the from and to days, each
    optional. Returns the rows and the two values to show in the form."""
    start, end = _day(request.GET.get("from")), _day(request.GET.get("to"))
    if start:
        rows = rows.filter(at__date__gte=start)
    if end:
        rows = rows.filter(at__date__lte=end)
    return rows, (start.isoformat() if start else ""), (end.isoformat() if end else "")


@login_required
@access.manager_required
def activity(request):
    people = access.managed_people(request.user)
    names = {p.pk: p.name for p in people}
    # Allowance rows are about a person; show whose, not a bare "allowance".
    allowances = dict(Allowance.objects.filter(person__in=people).values_list("pk", "person_id"))
    # A rota cell is audited against its person under shifts.entry (fields
    # cell, appearance, notified); templates are shared by every manager.
    entries = AuditEntry.objects.filter(
        Q(model__in=("people.person", "shifts.entry"), object_id__in=list(names))
        | Q(model="people.allowance", object_id__in=list(allowances))
        | Q(model__in=("people.department", "shifts.template")))
    person = request.GET.get("person")
    if person:
        pk = _pk(person)
        if pk not in names:
            entries = entries.none()
        else:
            entries = entries.filter(Q(model__in=("people.person", "shifts.entry"), object_id=pk)
                                     | Q(model="people.allowance",
                                         object_id__in=[a for a, p in allowances.items() if p == pk]))
    field = request.GET.get("field")
    if field:
        entries = entries.filter(field=field)
    entries, start, end = _between(entries, request)
    entries = list(entries.select_related("actor")[:500])
    for entry in entries:
        if entry.model in ("people.person", "shifts.entry"):
            entry.record = names.get(entry.object_id, "person")
        elif entry.model == "people.allowance":
            entry.record = names.get(allowances.get(entry.object_id), "allowance")
        else:
            entry.record = entry.model.split(".", 1)[1]
    return render(request, "people/activity.html", {
        "page_title": "Activity log", "entries": entries,
        "people": people.order_by("name"), "person": person or "", "field": field or "",
        "date_from": start, "date_to": end})


@login_required
@access.all_teams_required
def logins(request):
    events = LoginEvent.objects.select_related("user")
    person = request.GET.get("person")
    if person:
        events = events.filter(user_id=_pk(person)) if _pk(person) is not None else events.none()
    events, start, end = _between(events, request)
    return render(request, "people/logins.html", {
        "page_title": "Log in logs", "events": events[:1000],
        "users": User.objects.filter(login_events__isnull=False).distinct().order_by("email"),
        "person": person or "", "date_from": start, "date_to": end})
