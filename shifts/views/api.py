"""The grid's JSON API (spec, section 4). JSON in and out, never a redirect:
signed out is 401, refused is 403, bad input is 400, each with an "error"
sentence the island shows in its bar. Every write is a service call."""

import json
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from people.models import Person
from people.services import access, profiles
from shifts.models import Entry
from shifts.services import entries, serialize, window


def api_login_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "signed out"}, status=401)
        return view(request, *args, **kwargs)
    return wrapped


def json_view(view):
    """Parse the body into request.json and turn the services' refusals into
    status codes. A JSON body that is not an object is a 400 too.

    A ValueError or PermissionDenied here carries a sentence a service or
    this module wrote for the person to read, and that sentence is the
    answer. Nothing below parses a request with a bare int(), so Python's
    own wording, which quotes what was sent, is never one of them. A
    TypeError or KeyError is nobody's sentence: it is answered plainly."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.method == "POST":
            try:
                request.json = json.loads(request.body or b"{}")
            except ValueError:
                return JsonResponse({"error": "the request body is not JSON"}, status=400)
            if not isinstance(request.json, dict):
                return JsonResponse({"error": "the request body is not an object"}, status=400)
        try:
            return view(request, *args, **kwargs)
        except PermissionDenied as e:
            return JsonResponse({"error": str(e) or "you can't do that"}, status=403)
        except ValueError as e:
            return JsonResponse({"error": str(e) or "bad request"}, status=400)
        except (TypeError, KeyError):
            return JsonResponse({"error": "bad request"}, status=400)
    return wrapped


def _whole(value, name):
    """A whole number sent as JSON, else a refusal in the app's words."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{name} must be a whole number")
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"{name} must be a whole number") from None


def _row_order(request):
    order = request.json.get("row_order", [])
    if not isinstance(order, list) or not all(window.is_pk(p) for p in order):
        raise ValueError("row_order must be a list of people")
    return [int(p) for p in order]


def _day(value):
    return window.parse_day(value)


def _person(request):
    pk = request.json.get("person")
    if not window.is_pk(pk):
        raise ValueError("no person")
    return get_object_or_404(Person, pk=int(pk))


def _changed(request, result):
    body = serialize.changed(result)
    body["skipped_days"] = getattr(result, "skipped_days", 0)   # a paste's days off, counted in "skipped" too
    body["unnotified"] = window.payload_unnotified(request.user)
    return JsonResponse(body)


@api_login_required
@require_GET
@json_view
def window_view(request):
    start = _day(request.GET.get("from") or timezone.localdate().isoformat())
    weeks = window.clamp_weeks(request.GET.get("weeks", 1))
    return JsonResponse(window.payload(request.user, start, weeks, request.GET))


@api_login_required
@require_POST
@json_view
def cell(request):
    person, day = _person(request), _day(request.json.get("day"))
    rows = entries.set_cell_text(request.user, person, day, str(request.json.get("text") or ""))
    return _changed(request, _single(person, day, rows))


@api_login_required
@require_POST
@json_view
def cell_items(request):
    person, day = _person(request), _day(request.json.get("day"))
    items = request.json.get("items")
    if not isinstance(items, list):
        raise ValueError("items must be a list")
    rows = entries.set_cell(request.user, person, day, items)
    return _changed(request, _single(person, day, rows))


def _single(person, day, rows):
    result = entries.Changed()
    result.add(person, day, rows)
    return result


@api_login_required
@require_POST
@json_view
def entry_patch(request, pk):
    entry = get_object_or_404(Entry.objects.select_related("person", "department"), pk=pk)
    fields = {k: v for k, v in request.json.items() if k in entries.PATCHABLE}
    if not fields:
        raise ValueError("nothing to change")
    entry = entries.patch(request.user, entry, **fields)
    rows = list(Entry.objects.filter(person=entry.person, day=entry.day).select_related("department").order_by("position"))
    return _changed(request, _single(entry.person, entry.day, rows))


def _cells(request):
    cells = request.json.get("cells")
    if not isinstance(cells, list) or not cells:
        raise ValueError("no cells")
    if len(cells) > entries.MAX_CELLS:
        raise ValueError(entries.TOO_MANY)
    if not all(isinstance(c, list) and len(c) == 2 and window.is_pk(c[0]) for c in cells):
        raise ValueError("cells must be pairs of a person and a day")
    return [(int(p), _day(d)) for p, d in cells]


@api_login_required
@require_POST
@json_view
def move(request):
    j = request.json
    return _changed(request, entries.move(request.user, _cells(request), _whole(j.get("days", 0), "days"),
                                          _whole(j.get("rows", 0), "rows"), bool(j.get("copy")), _row_order(request)))


@api_login_required
@require_POST
@json_view
def paste(request):
    if not access.is_manager(request.user):
        raise PermissionDenied("managers only")  # the service skips rows; a non-manager has none to paste into
    j = request.json
    anchor = j.get("anchor")
    if not isinstance(anchor, list) or len(anchor) != 2:
        raise ValueError("no anchor")
    if not window.is_pk(anchor[0]):
        raise ValueError("the anchor must be a person and a day")
    return _changed(request, entries.paste(request.user, (int(anchor[0]), _day(anchor[1])), j.get("block"),
                                           j.get("mode", "replace"), _row_order(request)))


@api_login_required
@require_POST
@json_view
def clear(request):
    return _changed(request, entries.clear(request.user, _cells(request)))


@api_login_required
@require_POST
@json_view
def replace(request):
    j = request.json
    return _changed(request, entries.replace(request.user, _cells(request), str(j.get("find") or ""),
                                             str(j.get("replace") or ""), bool(j.get("match_case"))))


@api_login_required
@require_POST
@json_view
def order(request):
    if not access.is_manager(request.user):
        raise PermissionDenied("managers only")
    ids = [int(p) for p in request.json.get("people", []) if window.is_pk(p)]
    profiles.reorder(request.user, ids)
    return JsonResponse({"ok": True})
