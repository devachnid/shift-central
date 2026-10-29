"""Read people from Practice HR. Run by shift-central-hr-sync.timer every
fifteen minutes, and by the Staff page's Sync now button."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from people.services import hr_sync


class Command(BaseCommand):
    help = "Read people from Practice HR into Shift Central"

    def handle(self, *args, **options):
        if not settings.PRACTICE_HR_URL:
            raise CommandError("PRACTICE_HR_URL is not set; nothing to read from")
        if not settings.HR_API_TOKEN:
            raise CommandError("HR_API_TOKEN is not set; Practice HR would refuse the request")
        run = hr_sync.sync()
        if not run.ok:
            raise CommandError(f"hr_sync failed: {run.message}")
        self.stdout.write(f"{run.people_seen} people read from Practice HR")
