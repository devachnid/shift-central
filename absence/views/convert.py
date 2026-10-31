"""Convert days to sickness (LEAVE-28): a manager's pop-up on an approved
annual leave booking; re-renders with a preview on each change."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from absence.forms import ConvertForm
from absence.services import convert
from leave.models import Booking
from leave.services import bookings, sickness
from leave.services.common import LeaveError
from people.services import access


def _preview(booking, first, last):
    rows = sickness.instances(booking.person)
    count = len(rows) + (1 if sickness.overlaps_window(first, last) else 0)
    return {"hours_back": convert.hours_back(booking, first, last), "instances_after": count,
            "level_label": sickness.level_label(sickness.level(count)), "long": (last - first).days + 1 >= sickness.LONG_DAYS}


@login_required
@access.manager_required
def convert_view(request, pk):
    booking = get_object_or_404(Booking.objects.select_related("person", "type"), pk=pk)
    if not bookings.may_decide(request.user, booking):
        raise PermissionDenied
    form = ConvertForm(request.POST or None, booking=booking)
    preview, error = None, None
    if form.is_valid():
        d = form.cleaned_data
        try:
            convert.check(booking, d["type"], d["first_day"], d["last_day"])
            preview = _preview(booking, d["first_day"], d["last_day"])
            if request.method == "POST" and not request.POST.get("preview"):
                convert.convert(request.user, booking, d["type"], d["first_day"], d["last_day"], d["note"], base_url=request.build_absolute_uri("/"))
                return JsonResponse({"refresh": True})
        except LeaveError as e:
            error = e.message
    return render(request, "absence/convert_dialog.html", {"b": booking, "form": form, "preview": preview, "error": error})
