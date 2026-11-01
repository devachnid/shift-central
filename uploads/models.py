"""A document held for the practice (spec 5, section 6): shared with all
staff, or kept on one person's file for their managers."""

from django.conf import settings
from django.db import models


class UploadedFile(models.Model):
    class Kind(models.TextChoices):
        SHARED = "shared"
        PERSON = "person"

    kind = models.CharField(max_length=6, choices=Kind.choices)
    person = models.ForeignKey("people.Person", null=True, blank=True, on_delete=models.CASCADE, related_name="uploads")
    title = models.CharField(max_length=120)
    original_name = models.CharField(max_length=200)
    stored_name = models.CharField(max_length=40, unique=True)
    size = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.CheckConstraint(
            condition=models.Q(kind="shared", person__isnull=True) | models.Q(kind="person", person__isnull=False),
            name="person_file_has_a_person")]

    def __str__(self):
        return self.title
