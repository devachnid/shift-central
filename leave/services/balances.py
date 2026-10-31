"""Balances are never stored (REP-10). A statement is recomputed from the
pro-rated allowances, the adjustments and the approved bookings, and lists
the lines that make it up."""

from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from leave.models import Adjustment, Booking, BookingDay
from leave.services import costing, hours, prorata, years
from shifts.models import Entry

ACCOUNTS = ("annual", "bank_holiday", "toil", "none")


@dataclass
class Statement:
    person: object
    year: object
    prorata: dict
    annual_allowance: int = 0
    bank_holiday_allowance: int = 0
    adjustments: dict = field(default_factory=dict)
    taken: dict = field(default_factory=dict)
    pending: dict = field(default_factory=dict)
    bank_holiday_balance: int = 0
    annual_remaining: int = 0
    annual_available: int = 0
    toil_earned: int = 0
    toil_taken: int = 0
    toil_adjustments: int = 0
    toil_remaining: int = 0
    toil_available: int = 0
    missing: bool = False
    pending_bookings: list = field(default_factory=list)
    lines: list = field(default_factory=list)


def _zero():
    return {a: 0 for a in ACCOUNTS}


def toil_earned(person, today=None):
    today = today or timezone.localdate()
    worked = sum((e.hours for e in Entry.objects.filter(person=person, kind=Entry.Kind.SHIFT, overtime="toil", day__lte=today,
                                                        covered_by__isnull=True)), timedelta(0))
    return int(worked.total_seconds())


def _pending_costs(person, year):
    """One pass over the pending bookings: the cost by account, and each
    booking's total within the year, as (booking, seconds) pairs."""
    out, each = _zero(), []
    end = years.year_end(year)
    for b in Booking.objects.filter(person=person, status=Booking.Status.PENDING, first_day__lte=end, last_day__gte=year).select_related("type"):
        total = 0
        for day in b.days():
            if year <= day <= end:
                c = costing.cost(person, b.type, day, b.part, b.start, b.finish)
                out[c.account] += c.seconds
                total += c.seconds
        each.append((b, total))
    return out, each


def statement(person, year):
    pr = {a: prorata.allowance(person, year, a) for a in ("annual", "bank_holiday")}
    s = Statement(person, year, pr, missing=pr["annual"].missing)
    s.annual_allowance, s.bank_holiday_allowance = pr["annual"].seconds, pr["bank_holiday"].seconds
    s.adjustments = _zero()
    for row in Adjustment.objects.filter(person=person, leave_year=year):
        s.adjustments[row.account] += row.seconds
    s.taken = _zero()
    end = years.year_end(year)
    days = (BookingDay.objects.filter(booking__person=person, booking__status__in=Booking.ACTIVE, day__range=(year, end))
            .values("account").annotate(total=Sum("cost_seconds")))
    for row in days:
        s.taken[row["account"]] += row["total"] or 0
    s.pending, s.pending_bookings = _pending_costs(person, year)
    s.bank_holiday_balance = s.bank_holiday_allowance + s.adjustments["bank_holiday"] - s.taken["bank_holiday"]
    s.annual_remaining = s.annual_allowance + s.adjustments["annual"] - s.taken["annual"] + s.bank_holiday_balance
    s.annual_available = s.annual_remaining - s.pending["annual"] - s.pending["bank_holiday"]
    s.toil_earned = toil_earned(person)
    # LEAVE-24: TOIL never resets, so its balance runs across every leave year.
    s.toil_taken = (BookingDay.objects.filter(booking__person=person, booking__status__in=Booking.ACTIVE, account="toil")
                    .aggregate(total=Sum("cost_seconds"))["total"] or 0)
    s.toil_adjustments = Adjustment.objects.filter(person=person, account="toil").aggregate(total=Sum("seconds"))["total"] or 0
    s.toil_remaining = s.toil_earned + s.toil_adjustments - s.toil_taken
    s.toil_available = s.toil_remaining - s.pending["toil"]
    s.lines = _lines(s)
    return s


def _lines(s):
    out = []
    for account, label in (("annual", "Annual leave allowance"), ("bank_holiday", "Bank holiday allowance")):
        pr = s.prorata[account]
        if pr.missing:
            out.append(("allowance", f"{label}: not set", 0))
            continue
        for ln in pr.lines:
            out.append(("allowance", f"{label} {ln.from_day:%-d %b}–{ln.to_day:%-d %b}: {ln.weeks} weeks of 52 at {ln.full_hours} h", hours.from_hours(ln.share_hours.quantize(Decimal("0.01")))))
        if len(pr.lines) != 1 or pr.capped or pr.seconds != hours.from_hours(pr.lines[0].share_hours.quantize(Decimal("0.01"))):
            out.append(("allowance", f"{label} rounded to the half hour{' and capped at the full-year figure' if pr.capped else ''}", pr.seconds))
    for row in Adjustment.objects.filter(person=s.person, leave_year=s.year).order_by("at"):
        out.append(("adjustment", f"{row.reason} ({row.account.replace('_', ' ')})", row.seconds))
    for bd in (BookingDay.objects.filter(booking__person=s.person, booking__status__in=Booking.ACTIVE, day__range=(s.year, years.year_end(s.year)))
               .select_related("booking__type").order_by("day")):
        out.append(("booking", f"{bd.day:%a %-d %b}: {bd.booking.label} ({bd.account.replace('_', ' ')}, {bd.get_source_display().lower()})", -bd.cost_seconds))
    for b, cost in s.pending_bookings:
        first, last = f"{b.first_day:%-d %b}", f"{b.last_day:%-d %b}"
        out.append(("pending", f"Requested: {b.label} {first if first == last else f'{first}–{last}'}", -cost))
    out.append(("bank_holiday_balance", "Bank holiday allowance less bank holidays taken (moves into annual leave)", s.bank_holiday_balance))
    out.append(("remaining", "Annual leave remaining, bank holidays included", s.annual_remaining))
    out.append(("available", "Annual leave available to request (remaining less requests waiting)", s.annual_available))
    out.append(("toil", "TOIL earned (overtime marked TOIL, to today)", s.toil_earned))
    out.append(("toil_remaining", "TOIL remaining", s.toil_remaining))
    out.append(("toil_available", "TOIL available to request", s.toil_available))
    return out


def available(person, year, account):
    if account == "none":
        return None
    s = statement(person, year)
    return s.toil_available if account == "toil" else s.annual_available
