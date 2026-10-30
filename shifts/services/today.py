"""Who's in today (ROTA-12): everyone across all teams by site, WFH
listed apart, and "off" meaning no shift and no session until spec 3
brings time off."""

import re
from collections import OrderedDict

from people.models import Person
from shifts.models import Entry, GpSession
from shifts.services import render

SITES = ("AG", "PMC", "Either")


def site_of(entry):
    name = entry.department.name if entry.department else ""
    for site in ("AG", "PMC"):
        if re.search(r"(?<!\w)" + site + r"(?!\w)", name):
            return site
    return "Either"


def board(day):
    people = list(Person.objects.current(on=day).filter(display_on_rota=True).select_related("team"))
    by_site = {s: OrderedDict() for s in SITES}
    wfh, working = [], set()
    for e in Entry.objects.filter(person__in=people, day=day, kind=Entry.Kind.SHIFT).select_related("person__team", "department").order_by("person__team__display_order", "person__display_order", "person__last_name", "position"):
        working.add(e.person_id)
        if e.wfh:
            wfh.append((e.person, render.line(e)))
            continue
        team = by_site[site_of(e)].setdefault(e.person.team.name if e.person.team else "—", OrderedDict())
        team.setdefault(e.person, []).append(render.line(e))
    for s in GpSession.objects.filter(person__in=people, day=day).select_related("person__team").order_by("part"):
        working.add(s.person_id)
        site = s.site if s.site in ("AG", "PMC") else "Either"
        team = by_site[site].setdefault(s.person.team.name if s.person.team else "—", OrderedDict())
        team.setdefault(s.person, []).append(" ".join(x for x in (s.part, s.label, s.site) if x))
    grouped = OrderedDict()
    for person, line in wfh:
        grouped.setdefault(person, []).append(line)
    return {
        "sites": [{"name": site, "teams": [{"team": team, "people": [{"person": p, "lines": lines} for p, lines in members.items()]}
                                           for team, members in by_site[site].items()]}
                  for site in SITES if by_site[site]],
        "wfh": [{"person": p, "lines": lines} for p, lines in grouped.items()],
        "off": [p for p in people if p.pk not in working],
    }
