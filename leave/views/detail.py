"""View and Cancel dialogs. View shows type-only to colleagues; Cancel is
a cancellation request for the person and an outright cancel for a manager."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from leave.forms import CancelForm
from leave.models import Booking
from leave.services import bookings, sickness
from leave.services.common import LeaveError
from people.services import access
from shifts.services.window import visible_people

REFRESH = {"refresh": True}


def status_for(booking, detail):
    """The status as the viewer may see it: a cancellation request is the
    person's and their managers' business; to everyone else the leave is
    still approved (section 5)."""
    if not detail and booking.status == Booking.Status.CANCEL_REQUESTED:
        return Booking.Status.APPROVED.label
    return booking.get_status_display()


@login_required
def view(request, pk):
    b = get_object_or_404(Booking.objects.select_related("person", "type", "decided_by"), pk=pk)
    detail = bookings.may_view_detail(request.user, b)
    if not detail and (b.status not in Booking.LIVE
                       or not visible_people(request.user, b.first_day, b.last_day).filter(pk=b.person_id).exists()):
        raise Http404      # colleagues see live leave of the people the grid shows them, as the list does
    days = list(b.booking_days.order_by("day")) if detail else []
    manager = access.can_manage(request.user, b.person)
    return render(request, "leave/view_dialog.html", {
        "b": b, "detail": detail, "days": days, "total": sum(d.cost_seconds for d in days), "status": status_for(b, detail),
        "can_cancel": (access.is_self(request.user, b.person) and b.status == Booking.Status.APPROVED and b.last_day >= timezone.localdate())
                      or (manager and b.status in Booking.LIVE),
        "can_edit": manager and b.status in (Booking.Status.APPROVED, Booking.Status.PENDING),
        "can_convert": manager and b.status in Booking.ACTIVE and not b.dates_only and b.part == Booking.Part.WHOLE
                       and b.type.draws_from in ("annual", "bank_holiday"),
        "long_sickness": b.type.sickness and sickness.is_long(b),
        "after_leaving": b.person.end_date is not None and b.last_day > b.person.end_date})


@login_required
def cancel(request, pk):
    b = get_object_or_404(Booking.objects.select_related("person", "type"), pk=pk)
    manager = access.can_manage(request.user, b.person)
    if not (manager or access.is_self(request.user, b.person)):
        raise PermissionDenied
    form = CancelForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        base = request.build_absolute_uri("/")
        try:
            if manager:
                bookings.cancel(request.user, b, form.cleaned_data["note"], base_url=base)
            else:
                bookings.request_cancel(request.user, b, form.cleaned_data["note"], base_url=base)
            return JsonResponse(REFRESH)
        except LeaveError as e:
            form.add_error(None, e.message)
    return render(request, "leave/cancel_dialog.html", {"b": b, "form": form, "manager": manager})
