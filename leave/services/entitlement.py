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

import logging
import math
from dataclasses import dataclass
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from django.db import transaction
from django.utils import timezone

from leave.models import BankHoliday
from leave.services import hours, years
from leave.services import settings as leave_settings
from leave.services.yearend import LAUNCH
from people.models import Allowance, Contract, Person
from people.services import access, audit, profiles
from people.services import contracts as held

log = logging.getLogger("leave.entitlement")

FOUR_PLACES = Decimal("0.0001")
TWO_PLACES = Decimal("0.01")
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

Source = Allowance.Source


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


# --- refresh (spec section 7) -----------------------------------------------------

def note(period, prefix=audit.SYNC_NOTE):
    """The audit note for a figure written from a period: where it came
    from, then the working."""
    return f"{prefix}: {period.working[0]}; {period.working[1]}"[:300]


def current_and_starting(people, today):
    """Current people and starters, as the Health card counts them."""
    return (people.current(on=today) | people.filter(start_date__gt=today)).distinct()


@dataclass(frozen=True)
class Refreshed:
    written: int
    failed: int


def refresh(today=None):
    """Bring every current person's and starter's allowance rows into step
    with their contracts (spec section 7). Run by hr_sync after each good
    read, inside a transaction of the caller's. One person's failure is
    logged by id and skipped; `failed` counts them."""
    today = today or timezone.localdate()
    people = list(current_and_starting(Person.objects.all(), today))
    data = load(people)
    need_check = leave_settings.get().allowances_need_checking
    copying = held.in_use()
    written = failed = 0
    for person in people:
        try:
            with transaction.atomic():
                written += _refresh_person(person, today, data, need_check, copying)
        except Exception:
            log.exception("allowances: person %s", person.pk)
            failed += 1
    if written or failed:
        log.info("allowances: %s rows written, %s people skipped", written, failed)
    return Refreshed(written, failed)


def _refresh_person(person, today, data, need_check, copying):
    """`copying` is off until Practice HR has sent anyone a contract or a
    figure has been worked out: before that nothing is worked out and
    nothing is copied, exactly as it was."""
    this, following = years.years_for(person, today)
    written = 0
    for year in covered(person, today):
        result = worked(person, year, data)
        rows = data.rows.setdefault((person.pk, year), [])
        if result.ok:
            written += _reconcile(person, year, result, rows, need_check)
        elif copying and year == following and not rows and result.reason != NOT_EMPLOYED:
            written += _copy_forward(person, this, following, data, need_check)
    return written


def _days_in_force(person, rows, day):
    """The days per week in force just before `day`: the latest earlier row
    of the year that carries them, else the person's."""
    earlier = [r.days_per_week for r in rows if r.from_day < day and r.days_per_week]
    return earlier[-1] if earlier else person.days_per_week


def same(row, period):
    """Whether a row holds the figures a period gives. A typed row is read
    at two places, as a manager types it: a GP's 66.67 is the contract's
    66.6667. Every other row is compared exactly."""
    figures = (Decimal(row.annual_hours), Decimal(row.bank_holiday_hours))
    rule = (period.annual, period.bank_holiday)
    if row.source == Source.TYPED:
        return tuple(f.quantize(TWO_PLACES) for f in figures) == tuple(f.quantize(TWO_PLACES) for f in rule)
    return figures == rule


