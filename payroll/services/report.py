"""The monthly payroll report (PAY-01): one row per person for a calendar
month, every figure the sum of rows a manager can open (REP-10). Days still
to come are taken from the rota as it stands (PAY-02). The bureau does the
pay; this is the hours."""

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.utils import timezone

from leave.models import Booking, BookingDay
from leave.services import hours, leavers, sessions
from people.models import Person
from people.services import access
from shifts.models import Entry, GpSession

FIELDS = ("worked", "paid_leave", "total", "paid_overtime", "unpaid", "sickness", "sickness_instances", "toil_taken", "leave_half_days")
HOUR_FIELDS = ("worked", "paid_leave", "total", "paid_overtime", "unpaid", "sickness", "toil_taken")
LABELS = {"worked": "Worked", "paid_leave": "Paid leave", "total": "Total to pay", "paid_overtime": "Paid overtime", "unpaid": "Unpaid leave",
          "sickness": "Sickness", "sickness_instances": "Sickness instances", "toil_taken": "TOIL taken", "leave_half_days": "Leave days",
          "started": "Started", "leaves": "Leaves", "leaver_balance": "Leaver's leave remaining"}
EARLIEST = date(2026, 1, 1)


@dataclass
class Row:
    person: Person
    team: str
    worked: int = 0
    paid_leave: int = 0
    total: int = 0
    paid_overtime: int = 0
    unpaid: int = 0
    sickness: int = 0
    sickness_instances: int = 0
    toil_taken: int = 0
    leave_half_days: int = 0
    types: dict = field(default_factory=dict)       # always-reported types present: name -> {"days", "seconds"}
    started: date | None = None
    leaves: date | None = None
    leaver_balance: int | None = None
    leaver_missing: bool = False

    @property
    def leave_days_text(self):
        whole, half = divmod(self.leave_half_days, 2)
        return f"{whole or ''}{'½' if half else ''}" or "0"

    def figures(self):
        out = {f: getattr(self, f) for f in FIELDS}
        out["types"] = {name: dict(v) for name, v in sorted(self.types.items())}
        out["started"] = self.started.isoformat() if self.started else None
        out["leaves"] = self.leaves.isoformat() if self.leaves else None
        out["leaver_balance"] = self.leaver_balance
        return out


def _in_range(first, today):
    if first < EARLIEST or first > date(today.year + 1, today.month, 1):
        raise ValueError("Choose a month from January 2026 to a year ahead")
    return first


def month_of(text):
    """"YYYY-MM" to its first day; blank or unreadable means this month;
    before January 2026 or more than a year ahead raises ValueError."""
    today = timezone.localdate()
    try:
        year, month = (int(x) for x in (text or "").split("-"))
        first = date(year, month, 1)
    except (TypeError, ValueError):
        first = today.replace(day=1)
    return _in_range(first, today)


def month_strict(text):
    """Exactly "YYYY-MM" with a real month, in the same range as month_of;
    anything else raises ValueError, never a fallback (marking a month sent
    is a record)."""
    if not re.fullmatch(r"\d{4}-\d{2}", text or ""):
        raise ValueError("Say which month, as YYYY-MM")
    try:
        first = date(int(text[:4]), int(text[5:]), 1)
    except ValueError:
        raise ValueError("Say which month, as YYYY-MM") from None
    return _in_range(first, timezone.localdate())


def month_end(month):
    return date(month.year, month.month, calendar.monthrange(month.year, month.month)[1])


def people_for(user, month):
    """The viewer's people current on any day of the month, GPs included."""
    end = month_end(month)
    people = Person.objects.all() if access.is_all_teams(user) else access.managed_people(user)
    return (people.filter(start_date__lte=end).exclude(end_date__lt=month).distinct()
            .select_related("team").order_by("team__display_order", "team__name", "last_name", "first_name"))


def _resolved_paid(bd):
    t = bd.booking.type
    return bd.booking.paid if bd.booking.paid is not None else t.default_paid


