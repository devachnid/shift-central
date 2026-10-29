from django.conf import settings
from django.db import models

from .person import Person
from .team import Team


class TeamManager(models.Model):
    """Manager access for one team (PEOPLE-04): the lead nurse for Nursing,
    the head pharmacist for Pharmacy. All-teams managers are HR's `admin`
    claim, not rows here."""
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="manager_of")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="managers")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["person", "team"],
                                               name="one_grant_per_person_per_team")]
