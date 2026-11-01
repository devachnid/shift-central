"""LEAVE-29 and NOTIF-07: the day after a long sickness, or a booking of a
type that flags the return (maternity, adoption), the managers are told
the person is back and what leave they have, so it can be planned. Once
per booking; a run that missed a day catches up for a fortnight."""

import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from leave.models import Booking
from leave.services import balances, notify, sickness, years

log = logging.getLogger("leave.returns")

CATCH_UP = timedelta(days=14)


def due(today=None):
    today = today or timezone.localdate()
    rows = (Booking.objects.filter(status__in=Booking.ACTIVE, dates_only=False, return_flagged_at__isnull=True,
                                   last_day__lt=today, last_day__gte=today - CATCH_UP)
            .filter(Q(type__flag_return=True) | Q(type__sickness=True))
            .filter(Q(person__end_date__isnull=True) | Q(person__end_date__gte=today))
            .select_related("person", "type").order_by("last_day", "pk"))
    return [b for b in rows if b.type.flag_return or sickness.is_long(b)]


def send(today=None, base_url=""):
    """One email per booking due; one booking's failure is logged and the
    others still go."""
    today = today or timezone.localdate()
    n = 0
    for b in due(today):
        try:
            # The figures first, so a failure here cannot leave a booking claimed and never sent.
            statement = balances.statement(b.person, years.year_of(b.person, today))
            # Claim, then send: a second run alongside this one finds it claimed and sends nothing.
            if not Booking.objects.filter(pk=b.pk, return_flagged_at__isnull=True).update(return_flagged_at=timezone.now()):
                continue
            notify.returned(b, statement, base_url)
        except Exception:
            log.exception("return flag: booking %s", b.pk)
            continue
        n += 1
    return n
