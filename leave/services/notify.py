"""The emails of spec section 7, through messaging.send: plain text, one
Outbox row each, never raising, never a description or note in a subject."""

import logging

from django.conf import settings

from leave.services import hours, sickness
from leave.services.common import recipients, span
from messaging import services as messaging

log = logging.getLogger("leave.notify")


def _link(base_url, path):
    """An absolute link: the request's own address, or, for mail sent with
    none (a rota write, the reminder timer), the first trusted origin."""
    base_url = base_url or (settings.CSRF_TRUSTED_ORIGINS or [""])[0]
    return (base_url.rstrip("/") + path) if base_url else path


def _send_all(people, subject, body, url=None):
    rows = []
    for p in people:
        try:
            rows.append(messaging.send(p, subject, body, url=url))
        except Exception:   # messaging.send never raises; belt and braces for the booking's sake
            log.exception("leave mail failed")
    return rows


def request_made(booking, base_url=""):
    p = booking.person
    body = (f"{p.name} has requested {booking.type.name} for {span(booking)}.\n\n"
            f"Decide here: {_link(base_url, '/time-off/approve/')}\n")
    return _send_all(recipients(p), f"{p.name} has requested time off", body, url="/time-off/approve/")


def decided(booking, base_url=""):
    word = "approved" if booking.status == "approved" else "declined"
    body = (f"Your {booking.type.name} for {span(booking)} has been {word}.\n"
            + (f"\nNote from your manager: {booking.manager_note}\n" if booking.manager_note else "")
            + f"\nYour leave: {_link(base_url, '/time-off/mine/')}\n")
    return _send_all([booking.person], f"Your time off has been {word}", body, url="/time-off/mine/")


def cancel_requested(booking, base_url=""):
    p = booking.person
    body = f"{p.name} has asked to cancel {booking.type.name} for {span(booking)}.\n\nDecide here: {_link(base_url, '/time-off/approve/')}\n"
    return _send_all(recipients(p), f"{p.name} has asked to cancel time off", body, url="/time-off/approve/")


def cancel_decided(booking, approved, base_url=""):
    word = "cancelled" if approved else "kept"
    body = f"Your {booking.type.name} for {span(booking)} has been {word}.\n\nYour leave: {_link(base_url, '/time-off/mine/')}\n"
    return _send_all([booking.person], f"Your time off has been {word}", body, url="/time-off/mine/")


def cost_to_check(person, days, base_url=""):
    lines = "\n".join(f"  {bd.day:%a %-d %b %Y}: {hours.fmt(bd.cost_seconds)}"
                      + (" (average day, no rota yet)" if bd.placeholder else " (recalculated from the rota)") for bd in days)
    body = (f"Leave for {person.name} was costed on a day whose rota was not set, or has been recalculated now the rota is set:\n\n{lines}\n\n"
            f"Check it here: {_link(base_url, f'/staff/{person.pk}/profile/?tab=hours')}\n")
    return _send_all(recipients(person), f"Leave cost to check for {person.name}", body, url="/staff/")


def negative_balance(person, statement, base_url=""):
    body = (f"After the hours change, {person.name}'s annual leave remaining is {hours.fmt(statement.annual_remaining)}.\n\n"
            f"Statement: {_link(base_url, f'/staff/{person.pk}/profile/?tab=hours')}\n")
    return _send_all(recipients(person), f"{person.name}'s leave balance is negative", body, url="/staff/")


def reminder(booking, base_url=""):
    p = booking.person
    what = "cancel" if booking.status == "cancel_requested" else "take"
    body = f"{p.name}'s request to {what} {booking.type.name} for {span(booking)} is still waiting.\n\nDecide here: {_link(base_url, '/time-off/approve/')}\n"
    return _send_all(recipients(p), "Time off request still waiting", body, url="/time-off/approve/")


