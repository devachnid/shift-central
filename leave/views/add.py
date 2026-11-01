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
from leave.services import balances, bookings, costing, sickness, years
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
    dates_only = booking is not None and booking.dates_only
    try:
        if dates_only:      # a past schedule entry: the service's own rule, not the leave-year one (2026 is edited in 2027)
            bookings._check_dates_only(kw["leave_type"], kw["first"], kw["last"], kw["part"])
        else:               # an edit is held to "this leave year and the next" only for the days it adds (bookings._check_dates)
            bookings._check_dates(person, kw["first"], kw["last"], kw["part"], kw["start"], kw["finish"], was=booking)
        bookings._check_overlap(person, kw["first"], kw["last"], exclude=booking)
    except LeaveError as e:
        return {"error": e.message}
    if dates_only:          # no costed days: no cost table, no balance
        return _sickness_preview(person, kw["leave_type"], kw["first"], kw["last"], booking, dates_only=True)
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
    out_sickness = _sickness_preview(person, kw["leave_type"], kw["first"], kw["last"], booking, dates_only=False)
    account = kw["leave_type"].draws_from
    pool = POOLS.get(account)
    out = {"days": days, "total": sum(d["cost"] for d in days),
           "placeholders": any(d["placeholder"] for d in days), "unknown_hours": any(not d["hours_known"] for d in days),
           "missing_allowance": False}
    if pool is None:
        return out | {"before": None, "after": None, "available": None, "over": False, "balances": []} | out_sickness
    lines = _balance_lines(person, booking, pool, [(d["day"], d["account"], d["cost"]) for d in days])
    out["missing_allowance"] = any(line["missing"] for line in lines)
    first = lines[0]
    return out | {"before": first["before"], "after": first["after"], "available": first["available"],
                  "over": any(line["over"] for line in lines), "balances": lines} | out_sickness


def _sickness_preview(person, leave_type, first, last, booking=None, dates_only=False):
    """For a sickness type: the entry this one joins on to (LEAVE-41) with
    the dates an Extend would give, whether it is long, and the instances
    and trigger after it when recorded separately. Empty for other types.
    `dates_only`: the entry being typed is a past schedule entry (no hours)."""
    if not leave_type.sickness:
        return {}
    joins = sickness.joins_on(person, first, last, exclude=booking)
    others = [b for b in sickness.instances(person) if booking is None or b.pk != booking.pk]
    count = len(others) + (1 if sickness.overlaps_window(first, last) else 0)
    out = {"joins": joins, "extended_first": None, "extended_last": None,
           "long": (last - first).days + 1 >= sickness.LONG_DAYS,
           "instances_after": count, "level_label": sickness.level_label(sickness.level(count))}
    if joins:       # Extend: the two become one instance, so the count is the other entries plus the joined one
        out["extended_first"], out["extended_last"] = min(first, joins.first_day), max(last, joins.last_day)
        merged = len([b for b in others if b.pk != joins.pk]) + (1 if sickness.overlaps_window(out["extended_first"], out["extended_last"]) else 0)
        out["instances_extended"], out["level_label_extended"] = merged, sickness.level_label(sickness.level(merged))
        # Extend joins entries of the same kind only: a booked entry extended onto a past schedule entry would
        # take its days off payroll, and a past schedule entry extended onto a booked one would cost history.
        out["extend_blocked"] = joins.dates_only != dates_only
        out["joins_dates_only"] = joins.dates_only
    return {"sickness": out}


def _year_groups(person, pool, items):
    """The days by the balance they are checked against: annual leave by
    leave year, TOIL as one (it never resets)."""
    groups = {}
    for day, account, seconds in items:
        year = years.year_of(person, items[0][0] if pool == ("toil",) else day)
        groups.setdefault(year, []).append((account, seconds))
    return sorted(groups.items())


def _balance_lines(person, booking, pool, items):
    """Before, after and available for each balance the booking draws on
    (bookings.pools' rule): one line, or one per leave year when an annual
    leave booking crosses the leave year's end, each named by its year."""
    groups = _year_groups(person, pool, items)
    toil = pool == ("toil",)
    out = []
    for year, rows in groups:
        s = balances.statement(person, year)
        remaining, available = (s.toil_remaining, s.toil_available) if toil else (s.annual_remaining, s.annual_available)
        given_back = _own_spend(booking, person, pool, year)
        spend = sum(seconds for account, seconds in rows if account in pool)
        before, available = remaining + (given_back if booking and booking.is_active else 0), available + given_back
        out.append({"year": years.label(year) if len(groups) > 1 else "", "before": before, "after": before - spend,
                    "available": available, "over": spend > available, "missing": bool(s.missing) and not toil})
    return out


@login_required
@access.manager_required
def add(request):
    if request.method == "POST":
        form = BookingForm(request.user, request.POST)
        preview = _preview(form)
        if form.is_valid() and not request.POST.get("preview") and "error" not in preview:
            s = preview.get("sickness") or {}
            base = request.build_absolute_uri("/")
            if s.get("joins") is not None and not s.get("extend_blocked") and request.POST.get("join", "extend") == "extend":
                try:        # LEAVE-41: the manager chose to extend the entry this one joins on to
                    bookings.edit(request.user, s["joins"], base_url=base, note="extended (joined on)",
                                  first=s["extended_first"], last=s["extended_last"])
                    return JsonResponse(REFRESH)
                except LeaveError as e:
                    form.add_error(None, e.message)
            else:
                person = form.cleaned_data["person"]
                kw = form.booking_kwargs()
                note = form.cleaned_data["manager_note"]
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
    # A person's own leave is costed from the rota (book() drops typed figures for it): no boxes.
    chosen = form.cleaned_data.get("person") if form.is_bound and hasattr(form, "cleaned_data") else form.initial.get("person")
    can_type = not (chosen is not None and access.is_self(request.user, chosen))
    return render(request, "leave/add_dialog.html", {"form": form, "preview": preview, "title": "Time off", "can_type": can_type,
                                                    "join": request.POST.get("join", "extend"), "editing": False})


def _booking_data(booking):
    return {"person": str(booking.person_id), "type": str(booking.type_id), "description": booking.description,
            "first_day": booking.first_day.isoformat(), "last_day": booking.last_day.isoformat(), "part": booking.part,
            "start": booking.start.strftime("%H:%M") if booking.start else "", "finish": booking.finish.strftime("%H:%M") if booking.finish else "",
            "paid": {None: "unknown", True: "true", False: "false"}[booking.paid], "manager_note": ""}


@login_required
@access.manager_required
def edit(request, pk):
    booking = get_object_or_404(Booking.objects.select_related("person", "type"), pk=pk)
    if not bookings.may_decide(request.user, booking):
        raise PermissionDenied
    if request.method == "POST":
        form = BookingForm(request.user, request.POST, person=booking.person, booking=booking)
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
        # Bound from the booking, so the dialog opens with each day's cost (a
        # manager's stored figure in its box) and the balance, as on a change.
        form = BookingForm(request.user, _booking_data(booking), person=booking.person, booking=booking)
        preview = _preview(form, booking, person=booking.person)
    return render(request, "leave/add_dialog.html", {"form": form, "preview": preview, "booking": booking, "title": "Edit time off",
                                                    "can_type": booking.is_active and not booking.dates_only, "editing": True})
