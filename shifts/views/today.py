"""The Who's in today board (ROTA-12), for managers, one day at a time."""

from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from people.services import access
from shifts.services import today as today_service


@login_required
@access.manager_required
def today_view(request):
    try:
        day = date.fromisoformat(request.GET.get("day", ""))
    except ValueError:
        day = timezone.localdate()
    return render(request, "shifts/today.html", {
        "page_title": "Who's in today", "day": day, "board": today_service.board(day),
        "prev": day - timedelta(days=1), "next": day + timedelta(days=1)})
