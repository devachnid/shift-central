"""Add time off (managers) and Edit: the dialog re-renders with the
preview on every change (data-submit-on-change posts with preview=1);
saving answers {"refresh": true} so the grid reloads."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from leave.forms import BookingForm
from leave.models import Booking
from leave.services import balances, bookings, costing, years
from leave.services.common import LeaveError
from people.models import Person
from people.services import access

REFRESH = {"refresh": True}
POOLS = {"annual": ("annual", "bank_holiday"), "bank_holiday": ("annual", "bank_holiday"), "toil": ("toil",)}


def _own_spend(booking, person, pool, year):
    """What an existing booking already takes from the pool (the statement's
    balance counts it); an edit must not count it twice. An approved
    booking's days are stored; a pending one is costed as it would be."""
    if booking is None or booking.status not in Booking.LIVE:
        return 0
    end = years.year_end(year)
    toil = pool == ("toil",)
    if booking.is_active:
        return sum(bd.cost_seconds for bd in booking.booking_days.all() if bd.account in pool and (toil or year <= bd.day <= end))
    total = 0
    for day in booking.days():
        if toil or year <= day <= end:
            c = costing.cost(person, booking.type, day, booking.part, booking.start, booking.finish)
            if c.account in pool:
                total += c.seconds
    return total


def _preview(form, booking=None, person=None):
    """Costs per day, the balance before and after, and any warning."""
    if not form.is_valid():
        return {}
    kw = form.booking_kwargs()
    person = person or form.cleaned_data.get("person") or booking.person
    try:
        bookings._check_dates(person, kw["first"], kw["last"], kw["part"], kw["start"], kw["finish"])
        bookings._check_overlap(person, kw["first"], kw["last"], exclude=booking)
    except LeaveError as e:
        return {"error": e.message}
    if booking is None:
        costs = bookings.preview(person, kw["leave_type"], kw["first"], kw["last"], kw["part"], kw["start"], kw["finish"])
    else:      # the booking's own covered shifts still count towards its cost
        own = {bd.day: bd for bd in booking.booking_days.all()}
        costs = [costing.cost(person, kw["leave_type"], d, kw["part"], kw["start"], kw["finish"], include=own.get(d))
                 for d in Booking(first_day=kw["first"], last_day=kw["last"]).days()]
    typed = form.costs()
    stored = {bd.day: bd for bd in booking.booking_days.all() if bd.source == "override"} if booking is not None else {}
    days = []
    for c, day in zip(costs, Booking(first_day=kw["first"], last_day=kw["last"]).days()):
        key = f"cost_{day.isoformat()}"
        row = {"day": day, "cost": typed.get(day, c.seconds), "source": c.source, "placeholder": c.placeholder,
               "hours_known": c.hours_known, "account": c.account, "typed": day in typed,
               "text": form.data.get(key, "").strip()}
        if day in stored and key not in form.data:      # a manager's earlier figure stands until another is typed
            row.update(cost=stored[day].cost_seconds, source="override", placeholder=False, account=stored[day].account)
            if stored[day].cost_seconds % 60 == 0:
                row["text"] = f"{stored[day].cost_seconds // 3600}:{stored[day].cost_seconds % 3600 // 60:02d}"
        elif day in stored and day not in typed:
            row.update(cost=stored[day].cost_seconds, source="override", placeholder=False, account=stored[day].account)
        days.append(row)
    total = {}
    for d in days:
        total[d["account"]] = total.get(d["account"], 0) + d["cost"]
    year = years.year_of(person, kw["first"])
    s = balances.statement(person, year)
    account = kw["leave_type"].draws_from
    pool = POOLS.get(account)
    out = {"days": days, "total": sum(total.values()),
           "placeholders": any(d["placeholder"] for d in days), "unknown_hours": any(not d["hours_known"] for d in days),
           "missing_allowance": bool(s.missing) and account in ("annual", "bank_holiday")}
    if pool is None:
        return out | {"before": None, "after": None, "available": None, "over": False}
    remaining, available = (s.annual_remaining, s.annual_available) if pool != ("toil",) else (s.toil_remaining, s.toil_available)
    given_back = _own_spend(booking, person, pool, year)
    spend = sum(total.get(a, 0) for a in pool)
    before, available = remaining + (given_back if booking and booking.is_active else 0), available + given_back
    return out | {"before": before, "after": before - spend, "available": available, "over": spend > available}


@login_required
@access.manager_required
def add(request):
    if request.method == "POST":
        form = BookingForm(request.user, request.POST)
        preview = _preview(form)
        if form.is_valid() and not request.POST.get("preview") and "error" not in preview:
            person = form.cleaned_data["person"]
            kw = form.booking_kwargs()
            note = form.cleaned_data["manager_note"]
            base = request.build_absolute_uri("/")
            try:
                if bookings.may_book(request.user, person):
                    bookings.book(request.user, person, note=note, costs=form.costs(), base_url=base, **kw)
                    return JsonResponse(REFRESH)
                if access.is_self(request.user, person):
                    bookings.request(request.user, person, note=note, base_url=base, **kw)
                    return render(request, "leave/add_dialog.html", {"form": form, "preview": {}, "pending_own": True, "refresh": True})
                raise PermissionDenied
            except LeaveError as e:
                form.add_error(None, e.message)
    else:
        initial = {"part": "whole"}
        person = request.GET.get("person", "")
        if person.isascii() and person.isdigit():
            initial["person"] = Person.objects.filter(pk=int(person)).first()
        if request.GET.get("day"):
            try:
                initial["first_day"] = initial["last_day"] = date.fromisoformat(request.GET["day"])
            except ValueError:
                pass
        form = BookingForm(request.user, initial=initial)
        preview = {}
    return render(request, "leave/add_dialog.html", {"form": form, "preview": preview, "title": "Time off", "can_type": True})


@login_required
@access.manager_required
def edit(request, pk):
    booking = get_object_or_404(Booking.objects.select_related("person", "type"), pk=pk)
    if not bookings.may_decide(request.user, booking):
        raise PermissionDenied
    if request.method == "POST":
        form = BookingForm(request.user, request.POST, person=booking.person)
        preview = _preview(form, booking, person=booking.person)
        if form.is_valid() and not request.POST.get("preview") and "error" not in preview:
            kw = form.booking_kwargs()
            try:
                bookings.edit(request.user, booking, base_url=request.build_absolute_uri("/"), costs=form.costs(), type=kw["leave_type"], first=kw["first"], last=kw["last"],
                              part=kw["part"], start=kw["start"], finish=kw["finish"], description=kw["description"], paid=kw["paid"])
                return JsonResponse(REFRESH)
            except LeaveError as e:
                form.add_error(None, e.message)
    else:
        form = BookingForm(request.user, initial={"person": booking.person, "type": booking.type, "description": booking.description,
                                                  "first_day": booking.first_day, "last_day": booking.last_day, "part": booking.part,
                                                  "start": booking.start, "finish": booking.finish, "paid": booking.paid},
                           person=booking.person)
        preview = {}
    return render(request, "leave/add_dialog.html", {"form": form, "preview": preview, "booking": booking, "title": "Edit time off",
                                                    "can_type": booking.is_active})
