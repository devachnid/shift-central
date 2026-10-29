"""The profile pop-up: one dialog, four tabs, each a GET to render and a
POST to save. Who may see which tab is decided here from access.*."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, render

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
    context = {"person": person, "tab": tab, "manages": manages, "saved": False,
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
    initial = {"weekly_hours": person.weekly_hours, "days_per_week": person.days_per_week}
    for a in person.allowances.filter(leave_year__in=years):
        initial[f"annual_{a.leave_year.year}"] = a.annual_hours
        initial[f"bank_holiday_{a.leave_year.year}"] = a.bank_holiday_hours
    return initial


def _hours(request, person, context):
    years = profiles.leave_years()
    form = None
    if request.method == "POST":
        form = HoursForm(request.POST, years=years, is_gp=person.is_gp)
        if form.is_valid():
            try:
                with transaction.atomic():      # a refused allowance leaves the hours unchanged too
                    if not person.is_gp:
                        profiles.update_hours(request.user, person, form.cleaned_data["weekly_hours"],
                                              form.cleaned_data["days_per_week"])
                    for year, annual, bank in form.allowances():
                        profiles.set_allowance(request.user, person, year, annual, bank,
                                               note=form.cleaned_data["note"])
                context["saved"] = True
            except ValueError as e:
                person.refresh_from_db()
                form.add_error("note", str(e))
    if form is None or context["saved"]:
        form = HoursForm(initial=_stored(person, years), years=years, is_gp=person.is_gp)
    existing = {a.leave_year: a for a in person.allowances.filter(leave_year__in=years)}
    context.update({"form": form, "allowance_rows": [(y, existing.get(y)) for y in years]})


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
        AuditEntry.objects.filter(model="people.allowance", object_id__in=allowance_ids)
    return render(request, "people/history_dialog.html",
                  {"person": person, "entries": entries.order_by("-at")[:200]})
