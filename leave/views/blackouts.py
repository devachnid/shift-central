"""Blackouts (REQ-08): days staff cannot request leave on, for some teams
or everyone. Managers still book. A list, with add and edit pop-ups; the
pop-up answers with a redirect to the list, which is not the rota grid."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from leave.forms import BlackoutForm
from leave.models import Blackout
from leave.services import blackouts
from people.services import access

LIST = "/time-off/blackouts/"


@login_required
@access.manager_required
def index(request):
    rows = Blackout.objects.prefetch_related("teams").order_by("-first_day", "-pk")
    return render(request, "leave/blackouts.html", {"page_title": "Blackouts", "rows": rows})


def _dialog(request, row=None):
    initial = {"first_day": row.first_day, "last_day": row.last_day, "note": row.note, "teams": list(row.teams.all())} if row else None
    form = BlackoutForm(request.POST or None, initial=initial, row=row)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        if row is None:
            blackouts.add(request.user, d["first_day"], d["last_day"], d["teams"], d["note"])
        else:
            blackouts.update(request.user, row, d["first_day"], d["last_day"], d["teams"], d["note"])
        return JsonResponse({"redirect": LIST})
    return render(request, "leave/blackout_dialog.html", {"form": form, "row": row})


@login_required
@access.manager_required
def add(request):
    return _dialog(request)


@login_required
@access.manager_required
def edit(request, pk):
    return _dialog(request, get_object_or_404(Blackout, pk=pk))


@login_required
@access.manager_required
@require_POST
def delete(request, pk):
    blackouts.remove(request.user, get_object_or_404(Blackout, pk=pk))
    return redirect(LIST)