def _reconcile(person, year, result, rows, need_check):
    """The table in spec 7.2. `rows` is the year's rows, oldest first, kept
    in step with what is written. A dated row that is created or rewritten
    always waits for a manager, whatever the setting (spec 7.6): the
    contract cannot give its days per week."""
    now = timezone.now()
    by_day = {r.from_day: r for r in rows}
    written = 0
    for period in result.periods:
        row = by_day.get(period.from_day)
        dated = period.from_day != year
        checked_at = None if need_check or dated else now
        if row is None:
            extra = {"weekly_hours": period.weekly_hours, "days_per_week": _days_in_force(person, rows, period.from_day),
                     "hours_applied": True} if dated else {}
            rows.append(profiles.add_allowance(None, person, year, period.from_day, period.annual, period.bank_holiday,
                                               Source.WORKED_OUT, note(period), checked_at=checked_at, **extra))
            rows.sort(key=lambda r: r.from_day)
            written += 1
            continue
        matches = same(row, period)
        if row.source == Source.TYPED:
            if matches:     # the manager typed what the contract gives: it follows the contract from now on, at its exact figures
                fields = {"source": Source.WORKED_OUT, "checked_at": now, "checked_by": None}
                if (row.annual_hours, row.bank_holiday_hours) != (period.annual, period.bank_holiday):
                    fields.update(annual_hours=period.annual, bank_holiday_hours=period.bank_holiday)
                profiles.write_allowance(None, row, fields, note(period))
                written += 1
        elif matches:
            if row.source == Source.COPIED:     # last year's figures turned out to be the contract's: its check is left as it is
                profiles.write_allowance(None, row, {"source": Source.WORKED_OUT}, note(period))
                written += 1
        else:
            fields = {"annual_hours": period.annual, "bank_holiday_hours": period.bank_holiday, "source": Source.WORKED_OUT,
                      "checked_at": checked_at, "checked_by": None}
            if dated:
                fields["weekly_hours"] = period.weekly_hours
            profiles.write_allowance(None, row, fields, note(period))
            written += 1
    starts = {period.from_day for period in result.periods}
    for row in [r for r in rows if r.from_day != year and r.source == Source.WORKED_OUT and r.from_day not in starts]:
        profiles.remove_allowance(None, row, f"{audit.SYNC_NOTE}: the contracts no longer change on this day")
        rows.remove(row)
        written += 1
    return written


def _copy_forward(person, this, following, data, need_check):
    """Spec 7.5: a year that is not worked out and has no rows yet starts
    with the full-year figures of this year's last row, to be checked."""
    earlier = data.rows.get((person.pk, this), [])
    if not earlier:
        return 0
    last = earlier[-1]
    row = profiles.add_allowance(None, person, following, following, last.annual_hours, last.bank_holiday_hours, Source.COPIED,
                                 f"{audit.SYNC_NOTE}: copied from {years.label(this)}",
                                 checked_at=None if need_check else timezone.now())
    data.rows[(person.pk, following)].append(row)
    return 1


# --- what a manager is shown (spec section 8) -------------------------------------

def state(row):
    """How a row's figures came about, as the profile says it."""
    if row.source == Source.TYPED:
        return "typed"
    what = row.get_source_display()
    if row.checked_at is None:
        return f"{what}, not yet checked"
    on = f"{timezone.localtime(row.checked_at):%-d %b %Y}"
    if row.checked_by_id is None:
        return f"{what}, checked automatically on {on}"
    who = getattr(getattr(row.checked_by, "person", None), "name", "") or row.checked_by.email
    return f"{what}, checked by {who} on {on}"


@dataclass
class Shown:
    """One Allowance row beside what the contracts give for its day."""
    row: object
    state: str
    working: object = None      # (annual line, bank holiday line) when the row's figures are the contracts'
    rule: object = None         # the Period the contracts give, when the row is typed and differs from it
    orphan: bool = False        # a typed dated row on a day the contracts do not change

    @property
    def dated(self):
        return self.row.from_day != self.row.leave_year

    @property
    def takes_days(self):
        return profiles.takes_days(self.row)

    @property
    def differs(self):
        return self.rule is not None or self.orphan

    @property
    def ended(self):
        """The row's leave year has ended: its figures are not changed, an
        adjustment puts it right."""
        return years.year_end(self.row.leave_year) < timezone.localdate()


