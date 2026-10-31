"""The statement shown on the profile and My leave, and its pop-ups: Adjust and Add hours change (managers)."""

from datetime import date

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from leave.forms import AdjustForm, HoursChangeForm
from leave.services import adjustments, balances, notify, years
from people.models import Person
from people.services import access, profiles

REFRESH = {"refresh": True}


def _statement_for(person, text):
    """The statement for the ISO year asked for when it is one of the
    person's two; else the current year's, or the next year's when only that
    one has an allowance set (a new person, or the last weeks of a year)."""
    options = years.years_for(person)
    try:
        asked = date.fromisoformat(text or "")
    except ValueError:
        asked = None
    if asked in options:
        return balances.statement(person, asked)
    current = balances.statement(person, options[0])
    if current.missing:
        following = balances.statement(person, options[1])
        if not following.missing:
            return following
    return current


def statement_context(person, year_text, manages=False, in_dialog=False):
    """What _statement.html needs: the statement and the person's two years
    to switch between."""
    return {"statement": _statement_for(person, year_text), "person": person, "manages": manages, "in_dialog": in_dialog,
            "year_options": [(y.isoformat(), years.label(y)) for y in years.years_for(person)]}


def _managed(request, pk):
    person = get_object_or_404(Person, pk=pk)
    if not access.can_manage(request.user, person):
        raise PermissionDenied
    return person


@login_required
def adjust(request, pk):
    person = _managed(request, pk)
    options = years.years_for(person)
    form = AdjustForm(request.POST or None, initial={"leave_year": options[0]})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        if d["leave_year"] not in options:
            form.add_error("leave_year", "Choose one of the leave years listed")
        else:
            try:
                adjustments.add(request.user, person, d["leave_year"], d["account"], d["hours"], d["reason"])
                return JsonResponse(REFRESH)
            except ValueError as e:
                form.add_error(None, str(e))
    return render(request, "leave/adjust_dialog.html", {
        "person": person, "form": form, "years": options, "selected": request.POST.get("leave_year") or options[0].isoformat()})


@login_required
def hours_change(request, pk):
    person = _managed(request, pk)
    form = HoursChangeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            profiles.add_hours_change(request.user, person, d["from_day"], d["weekly_hours"], d["days_per_week"],
                                      d["annual_hours"], d["bank_holiday_hours"], d["note"])
        except ValueError as e:
            form.add_error(None, str(e))
        else:
            s = balances.statement(person, years.year_of(person, d["from_day"]))
            if s.annual_remaining < 0:
                notify.negative_balance(person, s, request.build_absolute_uri("/"))
            return JsonResponse(REFRESH)
    return render(request, "leave/hours_change_dialog.html", {"person": person, "form": form})
