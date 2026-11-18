"""Read people from Practice HR. Run by shift-central-hr-sync.timer every
fifteen minutes, and by the Staff page's Sync now button."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from people.services import hr_sync


class Command(BaseCommand):
    help = "Read people from Practice HR into Shift Central"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Read the feed and count what a run would change, then undo it all")

    def handle(self, *args, **options):
        if not settings.PRACTICE_HR_URL:
            raise CommandError("PRACTICE_HR_URL is not set; nothing to read from")
        if not settings.HR_API_TOKEN:
            raise CommandError("HR_API_TOKEN is not set; Practice HR would refuse the request")
        if options["dry_run"]:
            return self._dry_run()
        run = hr_sync.sync()
        if not run.ok:
            raise CommandError(f"hr_sync failed: {run.message}")
        self.stdout.write(f"{run.people_seen} people read from Practice HR")

    def _dry_run(self):
        seen = hr_sync.preview()
        if seen["message"]:
            raise CommandError(f"hr_sync failed: {seen['message']}")
        for line in ("Dry run: nothing has been changed.",
                     f"{seen['people']} people in the feed",
                     f"{seen['weekly_hours']} people whose weekly hours would be set from a contract",
                     f"{seen['created']} allowance rows would be created",
                     f"{seen['changed']} allowance rows would be changed",
                     f"{seen['adopted']} typed allowance rows would be taken over as worked out",
                     f"{seen['removed']} allowance rows would be removed",
                     "Working out the allowances would fail for someone; see the journal" if seen["allowances_failed"]
                     else "Working out the allowances would not fail for anyone"):
            self.stdout.write(line)
