"""The Health card on the Staff page: what a manager should glance at."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from people.models import Allowance
from people.services import access, hr_sync, profiles

LEAVING_WINDOW = timedelta(days=30)


def figures(user):
    """The card's four figures, limited to the people this user manages.
    Starters count as well as current staff: their hours are wanted before
    day one. GPs are salaried by session and never need weekly hours.
    Setup is hours, days and an allowance: someone with an allowance for
    neither this leave year nor the next still needs a manager."""
    today = timezone.localdate()
    people = access.managed_people(user).current(on=today) | access.managed_people(user).filter(
        start_date__gt=today)
    people = people.distinct()
    with_allowance = Allowance.objects.filter(leave_year__in=profiles.leave_years(today)).values("person")
    needs_setup = people.filter(is_gp=False).filter(
        Q(weekly_hours__isnull=True) | Q(days_per_week__isnull=True) | ~Q(pk__in=with_allowance))
    return {
        "last_run": hr_sync.last_run(),
        "needs_setup": needs_setup.order_by("name"),
        "not_seen": hr_sync.not_seen_recently().filter(pk__in=people).order_by("name"),
        "leaving_soon": people.filter(end_date__gte=today, end_date__lte=today + LEAVING_WINDOW)
                              .order_by("end_date"),
    }
