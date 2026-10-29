"""One row per Practice HR employee. The HR-owned fields are overwritten by
every sync and never edited here; the typed fields are the profile's."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .team import Team

HEX_COLOUR = r"^#[0-9a-fA-F]{6}$"


class PersonQuerySet(models.QuerySet):
    def current(self, on=None):
        on = on or timezone.localdate()
        return self.filter(start_date__lte=on).filter(Q(end_date__isnull=True) | Q(end_date__gte=on))


class Person(models.Model):
    # --- from Practice HR -----------------------------------------------
    hr_employee_id = models.PositiveIntegerField(unique=True)
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.PROTECT,
                             related_name="people")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    # HR's contract unit is "sessions": a GP, whose sessions come from the
    # rota app (spec 2) and who has no weekly hours here.
    is_gp = models.BooleanField(default=False)
    last_seen_from_hr = models.DateTimeField(null=True, blank=True)

    # --- typed here, on the profile ------------------------------------
    job_title = models.CharField(max_length=80, blank=True, default="")
    name_colour = models.CharField(max_length=7, default="#143D5C",
                                   validators=[RegexValidator(HEX_COLOUR)])
    display_order = models.PositiveIntegerField(default=100)
    display_on_rota = models.BooleanField(default=True)
    show_to_other_staff = models.BooleanField(default=True)
    can_see_other_staff = models.BooleanField(default=True)
    weekly_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    days_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="person")

    objects = PersonQuerySet.as_manager()

    class Meta:
        ordering = ["team__display_order", "team__name", "display_order", "last_name", "first_name"]
        verbose_name_plural = "people"

    def __str__(self):
        return self.name

    @property
    def average_day(self):
        """Weekly hours over days per week (PAT-05), to two places as the
        profile shows it; None until both are set."""
        if self.weekly_hours is None or not self.days_per_week:
            return None
        return (self.weekly_hours / Decimal(self.days_per_week)).quantize(Decimal("0.01"))

    def current(self, on=None):
        on = on or timezone.localdate()
        return self.start_date <= on and (self.end_date is None or self.end_date >= on)

    @property
    def initials(self):
        return (self.first_name[:1] + self.last_name[:1]).upper()
