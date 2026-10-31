"""Waiting for approval (REQ-12) and the decision dialog, for requests and
cancellation requests alike."""

from types import SimpleNamespace

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from leave.forms import DecideForm
from leave.models import Booking
from leave.services import balances, bookings, years
from leave.services.common import LeaveError
from people.services import access

REFRESH = {"refresh": True}


def _preview_costs(b):
    return bookings.preview(b.person, b.type, b.first_day, b.last_day, b.part, b.start, b.finish)


@login_required
@access.manager_required
def waiting(request):
    people = access.managed_people(request.user)
    rows = (Booking.objects.filter(person__in=people, status__in=(Booking.Status.PENDING, Booking.Status.CANCEL_REQUESTED))
            .select_related("person__team", "type").prefetch_related("booking_days").order_by("requested_at", "pk"))
    rows = [b for b in rows if access.can_manage(request.user, b.person)]
    now = timezone.now()
    for b in rows:
        b.waiting_days = (now - (b.cancel_requested_at or b.requested_at)).days
        b.cost = sum(bd.cost_seconds for bd in b.booking_days.all()) if b.status == Booking.Status.CANCEL_REQUESTED \
            else sum(c.seconds for c in _preview_costs(b))
    return render(request, "leave/approve.html", {"page_title": "Waiting for approval", "rows": rows})


def _day_costs(b):
    """[(day, cost)] for the dialog: a request's days costed as they would
    be now; a cancellation request's days as they were stored."""
    if b.status == Booking.Status.PENDING:
        return list(zip(b.days(), _preview_costs(b)))
    return [(bd.day, SimpleNamespace(seconds=bd.cost_seconds, placeholder=bd.placeholder, account=bd.account))
            for bd in b.booking_days.all()]


@login_required
def decide(request, pk):
    b = get_object_or_404(Booking.objects.select_related("person__team", "type"), pk=pk)
    if not bookings.may_decide(request.user, b):
        raise PermissionDenied
    form = DecideForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        approve = form.cleaned_data["decision"] == "approve"
        base = request.build_absolute_uri("/")
        try:
            if b.status == Booking.Status.CANCEL_REQUESTED:
                bookings.decide_cancel(request.user, b, approve, form.cleaned_data["note"], base_url=base)
            elif approve:
                bookings.approve(request.user, b, form.cleaned_data["note"], base_url=base)
            else:
                bookings.decline(request.user, b, form.cleaned_data["note"], base_url=base)
            return JsonResponse(REFRESH)
        except LeaveError as e:
            form.add_error(None, e.message)
            b.refresh_from_db()
    days = _day_costs(b)
    total = sum(cost.seconds for _, cost in days)
    s = balances.statement(b.person, years.year_of(b.person, b.first_day))
    account = b.type.draws_from
    before = s.toil_remaining if account == "toil" else s.annual_remaining
    others = Booking.objects.none()
    if b.person.team_id:
        others = (Booking.objects.filter(person__team=b.person.team, status__in=Booking.ACTIVE, first_day__lte=b.last_day, last_day__gte=b.first_day)
                  .exclude(person=b.person).select_related("person", "type"))
    return render(request, "leave/decide_dialog.html", {
        "b": b, "form": form, "days": days, "total": total, "before": before, "account": account,
        "after": before - total if account != "none" and b.status == Booking.Status.PENDING else before, "others": others})
