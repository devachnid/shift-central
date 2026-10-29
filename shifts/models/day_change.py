"""What "Notify staff" compares against: the day's rendering when its first
unnotified change landed (spec, sections 2 and 8). One row per person and
day; deleted when the person is told."""

from django.db import models


class DayChange(models.Model):
    person = models.ForeignKey("people.Person", on_delete=models.CASCADE, related_name="day_changes")
    day = models.DateField()
    before = models.TextField(blank=True, default="")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["person", "day"], name="one_change_per_day")]
        ordering = ["person_id", "day"]
