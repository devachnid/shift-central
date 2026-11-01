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
