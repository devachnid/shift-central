from django.conf import settings
from django.db import models


class Adjustment(models.Model):
    """LEAVE-31's manual ledger: a signed number of seconds on one account
    for one leave year, with the typed reason. MIG-04's carry-over from
    FindMyShift and spec 4's year-end carry-over are rows here."""
    person = models.ForeignKey("people.Person", on_delete=models.CASCADE, related_name="leave_adjustments")
    leave_year = models.DateField()
    account = models.CharField(max_length=12)
    seconds = models.IntegerField()
    reason = models.CharField(max_length=300)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["at"]
        indexes = [models.Index(fields=["person", "leave_year"])]
