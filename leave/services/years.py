"""A person's leave year (LEAVE-03): 1 January unless the profile says
otherwise. A year is named by its first day, which is Allowance.leave_year."""

from datetime import date, timedelta

from django.utils import timezone


def parse_start(text):
    month, day = (int(x) for x in text.split("-"))
    date(2001, month, day)        # 2001 is not a leap year: 02-29 is refused too
    return month, day


def year_of(person, day):
    month, dom = parse_start(person.leave_year_start)
    first = date(day.year, month, dom)
    return first if day >= first else date(day.year - 1, month, dom)


def year_end(year):
    return date(year.year + 1, year.month, year.day) - timedelta(days=1)


def next_year(year):
    return date(year.year + 1, year.month, year.day)


def years_for(person, today=None):
    this = year_of(person, today or timezone.localdate())
    return [this, next_year(this)]


def previous_year(year):
    return date(year.year - 1, year.month, year.day)


def correctable(person, today=None):
    """The leave years an adjustment or an hours change may be dated in:
    the previous one (last year's statement is put right in January), this
    one and the next. Leave itself is booked in this one and the next only."""
    this, following = years_for(person, today)
    return [previous_year(this), this, following]


def label(year):
    """"2027", or "2027/28" for a year that starts after 1 January."""
    return str(year.year) if (year.month, year.day) == (1, 1) else f"{year.year}/{str(year.year + 1)[2:]}"
