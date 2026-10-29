from django.db import models

from .person import Person


class Allowance(models.Model):
    """The two full-year figures a manager types (LEAVE-01), per leave year.
    Stored in this release; spec 3 uses them. `leave_year` is the year's
    first day, so a per-person leave year can follow without a rebuild."""
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="allowances")
    leave_year = models.DateField()
    annual_hours = models.DecimalField(max_digits=6, decimal_places=2)
    bank_holiday_hours = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["person", "leave_year"],
                                               name="one_allowance_per_person_per_year")]
        ordering = ["leave_year"]
