"""REP-05: the leave one-pager for a leave year: taken and remaining per
person, with team and practice totals. A person whose leave year starts on
another day is reported for the year of theirs that holds the chosen
year's first day, and a footnote says so."""

from dataclasses import dataclass

from leave.services import balances, hours, years
from people.services import access


@dataclass
class LeaveTotals:
    name: str
    people: int = 0
    allowance: int = 0
    adjustments: int = 0
    taken: int = 0
    remaining: int = 0
    toil: int = 0
    pending: int = 0


@dataclass
class LeaveRow:
    person: object
    team: str
    year: object
    missing: bool
    allowance: int = 0
    adjustments: int = 0
    taken: int = 0
    remaining: int = 0
    toil: int = 0
    pending: int = 0


def _row(person, year):
    own = years.year_of(person, year)
    s = balances.statement(person, own)
    if s.missing:
        return LeaveRow(person, person.team.name if person.team else "—", own, True, toil=s.toil_remaining)
    return LeaveRow(person, person.team.name if person.team else "—", own, False,
                    s.annual_allowance + s.bank_holiday_allowance, s.adjustments["annual"] + s.adjustments["bank_holiday"],
                    s.taken["annual"] + s.taken["bank_holiday"], s.annual_remaining, s.toil_remaining, s.pending["annual"] + s.pending["bank_holiday"])


def _add(t, r):
    t.people += 1
    for f in ("allowance", "adjustments", "taken", "remaining", "toil", "pending"):
        setattr(t, f, getattr(t, f) + getattr(r, f))


def summary(user, year):
    end = years.year_end(year)
    people = (access.managed_people(user).filter(start_date__lte=end).exclude(end_date__lt=year)
              .select_related("team").order_by("team__display_order", "team__name", "last_name", "first_name"))
    practice, teams, rows, other_years = LeaveTotals("Practice"), {}, [], set()
    for p in people:
        r = _row(p, year)
        rows.append(r)
        if r.year != year:
            other_years.add(years.label(r.year))
        _add(practice, r)
        _add(teams.setdefault(r.team, LeaveTotals(r.team)), r)
    footnotes = [f"Reported for leave year {label}, which holds {year:%-d %b %Y}, for those whose leave year starts on another day." for label in sorted(other_years)]
    return {"practice": practice, "teams": list(teams.values()), "people": rows, "footnotes": footnotes}


def _t(t):
    return [t.name, t.people, hours.fmt(t.allowance), hours.fmt(t.adjustments), hours.fmt(t.taken), hours.fmt(t.remaining), hours.fmt(t.toil), hours.fmt(t.pending)]


def sections(data):
    head = ["", "People", "Allowance", "Adjustments", "Taken", "Remaining", "TOIL remaining", "Waiting for approval"]
    return [("Practice", head, [_t(data["practice"])]), ("Teams", head, [_t(t) for t in data["teams"]]),
            ("People", ["Name", "Team", "Leave year", "Allowance", "Adjustments", "Taken", "Remaining", "TOIL remaining", "Waiting for approval"],
             [[r.person.name, r.team, years.label(r.year), "not set" if r.missing else hours.fmt(r.allowance), hours.fmt(r.adjustments), hours.fmt(r.taken),
               "—" if r.missing else hours.fmt(r.remaining), hours.fmt(r.toil), hours.fmt(r.pending)] for r in data["people"]])]
