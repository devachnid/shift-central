"""The pop-ups over the grid (spec, section 4): the shift editor, Options,
Filters, Find & Replace and Templates. Each saves through a service and
answers {"refresh": true}, which modal.js turns into a reload of the
island's window."""

import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render

from people.models import Department, Person, Team
from people.services import access
from shifts.forms import OptionsForm, ReplaceForm, ShiftForm, TemplateForm
from shifts.models import Entry, Template
from shifts.services import entries, options, window
from shifts.services import templates as template_service

REFRESH = {"refresh": True}


def _cells(text):
    """'12:2027-03-01,12:2027-03-02' → [(12, date), …]."""
    out = []
    for part in (text or "").split(","):
        if ":" not in part:
            continue
        pk, day = part.split(":", 1)
        if window.is_pk(pk):
            out.append((int(pk), window.parse_day(day)))
    if not out:
        raise ValueError("no cells selected")
    return out


def _row_order(text):
    return [int(p) for p in (text or "").split(",") if window.is_pk(p)]


@login_required
def shift(request, person_pk, day, entry_pk=None):
    person = get_object_or_404(Person, pk=person_pk)
    if not access.can_manage(request.user, person):
        raise PermissionDenied
    try:
        day = window.parse_day(day)
    except ValueError:
        raise Http404("not a date") from None
    entry = get_object_or_404(Entry, pk=entry_pk, person=person, day=day) if entry_pk else None
    if request.method == "POST":
        form = ShiftForm(request.POST)
        if form.is_valid():
            cell = list(Entry.objects.filter(person=person, day=day).order_by("position"))
            items = [{"kind": e.kind, "start": e.start and e.start.strftime("%H:%M"),
                      "finish": e.finish and e.finish.strftime("%H:%M"), "break_minutes": e.break_minutes,
                      "department": e.department_id, "text": e.text, "wfh": e.wfh, "overtime": e.overtime,
                      "appearance": e.appearance}
                     for e in cell]
            new = form.item()
            if entry is None:
                items.append(new)
            else:
                # By pk, not by position: an admin delete can leave a gap in the positions.
                new["appearance"] = entry.appearance
                items[[e.pk for e in cell].index(entry.pk)] = new
            try:
                entries.set_cell(request.user, person, day, items)
                return JsonResponse(REFRESH)
            except ValueError as e:
                form.add_error(None, str(e))
    else:
        initial = {}
        if entry is not None:
            initial = {"start": entry.start, "finish": entry.finish, "break_minutes": entry.break_minutes,
                       "department": entry.department, "text": entry.text, "wfh": entry.wfh, "overtime": entry.overtime}
        form = ShiftForm(initial=initial)
    return render(request, "shifts/shift_dialog.html", {"form": form, "person": person, "day": day, "entry": entry})


@login_required
def options_view(request):
    if request.method == "POST":
        form = OptionsForm(request.POST)
        if form.is_valid():
            options.save(request.user, form.cleaned_data)
            return JsonResponse(REFRESH)
    else:
        current = options.for_user(request.user)
        current["days"] = [str(d) for d in current["days"]]
        form = OptionsForm(initial=current)
    return render(request, "shifts/options_dialog.html", {"form": form, "is_manager": access.is_manager(request.user),
                                                          "query": request.META.get("QUERY_STRING", "")})


@login_required
def filters(request):
    return render(request, "shifts/filters_dialog.html", {
        "teams": Team.objects.filter(active=True), "departments": Department.objects.filter(archived=False),
        "name": request.GET.get("name", ""), "team": request.GET.getlist("team"), "dept": request.GET.getlist("dept"),
        "from": request.GET.get("from", ""), "weeks": request.GET.get("weeks", "1")})


@login_required
@access.manager_required
def replace(request):
    if request.method == "POST":
        form = ReplaceForm(request.POST)
        if form.is_valid():
            try:
                entries.replace(request.user, _cells(form.cleaned_data["cells"]), form.cleaned_data["find"],
                                form.cleaned_data["replace"], form.cleaned_data["match_case"])
                return JsonResponse(REFRESH)
            except ValueError as e:
                form.add_error(None, str(e))
    else:
        form = ReplaceForm(initial={"cells": request.GET.get("cells", "")})
    return render(request, "shifts/replace_dialog.html", {"form": form})


def _templates_dialog(request, cell, row_order, **flash):
    return render(request, "shifts/templates_dialog.html", {
        "templates": Template.objects.all(), "cell": cell, "row_order": row_order, **flash})


@login_required
@access.manager_required
def templates_list(request):
    return _templates_dialog(request, request.GET.get("cell", ""), request.GET.get("row_order", ""))


@login_required
@access.manager_required
def template_save(request):
    if request.method == "POST":
        form = TemplateForm(request.POST)
        if form.is_valid():
            try:
                block = json.loads(request.POST.get("block") or "{}")
                template_service.save(request.user, form.cleaned_data["name"], block)
                return JsonResponse(REFRESH)
            except ValueError as e:
                form.add_error("name", str(e))
    else:
        form = TemplateForm()
    return render(request, "shifts/template_save_dialog.html", {
        "form": form,
        # not "block": inside a {% block %} that name is the template engine's own
        "block_json": request.POST.get("block") or request.GET.get("block", "")})


@login_required
@access.manager_required
def template_apply(request, pk):
    template = get_object_or_404(Template, pk=pk)
    if request.method != "POST":
        raise PermissionDenied
    cell, row_order = request.POST.get("cell", ""), request.POST.get("row_order", "")
    try:
        result = entries.paste(request.user, _cells(cell)[0], template.block,
                               options.for_user(request.user)["paste"], _row_order(row_order))
    except ValueError as e:
        return _templates_dialog(request, cell, row_order, error=str(e))
    if result.skipped:
        # Shown in place of the refresh: the island picks the paste up on its next window load.
        # Without the cell and row order, so no Apply button is offered: a second click would
        # paste the template again on top of the first.
        noun = "row" if result.skipped == 1 else "rows"
        return _templates_dialog(request, "", "", warning=f"{result.skipped} {noun} couldn't be pasted onto.")
    return JsonResponse(REFRESH)


@login_required
@access.manager_required
def template_rename(request, pk):
    template = get_object_or_404(Template, pk=pk)
    form = TemplateForm(request.POST if request.method == "POST" else None, initial={"name": template.name})
    if request.method == "POST" and form.is_valid():
        try:
            template_service.rename(request.user, template, form.cleaned_data["name"])
            return JsonResponse(REFRESH)
        except ValueError as e:
            form.add_error("name", str(e))
    return render(request, "shifts/template_save_dialog.html", {"form": form, "template": template})


@login_required
@access.manager_required
def template_delete(request, pk):
    if request.method != "POST":
        raise PermissionDenied
    template_service.delete(request.user, get_object_or_404(Template, pk=pk))
    return JsonResponse(REFRESH)


@login_required
@access.manager_required
def notify_view(request):
    from shifts.services import notify
    outcome = warning = None
    if request.method == "POST":
        ids = [int(p) for p in request.POST.getlist("people") if window.is_pk(p)]
        if ids:
            outcome = notify.send(request.user, ids, request.build_absolute_uri("/"))
        else:
            warning = "Nothing ticked."
    return render(request, "shifts/notify_dialog.html",
                  {"pending": notify.pending(request.user), "outcome": outcome, "warning": warning})
