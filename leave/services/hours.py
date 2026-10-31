"""Durations as LEAVE-04 shows them. Everything in leave is integer seconds;
a half-minute (half of an odd-minute shift, LV-04b) is 30 seconds and is
written as ½ after the minutes. A GP session is 4 h 10 min (ROTA-GP-02)."""

from decimal import Decimal

GP_SESSION = 4 * 3600 + 10 * 60   # 15000


def from_hours(value):
    """Decimal hours (an allowance box) to whole seconds; 87.40 h is 314640 s exactly."""
    return int((Decimal(value) * 3600).to_integral_value())


def fmt(seconds):
    sign = "−" if seconds < 0 else ""
    total = abs(int(seconds))
    h, rest = divmod(total, 3600)
    m, s = divmod(rest, 60)
    half = "½" if s >= 30 else ""
    if h and (m or half):
        return f"{sign}{h} h {m}{half} min"
    if h:
        return f"{sign}{h} h"
    return f"{sign}{m}{half} min"


def fmt_short(seconds):
    """H:MM, the way an hours box is typed and read back (parse_hours)."""
    h, rest = divmod(max(int(seconds), 0), 3600)
    return f"{h}:{rest // 60:02d}"
