"""A saved clipboard block (spec, section 5), shared by every manager."""

from django.conf import settings
from django.db import models


class Template(models.Model):
    name = models.CharField(max_length=80, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    block = models.JSONField(default=dict)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
