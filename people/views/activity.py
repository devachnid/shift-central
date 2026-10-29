from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from accounts.models import LoginEvent
from people.models import AuditEntry, Person
from people.services import access


@login_required
@access.manager_required
def activity(request):
    people = access.managed_people(request.user)
    ids = list(people.values_list("pk", flat=True))
    allowance_ids = [pk for pk in Person.objects.filter(pk__in=ids).values_list("allowances__pk", flat=True) if pk]
    entries = AuditEntry.objects.filter(
        Q(model="people.person", object_id__in=ids) | Q(model="people.allowance", object_id__in=allowance_ids)
        | Q(model="people.department"))
    person = request.GET.get("person")
    if person:
        # isdigit() alone admits superscripts and circled digits that int() refuses
        p = people.filter(pk=person).first() if person.isascii() and person.isdigit() else None
        if p is None:
            entries = entries.none()
        else:
            entries = entries.filter(Q(model="people.person", object_id=p.pk)
                                     | Q(model="people.allowance",
                                         object_id__in=p.allowances.values_list("pk", flat=True)))
    field = request.GET.get("field")
    if field:
        entries = entries.filter(field=field)
    names = {p.pk: p.name for p in people}
    entries = list(entries.select_related("actor")[:500])
    for entry in entries:
        if entry.model == "people.person":
            entry.record = names.get(entry.object_id, "person")
        else:
            entry.record = entry.model.removeprefix("people.")
    return render(request, "people/activity.html", {
        "page_title": "Activity log", "entries": entries,
        "people": people.order_by("name"), "person": person or "", "field": field or ""})


@login_required
@access.all_teams_required
def logins(request):
    return render(request, "people/logins.html", {
        "page_title": "Log in logs",
        "events": LoginEvent.objects.select_related("user")[:1000]})
