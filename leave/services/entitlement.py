"""Full-year allowances worked out from the contracts Practice HR sends
(allowance spec 2026-11-18, sections 6 to 8).

The arithmetic (service_years, periods and what they call) is pure: it is
given a person's copied contracts, their dates, the leave year and the
number of bank holidays in it, and runs no query. load() does the queries
for any number of people at once, so the Health card can work everyone out
for the price of three queries. Every figure here is a FULL-YEAR one;
starters, leavers and changes are pro-rated in prorata.py as before.

refresh() keeps the Allowance rows in step after each read of Practice HR;
review() builds the lists a manager works through. Nothing extra is stored."""

import math
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from leave.models import BankHoliday
from leave.services import hours, years
from leave.services.yearend import LAUNCH
from people.models import Allowance, Contract
from people.services import contracts as held

FOUR_PLACES = Decimal("0.0001")
HALF = Fraction(1, 2)
SESSION_HOURS = Fraction(hours.GP_SESSION, 3600)      # 4 h 10 min

# Why a leave year is not worked out.
NOT_EMPLOYED = "not employed in this leave year"
NO_CONTRACT = "no contract from Practice HR"
NOT_IN_FORCE = "no contract in force on the first day"
MIXED = "hours and sessions contracts in the same leave year"
NO_TERMS = "a contract with no leave terms"
NO_HOURS = "a contract with no fixed weekly amount"       # bank staff: typed, and nobody's mistake
BAD_TERMS = "leave terms that cannot be worked out"       # steps that do not rise: a contract to look at


@dataclass(frozen=True)
class Period:
    """The full-year figures in force from a day of the leave year."""
    from_day: object
    annual: Decimal             # hours, to four places
    bank_holiday: Decimal
    weekly_hours: object        # the hours contracts added up; None for a GP
    working: tuple              # (the annual leave line, the bank holiday line)


@dataclass(frozen=True)
class Worked:
    """A person's leave year from their contracts: its periods, or the
    reason it is not worked out. `gaps` are the days from which no contract
    is in force while the person is still employed; `changes` the days
    after the first on which the weekly amount in force changes."""
    periods: tuple = ()
    reason: str = ""
    gaps: tuple = ()
    changes: tuple = ()

    @property
    def ok(self):
        return not self.reason


# --- the arithmetic -----------------------------------------------------------

def service_years(start_date, year):
    """Complete years from the start date to the leave year's first day: 0
    for a year the person starts in. Fixed for the whole leave year, so a
    step up always starts with a leave year."""
    if start_date >= year:
        return 0
    return year.year - start_date.year - ((year.month, year.day) < (start_date.month, start_date.day))


def _steps(contract):
    return [(int(after), Decimal(total)) for after, total in contract.leave_steps]


def entitled(contract, service):
    """Days (weeks for a GP) a year: the base, or the total of the highest
    step whose years are not more than the service."""
    reached = [total for after, total in _steps(contract) if after <= service]
    return reached[-1] if reached else contract.leave_base


def sound(contract):
    """Whether a contract's terms can be worked out: a base above nothing
    and steps that rise. Practice HR refuses to save terms that cannot, so
    this is a guard (spec 5.1). A contract with no terms is not asked."""
    if contract.leave_base <= 0:
        return False
    if contract.unit == Contract.Unit.SESSIONS and contract.full_time_weekly <= 0:
        return False
    years_before, total_before = 0, contract.leave_base
    for after, total in _steps(contract):
        if after <= years_before or total <= total_before:
            return False
        years_before, total_before = after, total
    return True


def _round(value, step):
    """To the nearest whole `step`, a half rounding up."""
    return math.floor(value / step + HALF) * step


def _n(number):
    """22.00 as "22", 37.50 as "37.5", 11.25 as it is."""
    number = Decimal(number.numerator) / number.denominator if isinstance(number, Fraction) else Decimal(number)
    text = f"{number.normalize():f}"
    return text if "." not in text or len(text.split(".")[1]) <= 2 else f"{number:.2f}"


def _count(number, word):
    return f"{_n(number)} {word}" if number == 1 else f"{_n(number)} {word}s"


def _time(hours_):
    return hours.fmt(round(hours_ * 3600))


def _hours_figure(raw):
    """(hours as a Decimal, how the working ends) for an hours contract:
    the nearest half hour, a quarter hour rounding up."""
    rounded = _round(raw, HALF)
    text = _time(rounded) if rounded == raw else f"{_time(raw)}, rounded to {_time(rounded)}"
    return (Decimal(rounded.numerator) / rounded.denominator).quantize(FOUR_PLACES), text


def _sessions_figure(raw):
    """The same for a sessions contract: the nearest whole session, a half
    rounding up, held as sessions × 4 h 10 min."""
    rounded = _round(raw, 1)
    as_hours = (Decimal(rounded) * 25 / 6).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
    said = _count(rounded, "session") if rounded == raw else f"{_n(raw)} sessions, rounded to {_count(rounded, 'session')}"
    return as_hours, f"{said} = {_time(rounded * SESSION_HOURS)}"


