"""One row per email the app sends, sent or not (spec, section 2). Spec 5's
Outbox page lists these."""

from django.db import models


class Outbox(models.Model):
    to_person = models.ForeignKey("people.Person", null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="messages")
    to_email = models.EmailField(blank=True, default="")
    subject = models.CharField(max_length=200)
    body = models.TextField()
    queued_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-queued_at"]
        verbose_name_plural = "outbox"
