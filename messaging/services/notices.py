"""The notice board (spec 5, section 5): managers post plain text for
everyone or chosen teams; staff read. Posting tells nobody unless asked."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from messaging import services as mail
from messaging.models import Notice
from people.models import Person, Team
from people.services import access, audit

TITLE_MAX, BODY_MAX = 120, 5000


class NoticeError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _check(title, body, everyone, team_ids):
    title, body = (title or "").strip(), (body or "").strip()
    if not title:
        raise NoticeError("A notice needs a title.")
    if not body:
        raise NoticeError("A notice needs some text.")
    if len(title) > TITLE_MAX or len(body) > BODY_MAX:
        raise NoticeError(f"That is too long: the title is at most {TITLE_MAX} characters and the text {BODY_MAX}.")
    if not everyone and not list(team_ids):
        raise NoticeError("Choose everyone or at least one team.")
    return title, body


def post(user, title, body, everyone, team_ids, pinned=False, show_until=None, notify=False, base_url=""):
    if not access.is_manager(user):
        raise PermissionDenied("only managers post notices")
    title, body = _check(title, body, everyone, team_ids)
    with transaction.atomic():
        notice = Notice.objects.create(title=title, body=body, everyone=bool(everyone), pinned=bool(pinned),
                                       show_until=show_until, posted_by=user)
        if not everyone:
            notice.teams.set(Team.objects.filter(pk__in=list(team_ids)))
        audit.record(user, notice, {"posted": ("", title)}, note="notice")
    if notify:
        transaction.on_commit(lambda: _tell(notice, user, base_url))
    return notice


def _may_change(user, notice):
    if not (access.is_all_teams(user) or (access.is_manager(user) and notice.posted_by_id == user.pk)):
        raise PermissionDenied("not your notice")


def edit(user, notice, title, body, everyone, team_ids, pinned=False, show_until=None):
    _may_change(user, notice)
    title, body = _check(title, body, everyone, team_ids)
    with transaction.atomic():
        notice.title, notice.body, notice.everyone, notice.pinned, notice.show_until = title, body, bool(everyone), bool(pinned), show_until
        notice.save()
        notice.teams.set([] if everyone else Team.objects.filter(pk__in=list(team_ids)))
        audit.record(user, notice, {"edited": ("", title)}, note="notice")
    return notice


def remove(user, notice):
    _may_change(user, notice)
    with transaction.atomic():
        audit.record(user, notice, {"removed": ("", notice.title)}, note="notice")
        notice.delete()


def visible_to(user):
    """The notices this user's team (or everyone) was given, not past their
    show-until date; pinned first, then newest."""
    me = getattr(user, "person", None)
    audience = Q(everyone=True)
    if me is not None and me.team_id:
        audience |= Q(teams=me.team_id)
    today = timezone.localdate()
    return (Notice.objects.filter(audience).filter(Q(show_until__isnull=True) | Q(show_until__gte=today))
            .distinct().order_by("-pinned", "-created_at", "-pk"))


def editable(user):
    if access.is_all_teams(user):
        return Notice.objects.all()
    if access.is_manager(user):
        return Notice.objects.filter(posted_by=user)
    return Notice.objects.none()


def _tell(notice, poster, base_url):
    people = Person.objects.current().filter(user__isnull=False, user__is_active=True).exclude(user=poster)
    if not notice.everyone:
        people = people.filter(team__in=notice.teams.all())
    text = f"{notice.title}\n\nRead it on the notice board: {mail.absolute_link(base_url, '/notices/')}\n"
    with mail.batch() as connection:
        for person in people:
            mail.send(person, notice.title, text, connection=connection, url="/notices/")
