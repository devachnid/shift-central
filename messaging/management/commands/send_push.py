"""Send the queued phone notifications. Run every minute by
shift-central-push.timer; exits 0 whatever happened so the timer does not go
red for one bad phone."""

from django.core.management.base import BaseCommand

from messaging.services import push


class Command(BaseCommand):
    help = "Send the queued push notifications"

    def handle(self, *args, **options):
        if not push.configured():
            self.stdout.write("push is not configured; nothing to send")
            return
        c = push.send_pending()
        self.stdout.write(f"{c['sent']} sent, {c['failed']} given up, {c['expired']} expired, "
                          f"{c['gone']} devices removed, {c['no_device']} with no device")
