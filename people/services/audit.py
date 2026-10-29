"""The one writer of AuditEntry. Every service in people calls record()
after a change. The sync has no user; it writes as SYNC_ACTOR_EMAIL."""

from people.models import AuditEntry

SYNC_ACTOR_EMAIL = "practice-hr"
SYNC_NOTE = "from Practice HR"


def _label(obj):
    return f"{obj._meta.app_label}.{obj._meta.model_name}"


def record(actor, obj, changes, note=""):
    """changes is {field: (before, after)}; unchanged pairs are skipped.
    actor None means the sync."""
    email = getattr(actor, "email", "") if actor is not None else SYNC_ACTOR_EMAIL
    rows = [
        AuditEntry(actor=actor, actor_email=email, kind=AuditEntry.Kind.CHANGE, model=_label(obj),
                   object_id=obj.pk, field=field, before=str(before), after=str(after), note=note)
        for field, (before, after) in changes.items() if before != after
    ]
    return AuditEntry.objects.bulk_create(rows)
