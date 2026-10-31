from django.db import models

from .person import Person


class Allowance(models.Model):
    """The two full-year figures a manager types (LEAVE-01), per leave year.
    `leave_year` is the year's first day. The first row of a year has
    `from_day` = `leave_year`; a later row is a dated hours change (PAT-06,
    LEAVE-12) carrying the new full-year figures and, when set, the new
    weekly hours and days per week from that day."""
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="allowances")
    leave_year = models.DateField()
    from_day = models.DateField(editable=False)
    annual_hours = models.DecimalField(max_digits=6, decimal_places=2)
    bank_holiday_hours = models.DecimalField(max_digits=6, decimal_places=2)
    weekly_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    days_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    hours_applied = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["person", "leave_year", "from_day"],
                                               name="one_allowance_per_person_year_and_day")]
        ordering = ["leave_year", "from_day"]

    def save(self, *args, **kwargs):
        if self.from_day is None:
            self.from_day = self.leave_year
        super().save(*args, **kwargs)
