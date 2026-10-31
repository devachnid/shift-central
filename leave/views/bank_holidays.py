"""Bank holidays (LEAVE-16, 19): the list for a year with add and delete,
and "Add for everyone": each person with the suggested hours to confirm."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.forms import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from leave.forms import BankHolidayForm, parse_hours
from leave.models import BankHoliday, Booking, LeaveType
from leave.services import bank_holidays, hours, years
from people.services import access

MAX_DAY = 24 * 3600


def _year(text):
    try:
        year = int(text)
    except (TypeError, ValueError):
        return timezone.localdate().year
    return year if 2000 <= year <= 2100 else timezone.localdate().year


@login_required
@access.manager_required
def index(request):
    form = BankHolidayForm(request.POST or None)
    if request.method == "POST":
        if request.POST.get("delete"):
            try:
                day = date.fromisoformat(request.POST["delete"])
            except ValueError:
                raise Http404 from None
            bank_holidays.remove(request.user, day)
            return redirect(f"/time-off/bank-holidays/?year={day.year}")
        if form.is_valid():
            bank_holidays.add(request.user, form.cleaned_data["day"], form.cleaned_data["name"])
            return redirect(f"/time-off/bank-holidays/?year={form.cleaned_data['day'].year}")
    year = _year(request.GET.get("year"))
    rows = list(BankHoliday.objects.filter(day__year=year))
    types = LeaveType.objects.filter(seeded=True, draws_from=LeaveType.Account.BANK_HOLIDAY)
    booked = {}
    for b in Booking.objects.filter(type__in=types, first_day__in=[r.day for r in rows], status__in=Booking.ACTIVE):
        booked[b.first_day] = booked.get(b.first_day, 0) + 1
    for r in rows:
        r.booked = booked.get(r.day, 0)
    return render(request, "leave/bank_holidays.html", {"page_title": "Bank holidays", "rows": rows, "year": year, "previous": year - 1,
                                                        "next": year + 1, "form": form})


@login_required
@access.manager_required
def everyone(request, day):
    try:
        day = date.fromisoformat(day)
    except ValueError:
        raise Http404 from None
    holiday = BankHoliday.objects.filter(day=day).first()
    if holiday is None:
        raise Http404
    posted = request.method == "POST"
    rows = []
    for person, suggested in bank_holidays.suggestions(request.user, day):
        if not access.can_manage(request.user, person):
            continue          # a manager's own leave is booked by another manager
        text = hours.fmt_short(suggested)
        ticked = not person.is_gp
        error = ""
        if posted:
            ticked = f"tick_{person.pk}" in request.POST
            text = request.POST.get(f"hours_{person.pk}", "").strip()
            try:
                seconds = parse_hours(text) or 0
                if seconds > MAX_DAY:
                    raise ValidationError("A day has 24 hours")
            except ValidationError as e:
                seconds, error = 0, e.messages[0]
        else:
            seconds = suggested
        rows.append({"person": person, "text": text, "ticked": ticked, "error": error, "seconds": seconds})
    context = {"day": day, "holiday": holiday}
    if posted:
        if LeaveType.objects.filter(seeded=True, draws_from=LeaveType.Account.BANK_HOLIDAY, archived=True).exists():
            return render(request, "leave/bank_holiday_everyone.html", {
                **context, "rows": rows, "problem": "The Bank holiday leave type is archived. Restore it under Leave types to book bank holidays."})
        if any(r["error"] and r["ticked"] for r in rows):
            return render(request, "leave/bank_holiday_everyone.html", {**context, "rows": rows})
        ticked = [r for r in rows if r["ticked"]]
        # Leave can be booked in a person's current leave year and the next only.
        outside = [r for r in ticked if years.year_of(r["person"], day) not in years.years_for(r["person"])]
        booked, skipped = bank_holidays.book_many(request.user, day, {r["person"].pk: r["seconds"] for r in ticked if r not in outside})
        return render(request, "leave/bank_holiday_everyone.html", {**context, "done": True, "booked": booked, "skipped": skipped,
                                                                    "outside": len(outside)})
    return render(request, "leave/bank_holiday_everyone.html", {**context, "rows": rows})
