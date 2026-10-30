"""A GP's session as the GP rota app published it. Replaced in full for the
synced window by gp_sync; never edited here (spec, section 9)."""

from datetime import timedelta

from django.db import models


class GpSession(models.Model):
    HOURS = timedelta(hours=4, minutes=10)   # ROTA-GP-02

    person = models.ForeignKey("people.Person", on_delete=models.CASCADE, related_name="gp_sessions")
    day = models.DateField()
    part = models.CharField(max_length=2)        # AM / PM
    label = models.CharField(max_length=60)
    site = models.CharField(max_length=60, blank=True, default="")
    note = models.CharField(max_length=200, blank=True, default="")
    synced_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["person", "day", "part"], name="one_session_per_part")]
        ordering = ["day", "part"]
        indexes = [models.Index(fields=["person", "day"])]
