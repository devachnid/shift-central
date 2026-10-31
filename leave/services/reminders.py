"""REQ-13: a request still waiting after N working days reminds its
managers, once. Working days are Monday to Friday less the bank holidays."""

from datetime import timedelta

from django.utils import timezone

from leave.models import BankHoliday, Booking
from leave.services import notify, settings


def working_days_between(a, b):
    """Working days after `a` up to and including `b`."""
    if b <= a:
        return 0
    holidays = set(BankHoliday.objects.filter(day__range=(a, b)).values_list("day", flat=True))
    n, day = 0, a + timedelta(days=1)
    while day <= b:
        if day.weekday() < 5 and day not in holidays:
            n += 1
        day += timedelta(days=1)
    return n


def due(now=None):
    now = now or timezone.now()
    today = timezone.localtime(now).date()
    limit = settings.get().reminder_working_days
    out = []
    for b in Booking.objects.filter(status__in=(Booking.Status.PENDING, Booking.Status.CANCEL_REQUESTED), reminded_at__isnull=True).select_related("person", "type"):
        since = timezone.localtime(b.cancel_requested_at or b.requested_at).date()
        if working_days_between(since, today) >= limit:
            out.append(b)
    return out


def send(now=None, base_url=""):
    now = now or timezone.now()
    count = 0
    for b in due(now):
        notify.reminder(b, base_url)
        b.reminded_at = now
        b.save(update_fields=["reminded_at"])
        count += 1
    return count
