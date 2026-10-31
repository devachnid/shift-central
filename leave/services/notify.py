"""The emails of spec section 7, through messaging.send: plain text, one
Outbox row each, never raising, never a description or note in a subject."""

import logging

from leave.services import hours
from leave.services.common import recipients, span
from messaging import services as messaging

log = logging.getLogger("leave.notify")


def _link(base_url, path):
    return (base_url.rstrip("/") + path) if base_url else path


def _send_all(people, subject, body):
    rows = []
    for p in people:
        try:
            rows.append(messaging.send(p, subject, body))
        except Exception:   # messaging.send never raises; belt and braces for the booking's sake
            log.exception("leave mail failed")
    return rows


def request_made(booking, base_url=""):
    p = booking.person
    body = (f"{p.name} has requested {booking.type.name} for {span(booking)}.\n\n"
            f"Decide here: {_link(base_url, '/time-off/approve/')}\n")
    return _send_all(recipients(p), f"{p.name} has requested time off", body)


def decided(booking, base_url=""):
    word = "approved" if booking.status == "approved" else "declined"
    body = (f"Your {booking.type.name} for {span(booking)} has been {word}.\n"
            + (f"\nNote from your manager: {booking.manager_note}\n" if booking.manager_note else "")
            + f"\nYour leave: {_link(base_url, '/time-off/mine/')}\n")
    return _send_all([booking.person], f"Your time off has been {word}", body)


def cancel_requested(booking, base_url=""):
    p = booking.person
    body = f"{p.name} has asked to cancel {booking.type.name} for {span(booking)}.\n\nDecide here: {_link(base_url, '/time-off/approve/')}\n"
    return _send_all(recipients(p), f"{p.name} has asked to cancel time off", body)


def cancel_decided(booking, approved, base_url=""):
    word = "cancelled" if approved else "kept"
    body = f"Your {booking.type.name} for {span(booking)} has been {word}.\n\nYour leave: {_link(base_url, '/time-off/mine/')}\n"
    return _send_all([booking.person], f"Your time off has been {word}", body)


def cost_to_check(person, days, base_url=""):
    lines = "\n".join(f"  {bd.day:%a %-d %b %Y}: {hours.fmt(bd.cost_seconds)}"
                      + (" (average day, no rota yet)" if bd.placeholder else " (recalculated from the rota)") for bd in days)
    body = (f"Leave for {person.name} was costed on a day whose rota was not set, or has been recalculated now the rota is set:\n\n{lines}\n\n"
            f"Check it here: {_link(base_url, f'/staff/{person.pk}/profile/?tab=hours')}\n")
    return _send_all(recipients(person), f"Leave cost to check for {person.name}", body)


def negative_balance(person, statement, base_url=""):
    body = (f"After the hours change, {person.name}'s annual leave remaining is {hours.fmt(statement.annual_remaining)}.\n\n"
            f"Statement: {_link(base_url, f'/staff/{person.pk}/profile/?tab=hours')}\n")
    return _send_all(recipients(person), f"{person.name}'s leave balance is negative", body)
