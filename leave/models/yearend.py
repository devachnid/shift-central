from django.conf import settings
from django.db import models


class YearEnd(models.Model):
    """LEAVE-21's flag for one person and one leave year that has ended:
    the figures the flag found, then the manager's decision. The carry and
    any loss are written as Adjustments in the new year; this row is the
    record that the question was asked and answered."""

    person = models.ForeignKey("people.Person", on_delete=models.PROTECT, related_name="year_ends")
    year_ended = models.DateField()                   # the first day of the leave year that ended
    notified_at = models.DateTimeField(null=True, blank=True)
    annual_remaining = models.IntegerField(default=0)  # seconds, bank holiday balance folded in
    toil_remaining = models.IntegerField(default=0)
    annual_carried = models.IntegerField(null=True, blank=True)
    annual_lost = models.IntegerField(null=True, blank=True)
    toil_lost = models.IntegerField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-year_ended", "person__last_name", "person__first_name"]
        constraints = [models.UniqueConstraint(fields=["person", "year_ended"], name="one_year_end_per_person_year")]

    @property
    def decided(self):
        return self.decided_at is not None

    def __str__(self):
        return f"{self.person_id} year end {self.year_ended}"
