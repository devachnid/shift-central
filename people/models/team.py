from django.db import models


class Team(models.Model):
    """Mirrors Practice HR's teams: created by the sync when a new name
    arrives; the order and active flag are edited here."""
    name = models.CharField(max_length=60, unique=True)
    display_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name
