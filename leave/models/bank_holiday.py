from django.db import models


class BankHoliday(models.Model):
    day = models.DateField(unique=True)
    name = models.CharField(max_length=60)

    class Meta:
        ordering = ["day"]

    def __str__(self):
        return f"{self.day} {self.name}"
