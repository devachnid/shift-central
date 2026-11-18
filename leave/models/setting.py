from django.db import models


class LeaveSetting(models.Model):
    """One row. Read through leave.services.settings.get()."""
    reminder_working_days = models.PositiveSmallIntegerField(default=3)
    # Allowance spec, 7.6: while on, an allowance the app works out from a
    # contract (or copies from last year) waits for a manager to check it.
    allowances_need_checking = models.BooleanField(default=True)

    class Meta:
        verbose_name = "leave settings"
        verbose_name_plural = "leave settings"
