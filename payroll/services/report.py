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
        return half_days_text(self.leave_half_days)

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


def half_days_text(n):
    """Half-days as the screen writes them: 5 is "2½", −1 is "−½", 0 is "0"."""
    sign = "−" if n < 0 else ""
    whole, half = divmod(abs(int(n)), 2)
    return sign + (f"{whole or ''}{'½' if half else ''}" or "0")


def _by_person(objects):
    out = {}
    for x in objects:
        out.setdefault(x.person_id, []).append(x)
    return out


def rows(people, month):
    """Every table is read once for the whole people set and grouped here, so
    a month costs a handful of queries however many people it covers."""
    first, last = month, month_end(month)
    people = list(people)
    pks = [p.pk for p in people]
    hidden = sessions.hidden(pks, first, last)
    entries = _by_person(Entry.objects.filter(person_id__in=pks, day__range=(first, last), kind=Entry.Kind.SHIFT, covered_by__isnull=True)
                         .only("person_id", "kind", "start", "finish", "break_minutes", "overtime"))
    gp_pks = [p.pk for p in people if p.is_gp]
    gp_sessions = _by_person(GpSession.objects.filter(person_id__in=gp_pks, day__range=(first, last))) if gp_pks else {}
    booking_days = list(BookingDay.objects.filter(booking__person_id__in=pks, booking__status__in=Booking.ACTIVE, booking__dates_only=False,
                                                  day__range=(first, last)).select_related("booking__type"))
    halves = [bd.pk for bd in booking_days if bd.booking.part in (Booking.Part.AM, Booking.Part.PM)]
    covered = {}
    if halves:
        for e in Entry.objects.filter(covered_by_id__in=halves, overtime="").only("covered_by_id", "kind", "start", "finish", "break_minutes"):
            covered[e.covered_by_id] = covered.get(e.covered_by_id, timedelta(0)) + e.hours
    days_of = {}
    for bd in booking_days:
        days_of.setdefault(bd.booking.person_id, []).append(bd)
    instances = {}
    for pid in (Booking.objects.filter(person_id__in=pks, status__in=Booking.ACTIVE, dates_only=False, type__sickness=True,
                                       first_day__lte=last, last_day__gte=first).values_list("person_id", flat=True)):
        instances[pid] = instances.get(pid, 0) + 1
    out = []
    for p in people:
        r = Row(person=p, team=p.team.name if p.team else "—")
        for e in entries.get(p.pk, ()):
            secs = int(e.hours.total_seconds())
            if e.overtime == Entry.Overtime.PAID:
                r.paid_overtime += secs
            elif e.overtime == "":
                r.worked += secs
        if p.is_gp:
            visible = sessions.visible(gp_sessions.get(p.pk, ()), hidden)
            r.worked += len(visible) * hours.GP_SESSION
        for bd in days_of.get(p.pk, ()):
            t, cost = bd.booking.type, bd.cost_seconds
            if bd.booking.part in (Booking.Part.AM, Booking.Part.PM):
                # A half day covers the whole shift on the grid (leave spec, section 4); the other half was worked.
                r.worked += max(int(covered.get(bd.pk, timedelta(0)).total_seconds()) - cost, 0)
            costed = cost > 0         # a day off inside a booking (a weekend, a part-timer's day) costs nothing and is no leave day
            if bd.account in ("annual", "bank_holiday") and costed:
                r.leave_half_days += 2 if bd.booking.part == Booking.Part.WHOLE else 1
            if bd.account == "toil":
                r.toil_taken += cost
            if not _resolved_paid(bd):
                r.unpaid += cost
            elif t.sickness:
                r.sickness += cost
            elif t.on_payroll == t.Payroll.ALWAYS:
                if costed:
                    slot = r.types.setdefault(t.name, {"days": 0, "seconds": 0})
                    slot["days"] += 1
                    slot["seconds"] += cost
            else:
                r.paid_leave += cost
        r.sickness_instances = instances.get(p.pk, 0)
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


def lookback(month):
    """[(earlier month, its latest run)] for each of the twelve months before
    `month` that has been marked sent, oldest first: one query."""
    from payroll.models import PayrollRun
    months = []
    y, m = month.year, month.month
    for _ in range(12):
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
        months.append(date(y, m, 1))
    latest = {}
    for run in PayrollRun.objects.filter(month__in=months).order_by("month", "sent_at", "pk"):
        latest[run.month] = run          # ordered oldest first, so the last one seen is the latest
    return [(past, latest[past]) for past in sorted(latest)]


def recompute(past, run, among=None):
    """The figures as they stand today for an earlier month: everyone in its
    run plus anyone now current in it, limited to `among` (a person
    queryset) when given. ({pk: sent figures}, {pk: Row})."""
    sent = run.figures.get("rows", {})
    current = Person.objects.filter(start_date__lte=month_end(past)).exclude(end_date__lt=past) | Person.objects.filter(pk__in=[int(k) for k in sent])
    if among is not None:
        mine = set(among.values_list("pk", flat=True))
        current = current.filter(pk__in=mine)
        sent = {pk: v for pk, v in sent.items() if int(pk) in mine}
    return sent, {str(r.person.pk): r for r in rows(current.distinct().select_related("team"), past)}


def differences(past, sent, now):
    """Field-by-field differences between what was sent and what is true
    now, as Corrections."""
    out = []
    gone = {pk for pk in sent if pk not in now}
    vanished = {p.pk: p for p in Person.objects.filter(pk__in=[int(pk) for pk in gone])} if gone else {}
    for pk in sorted(set(sent) | set(now), key=int):
        person = now[pk].person if pk in now else vanished.get(int(pk))
        if person is None:
            continue
        was, is_now = _flat(sent.get(pk, {})), _flat(now[pk].figures()) if pk in now else _flat({})
        for key in sorted(set(was) | set(is_now)):
            a, b = was.get(key), is_now.get(key)
            if a == b or (not a and not b):
                continue
            numeric = isinstance(a, int) and isinstance(b, int) and not isinstance(a, bool)
            out.append(Correction(past, person, key, _label(key), a, b, (b - a) if numeric else None))
    return out


def corrections(user, month):
    """PAY-02: for each sent month of the previous twelve, what has changed
    since it was last sent, for the viewer's people only (the people set is
    limited before anything is computed)."""
    among = None if access.is_all_teams(user) else access.managed_people(user)
    out = []
    for past, run in lookback(month):
        sent, now = recompute(past, run, among)
        out += differences(past, sent, now)
    return out
