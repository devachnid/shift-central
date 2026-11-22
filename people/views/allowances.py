"""The Allowances page (allowance spec 2026-11-18, section 8): the four
lists a manager works through, and what they do to a row. Managers only;
each list holds only the people the viewer manages, and nobody acts on
their own row (the services refuse)."""

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from leave.services import entitlement
from people.forms import AllowanceChangeForm
from people.models import Allowance
from people.services import access, filters, profiles

LIST = "/staff/allowances/"
REFRESH = {"refresh": True}


def _teams(request):
    return list(access.managed_teams(request.user).filter(active=True))


def _query(team):
    """"?team=3" when a team is chosen, for the forms' actions and the way back."""
    query = filters.query(team=team)
    return "?" + query[1:] if query else ""


def _back(request):
    """The list, with the Team box as it was (the forms post to ?team=)."""
    return redirect(LIST + _query(filters.chosen(request, _teams(request), "team")))


def _row(request, pk):
    row = get_object_or_404(Allowance.objects.select_related("person__team", "checked_by"), pk=pk)
    if not access.can_manage(request.user, row.person):
        raise PermissionDenied
    return row


@login_required
@access.manager_required
def index(request):
    choices = _teams(request)
    team = filters.chosen(request, choices, "team")
    review = entitlement.review(request.user, team)
    return render(request, "people/allowances.html", {
        "page_title": "Allowances", "review": review, "team_choices": choices, "team": team,
        "back_query": _query(team),
        "confirmable": [item for item in review.to_check if item.shown and item.can_act]})


def _posted(request):
    """([(row id, annual, bank holiday, days per week or None)], how many
    rows came with days per week outside 1 to 7) from the page's hidden
    fields. A row whose fields do not read is left out; one with such
    days is not confirmed, and counted."""
    items = []
    for value in request.POST.getlist("row"):
        try:
            pk = int(value)
            days = request.POST.get(f"days_{pk}", "").strip()
            items.append((pk, Decimal(request.POST[f"annual_{pk}"]), Decimal(request.POST[f"bank_holiday_{pk}"]),
                          int(days) if days else None))
        except (KeyError, ValueError, InvalidOperation):
            continue
    good = [item for item in items if item[3] is None or 1 <= item[3] <= 7]
    return good, len(items) - len(good)


@login_required
@access.manager_required
@require_POST
def confirm(request):
    """Confirm one row or all shown. Each row arrives with the figures the
    page drew; one whose figures have changed since, that is no longer
    waiting, that is not the viewer's to confirm, or that came with days
    per week outside 1 to 7 is not confirmed, and counted."""
    items, bad_days = _posted(request)
    confirmed, skipped = profiles.confirm_allowances(request.user, items)
    skipped += bad_days
    if confirmed:
        messages.success(request, f"{confirmed} allowance{'' if confirmed == 1 else 's'} confirmed.")
    if skipped:
        messages.warning(request, f"{skipped} not confirmed: changed since this page was drawn, already confirmed, "
                                  "not yours to confirm, or days per week not from 1 to 7. Check what is listed now.")
    return _back(request)


@login_required
@access.manager_required
@require_POST
def use(request, pk):
    row = _row(request, pk)
    try:
        profiles.use_worked_out(request.user, row)
        removed = not Allowance.objects.filter(pk=pk).exists()
        messages.success(request, f"{row.person.name}: {'the change is removed' if removed else 'the worked-out figure is in use'}.")
    except ValueError as e:
        messages.error(request, str(e))
    return _back(request)


@login_required
@access.manager_required
def change(request, pk):
    row = _row(request, pk)
    form = AllowanceChangeForm(request.POST or None, with_days=profiles.takes_days(row), initial={
        "annual_hours": row.annual_hours.quantize(Decimal("0.01")), "bank_holiday_hours": row.bank_holiday_hours.quantize(Decimal("0.01")),
        "days_per_week": row.days_per_week})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            profiles.change_allowance(request.user, row, d["annual_hours"], d["bank_holiday_hours"], d["note"], d.get("days_per_week"))
            return JsonResponse(REFRESH)
        except ValueError as e:
            form.add_error(None, str(e))
    return render(request, "people/allowance_change_dialog.html", {"row": row, "form": form, "state": entitlement.state(row)})
