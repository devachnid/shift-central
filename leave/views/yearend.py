"""The year-end page (LEAVE-21): open flags for the manager's people, each
with a Decide pop-up; decided rows beneath for the record."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from leave.forms import YearEndForm
from leave.models import YearEnd
from leave.services import yearend, years
from people.services import access

REFRESH = {"refresh": True}


def _row(r, with_long=True):
    return {"row": r, "label": years.label(r.year_ended), "long": with_long and yearend.long_absence(r), "over": r.annual_remaining < 0}


@login_required
@access.manager_required
def index(request):
    people = access.managed_people(request.user)
    decided = (YearEnd.objects.filter(person__in=people, decided_at__isnull=False).exclude(decided_by__isnull=True)       # the auto-closed "nothing left" rows
               .select_related("person__team", "decided_by").order_by("-decided_at")[:200])
    return render(request, "leave/year_end.html", {
        "page_title": "Year end", "open": [_row(r) for r in yearend.open_rows(request.user)],
        "decided": [_row(r, with_long=False) for r in decided]})


@login_required
@access.manager_required
def decide(request, pk):
    row = get_object_or_404(YearEnd.objects.select_related("person"), pk=pk)
    if not access.can_manage(request.user, row.person):
        raise PermissionDenied
    form = YearEndForm(request.POST or None, row=row)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            yearend.decide(request.user, row, d["annual_carry"], d["toil_keep"], d["note"])
            return JsonResponse(REFRESH)
        except ValueError as e:
            form.add_error(None, str(e))
    return render(request, "leave/year_end_dialog.html", {"form": form, **_row(row), "new_year": years.label(years.next_year(row.year_ended))})