def _shown(row, result):
    out = Shown(row, state(row))
    if not result.ok:
        return out
    period = next((p for p in result.periods if p.from_day == row.from_day), None)
    if period is not None and same(row, period):
        out.working = period.working
    elif row.source == Source.TYPED:
        out.rule, out.orphan = period, period is None and out.dated
    return out


def shown(person, year_list, data=None):
    """The person's rows for these leave years, oldest first, each with its
    state, its working and what the contracts give instead (the profile)."""
    data = data or load([person])
    return [_shown(row, worked(person, year, data)) for year in year_list for row in data.rows.get((person.pk, year), [])]


@dataclass
class Item:
    """One line of a review list."""
    person: object
    year: object
    text: str
    can_act: bool = False       # the viewer manages this person (nobody acts on their own)
    shown: object = None        # the row, where the line is about one


@dataclass
class Review:
    to_check: list
    differ: list
    bank_holidays: list         # leave years refresh covers with no bank holiday on the list
    contracts: list


FINISHED = "the contracts now give different figures for this year, which has ended; put it right with an adjustment"


def review(user, team=None, today=None):
    """The four lists of spec section 8, for the people the user manages
    (current people and starters), optionally one team's. Built on demand
    from the rows and the copied contracts; nothing is stored."""
    today = today or timezone.localdate()
    people = current_and_starting(access.managed_people(user), today)
    if team is not None:
        people = people.filter(team=team)
    people = list(people.select_related("team").order_by("name"))
    data = load(people)
    listing_contracts = held.in_use()           # the last two lists stay empty until anything comes from Practice HR
    out, empty = Review([], [], [], []), set()
    for person in people:
        can_act = access.can_manage(user, person)
        look = stale = ""
        for year in covered(person, today):
            result = worked(person, year, data)
            rows = data.rows.get((person.pk, year), [])
            if data.holidays_in(year) == 0:
                empty.add(year)
            for one in (_shown(row, result) for row in rows):
                if one.row.needs_checking:
                    out.to_check.append(Item(person, year, one.state, can_act, one))
                elif one.differs:
                    text = "the contracts do not change on this day" if one.orphan else "typed figures that are not the contract's"
                    out.differ.append(Item(person, year, text, can_act, one))
            if not result.ok and rows:
                have = {r.from_day for r in rows}
                what = "sessions" if person.is_gp else "hours"
                out.to_check += [Item(person, year, f"{what} changed on {day:%-d %B}; add the hours change", can_act)
                                 for day in result.changes if day not in have]
            if not look and result.reason == BAD_TERMS:
                look = BAD_TERMS
            if not look and result.gaps:
                look = f"no contract from {result.gaps[0]:%-d %B %Y}"
            if (not stale and not result.ok and result.reason != NOT_EMPLOYED
                    and any(r.source == Source.WORKED_OUT for r in rows)):
                stale = (f"the {years.label(year)} allowance was worked out, but the contracts no longer give a figure "
                         f"({result.reason})")
        previous = years.previous_year(years.year_of(person, today))
        if years.year_end(previous) >= LAUNCH:
            result, rows = worked(person, previous, data), data.rows.get((person.pk, previous), [])
            out.to_check += [Item(person, previous, state(row), can_act, Shown(row, state(row))) for row in rows if row.needs_checking]
            starts = {p.from_day: p for p in result.periods}
            if result.ok and rows and ({r.from_day for r in rows} != set(starts)
                                       or not all(same(r, starts[r.from_day]) for r in rows)):
                out.differ.append(Item(person, previous, FINISHED, can_act))
        if listing_contracts:
            mine = data.contracts.get(person.pk, [])
            if not mine:
                look = NO_CONTRACT
            elif not held.in_force(mine, max(today, person.start_date)):
                look = "no contract in force today" if person.start_date <= today else "no contract in force on the start date"
            look = stale or look
            if look:
                out.contracts.append(Item(person, None, look))
    out.bank_holidays = sorted(empty) if listing_contracts else []
    return out
