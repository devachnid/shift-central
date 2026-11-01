"""Messages from managers to staff (spec 5, section 5): any manager may send
to people, teams or everyone; staff read and cannot reply. The email carries
the full text, the push only the subject."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from messaging import services as mail
from messaging.models import Message, MessageRecipient
from people.models import Person, Team
from people.services import access, audit

SUBJECT_MAX, BODY_MAX = 150, 5000


class MessageError(Exception):
    """A problem the sender can fix; `.message` is the sentence to show."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _recipients(sender, person_ids, team_ids, everyone):
    people = Person.objects.current()
    if everyone:
        chosen = people
    else:
        if not person_ids and not team_ids:
            raise MessageError("Choose who the message is for.")
        chosen = people.filter(Q(pk__in=list(person_ids)) | Q(team_id__in=list(team_ids)))
    me = getattr(sender, "person", None)
    if me is not None:
        chosen = chosen.exclude(pk=me.pk)
    out = list(chosen.distinct())
    if not out:
        raise MessageError("Nobody to send that to.")
    return out


def send(user, subject, body, person_ids=(), team_ids=(), everyone=False, base_url=""):
    if not access.is_manager(user):
        raise PermissionDenied("only managers send messages")
    subject, body = (subject or "").strip(), (body or "").strip()
    if not subject or not body:
        raise MessageError("A message needs a subject and some text.")
    if len(subject) > SUBJECT_MAX or len(body) > BODY_MAX:
        raise MessageError(f"That is too long: the subject is at most {SUBJECT_MAX} characters and the text {BODY_MAX}.")
    people = _recipients(user, person_ids, team_ids, everyone)
    with transaction.atomic():
        message = Message.objects.create(sender=user, subject=subject, body=body, everyone=bool(everyone))
        if not everyone:
            message.teams.set(Team.objects.filter(pk__in=list(team_ids)))
        MessageRecipient.objects.bulk_create([MessageRecipient(message=message, person=p) for p in people])
        audit.record(user, message, {"sent": ("", f"to {len(people)} people: {subject[:80]}")}, note="message")
    transaction.on_commit(lambda: _deliver(message, people, base_url))
    return message


def _deliver(message, people, base_url):
    sender = getattr(message.sender, "person", None) if message.sender_id else None
    path = f"/messages/{message.pk}/"
    text = f"{sender.name if sender else 'A manager'} wrote:\n\n{message.body}\n\n{mail.absolute_link(base_url, path)}\n"
    with mail.batch() as connection:
        for person in people:
            mail.send(person, message.subject, text, connection=connection, url=path)


def inbox(user):
    me = getattr(user, "person", None)
    if me is None:
        return MessageRecipient.objects.none()
    return (MessageRecipient.objects.filter(person=me).select_related("message__sender__person")
            .order_by("-message__created_at", "-message_id"))


def unread_count(user):
    if not getattr(user, "is_authenticated", False):
        return 0
    return inbox(user).filter(read_at__isnull=True).count()


def open_message(user, pk):
    message = Message.objects.select_related("sender__person").filter(pk=pk).first()
    me = getattr(user, "person", None)
    receipt = MessageRecipient.objects.filter(message_id=pk, person=me).first() if me is not None else None
    if message is None or not (receipt or message.sender_id == user.pk or access.is_all_teams(user)):
        raise Http404
    if receipt is not None and receipt.read_at is None:
        receipt.read_at = timezone.now()
        receipt.save(update_fields=["read_at"])
    return message, receipt


def sent(user):
    rows = Message.objects.select_related("sender__person").prefetch_related("recipients__person")
    return rows if access.is_all_teams(user) else rows.filter(sender=user)
