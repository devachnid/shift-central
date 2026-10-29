"""The Options panel's ticks, per user (spec, section 2)."""

from django.conf import settings
from django.db import models


class GridOptions(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name="grid_options")
    data = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "grid options"
