"""One row per email or push the app sends, sent or not (spec, section 2). Spec 5's
Outbox page lists these."""

from django.db import models


class Outbox(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        PUSH = "push", "Push"

    to_person = models.ForeignKey("people.Person", null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="messages")
    to_email = models.EmailField(blank=True, default="")
    channel = models.CharField(max_length=5, choices=Channel.choices, default=Channel.EMAIL)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    # The page a push opens, and how many times the timer has tried it.
    url = models.CharField(max_length=200, blank=True, default="")
    attempts = models.PositiveSmallIntegerField(default=0)
    queued_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-queued_at"]
        verbose_name_plural = "outbox"
        indexes = [models.Index(fields=["channel", "sent_at"])]


class PushDevice(models.Model):
    """One phone or browser that said yes to notifications (spec 5)."""
    person = models.ForeignKey("people.Person", on_delete=models.CASCADE, related_name="push_devices")
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    label = models.CharField(max_length=80, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_ok_at = models.DateTimeField(null=True, blank=True)
    failures = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["created_at", "pk"]

    def __str__(self):
        return f"{self.label or 'device'} of person {self.person_id}"
