from django.contrib import admin

from people.admin import ReadOnlyModelAdmin

from .models import Message, MessageRecipient, Notice, Outbox, PushDevice


@admin.register(Outbox)
class OutboxAdmin(ReadOnlyModelAdmin):
    list_display = ("queued_at", "to_email", "subject", "sent_at", "error")


@admin.register(PushDevice)
class PushDeviceAdmin(ReadOnlyModelAdmin):
    list_display = ("person", "label", "created_at", "last_ok_at", "failures")


@admin.register(Message)
class MessageAdmin(ReadOnlyModelAdmin):
    list_display = ("created_at", "sender", "subject", "everyone")


@admin.register(MessageRecipient)
class MessageRecipientAdmin(ReadOnlyModelAdmin):
    list_display = ("message", "person", "read_at")


@admin.register(Notice)
class NoticeAdmin(ReadOnlyModelAdmin):
    list_display = ("created_at", "posted_by", "title", "pinned", "show_until")
