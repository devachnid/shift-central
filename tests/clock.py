"""The suite's clock. Every test runs as if it were PIN unless it says
otherwise: the leave rules are relative to today ("this leave year and the
next", "in the past"), so a suite that read the real clock would start
failing as the calendar moved on.

A test (or a module, through pytestmark) written on a fixed calendar says
which day it is set on with @pytest.mark.today(day); the modules built on the
2026-27 calendar (the worked examples, bookings in 2027) use LATE_2026. A
test may also use the `today` fixture or monkeypatch timezone.now/localdate.

Change PIN, and only PIN, to run the rest of the suite on another day: it
passes on any day, which is the point (try 2027-06-01 and 2028-01-04).

The clock ticks on from the pin, so rows written one after another keep
their order."""

import datetime as dt
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
LATE_2026 = dt.date(2026, 11, 2)            # a Monday late in leave year 2026, so that 2027 is "next year"
PIN = dt.datetime(2026, 11, 2, 9, 0, tzinfo=LONDON)
