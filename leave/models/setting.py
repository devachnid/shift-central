from django.db import models


class LeaveSetting(models.Model):
    """One row. Read through leave.services.settings.get()."""
    reminder_working_days = models.PositiveSmallIntegerField(default=3)

    class Meta:
        verbose_name = "leave settings"
        verbose_name_plural = "leave settings"
