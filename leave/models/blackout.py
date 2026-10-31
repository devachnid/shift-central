from django.db import models


class Blackout(models.Model):
    """REQ-08: staff cannot request leave on these days; managers still book."""
    first_day = models.DateField()
    last_day = models.DateField()
    teams = models.ManyToManyField("people.Team", blank=True, related_name="blackouts")   # none = everyone
    note = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        ordering = ["first_day"]

    def applies_to(self, team):
        ids = list(self.teams.values_list("pk", flat=True))
        return not ids or (team is not None and team.pk in ids)
