"""View and Cancel dialogs. View shows type-only to colleagues; Cancel is
a cancellation request for the person and an outright cancel for a manager."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from leave.forms import CancelForm
from leave.models import Booking
from leave.services import bookings
from leave.services.common import LeaveError
from people.services import access

REFRESH = {"refresh": True}


@login_required
def view(request, pk):
    b = get_object_or_404(Booking.objects.select_related("person", "type", "decided_by"), pk=pk)
    detail = bookings.may_view_detail(request.user, b)
    days = list(b.booking_days.order_by("day")) if detail else []
    manager = access.can_manage(request.user, b.person)
    return render(request, "leave/view_dialog.html", {
        "b": b, "detail": detail, "days": days, "total": sum(d.cost_seconds for d in days),
        "can_cancel": (access.is_self(request.user, b.person) and b.status == Booking.Status.APPROVED and b.last_day >= timezone.localdate())
                      or (manager and b.status in Booking.LIVE),
        "can_edit": manager and b.status in (Booking.Status.APPROVED, Booking.Status.PENDING)})


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
