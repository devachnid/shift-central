"""Turning push on for a phone (spec 5, section 4)."""

import json
import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from messaging.services import push

log = logging.getLogger("messaging.push")
NO_PERSON = ("This account has no staff record, so it can't receive notifications. "
             "Sign in with your own practice account.")


def _person(request):
    return getattr(request.user, "person", None)


@login_required
def notifications(request):
    person = _person(request)
    return render(request, "messaging/notifications.html", {
        "page_title": "Notifications", "configured": push.configured(), "public_key": settings.VAPID_PUBLIC_KEY,
        "has_person": person is not None, "no_person": NO_PERSON,
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
    """Register this phone for the signed-in person. push.js calls it when
    notifications are turned on and again on every visit to the page, so a
    phone the server lost, or one last used by someone else, is put right;
    `created` tells the page to reload its list."""
    person = _person(request)
    if not push.configured():
        return JsonResponse({"error": "Notifications are not available."}, status=400)
    if person is None:
        log.info("push subscribe refused for user %s: no staff record", request.user.pk)
        return JsonResponse({"error": NO_PERSON}, status=400)
    data = _body(request)
    keys = data.get("keys") if isinstance(data.get("keys"), dict) else {}
    try:
        device, created = push.register(person, data.get("endpoint"), keys.get("p256dh"), keys.get("auth"),
                                        request.META.get("HTTP_USER_AGENT", ""))
    except ValueError as e:
        log.info("push subscribe refused for user %s: %s (host %s)", request.user.pk, e,
                 push.endpoint_host(data.get("endpoint")))
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"ok": True, "id": device.pk, "created": created})


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
    if person is None or not push.remove_device(person, pk):
        raise Http404
    return redirect("notifications")
