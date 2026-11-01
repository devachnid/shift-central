"""Open shifts (ROTA-11, REQ-16; spec 5 section 3). A manager of the owning
team posts a shift for chosen teams or everyone; people in the audience
claim it; a manager of the owning team approves one claim, which adds the
shift to the claimant's rota through entries.add_item and closes the post."""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from leave.services import costing as leave_costing
from people.models import Person
from people.services import access, audit
from shifts.models import Entry, OpenShift, OpenShiftClaim
from shifts.services import entries
from shifts.services import notify as rota_notify
from shifts.services import open_shift_mail as mail

OPEN, FILLED, WITHDRAWN = OpenShift.State.OPEN, OpenShift.State.FILLED, OpenShift.State.WITHDRAWN
WAITING, APPROVED, DECLINED, WITHDRAWN_CLAIM, CLOSED = (
    OpenShiftClaim.State.WAITING, OpenShiftClaim.State.APPROVED, OpenShiftClaim.State.DECLINED,
    OpenShiftClaim.State.WITHDRAWN, OpenShiftClaim.State.CLOSED)


class OpenShiftError(Exception):
    """Something the person can fix or should be told; `.message` is the
    sentence to show."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


# --- who ----------------------------------------------------------------------

def _me(user):
    person = getattr(user, "person", None)
    if person is None:
        raise PermissionDenied("you are not on the rota")
    return person


def _require_owner(user, shift):
    if not access.can_manage_team(user, shift.team):
        raise PermissionDenied("you don't manage this team")


def audience(shift):
    """The people offered the shift: current on its day, able to sign in,
    and in a chosen team (or anyone, for everyone)."""
    people = Person.objects.current(on=shift.day).filter(user__isnull=False, user__is_active=True)
    if not shift.everyone:
        people = people.filter(team__in=shift.audience.all())
    return people


def managers_of(team):
    """All-teams managers and the team's managers who can sign in and are
    current (the people who can approve a claim on the team's posts)."""
    reachable = Person.objects.current().filter(user__is_active=True)
    out = {p.pk: p for p in reachable.filter(user__is_all_teams_manager=True)}
    for p in reachable.filter(manager_of__team_id=team.pk):
        out[p.pk] = p
    return [out[k] for k in sorted(out)]


def visible_to(user):
    """The posts a user may see: those offered to their team (or everyone),
    and every post of a team they manage; all of them for an all-teams manager."""
    if access.is_all_teams(user):
        return OpenShift.objects.all()
    q = Q(team__in=access.managed_teams(user))
    me = getattr(user, "person", None)
    if me is not None:
        q |= Q(everyone=True)
        if me.team_id:
            q |= Q(audience=me.team_id)
    return OpenShift.objects.filter(q).distinct()


def can_claim(user, shift):
    me = getattr(user, "person", None)
    return (me is not None and shift.state == OPEN and not shift.expired
            and audience(shift).filter(pk=me.pk).exists())


def waiting_claims(user):
    return OpenShiftClaim.objects.filter(state=WAITING, open_shift__state=OPEN,
                                         open_shift__team__in=access.managed_teams(user))


# --- posting ------------------------------------------------------------------

def post(user, team, day, start, finish, break_minutes=0, department=None, comment="",
         everyone=False, audience_teams=(), base_url=""):
    if not access.can_manage_team(user, team):
        raise PermissionDenied("you don't manage this team")
    teams = list(audience_teams)
    if day < timezone.localdate():
        raise OpenShiftError("That day has passed.")
    if finish <= start:
        raise OpenShiftError("The finish must be later than the start.")
    if break_minutes not in Entry.BREAKS:
        raise OpenShiftError("The break must be none, 15, 30, 45 or 60 minutes.")
    if not everyone and not teams:
        raise OpenShiftError("Choose who is offered this shift.")
    with transaction.atomic():
        shift = OpenShift.objects.create(team=team, day=day, start=start, finish=finish, break_minutes=break_minutes,
                                         department=department, comment=(comment or "")[:200],
                                         everyone=bool(everyone), posted_by=user)
        if not everyone:
            shift.audience.set(teams)
        audit.record(user, shift, {"posted": ("", f"{day.isoformat()} {start:%H:%M}-{finish:%H:%M}")},
                     note=f"open shift · {team.name}")
    # Registered after the block, so it runs when the caller's own transaction (if any) commits.
    transaction.on_commit(lambda: mail.posted(shift, list(audience(shift).exclude(user=user)), base_url))
    return shift


def withdraw(user, shift, base_url=""):
    with transaction.atomic():
        shift = OpenShift.objects.select_related("team").get(pk=shift.pk)
        _require_owner(user, shift)
        if shift.state != OPEN:
            raise OpenShiftError("This open shift is no longer open.")
        waiting = list(shift.claims.filter(state=WAITING).select_related("person"))
        shift.claims.filter(state=WAITING).update(state=CLOSED, decided_by=user, decided_at=timezone.now())
        shift.state = WITHDRAWN
        shift.save(update_fields=["state"])
        audit.record(user, shift, {"state": ("open", "withdrawn")}, note=f"open shift · {shift.team.name}")
    transaction.on_commit(lambda: mail.closed(waiting, shift, "withdrawn", base_url))
    return shift


# --- claiming -----------------------------------------------------------------

def claim(user, shift, overtime="", note="", base_url=""):
    person = _me(user)
    if overtime not in Entry.Overtime.values:
        raise OpenShiftError("Overtime must be normal hours, paid or TOIL.")
    with transaction.atomic():
        shift = OpenShift.objects.select_related("team", "department").get(pk=shift.pk)
        if shift.state != OPEN or shift.expired:
            raise OpenShiftError("This open shift is no longer open.")
        if not audience(shift).filter(pk=person.pk).exists():
            raise PermissionDenied("this shift is not offered to you")
        if shift.claims.filter(person=person, state=WAITING).exists():
            raise OpenShiftError("You have already claimed this shift.")
        made = OpenShiftClaim.objects.create(open_shift=shift, person=person, overtime=overtime, note=(note or "")[:200])
        managers = [m for m in managers_of(shift.team) if m.pk != person.pk]
    transaction.on_commit(lambda: mail.claimed(made, managers, base_url))
    return made


def withdraw_claim(user, claim):
    person = _me(user)
    with transaction.atomic():
        claim = OpenShiftClaim.objects.get(pk=claim.pk)
        if claim.person_id != person.pk:
            raise PermissionDenied("not your claim")
        if claim.state != WAITING:
            raise OpenShiftError("This claim has already been decided.")
        claim.state = WITHDRAWN_CLAIM
        claim.save(update_fields=["state"])
    return claim


# --- deciding -----------------------------------------------------------------

def clashes(claim):
    """Plain sentences about the claimant's own rota that day: an overlapping
    shift, or leave (its type only). Warnings, never blocks."""
    shift, out = claim.open_shift, []
    for e in Entry.objects.filter(person=claim.person, day=shift.day, kind=Entry.Kind.SHIFT, covered_by__isnull=True):
        if e.start < shift.finish and shift.start < e.finish:
            out.append(f"Already working {e.start:%H:%M}–{e.finish:%H:%M} that day.")
    booked = leave_costing.active_day(claim.person, shift.day)
    if booked is not None:
        out.append(f"Has {booked.booking.type.name} booked that day.")
    return out


def approve(user, claim, overtime=None, base_url=""):
    with transaction.atomic():
        claim = OpenShiftClaim.objects.select_related("open_shift__team", "open_shift__department", "person").get(pk=claim.pk)
        shift = claim.open_shift
        _require_owner(user, shift)
        if claim.state != WAITING or shift.state != OPEN:
            raise OpenShiftError("This claim has already been decided.")
        overtime = claim.overtime if overtime is None else overtime
        if overtime not in Entry.Overtime.values:
            raise OpenShiftError("Overtime must be normal hours, paid or TOIL.")
        booked = leave_costing.active_day(claim.person, shift.day)
        if booked is not None and booked.booking.part == "whole":
            raise OpenShiftError(f"{claim.person.name} is on leave that day.")
        since = timezone.now()
        item = {"kind": "shift", "start": shift.start.strftime("%H:%M"), "finish": shift.finish.strftime("%H:%M"),
                "break_minutes": shift.break_minutes, "department": shift.department_id, "text": shift.comment,
                "wfh": False, "overtime": overtime}
        try:
            rows = entries.add_item(user, claim.person, shift.day, item, via_open_shift=True)
        except ValueError as e:
            raise OpenShiftError(str(e)) from None
        others = list(shift.claims.filter(state=WAITING).exclude(pk=claim.pk).select_related("person"))
        now = timezone.now()
        shift.claims.filter(pk__in=[c.pk for c in others]).update(state=CLOSED, decided_by=user, decided_at=now)
        claim.state, claim.overtime, claim.decided_by, claim.decided_at = APPROVED, overtime, user, now
        claim.save(update_fields=["state", "overtime", "decided_by", "decided_at"])
        shift.state, shift.filled_by, shift.entry = FILLED, claim.person, (rows[-1] if rows else None)
        shift.save(update_fields=["state", "filled_by", "entry"])
        # The claimant hears from the approval email; the day is not left for the next Notify staff.
        rota_notify.settle_baseline(user, [claim.person], since, "open shift approved: the claimant is told by the approval email")
        audit.record(user, shift, {"state": ("open", "filled"), "filled_by": ("", claim.person.name)},
                     note=f"open shift · {shift.team.name}")

    def tell():
        mail.approved(claim, base_url)
        mail.closed(others, shift, "filled", base_url)
    transaction.on_commit(tell)
    return claim


def decline(user, claim, base_url=""):
    with transaction.atomic():
        claim = OpenShiftClaim.objects.select_related("open_shift__team", "open_shift__department", "person").get(pk=claim.pk)
        shift = claim.open_shift
        _require_owner(user, shift)
        if claim.state != WAITING or shift.state != OPEN:
            raise OpenShiftError("This claim has already been decided.")
        claim.state, claim.decided_by, claim.decided_at = DECLINED, user, timezone.now()
        claim.save(update_fields=["state", "decided_by", "decided_at"])
        audit.record(user, shift, {"claim": ("waiting", "declined")}, note=f"open shift · {claim.person.name}")
    transaction.on_commit(lambda: mail.declined(claim, base_url))
    return claim
