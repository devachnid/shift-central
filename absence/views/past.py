"""The past schedule section (MIG-05, ACC-06): managers only; 2026
sickness typed as dates-only bookings so the triggers are right from
launch. Entries are listed with each person's instances and trigger."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from absence.forms import PastSicknessForm
from leave.models import Booking
from leave.services import bookings, sickness
from leave.services.common import LeaveError
from leave.views.add import _sickness_preview
from people.services import access

REFRESH = {"refresh": True}


@login_required
@access.manager_required
def index(request):
    people = access.managed_people(request.user)
    rows = (Booking.objects.filter(person__in=people, dates_only=True, status__in=Booking.LIVE)
            .select_related("person__team", "type", "decided_by").order_by("-first_day", "person__last_name"))
    levels = {}
    out = []
    for b in rows:
        if b.person_id not in levels:
            n = len(sickness.instances(b.person))
            levels[b.person_id] = (n, sickness.level_label(sickness.level(n)))
        out.append({"b": b, "days": (b.last_day - b.first_day).days + 1, "long": sickness.is_long(b), "instances": levels[b.person_id][0], "trigger": levels[b.person_id][1]})
    return render(request, "absence/past.html", {"page_title": "Past schedule", "rows": out})


@login_required
@access.manager_required
def add(request):
    form = PastSicknessForm(request.user, request.POST or None)
    preview = {}
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        preview = _sickness_preview(d["person"], d["type"], d["first_day"], d["last_day"], dates_only=True)
        if not request.POST.get("preview"):
            s = preview.get("sickness") or {}
            base = request.build_absolute_uri("/")
            try:
                if s.get("joins") is not None and not s.get("extend_blocked") and request.POST.get("join", "extend") == "extend":
                    bookings.edit(request.user, s["joins"], base_url=base, note="extended (joined on)", first=s["extended_first"], last=s["extended_last"])
                else:
                    bookings.book(request.user, d["person"], d["type"], d["first_day"], d["last_day"], "whole", base_url=base, dates_only=True)
                return JsonResponse(REFRESH)
            except LeaveError as e:
                form.add_error(None, e.message)
    return render(request, "absence/past_dialog.html", {"form": form, "preview": preview, "join": request.POST.get("join", "extend"), "editing": False})
