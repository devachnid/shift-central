"""The daily flags (spec 4, section 6): the leaver reminder a week out, the
return from a long absence, the year-end flag. Each step fails on its own
so one bad row never stops the others; the command exits 0 regardless so
the timer does not go red for one person. Run by
shift-central-daily-flags.timer at 08:25 every day."""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand

from leave.services import leavers, returns, yearend

log = logging.getLogger("leave.daily_flags")


class Command(BaseCommand):
    help = "Email managers the leaver, return and year-end flags that fall due today"

    def handle(self, *args, **options):
        base = (settings.CSRF_TRUSTED_ORIGINS or [""])[0]
        steps = (("leaver reminders", lambda: leavers.week_flags(base_url=base)),
                 ("return flags", lambda: returns.send(base_url=base)),
                 ("year-end flags", lambda: yearend.run(base_url=base)))
        for name, step in steps:
            try:
                n = step()
            except Exception:
                log.exception("daily_flags: %s failed", name)
                self.stderr.write(f"{name} failed; see the journal")
                continue
            self.stdout.write(f"{n} {name}")
