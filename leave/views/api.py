"""GET /api/v1/leave?from=YYYY-MM-DD&to=YYYY-MM-DD → approved GP leave in the
range, for the GP rota app. Read-only; the token is checked by api_auth. The
answer is never logged."""

from datetime import date

from django.http import JsonResponse
from django.utils import timezone

from leave.api_auth import token_required
from leave.services import feed

MAX_DAYS = 1100


def _bad(message):
    return JsonResponse({"error": message}, status=400)


@token_required
def leave_feed(request):
    try:
        start = date.fromisoformat(request.GET.get("from", ""))
        end = date.fromisoformat(request.GET.get("to", ""))
    except ValueError:
        return _bad("from and to must be dates (YYYY-MM-DD)")
    if end < start:
        return _bad("to is before from")
    if (end - start).days > MAX_DAYS:
        return _bad(f"the range is over {MAX_DAYS} days")
    return JsonResponse({"from": start.isoformat(), "to": end.isoformat(), "generated_at": timezone.now().isoformat(), "leave": feed.records(start, end)})