def rows(people, month):
    first, last = month, month_end(month)
    people = list(people)
    hidden = sessions.hidden(people, first, last)
    out = []
    for p in people:
        r = Row(person=p, team=p.team.name if p.team else "—")
        for e in Entry.objects.filter(person=p, day__range=(first, last), kind=Entry.Kind.SHIFT, covered_by__isnull=True):
            secs = int(e.hours.total_seconds())
            if e.overtime == Entry.Overtime.PAID:
                r.paid_overtime += secs
            elif e.overtime == "":
                r.worked += secs
        if p.is_gp:
            visible = sessions.visible(GpSession.objects.filter(person=p, day__range=(first, last)), hidden)
            r.worked += len(visible) * hours.GP_SESSION
        days = (BookingDay.objects.filter(booking__person=p, booking__status__in=Booking.ACTIVE, booking__dates_only=False, day__range=(first, last))
                .select_related("booking__type"))
        for bd in days:
            t, cost = bd.booking.type, bd.cost_seconds
            if bd.booking.part in (Booking.Part.AM, Booking.Part.PM):
                # A half day covers the whole shift on the grid (leave spec, section 4); the other half was worked.
                covered = sum((e.hours for e in Entry.objects.filter(covered_by=bd, overtime="")), timedelta(0))
                r.worked += max(int(covered.total_seconds()) - cost, 0)
            if bd.account in ("annual", "bank_holiday"):
                r.leave_half_days += 2 if bd.booking.part == Booking.Part.WHOLE else 1
            if bd.account == "toil":
                r.toil_taken += cost
            if not _resolved_paid(bd):
                r.unpaid += cost
            elif t.sickness:
                r.sickness += cost
            elif t.on_payroll == t.Payroll.ALWAYS:
                slot = r.types.setdefault(t.name, {"days": 0, "seconds": 0})
                slot["days"] += 1
                slot["seconds"] += cost
            else:
                r.paid_leave += cost
        r.sickness_instances = Booking.objects.filter(person=p, status__in=Booking.ACTIVE, dates_only=False, type__sickness=True,
                                                      first_day__lte=last, last_day__gte=first).count()
        r.total = r.worked + r.paid_leave
        if first <= p.start_date <= last:
            r.started = p.start_date
        if p.end_date is not None and first <= p.end_date <= last:
            r.leaves = p.end_date
            _, s = leavers.figure(p)
            r.leaver_missing = s.missing
            r.leaver_balance = None if s.missing else s.annual_remaining
        out.append(r)
    return out


def type_names(rows_):
    return sorted({name for r in rows_ for name in r.types})


@dataclass(frozen=True)
class Correction:
    month: date
    person: Person
    field: str
    label: str
    sent: object
    now: object
    delta: object


def _flat(figures):
    """A row's figures as one flat {field: value} for comparing."""
    out = {f: figures.get(f, 0) for f in FIELDS}
    for name, v in (figures.get("types") or {}).items():
        out[f"{name} days"], out[f"{name} hours"] = v["days"], v["seconds"]
    out["started"], out["leaves"], out["leaver_balance"] = figures.get("started"), figures.get("leaves"), figures.get("leaver_balance")
    return out


def _label(field_name):
    return LABELS.get(field_name, field_name)


def corrections(user, month):
    """PAY-02: for each sent month of the previous twelve, what has changed
    since it was sent, for the viewer's people."""
    from payroll.services import runs
    mine = set(access.managed_people(user).values_list("pk", flat=True)) if not access.is_all_teams(user) else None
    out = []
    for back in range(12, 0, -1):
        y, m = month.year, month.month - back
        while m <= 0:
            y, m = y - 1, m + 12
        past = date(y, m, 1)
        run = runs.latest(past)
        if run is None:
            continue
        sent = run.figures.get("rows", {})
        current = Person.objects.filter(start_date__lte=month_end(past)).exclude(end_date__lt=past) | Person.objects.filter(pk__in=[int(k) for k in sent])
        now = {str(r.person.pk): (r.person, _flat(r.figures())) for r in rows(current.distinct().select_related("team"), past)}
        for pk in sorted(set(sent) | set(now), key=int):
            person = now[pk][0] if pk in now else Person.objects.filter(pk=int(pk)).first()
            if person is None or (mine is not None and person.pk not in mine):
                continue
            was, is_now = _flat(sent.get(pk, {})), now[pk][1] if pk in now else _flat({})
            for key in sorted(set(was) | set(is_now)):
                a, b = was.get(key), is_now.get(key)
                if a == b or (not a and not b):
                    continue
                numeric = isinstance(a, int) and isinstance(b, int) and not isinstance(a, bool)
                out.append(Correction(past, person, key, _label(key), a, b, (b - a) if numeric else None))
    return out
