from django.contrib import admin

from people.admin import ReadOnlyModelAdmin

from .models import Outbox, PushDevice


@admin.register(Outbox)
class OutboxAdmin(ReadOnlyModelAdmin):
    list_display = ("queued_at", "to_email", "subject", "sent_at", "error")


@admin.register(PushDevice)
class PushDeviceAdmin(ReadOnlyModelAdmin):
    list_display = ("person", "label", "created_at", "last_ok_at", "failures")
