from django.conf import settings
from django.db import models


class AuditEntry(models.Model):
    """One row per field changed by a service, and the activity log's
    source (ACC-08, LEAVE-31). Never edited or deleted."""

    class Kind(models.TextChoices):
        CHANGE = "change"
        VIEWED = "viewed"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="+")
    actor_email = models.CharField(max_length=254, blank=True, default="")
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.CHANGE)
    model = models.CharField(max_length=60, db_index=True)
    object_id = models.PositiveBigIntegerField(db_index=True)
    field = models.CharField(max_length=60)
    before = models.TextField(blank=True, default="")
    after = models.TextField(blank=True, default="")
    note = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-at", "-pk"]
        verbose_name_plural = "audit entries"
