"""The Health card on the Staff page: what a manager should glance at."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from people.models import Allowance
from people.services import access, hr_sync

LEAVING_WINDOW = timedelta(days=30)


def figures(user):
    """The card's figures, limited to the people this user manages.
    Starters count as well as current staff: their hours are wanted before
    day one. GPs are salaried by session and never need weekly hours.
    Setup is hours, days and an allowance: someone with an allowance for
    neither this leave year nor the next still needs a manager. Whatever day
    a person's leave year starts, those two years begin within a year of today."""
    from shifts.services import gp_sync, notify
    today = timezone.localdate()
    people = access.managed_people(user).current(on=today) | access.managed_people(user).filter(
        start_date__gt=today)
    people = people.distinct()
    with_allowance = Allowance.objects.filter(leave_year__gte=today - timedelta(days=365),
                                              leave_year__lte=today + timedelta(days=365)).values("person")
    needs_setup = people.filter(is_gp=False).filter(
        Q(weekly_hours__isnull=True) | Q(days_per_week__isnull=True) | ~Q(pk__in=with_allowance))
    gp_unmatched = gp_sync.unmatched()
    leave = _leave(user, people, today)
    return {
        "last_run": hr_sync.last_run(),
        "gp_configured": gp_sync.configured(),
        "gp_last_run": gp_sync.last_run(),
        "gp_unmatched": gp_unmatched if access.is_all_teams(user) else [],
        "gp_unmatched_count": len(gp_unmatched),
        "unnotified_old": notify.old_count(user),
        "needs_setup": needs_setup.order_by("name"),
        "not_seen": hr_sync.not_seen_recently().filter(pk__in=people).order_by("name"),
        "leaving_soon": people.filter(end_date__gte=today, end_date__lte=today + LEAVING_WINDOW)
                              .order_by("end_date"),
        **leave,
    }


def _leave(user, people, today):
    """Leave's lines: requests waiting for a decision (the user's own never
    are, another manager decides those), placeholder days still to be
    costed from a rota, and people whose leave year, this one or the next
    (the two a booking can be made in), has gone below zero."""
    from leave.models import Adjustment, Booking, BookingDay
    from leave.services import balances, years
    me = getattr(user, "person", None)
    waiting = Booking.objects.filter(person__in=people, status__in=(Booking.Status.PENDING, Booking.Status.CANCEL_REQUESTED))
    if me is not None:
        waiting = waiting.exclude(person=me)
    since = [b.cancel_requested_at or b.requested_at for b in waiting.only("requested_at", "cancel_requested_at")]
    placeholders = BookingDay.objects.filter(booking__person__in=people, booking__status__in=Booking.ACTIVE, placeholder=True)
    # A balance can only be below zero for someone with leave taken or hours
    # taken away in those two years; the statement is the slow part.
    window = (today - timedelta(days=366), today + timedelta(days=732))
    drawing = ("annual", "bank_holiday")
    candidates = set(BookingDay.objects.filter(booking__person__in=people, booking__status__in=Booking.ACTIVE, account__in=drawing,
                                               day__range=window).values_list("booking__person", flat=True))
    candidates |= set(Adjustment.objects.filter(person__in=people, account__in=drawing, seconds__lt=0,
                                                leave_year__range=window).values_list("person", flat=True))
    negative = []
    for p in people.filter(pk__in=candidates, is_gp=False).order_by("name"):
        statements = (balances.statement(p, year) for year in years.years_for(p, today))
        # A year with no allowance set is "needs hours and allowances", not a deficit.
        if any(not s.missing and s.annual_remaining < 0 for s in statements):
            negative.append(p)
    return {
        "waiting": len(since),
        "waiting_oldest_days": (timezone.now() - min(since)).days if since else 0,
        "placeholder_count": placeholders.count(),
        "placeholders": list(placeholders.select_related("booking__person").order_by("day", "pk")[:20]),
        "negative": negative,
    }
