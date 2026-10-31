"""Request time off (staff, a page so it works on a phone) and My leave."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone

from leave.forms import BookingForm
from leave.models import Booking
from leave.services import balances, blackouts, bookings, years
from leave.services.common import LeaveError
from leave.views.add import _preview


def _me(request):
    me = getattr(request.user, "person", None)
    if me is None:
        raise PermissionDenied
    return me


def _staff_preview(form, me):
    """The manager preview plus the blackout check, for a staff member."""
    preview = _preview(form, person=me)
    if preview.get("days") and any(blackouts.blocks(me, d["day"]) for d in preview["days"]):
        preview["blackout"] = True
        preview["error"] = "Leave cannot be requested on one of these days (a blackout period)"
    return preview


def _label(year):
    return str(year.year) if (year.month, year.day) == (1, 1) else f"{year.year}/{str(year.year + 1)[2:]}"


def _balances(me):
    """A statement for each leave year leave can be booked in. The current
    year always; the next once an allowance is set for it (a request in
    October is often for the spring)."""
    out = []
    for i, year in enumerate(years.years_for(me)):
        statement = balances.statement(me, year)
        if i == 0 or not statement.missing:
            out.append({"label": _label(year), "statement": statement})
    return out


@login_required
def request_time_off(request):
    me = _me(request)
    if request.method == "POST":
        form = BookingForm(request.user, request.POST, staff=True)
        preview = _staff_preview(form, me)
        if form.is_valid() and not request.POST.get("preview") and "error" not in preview and not preview.get("over"):
            try:
                bookings.request(request.user, me, note=form.cleaned_data["staff_note"], base_url=request.build_absolute_uri("/"), **form.booking_kwargs())
                return redirect("time-off-mine")
            except LeaveError as e:
                form.add_error(None, e.message)
    else:
        form = BookingForm(request.user, initial={"part": "whole"}, staff=True)
        preview = {}
    return render(request, "leave/request.html", {
        "page_title": "Request time off", "form": form, "preview": preview, "balances": _balances(me),
        "can_send": bool(preview.get("days")) and not preview.get("over") and "error" not in preview and not form.non_field_errors()})


@login_required
def mine(request):
    me = _me(request)
    today = timezone.localdate()
    bookings_ = Booking.objects.filter(person=me).select_related("type").prefetch_related("booking_days").order_by("-first_day")[:100]
    rows = [{"b": b, "cost": sum(bd.cost_seconds for bd in b.booking_days.all()) if b.is_active else None,
             "can_cancel": b.status == Booking.Status.APPROVED and b.last_day >= today} for b in bookings_]
    return render(request, "leave/mine.html", {"page_title": "My leave", "rows": rows, "balances": _balances(me), "today": today})
