from django.core.validators import RegexValidator
from django.db import models

from .person import HEX_COLOUR


class Department(models.Model):
    """The one combined list of teams, roles and tasks a shift is tagged
    with (ROTA-02). Archived, never deleted: spec 2's shifts reference it."""
    name = models.CharField(max_length=60, unique=True)
    colour = models.CharField(max_length=7, validators=[RegexValidator(HEX_COLOUR)])
    display_order = models.PositiveIntegerField(default=100)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name
