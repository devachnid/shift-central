"""LEAVE-10 to 13. Each Allowance row of the year is a period from its
from_day to the day before the next row, cut to the person's employment
and the year. weeks = days / 7 rounded up (a part week is whole, on both
sides of a change: the week of the change counts twice, the practice's
deliberate choice). The shares are summed, rounded ONCE to the nearest
half hour (ties up), then capped at the largest full-year figure among the
rows, which is also what makes a 53-week whole year exactly the full
allowance (LEAVE-13).

A GP's allowances are whole sessions: for a GP the one rounding is to the
nearest whole session (4 h 10 min, a half session rounding up) instead of
the half hour, whether the full-year figure was worked out or typed. A GP
whose shares already add up to the full-year figure gets exactly that
figure, so one typed in hours that is not a whole number of sessions is
still met in full by a whole year (LEAVE-13)."""

import math
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction

from leave.services import hours, years
from people.models import Allowance

FIELD = {"annual": "annual_hours", "bank_holiday": "bank_holiday_hours"}


@dataclass(frozen=True)
class Line:
    from_day: object
    to_day: object
    days: int
    weeks: int
    full_hours: Decimal
    share_hours: Decimal


@dataclass(frozen=True)
class ProRata:
    seconds: int
    lines: list
    capped: bool
    missing: bool = False


def rows_for(person, year):
    return list(Allowance.objects.filter(person=person, leave_year=year).order_by("from_day"))


def row_in_force(person, day):
    year = years.year_of(person, day)
    return Allowance.objects.filter(person=person, leave_year=year, from_day__lte=day).order_by("-from_day").first()


def allowance(person, year, account):
    rows = rows_for(person, year)
    if not rows:
        return ProRata(0, [], False, missing=True)
    field = FIELD[account]
    year_end = years.year_end(year)
    total, lines = Fraction(0), []
    for i, row in enumerate(rows):
        start = max(row.from_day, person.start_date, year)
        end = rows[i + 1].from_day - timedelta(days=1) if i + 1 < len(rows) else year_end
        if person.end_date:
            end = min(end, person.end_date)
        if end < start:
            continue
        days = (end - start).days + 1
        weeks = -(-days // 7)
        full = getattr(row, field)
        share = _exact(person, full) * weeks / 52
        total += share
        lines.append(Line(start, end, days, weeks, full, _display(share)))
    cap = max(_exact(person, getattr(r, field)) for r in rows)
    rounded = _round_once(person, total)
    # A GP whose shares already reach the largest full-year figure has all of it,
    # whatever a whole session would round to: a typed 55 h is not 13 sessions.
    capped = rounded > cap or (person.is_gp and total >= cap)
    return ProRata(hours.from_hours(_decimal(cap if capped else rounded)), lines, capped)


SESSION = Fraction(hours.GP_SESSION, 3600)        # 4 h 10 min, in hours


def _exact(person, full):
    """A full-year figure as an exact number of hours. A GP's is taken to
    the whole second first: 58.3333 h is stored for 14 sessions, and must
    count as the 58 h 20 min it stands for."""
    return Fraction(hours.from_hours(full), 3600) if person.is_gp else Fraction(full)


def _round_once(person, total):
    """The single rounding of the summed shares, a half rounding up: to the
    half hour, or for a GP to the whole session."""
    step = SESSION if person.is_gp else Fraction(1, 2)
    return math.floor(total / step + Fraction(1, 2)) * step


def _decimal(value):
    return Decimal(value.numerator) / value.denominator


def _display(value):
    return _decimal(value).quantize(Decimal("0.01"))
