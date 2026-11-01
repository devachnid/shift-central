"""Turning push on for a phone (spec 5, section 4)."""

import json

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from messaging.models import PushDevice
from messaging.services import push


def _person(request):
    return getattr(request.user, "person", None)


@login_required
def notifications(request):
    person = _person(request)
    return render(request, "messaging/notifications.html", {
        "page_title": "Notifications", "configured": push.configured(), "public_key": settings.VAPID_PUBLIC_KEY,
        "devices": person.push_devices.all() if person is not None else []})


def _body(request):
    try:
        data = json.loads(request.body)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


@login_required
@require_POST
def subscribe(request):
    person = _person(request)
    if person is None or not push.configured():
        return JsonResponse({"error": "Notifications are not available."}, status=400)
    data = _body(request)
    keys = data.get("keys") if isinstance(data.get("keys"), dict) else {}
    try:
        device = push.register(person, data.get("endpoint"), keys.get("p256dh"), keys.get("auth"),
                               request.META.get("HTTP_USER_AGENT", ""))
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"ok": True, "id": device.pk})


@login_required
@require_POST
def unsubscribe(request):
    person = _person(request)
    if person is None or not push.unregister(person, _body(request).get("endpoint")):
        return JsonResponse({"error": "No such device."}, status=404)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def remove_device(request, pk):
    person = _person(request)
    if person is None:
        raise Http404
    get_object_or_404(PushDevice, pk=pk, person=person).delete()
    return redirect("notifications")
