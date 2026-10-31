from django.conf import settings
from django.db import models
from django.db.models import F, Q


class Booking(models.Model):
    class Part(models.TextChoices):
        WHOLE = "whole", "Whole day"
        AM = "am", "Morning"
        PM = "pm", "Afternoon"
        TIMES = "times", "Times"

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for approval"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"
        CANCEL_REQUESTED = "cancel_requested", "Cancellation requested"
        CANCELLED = "cancelled", "Cancelled"

    ACTIVE = (Status.APPROVED, Status.CANCEL_REQUESTED)   # statuses whose days cost and cover
    LIVE = (Status.PENDING, Status.APPROVED, Status.CANCEL_REQUESTED)   # statuses that block an overlap

    person = models.ForeignKey("people.Person", on_delete=models.PROTECT, related_name="bookings")
    type = models.ForeignKey("leave.LeaveType", on_delete=models.PROTECT, related_name="bookings")
    description = models.CharField(max_length=80, blank=True, default="")
    first_day = models.DateField()
    last_day = models.DateField()
    part = models.CharField(max_length=5, choices=Part.choices, default=Part.WHOLE)
    start = models.TimeField(null=True, blank=True)
    finish = models.TimeField(null=True, blank=True)
    paid = models.BooleanField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    cancel_requested_at = models.DateTimeField(null=True, blank=True)
    cancel_decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cancel_decided_at = models.DateTimeField(null=True, blank=True)
    staff_note = models.CharField(max_length=300, blank=True, default="")
    manager_note = models.CharField(max_length=300, blank=True, default="")
    reminded_at = models.DateTimeField(null=True, blank=True)
    # Spec 4. A past schedule entry (MIG-05): approved, dates only, no
    # costed days, covering nothing. return_flagged_at: the return email
    # has gone (LEAVE-29).
    dates_only = models.BooleanField(default=False)
    return_flagged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-first_day", "-pk"]
        indexes = [models.Index(fields=["person", "first_day"])]
        constraints = [
            models.CheckConstraint(condition=Q(first_day__lte=F("last_day")), name="booking_days_in_order"),
            models.CheckConstraint(condition=Q(part="whole") | Q(first_day=F("last_day")), name="part_day_is_one_day"),
            models.CheckConstraint(
                condition=(Q(part="times", start__isnull=False, finish__isnull=False, start__lt=F("finish"))
                           | (~Q(part="times") & Q(start__isnull=True, finish__isnull=True))),
                name="times_have_start_before_finish"),
            models.CheckConstraint(condition=Q(dates_only=False) | Q(part="whole"), name="dates_only_is_whole_days"),
        ]

    @property
    def label(self):
        return self.description or self.type.name

    @property
    def is_active(self):
        return self.status in self.ACTIVE

    def days(self):
        from datetime import timedelta
        d = self.first_day
        while d <= self.last_day:
            yield d
            d += timedelta(days=1)

    def __str__(self):
        return f"{self.person_id} {self.type_id} {self.first_day}..{self.last_day} {self.status}"


class BookingDay(models.Model):
    class Source(models.TextChoices):
        ROTA = "rota", "Rota"
        PLACEHOLDER = "placeholder", "Average day"
        HALF = "half", "Half day"
        TIMES = "times", "Times"
        OVERRIDE = "override", "Set by a manager"
        NONE = "none", "No shift"

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="booking_days")
    day = models.DateField()
    cost_seconds = models.IntegerField(default=0)
    source = models.CharField(max_length=11, choices=Source.choices, default=Source.NONE)
    account = models.CharField(max_length=12, default="none")
    placeholder = models.BooleanField(default=False)
    override_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    override_note = models.CharField(max_length=300, blank=True, default="")
    shortened_entry = models.ForeignKey("shifts.Entry", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    original_start = models.TimeField(null=True, blank=True)
    original_finish = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["day"]
        constraints = [models.UniqueConstraint(fields=["booking", "day"], name="one_row_per_booking_day")]
        indexes = [models.Index(fields=["day"])]
