"""Read GP sessions from the GP rota app. Run by shift-central-gp-sync.timer
every fifteen minutes."""

from django.core.management.base import BaseCommand, CommandError

from shifts.services import gp_sync


class Command(BaseCommand):
    help = "Read GP sessions from the GP rota app into Shift Central"

    def handle(self, *args, **options):
        if not gp_sync.configured():
            raise CommandError("ROTA_URL or ROTA_API_TOKEN is not set; nothing to read from")
        run = gp_sync.sync()
        if not run.ok:
            raise CommandError(f"gp_sync failed: {run.message}")
        self.stdout.write(f"sessions for {run.people_seen} GPs read from the GP rota" + (f" ({run.message})" if run.message else ""))
