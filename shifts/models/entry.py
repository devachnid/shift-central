"""One row per item in a cell. A cell is one person on one day and, as in
FindMyShift, holds several items in order: shifts, comments, separators
(spec, section 2). ROTA-06's overtime is a second shift in the same cell."""

from datetime import datetime, timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q


class Entry(models.Model):
    class Kind(models.TextChoices):
        SHIFT = "shift"
        COMMENT = "comment"
        SEPARATOR = "separator"

    class Overtime(models.TextChoices):
        NONE = "", "None"
        PAID = "paid", "Overtime – paid"
        TOIL = "toil", "Overtime – TOIL"

    BREAKS = (0, 15, 30, 45, 60)

    person = models.ForeignKey("people.Person", on_delete=models.PROTECT, related_name="entries")
    day = models.DateField()
    position = models.PositiveSmallIntegerField(default=0)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.SHIFT)
    start = models.TimeField(null=True, blank=True)
    finish = models.TimeField(null=True, blank=True)
    break_minutes = models.PositiveSmallIntegerField(default=0)
    department = models.ForeignKey("people.Department", null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="entries")
    text = models.CharField(max_length=200, blank=True, default="")
    overtime = models.CharField(max_length=4, choices=Overtime.choices, blank=True, default="")
    wfh = models.BooleanField(default=False)
    # bg, fg (hex), bold, italic, underline, strike, wrap (bool), size (sm/md/lg).
    # Empty means the department's colour and the defaults (ROTA-04a).
    appearance = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day", "person_id", "position"]
        verbose_name_plural = "entries"
        constraints = [
            models.UniqueConstraint(fields=["person", "day", "position"], name="one_item_per_slot"),
            models.CheckConstraint(
                condition=(Q(kind="shift", start__isnull=False, finish__isnull=False)
                           | (~Q(kind="shift") & Q(start__isnull=True, finish__isnull=True))),
                name="shift_has_times"),
        ]
        indexes = [models.Index(fields=["person", "day"])]

    def __str__(self):
        return f"{self.person_id} {self.day} #{self.position} {self.kind}"

    @property
    def hours(self):
        """finish − start − break for a shift, zero otherwise. Overtime is
        not subtracted here: readers that must leave it out filter on the
        mark (LEAVE-05, 23)."""
        if self.kind != self.Kind.SHIFT or self.start is None or self.finish is None:
            return timedelta(0)
        anchor = datetime(2000, 1, 1)
        worked = datetime.combine(anchor, self.finish) - datetime.combine(anchor, self.start)
        return max(worked - timedelta(minutes=self.break_minutes), timedelta(0))
