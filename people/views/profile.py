"""The profile pop-up: one dialog, four tabs, each a GET to render and a
POST to save. Who may see which tab is decided here from access.*."""

from copy import copy
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from leave.services import entitlement
from leave.services import years as leave_years
from leave.views.statement import statement_context
from people.forms import DisplayForm, HoursForm, NotesForm
from people.models import AuditEntry, Person
from people.services import access, contracts, profiles

TABS = ("general", "display", "hours", "notes")


def _person_for(request, pk):
    person = get_object_or_404(Person.objects.select_related("team"), pk=pk)
    if not (access.is_self(request.user, person) or access.can_manage(request.user, person)):
        raise PermissionDenied
    return person


@login_required
def profile(request, pk):
    person = _person_for(request, pk)
    manages = access.can_manage(request.user, person)
    tab = request.GET.get("tab", "general")
    if tab not in TABS:
        raise Http404
    if (tab == "notes" or request.method == "POST") and not manages:
        raise PermissionDenied      # staff read their own profile, never write it
    context = {"person": person, "tab": tab, "manages": manages, "can_manage_files": access.can_manage(request.user, person), "saved": False,
               "title": "Your profile" if access.is_self(request.user, person) else f"{person.name}'s profile"}
    if tab == "display":
        _display(request, person, context)
    elif tab == "hours":
        _hours(request, person, context)
    elif tab == "notes":
        _notes(request, person, context)
    return render(request, "people/profile_dialog.html", context)


def _display(request, person, context):
    if request.method == "POST":
        form = DisplayForm(request.POST)
        if form.is_valid():
            profiles.update_display(request.user, person, **form.cleaned_data)
            context["saved"] = True
            form = DisplayForm(initial={f: getattr(person, f) for f in profiles.DISPLAY_FIELDS})
    else:
        form = DisplayForm(initial={f: getattr(person, f) for f in profiles.DISPLAY_FIELDS})
    context["form"] = form


def _stored(person, years):
    """The hours form's initial values: what is stored now."""
    initial = {"weekly_hours": person.weekly_hours, "days_per_week": person.days_per_week,
               "leave_year_start": person.leave_year_start}
    # The year's first row: it is the one these boxes change. A dated row
    # is changed from the list beneath. Two places, as the boxes take them.
    for a in person.allowances.filter(leave_year__in=years, from_day=F("leave_year")):
        initial[f"annual_{a.leave_year.year}"] = a.annual_hours.quantize(Decimal("0.01"))
        initial[f"bank_holiday_{a.leave_year.year}"] = a.bank_holiday_hours.quantize(Decimal("0.01"))
    return initial


def _allowance_action(request, person, context):
    """The buttons beside each figure: Confirm, and Use the worked-out
    figure (allowance spec, 7.7). A refusal is shown above the list."""
    action, row_id = request.POST["allowance_action"], request.POST.get("row", "")
    if action not in ("confirm", "use") or not row_id.isascii() or not row_id.isdigit():
        raise Http404
    row = get_object_or_404(person.allowances.select_related("person__team", "checked_by"), pk=int(row_id))
    days = request.POST.get("days_per_week", "")
    try:
        if action == "use":
            profiles.use_worked_out(request.user, row)
        else:
            profiles.confirm_allowance(request.user, row, int(days) if days in list("1234567") else None)
        context["saved"] = True
    except ValueError as e:
        context["allowance_error"] = str(e)


def _posted_years(person, start):
    """The person's two leave years as they will be once a posted leave year
    start is applied, so the allowances typed with it land under the new years."""
    candidate = copy(person)
    try:
        leave_years.parse_start(start)
        candidate.leave_year_start = start
    except ValueError:      # blank or not a date: the form says so
        pass
    return leave_years.years_for(candidate)


def _hours(request, person, context):
    year_list = leave_years.years_for(person)
    from_hr = contracts.hours_from_hr(person)
    form = None
    if request.method == "POST" and "allowance_action" in request.POST:
        _allowance_action(request, person, context)
    elif request.method == "POST":
        year_list = _posted_years(person, request.POST.get("leave_year_start", ""))
        form = HoursForm(request.POST, years=year_list, is_gp=person.is_gp, hours_from_hr=from_hr)
        if form.is_valid():
            field = "leave_year_start"
            try:
                with transaction.atomic():      # a refused allowance leaves the hours unchanged too
                    if form.cleaned_data["leave_year_start"]:
                        profiles.update_leave_year_start(request.user, person, form.cleaned_data["leave_year_start"])
                    field = "note"
                    if not person.is_gp:
                        profiles.update_hours(request.user, person, form.cleaned_data.get("weekly_hours"),
                                              form.cleaned_data["days_per_week"])
                    for year, annual, bank in form.allowances():
                        profiles.set_allowance(request.user, person, year, annual, bank,
                                               note=form.cleaned_data["note"])
                context["saved"] = True
            except ValueError as e:
                person.refresh_from_db()
                if field == "leave_year_start":      # the year did not move: show the fields for the years it has
                    form = HoursForm(request.POST, years=leave_years.years_for(person), is_gp=person.is_gp, hours_from_hr=from_hr)
                    form.full_clean()
                form.add_error(field, str(e))
    year_list = leave_years.years_for(person)
    if form is None or context["saved"]:
        form = HoursForm(initial=_stored(person, year_list), years=year_list, is_gp=person.is_gp, hours_from_hr=from_hr)
    existing = {a.leave_year: a for a in person.allowances.filter(leave_year__in=year_list)}
    context.update({"form": form, "allowance_rows": [(y, existing.get(y)) for y in year_list], "hours_from_hr": from_hr,
                    # Managers only: staff see their figures with no state and no working.
                    "figures": entitlement.shown(person, year_list) if context["manages"] else []})
    context.update(statement_context(person, request.GET.get("year"), manages=context["manages"], in_dialog=True))


def _notes(request, person, context):
    if request.method == "POST":
        form = NotesForm(request.POST)
        if form.is_valid():
            profiles.set_notes(request.user, person, form.cleaned_data["notes"])
            context["saved"] = True
    else:
        form = NotesForm(initial={"notes": person.notes})
    context["form"] = form


@login_required
def history(request, pk):
    person = get_object_or_404(Person, pk=pk)
    if not access.can_manage(request.user, person):
        raise PermissionDenied
    allowance_ids = list(person.allowances.values_list("pk", flat=True))
    entries = AuditEntry.objects.filter(model="people.person", object_id=person.pk) | \
        AuditEntry.objects.filter(model="people.allowance", object_id__in=allowance_ids) | \
        AuditEntry.objects.filter(model__in=("leave.booking", "leave.adjustment"), object_id=person.pk)
    return render(request, "people/history_dialog.html",
                  {"person": person, "entries": entries.order_by("-at")[:200]})
