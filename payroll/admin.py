"""Read-only, as the leave admin: a run is made by Mark as sent on the
payroll page and never edited."""

from django.contrib import admin

from people.admin import ReadOnlyModelAdmin

from .models import PayrollRun


@admin.register(PayrollRun)
class PayrollRunAdmin(ReadOnlyModelAdmin):
    list_display = ("month", "sent_at", "sent_by", "people")
