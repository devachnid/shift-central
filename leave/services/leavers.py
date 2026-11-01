"""LEAVE-14 and NOTIF-06: when Practice HR gives someone an end date, their
managers are told what leave is left or over as at that day and which
bookings run past it; a week before the day they are told again. Nothing
is cancelled for them: the manager decides."""

import logging
from datetime import timedelta

from django.utils import timezone

from leave.models import Booking
from leave.services import balances, hours, notify, years
from people.models import Person

log = logging.getLogger("leave.leavers")

WEEK = timedelta(days=7)


def figure(person):
    """The leaving year and its statement: the pro-rata already stops at the
    end date, so annual_remaining is the figure LEAVE-14 asks for."""
    year = years.year_of(person, person.end_date)
    return year, balances.statement(person, year)


def figure_text(statement):
    if statement.missing:
        return "no allowance set for the leaving year"
    remaining = statement.annual_remaining
    if remaining < 0:
        return f"{hours.fmt(-remaining)} of annual leave over"
    return f"{hours.fmt(remaining)} of annual leave remaining"


def after_leaving(person):
    """Live bookings with a day after the end date, to shorten or cancel."""
    return list(Booking.objects.filter(person=person, status__in=Booking.LIVE, last_day__gt=person.end_date)
                .select_related("type").order_by("first_day", "pk"))


def flag(person, base_url=""):
    """The "date entered" email, once per end date. A cleared date resets
    both flags silently. Within a week of the date, or once it has passed,
    the one email covers the week's reminder too."""
    if person.end_date is None:
        if person.leaver_flagged_for or person.leaver_week_flagged_for:
            Person.objects.filter(pk=person.pk).update(leaver_flagged_for=None, leaver_week_flagged_for=None)
            person.leaver_flagged_for = person.leaver_week_flagged_for = None
        return False
    if person.leaver_flagged_for == person.end_date:
        return False
    today = timezone.localdate()
    past = person.end_date < today
    within_week = today <= person.end_date <= today + WEEK
    fields = {"leaver_flagged_for": person.end_date}
    if within_week or past:          # a date already gone has no week reminder to come
        fields["leaver_week_flagged_for"] = person.end_date
    # The figures first, so a failure here cannot leave a date claimed and never sent.
    _, statement = figure(person)
    after = after_leaving(person)
    # Claim, then send: two syncs seeing the same new date send one email between them.
    if not Person.objects.filter(pk=person.pk).exclude(leaver_flagged_for=person.end_date).update(**fields):
        return False
    for k, v in fields.items():
        setattr(person, k, v)
    notify.leaving(person, statement, after, week=within_week, past=past, base_url=base_url)
    return True


def week_flags(today=None, base_url=""):
    """The reminder a week out, for everyone leaving in the next seven days
    not yet reminded for that date. Run daily; one person's failure is
    logged and the others still go."""
    today = today or timezone.localdate()
    n = 0
    for p in Person.objects.filter(end_date__gte=today, end_date__lte=today + WEEK).order_by("end_date", "pk"):
        if p.leaver_week_flagged_for == p.end_date:
            continue
        try:
            # The figures first, so a failure here cannot leave a date claimed and never sent.
            _, statement = figure(p)
            after = after_leaving(p)
            if not Person.objects.filter(pk=p.pk).exclude(leaver_week_flagged_for=p.end_date).update(leaver_week_flagged_for=p.end_date):
                continue           # claimed by a run alongside this one
            notify.leaving(p, statement, after, week=True, base_url=base_url)
        except Exception:
            log.exception("leaver week reminder: person %s", p.pk)
            continue
        n += 1
    return n
