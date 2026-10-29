from django.db import models


class SyncRun(models.Model):
    """One row per hr_sync run. `message` is an error's text, never a
    record's values."""
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=False)
    people_seen = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-started_at"]
