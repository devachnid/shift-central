"""The manager's dashboard (REP-07, spec 5 section 8): a few cards, each one
function so each is tested alone. Team managers see their own teams' people;
all-teams managers see everyone. The home page still goes to the rota."""

from datetime import timedelta

from django.utils import timezone

from leave.models import Booking, BookingDay
from leave.services import returns, sickness
from messaging.services import outbox, push
from people.services import access, health, hr_sync
from shifts.models import Entry, OpenShift
from shifts.services import gp_sync, open_shifts
from shifts.services.today import SITES, site_of

NEXT_DAYS = 14


def today_card(people, today):
    by_site = {site: set() for site in SITES}
    home = set()
    shifts = Entry.objects.filter(person__in=people, day=today, kind=Entry.Kind.SHIFT, covered_by__isnull=True).select_related("department")
    for e in shifts:
        if e.wfh:
            home.add(e.person_id)
        else:
            by_site[site_of(e)].add(e.person_id)
    off = (BookingDay.objects.filter(booking__person__in=people, day=today, booking__status__in=Booking.ACTIVE)
           .values("booking__person").distinct().count())
    return {"sites": [(site, len(ids)) for site, ids in by_site.items() if ids], "wfh": len(home), "off": off}


def waiting_card(user, people, today):
    waiting = Booking.objects.filter(person__in=people, status__in=(Booking.Status.PENDING, Booking.Status.CANCEL_REQUESTED))
    me = getattr(user, "person", None)
    if me is not None:
        waiting = waiting.exclude(person=me)          # another manager decides your own
    since = [b.cancel_requested_at or b.requested_at for b in waiting.only("requested_at", "cancel_requested_at")]
    return {"leave": len(since), "leave_oldest_days": (timezone.now() - min(since)).days if since else 0,
            "claims": open_shifts.waiting_claims(user).count()}


def next_card(user, people, today):
    end = today + timedelta(days=NEXT_DAYS - 1)
    leave = list(Booking.objects.filter(person__in=people, status__in=Booking.ACTIVE, dates_only=False, first_day__range=(today, end))
                 .select_related("person", "type").order_by("first_day", "person__name"))
    posts = list(OpenShift.objects.filter(team__in=access.managed_teams(user), state=OpenShift.State.OPEN, day__range=(today, end))
                 .select_related("team").order_by("day", "start"))
    return {"leave": leave, "open_shifts": posts, "end": end}


def flags_card(people, today):
    triggers = []
    for p in people.current(on=today).order_by("name"):
        level = sickness.level_for(p, today)
        if level:
            triggers.append({"person": p, "label": sickness.level_label(level)})
    mine = set(people.values_list("pk", flat=True))
    return {"triggers": triggers, "leaving": health._leaving(people, today),
            "returning": [b for b in returns.due(today) if b.person_id in mine]}


def system_card(user):
    return {"hr": hr_sync.last_run(), "gp_configured": gp_sync.configured(), "gp": gp_sync.last_run(),
            "push": push.status(), "outbox_failures": outbox.failure_count(user)}


def build(user, today=None):
    today = today or timezone.localdate()
    people = access.managed_people(user)
    return {"day": today, "today": today_card(people, today), "waiting": waiting_card(user, people, today),
            "next": next_card(user, people, today), "flags": flags_card(people, today),
            "system": system_card(user) if access.is_all_teams(user) else None}
