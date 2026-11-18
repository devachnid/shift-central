from django.conf import settings
from django.db import models

from .person import Person


class Allowance(models.Model):
    """The two full-year figures (LEAVE-01), per leave year. `leave_year`
    is the year's first day. The first row of a year has `from_day` =
    `leave_year`; a later row is a dated hours change (PAT-06, LEAVE-12)
    carrying the new full-year figures and, when set, the new weekly hours
    and days per week from that day.

    `source` says where the figures came from: typed by a manager, worked
    out from the person's contract in Practice HR, or copied from last
    year's. A worked-out or copied row needs checking until `checked_at`
    is set; `checked_by` is the manager who confirmed it, or null when the
    app did (the figures a manager typed turned out to be the rule's, or
    Leave settings no longer asks for a check). The figures hold four
    decimal places so that a whole number of GP sessions is exact to the
    second (64 sessions is 266.6667 h); what a manager types stays at two."""

    class Source(models.TextChoices):
        TYPED = "typed", "typed"
        WORKED_OUT = "worked_out", "worked out"
        COPIED = "copied", "copied from last year"

    NEEDS_CHECK = (Source.WORKED_OUT, Source.COPIED)

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="allowances")
    leave_year = models.DateField()
    from_day = models.DateField(editable=False)
    annual_hours = models.DecimalField(max_digits=8, decimal_places=4)
    bank_holiday_hours = models.DecimalField(max_digits=8, decimal_places=4)
    weekly_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    days_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    hours_applied = models.BooleanField(default=False)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.TYPED)
    checked_at = models.DateTimeField(null=True, blank=True)
    checked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["person", "leave_year", "from_day"],
                                               name="one_allowance_per_person_year_and_day")]
        ordering = ["leave_year", "from_day"]

    @property
    def needs_checking(self):
        return self.source in self.NEEDS_CHECK and self.checked_at is None

    def save(self, *args, **kwargs):
        if self.from_day is None:
            self.from_day = self.leave_year
        super().save(*args, **kwargs)