def trigger_reached(person, lvl, rows, base_url=""):
    """NOTIF-05: the person's managers, when a sickness entry takes them to
    a higher trigger. Dates only: no description, no note."""
    lines = "\n".join(f"  {span(b)}" + (" (long sickness)" if sickness.is_long(b) else "") for b in rows)
    label = sickness.level_label(lvl)
    body = (f"{person.name} has reached {label}: {len(rows)} instances of absence in the last six months.\n\n{lines}\n\n"
            f"Profile: {_link(base_url, f'/staff/{person.pk}/profile/?tab=hours')}\n")
    return _send_all(recipients(person), f"{person.name} has reached {label}", body, url="/staff/")


def converted(label, dates, sick, base_url=""):
    """LEAVE-28: the person is told their leave was changed; the sickness
    itself is named by type only."""
    p = sick.person
    body = (f"Your {label} for {dates} has been changed: {span(sick)} is now recorded as {sick.type.name}, "
            f"and those hours have gone back to your allowance.\n\nYour leave: {_link(base_url, '/time-off/mine/')}\n")
    return _send_all([p], "Your time off has been changed", body, url="/time-off/mine/")


def leaving(person, statement, bookings_after, week=False, past=False, base_url=""):
    """NOTIF-06, the two leaver emails: the figure as at the leaving date
    (LEAVE-14) and the bookings that run past it."""
    from leave.services import leavers
    when = f"{person.end_date:%-d %b %Y}"
    lines = "".join(f"\n  {b.type.name} {span(b)}" for b in bookings_after)
    first = f"{person.name} left on {when}" if past else f"{person.name} {'leaves in a week' if week else 'is leaving'}, on {when}"
    body = (f"{first}.\n\n"
            f"As at that day: {leavers.figure_text(statement)}; TOIL remaining {hours.fmt(statement.toil_remaining)}.\n"
            + (f"\nTime off booked after the leaving date, to shorten or cancel:{lines}\n" if bookings_after else "")
            + f"\nProfile: {_link(base_url, f'/staff/{person.pk}/profile/?tab=hours')}\n")
    subject = first if past else (f"{person.name} leaves in a week, on {when}" if week else f"{person.name} is leaving on {when}")
    return _send_all(recipients(person), subject, body, url="/staff/")


def returned(booking, statement, base_url=""):
    """NOTIF-07: back from a long absence, with the leave still to take.
    The allowance was not reduced by the absence (LEAVE-29)."""
    p = booking.person
    weeks = max(1, ((booking.last_day - booking.first_day).days + 1 + 3) // 7)       # to the nearest week
    body = (f"{p.name} is back after {span(booking)} ({booking.type.name}).\n\n"
            f"Annual leave remaining this leave year: {'not set' if statement.missing else hours.fmt(statement.annual_remaining)}; "
            f"TOIL remaining {hours.fmt(statement.toil_remaining)}. The allowance is a full-year figure and was not reduced by the absence; "
            f"leave that could not be taken may need planning or carrying over.\n\n"
            f"Profile: {_link(base_url, f'/staff/{p.pk}/profile/?tab=hours')}\n")
    return _send_all(recipients(p), f"{p.name} is back after {weeks} week{'' if weeks == 1 else 's'} of {booking.type.name}", body, url="/staff/")


def year_end(manager, rows, base_url=""):
    """NOTIF-08: one email per manager at the start of a leave year."""
    from leave.services import years
    lines = "\n".join(
        f"  {r.person.name} ({years.label(r.year_ended)}): "
        + (f"{hours.fmt(-r.annual_remaining)} over" if r.annual_remaining < 0 else f"{hours.fmt(r.annual_remaining)} of annual leave left")
        + (f", TOIL {hours.fmt(r.toil_remaining)}" if r.toil_remaining > 0 else "") for r in rows)
    n = len(rows)
    body = (f"The leave year has ended for {n} of your people with annual leave or TOIL left, or annual leave over.\n\n{lines}\n\n"
            f"For each, choose carry all, lose all or carry part: {_link(base_url, '/time-off/year-end/')}\n")
    return _send_all([manager], f"Year end: {n} {'person has' if n == 1 else 'people have'} leave or TOIL left", body, url="/time-off/year-end/")
