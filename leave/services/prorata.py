"""LEAVE-10 to 13. Each Allowance row of the year is a period from its
from_day to the day before the next row, cut to the person's employment
and the year. weeks = days / 7 rounded up (a part week is whole, on both
sides of a change: the week of the change counts twice, the practice's
deliberate choice). The shares are summed, rounded ONCE to the nearest
half hour (ties up), then capped at the largest full-year figure among the
rows, which is also what makes a 53-week whole year exactly the full
allowance (LEAVE-13)."""

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
        share = Fraction(full) * weeks / 52
        total += share
        lines.append(Line(start, end, days, weeks, full, _display(share)))
    rounded = Fraction(math.floor(total * 2 + Fraction(1, 2)), 2)
    cap = max(Fraction(getattr(r, field)) for r in rows)
    capped = rounded > cap
    return ProRata(hours.from_hours(_decimal(min(rounded, cap))), lines, capped)


def _decimal(value):
    return Decimal(value.numerator) / value.denominator


def _display(value):
    return _decimal(value).quantize(Decimal("0.01"))
