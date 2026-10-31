"""Remind managers of requests still waiting (REQ-13). Run by
shift-central-leave-reminders.timer each weekday morning."""

from django.conf import settings
from django.core.management.base import BaseCommand

from leave.services import reminders


class Command(BaseCommand):
    help = "Email managers about leave requests waiting longer than the setting's working days"

    def handle(self, *args, **options):
        base = (settings.CSRF_TRUSTED_ORIGINS or [""])[0]
        n = reminders.send(base_url=base)
        self.stdout.write(f"{n} reminder{'' if n == 1 else 's'} sent")
