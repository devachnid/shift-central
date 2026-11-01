"""What the Outbox page shows and counts (spec 5, section 7)."""

from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from messaging.models import Outbox
from messaging.services import NOT_CONFIGURED
from people.models import Person, TeamManager
from people.services import access

RECENT = timedelta(days=7)      # how far back the nav badge looks
STUCK = timedelta(minutes=5)    # a queued push older than this is not just waiting its turn
STATUSES = ("sent", "queued", "failed", "not configured")


def status(row):
    if row.sent_at:
        return "sent"
    if row.error == NOT_CONFIGURED:
        return "not configured"
    if row.error:
        return "failed"
    return "queued"


def scope(user):
    """All rows for an all-teams manager; for a team manager, rows to people in
    their teams, less rows to other managers (a trigger email to the practice
    manager names a colleague the team manager may not read about) except rows
    to the viewer; nothing for anyone else."""
    if access.is_all_teams(user):
        return Outbox.objects.all()
    if access.is_manager(user):
        managers = Person.objects.filter(Q(pk__in=TeamManager.objects.values("person")) | Q(user__is_all_teams_manager=True))
        mine = access.managed_people(user)
        me = getattr(user, "person", None)
        rows = Outbox.objects.filter(to_person__in=mine).exclude(to_person__in=managers)
        if me is not None:
            rows = rows | Outbox.objects.filter(to_person=me)
        return rows
    return Outbox.objects.none()


def _with_status(rows, state):
    if state == "sent":
        return rows.filter(sent_at__isnull=False)
    unsent = rows.filter(sent_at__isnull=True)
    if state == "not configured":
        return unsent.filter(error=NOT_CONFIGURED)
    if state == "failed":
        return unsent.exclude(error="").exclude(error=NOT_CONFIGURED)
    if state == "queued":
        return unsent.filter(error="")
    return rows


def rows(user, state="", person=None, start=None, end=None):
    found = _with_status(scope(user).select_related("to_person"), state)
    if person is not None:
        found = found.filter(to_person=person)
    if start:
        found = found.filter(queued_at__date__gte=start)
    if end:
        found = found.filter(queued_at__date__lte=end)
    return found


def failure_count(user, now=None):
    """Rows in the last week that failed (a missing relay is not a failure)
    plus pushes still queued after five minutes."""
    now = now or timezone.now()
    recent = scope(user).filter(queued_at__gte=now - RECENT, sent_at__isnull=True)
    failed = recent.exclude(error="").exclude(error=NOT_CONFIGURED).count()
    stuck = recent.filter(channel=Outbox.Channel.PUSH, error="", queued_at__lt=now - STUCK).count()
    return failed + stuck


def blank_old_bodies(months=None, now=None):
    """Messages hold personal details, so their text goes after OUTBOX_BODY_MONTHS
    (the row, who and when stay). 0 keeps the text for ever."""
    months = settings.OUTBOX_BODY_MONTHS if months is None else months
    if months <= 0:
        return 0
    cutoff = (now or timezone.now()) - timedelta(days=round(months * 30.44))
    return Outbox.objects.filter(queued_at__lt=cutoff).exclude(body="").update(body="")