def _figure(contract, service, year, bank_holidays):
    """One contract's two full-year figures, each with its working:
    ((annual hours, text), (bank holiday hours, text))."""
    total, weekly = Fraction(entitled(contract, service)), Fraction(contract.weekly_amount)
    stepped = f" ({'no' if service == 0 else service} complete year{'' if service == 1 else 's'} on {year:%-d %b %Y})" if contract.leave_steps else ""
    holidays = _count(bank_holidays, "bank holiday")
    if contract.unit == Contract.Unit.SESSIONS:
        annual, said = _sessions_figure(total * weekly)
        bank, bank_said = _sessions_figure(Fraction(bank_holidays) * 2 * weekly / Fraction(contract.full_time_weekly))
        return ((annual, f"{_count(total, 'week')}{stepped} × {_count(weekly, 'session')} = {said}"),
                (bank, f"{holidays} × 2 sessions × {_n(weekly)} ÷ {_n(contract.full_time_weekly)} = {bank_said}"))
    annual, said = _hours_figure(total * weekly / 5)
    bank, bank_said = _hours_figure(Fraction(bank_holidays) * weekly / 5)
    return ((annual, f"{_count(total, 'day')}{stepped} × {_n(weekly)} h ÷ 5 = {said}"),
            (bank, f"{holidays} × {_n(weekly)} h ÷ 5 = {bank_said}"))


def _together(figures):
    """Several contracts in force together: each worked out and rounded,
    then added."""
    total = sum(amount for amount, _ in figures)
    if len(figures) == 1:
        return total, figures[0][1]
    return total, "; ".join(text for _, text in figures) + f"; together {hours.fmt(hours.from_hours(total))}"


def periods(contracts, start_date, end_date, year, bank_holidays):
    """The leave year `year` (its first day) as a Worked: one Period from
    the year's first day, worked out from the contracts in force on it (on
    the start date, for someone who starts in the year), then one from each
    later day on which the contracts in force change, up to the end date.
    A period equal to the one before is dropped. A day from which no
    contract is in force starts no period: the earlier figures carry on,
    and the day is a gap. A contract's dates are read within the person's
    own: Practice HR does not promise a contract sits inside its
    employment, so one that starts before the start date counts from the
    start date. No queries: `contracts` are the person's copied contracts
    and `bank_holidays` the number of bank holidays in the year."""
    last = years.year_end(year)
    if end_date is not None and end_date < last:
        last = end_date
    first = max(year, start_date)
    if first > last:
        return Worked(reason=NOT_EMPLOYED)
    if not contracts:
        return Worked(reason=NO_CONTRACT)
    in_year = [c for c in contracts if c.from_day <= last and (c.to_day is None or c.to_day >= first)]
    days = {first} | {c.from_day for c in in_year if c.from_day > first}
    days |= {c.to_day + timedelta(days=1) for c in in_year if c.to_day is not None and c.to_day < last}
    live = {day: held.in_force(in_year, day) for day in sorted(days)}
    gaps = tuple(day for day, on in live.items() if not on)
    changes, amount = [], None
    for day, on in live.items():
        if on:
            now = sum(c.weekly_amount for c in on)
            if amount is not None and now != amount:
                changes.append(day)
            amount = now
    found = {"gaps": gaps, "changes": tuple(changes)}
    if not live[first]:
        return Worked(reason=NOT_IN_FORCE, **found)
    if len({c.unit for c in in_year}) > 1:
        return Worked(reason=MIXED, **found)
    if not all(sound(c) for c in in_year if c.leave_base is not None):
        return Worked(reason=BAD_TERMS, **found)
    if any(c.leave_base is None for c in in_year):
        return Worked(reason=NO_TERMS, **found)
    if any(c.weekly_amount <= 0 for c in in_year):
        return Worked(reason=NO_HOURS, **found)
    service = service_years(start_date, year)
    out = []
    for day, on in live.items():
        if not on:
            continue
        figures = [_figure(c, service, year, bank_holidays) for c in on]
        (annual, annual_text), (bank, bank_text) = _together([f[0] for f in figures]), _together([f[1] for f in figures])
        weekly = held.weekly_hours_on(on, day)
        if out and (out[-1].annual, out[-1].bank_holiday, out[-1].weekly_hours) == (annual, bank, weekly):
            continue
        out.append(Period(year if day == first else day, annual, bank, weekly, (annual_text, bank_text)))
    return Worked(periods=tuple(out), **found)


# --- loading --------------------------------------------------------------------

@dataclass
class Data:
    contracts: dict         # person id -> [Contract], oldest first
    holidays: list          # every bank holiday on the list
    rows: dict              # (person id, leave year) -> [Allowance], oldest first

    def holidays_in(self, year):
        end = years.year_end(year)
        return sum(1 for day in self.holidays if year <= day <= end)


def load(people):
    """Everything the arithmetic needs for these people, in three queries."""
    ids = [p.pk for p in people]
    contracts, rows = {}, {}
    for c in Contract.objects.filter(person__in=ids):
        contracts.setdefault(c.person_id, []).append(c)
    for a in Allowance.objects.filter(person__in=ids).select_related("checked_by__person"):
        rows.setdefault((a.person_id, a.leave_year), []).append(a)
    return Data(contracts, list(BankHoliday.objects.values_list("day", flat=True)), rows)


def worked(person, year, data):
    return periods(data.contracts.get(person.pk, []), person.start_date, person.end_date, year, data.holidays_in(year))


def worked_for(person, year):
    """worked() for one person, doing its own loading."""
    return worked(person, year, load([person]))


def covered(person, today=None):
    """The leave years refresh keeps in step: the person's current one and
    the next, less a year that ended before launch (2026 is never worked out)."""
    return [year for year in years.years_for(person, today) if years.year_end(year) >= LAUNCH]
