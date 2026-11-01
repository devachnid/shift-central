"""The profile pop-up: one dialog, four tabs, each a GET to render and a
POST to save. Who may see which tab is decided here from access.*."""

from copy import copy

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from leave.services import years as leave_years
from leave.views.statement import statement_context
from people.forms import DisplayForm, HoursForm, NotesForm
from people.models import AuditEntry, Person
from people.services import access, profiles

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
    for a in person.allowances.filter(leave_year__in=years):
        initial[f"annual_{a.leave_year.year}"] = a.annual_hours
        initial[f"bank_holiday_{a.leave_year.year}"] = a.bank_holiday_hours
    return initial


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
    form = None
    if request.method == "POST":
        year_list = _posted_years(person, request.POST.get("leave_year_start", ""))
        form = HoursForm(request.POST, years=year_list, is_gp=person.is_gp)
        if form.is_valid():
            field = "leave_year_start"
            try:
                with transaction.atomic():      # a refused allowance leaves the hours unchanged too
                    if form.cleaned_data["leave_year_start"]:
                        profiles.update_leave_year_start(request.user, person, form.cleaned_data["leave_year_start"])
                    field = "note"
                    if not person.is_gp:
                        profiles.update_hours(request.user, person, form.cleaned_data["weekly_hours"],
                                              form.cleaned_data["days_per_week"])
                    for year, annual, bank in form.allowances():
                        profiles.set_allowance(request.user, person, year, annual, bank,
                                               note=form.cleaned_data["note"])
                context["saved"] = True
            except ValueError as e:
                person.refresh_from_db()
                if field == "leave_year_start":      # the year did not move: show the fields for the years it has
                    form = HoursForm(request.POST, years=leave_years.years_for(person), is_gp=person.is_gp)
                    form.full_clean()
                form.add_error(field, str(e))
    year_list = leave_years.years_for(person)
    if form is None or context["saved"]:
        form = HoursForm(initial=_stored(person, year_list), years=year_list, is_gp=person.is_gp)
    existing = {a.leave_year: a for a in person.allowances.filter(leave_year__in=year_list)}
    context.update({"form": form, "allowance_rows": [(y, existing.get(y)) for y in year_list]})
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
