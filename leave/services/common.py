from django.core.exceptions import PermissionDenied

from leave.services import hours
from people.models import Person, TeamManager
from people.services import access


class LeaveError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def recipients(person):
    """Managers who can manage the person: all-teams managers with a Person,
    and the person's team's managers; never the person; deduplicated."""
    out = {}
    for p in Person.objects.filter(user__is_all_teams_manager=True).exclude(pk=person.pk):
        out[p.pk] = p
    if person.team_id:
        for row in TeamManager.objects.filter(team_id=person.team_id).select_related("person").exclude(person=person):
            out[row.person.pk] = row.person
    return [out[k] for k in sorted(out)]


def span(booking):
    f, l = booking.first_day, booking.last_day
    if f == l:
        return f"{f:%-d %b %Y}"
    if f.month == l.month and f.year == l.year:
        return f"{f.day}–{l:%-d %b %Y}"
    return f"{f:%-d %b %Y}–{l:%-d %b %Y}"


def part_text(booking):
    if booking.part == "times":
        return f"{booking.start:%H:%M}–{booking.finish:%H:%M}"
    if booking.part == "whole":
        return "whole days" if booking.first_day != booking.last_day else "whole day"
    return {"am": "morning", "pm": "afternoon"}[booking.part]


def describe(booking, seconds=None):
    if seconds is None:
        seconds = sum(booking.booking_days.values_list("cost_seconds", flat=True)) if booking.pk else 0
    return f"{booking.label} {span(booking)}, {part_text(booking)}, {hours.fmt(seconds)}, {booking.status.replace('_', ' ')}"


def check_manager(user, person):
    if not access.can_manage(user, person):
        raise PermissionDenied("you don't manage this person")
