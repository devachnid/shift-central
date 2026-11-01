"""The Outbox page (spec 5, section 7)."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from messaging.services import outbox
from people.services import access

PER_PAGE = 50


def _day(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


@login_required
@access.manager_required
def index(request):
    state = request.GET.get("status", "")
    state = state if state in outbox.STATUSES else ""
    people = access.managed_people(request.user)
    raw = request.GET.get("person", "")
    person = people.filter(pk=int(raw)).first() if raw.isascii() and raw.isdigit() else None
    start, end = _day(request.GET.get("from")), _day(request.GET.get("to"))
    page = Paginator(outbox.rows(request.user, state, person, start, end), PER_PAGE).get_page(request.GET.get("page"))
    for r in page:
        r.state = outbox.status(r)
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "messaging/outbox.html", {
        "page_title": "Outbox", "page": page, "statuses": outbox.STATUSES, "state": state, "person": person,
        "people": people.order_by("name"), "date_from": start.isoformat() if start else "",
        "date_to": end.isoformat() if end else "", "query": params.urlencode()})
