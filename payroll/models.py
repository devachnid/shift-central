from django.conf import settings
from django.db import models
from django.utils import timezone


class PayrollRun(models.Model):
    """One "sent to the bureau" for one calendar month (PAY-02): who marked
    it, when, and the figures as they stood, so a later report can list what
    has changed since. Several runs for a month are allowed; the latest is
    what was sent."""

    month = models.DateField()                       # the first day
    sent_at = models.DateTimeField(default=timezone.now)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    people = models.PositiveIntegerField(default=0)
    figures = models.JSONField(default=dict)          # {"generated_at": iso, "rows": {"<person pk>": {field: value}}}

    class Meta:
        ordering = ["-month", "-sent_at"]
        indexes = [models.Index(fields=["month"])]

    def __str__(self):
        return f"Payroll {self.month:%B %Y}"
