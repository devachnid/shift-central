from django.db import models

from .person import Person


class Contract(models.Model):
    """A copy of one contract in Practice HR's feed (allowance spec, 5.1):
    what the entitlement service works allowances out from. The sync
    replaces a person's rows with what the feed sends; nothing here is
    edited or audited, because Practice HR audits the contract and Shift
    Central audits every allowance figure that results.

    `leave_base` and each step's total are days a year for an hours
    contract and weeks a year for a sessions one; `leave_base` is null when
    the contract has no terms and its allowances are typed. `leave_steps`
    is a list of [after_years, total] pairs, oldest step first, the total a
    string ("23.00") so the decimal is exact."""

    class Unit(models.TextChoices):
        HOURS = "hours"
        SESSIONS = "sessions"

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="contracts")
    hr_id = models.PositiveIntegerField(unique=True)
    type_name = models.CharField(max_length=60)
    unit = models.CharField(max_length=8, choices=Unit.choices)
    from_day = models.DateField()
    to_day = models.DateField(null=True, blank=True)
    weekly_amount = models.DecimalField(max_digits=5, decimal_places=2)
    full_time_weekly = models.DecimalField(max_digits=5, decimal_places=2)
    leave_base = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    leave_steps = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["from_day", "hr_id"]

    def __str__(self):
        return f"{self.type_name}, {self.weekly_amount} {self.unit} a week from {self.from_day:%-d %b %Y}"
