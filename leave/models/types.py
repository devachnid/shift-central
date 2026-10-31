from django.db import models


class LeaveType(models.Model):
    """LEAVE-25's list. draws_from and on_payroll decide the arithmetic and
    spec 4's payroll report, so on a seeded row they are fixed; a manager
    chooses them once for a type they add."""

    class Account(models.TextChoices):
        ANNUAL = "annual", "Annual leave"
        BANK_HOLIDAY = "bank_holiday", "Bank holiday allowance"
        TOIL = "toil", "TOIL"
        NONE = "none", "Nothing"

    class Payroll(models.TextChoices):
        ALWAYS = "always", "Always"
        IF_UNPAID = "if_unpaid", "If unpaid"
        LEAVERS = "leavers", "Only for leavers"
        NEVER = "never", "Never"

    name = models.CharField(max_length=60, unique=True)
    colour = models.CharField(max_length=7, default="#2F6FB3")
    draws_from = models.CharField(max_length=12, choices=Account.choices, default=Account.NONE)
    requestable = models.BooleanField(default=False)
    paid_choice = models.BooleanField(default=False)
    default_paid = models.BooleanField(default=True)
    on_payroll = models.CharField(max_length=9, choices=Payroll.choices, default=Payroll.NEVER)
    display_order = models.PositiveIntegerField(default=100)
    archived = models.BooleanField(default=False)
    seeded = models.BooleanField(default=False)
    # Spec 4. A type that counts as sickness makes instances of absence
    # (LEAVE-40); a type that flags the return emails the managers when a
    # booking of it ends (LEAVE-29). Both are a manager's to set.
    sickness = models.BooleanField(default=False)
    flag_return = models.BooleanField(default=False)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name
