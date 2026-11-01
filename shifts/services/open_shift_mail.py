"""The emails of open shifts (and, through messaging.send, their pushes):
NOTIF-03 and NOTIF-04, plus the three spec 5 adds. A subject names the day
and times only; a body never carries the post's comment or a claim's note."""

import logging

from messaging import services as messaging

log = logging.getLogger("shifts.open_shifts")


def _day(shift):
    return f"{shift.day:%a %-d %b}"


def _when(shift):
    return f"{shift.start:%H:%M}–{shift.finish:%H:%M}"


def _body(shift, intro, path, base_url):
    lines = [intro, "", f"Day: {_day(shift)}", f"Times: {_when(shift)}"]
    if shift.break_minutes:
        lines.append(f"Break: {shift.break_minutes} minutes")
    if shift.department_id:
        lines.append(f"Department: {shift.department.name}")
    lines += ["", messaging.absolute_link(base_url, path)]
    return "\n".join(lines) + "\n"


def _send_all(people, subject, body, path):
    with messaging.batch() as connection:
        for person in people:
            try:
                messaging.send(person, subject, body, connection=connection, url=path)
            except Exception:  # send never raises; a bug here must not undo the booking
                log.exception("open shift mail failed")


def posted(shift, people, base_url=""):
    _send_all(people, f"Open shift: {_day(shift)}, {_when(shift)}",
              _body(shift, "A shift is open and you can claim it.", "/rota/open/", base_url), "/rota/open/")


def claimed(claim, managers, base_url=""):
    shift, path = claim.open_shift, f"/rota/open/{claim.open_shift_id}/"
    _send_all(managers, f"{claim.person.name} has claimed an open shift",
              _body(shift, f"{claim.person.name} has claimed this open shift. Decide here.", path, base_url), path)


def approved(claim, base_url=""):
    shift = claim.open_shift
    _send_all([claim.person], f"Your open shift claim for {_day(shift)} is approved",
              _body(shift, "Your claim is approved and the shift is on your rota.", "/rota/", base_url), "/rota/")


def declined(claim, base_url=""):
    shift = claim.open_shift
    _send_all([claim.person], f"Your open shift claim for {_day(shift)} was declined",
              _body(shift, "Your claim was not accepted.", "/rota/open/", base_url), "/rota/open/")


def closed(claims, shift, word, base_url=""):
    """`word` is "filled" or "withdrawn": told to everyone whose claim was waiting."""
    _send_all([c.person for c in claims], f"The open shift on {_day(shift)} has been {word}",
              _body(shift, f"This open shift has been {word}.", "/rota/open/", base_url), "/rota/open/")
