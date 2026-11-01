"""Staff by hour (REP-07, spec 5 section 10): how many people are working in
each hour of each day. A shift counts in every hour it touches (08:00 to 16:15
is the 08:00 to 16:00 columns), once per person however many shifts they
have. Breaks are not subtracted (the pack does not place them). GPs are left
out: their sessions have no clock times here."""

from datetime import timedelta

from people.services import access
from shifts.models import Entry
from shifts.services.today import site_of

MAX_DAYS = 31


def _hours_of(entry):
    last = entry.finish.hour if entry.finish.minute else entry.finish.hour - 1
    return range(entry.start.hour, last + 1)


def report(user, start, end, site="", team=None):
    if end < start:
        start, end = end, start
    if (end - start).days >= MAX_DAYS:
        end = start + timedelta(days=MAX_DAYS - 1)
    people = access.managed_people(user).filter(is_gp=False)
    if team is not None:
        people = people.filter(team=team)
    shifts = (Entry.objects.filter(person__in=people, day__range=(start, end), kind=Entry.Kind.SHIFT, covered_by__isnull=True,
                                   start__isnull=False, finish__isnull=False).select_related("department"))
    per_day, first, last = {}, 24, -1
    for e in shifts:
        if site in ("AG", "PMC") and site_of(e) != site:
            continue
        hours = _hours_of(e)
        first, last = min(first, hours.start), max(last, hours.stop - 1)
        bucket = per_day.setdefault(e.day, {"all": {}, "wfh": {}})
        for h in hours:
            bucket["all"].setdefault(h, set()).add(e.person_id)
            if e.wfh:
                bucket["wfh"].setdefault(h, set()).add(e.person_id)
    columns = list(range(first, last + 1)) if last >= 0 else []
    rows, d = [], start
    while d <= end:
        bucket = per_day.get(d, {"all": {}, "wfh": {}})
        counts = [len(bucket["all"].get(h, ())) for h in columns]
        rows.append({"day": d, "counts": counts, "wfh": [len(bucket["wfh"].get(h, ())) for h in columns],
                     "peak": max(counts, default=0)})
        d += timedelta(days=1)
    return {"start": start, "end": end, "columns": columns, "labels": [f"{h:02d}:00" for h in columns],
            "rows": rows, "site": site, "team": team}
