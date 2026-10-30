from django.contrib import admin

from people.admin import ReadOnlyModelAdmin

from .models import Outbox


@admin.register(Outbox)
class OutboxAdmin(ReadOnlyModelAdmin):
    list_display = ("queued_at", "to_email", "subject", "sent_at", "error")
