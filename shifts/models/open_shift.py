"""Open shifts (ROTA-11, spec 5 section 2): a manager posts an unfilled
shift for chosen teams or everyone, staff claim it, a manager of the owning
team approves one claim and the shift goes on that person's rota."""

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from shifts.models.entry import Entry


class OpenShift(models.Model):
    class State(models.TextChoices):
        OPEN = "open"
        FILLED = "filled"
        WITHDRAWN = "withdrawn"

    # The owning team decides which managers approve; the audience decides
    # who is told and who can claim.
    team = models.ForeignKey("people.Team", on_delete=models.PROTECT, related_name="open_shifts")
    day = models.DateField()
    start = models.TimeField()
    finish = models.TimeField()
    break_minutes = models.PositiveSmallIntegerField(default=0)
    department = models.ForeignKey("people.Department", null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="+")
    comment = models.CharField(max_length=200, blank=True, default="")
    everyone = models.BooleanField(default=False)
    audience = models.ManyToManyField("people.Team", blank=True, related_name="open_shifts_offered")
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="+")
    state = models.CharField(max_length=9, choices=State.choices, default=State.OPEN)
    filled_by = models.ForeignKey("people.Person", null=True, blank=True,
                                  on_delete=models.SET_NULL, related_name="+")
    entry = models.ForeignKey("shifts.Entry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["day", "start", "pk"]
        constraints = [models.CheckConstraint(condition=Q(finish__gt=F("start")), name="open_shift_finish_after_start")]
        indexes = [models.Index(fields=["state", "day"])]

    def __str__(self):
        return f"open shift {self.day} {self.start:%H:%M}-{self.finish:%H:%M}"

    @property
    def expired(self):
        """Not a state: an open post whose day has gone just reads as expired."""
        return self.day < timezone.localdate()


class OpenShiftClaim(models.Model):
    class State(models.TextChoices):
        WAITING = "waiting"
        APPROVED = "approved"
        DECLINED = "declined"
        WITHDRAWN = "withdrawn"
        CLOSED = "closed"      # another claim was approved, or the post withdrawn

    open_shift = models.ForeignKey(OpenShift, on_delete=models.CASCADE, related_name="claims")
    person = models.ForeignKey("people.Person", on_delete=models.CASCADE, related_name="open_shift_claims")
    # The claimant's choice (ROTA-06): normal hours, or overtime paid / TOIL.
    overtime = models.CharField(max_length=4, choices=Entry.Overtime.choices, blank=True, default="")
    note = models.CharField(max_length=200, blank=True, default="")
    state = models.CharField(max_length=9, choices=State.choices, default=State.WAITING)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [models.UniqueConstraint(fields=["open_shift", "person"], condition=Q(state="waiting"),
                                               name="one_waiting_claim")]
