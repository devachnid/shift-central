"""Setup and repair only; every edit happens on the app's pages through the
services, so it is audited. Leave types, bank holidays and the settings row
are editable here as well, for the superuser."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from people.admin import ReadOnlyModelAdmin

from .models import Adjustment, BankHoliday, Blackout, Booking, BookingDay, LeaveSetting, LeaveType


@admin.register(LeaveType)
class LeaveTypeAdmin(ModelAdmin):
    list_display = ("name", "draws_from", "requestable", "paid_choice", "on_payroll", "display_order", "archived")


@admin.register(Booking)
class BookingAdmin(ReadOnlyModelAdmin):
    deletable = True
    list_display = ("person", "type", "first_day", "last_day", "part", "status", "requested_at")
    list_filter = ("status", "type")
    search_fields = ("person__name",)
    date_hierarchy = "first_day"


@admin.register(BookingDay)
class BookingDayAdmin(ReadOnlyModelAdmin):
    list_display = ("booking", "day", "cost_seconds", "source", "account", "placeholder")


@admin.register(Adjustment)
class AdjustmentAdmin(ReadOnlyModelAdmin):
    list_display = ("person", "leave_year", "account", "seconds", "reason", "at")


@admin.register(Blackout)
class BlackoutAdmin(ReadOnlyModelAdmin):
    list_display = ("first_day", "last_day", "note")


@admin.register(BankHoliday)
class BankHolidayAdmin(ModelAdmin):
    list_display = ("day", "name")


@admin.register(LeaveSetting)
class LeaveSettingAdmin(ModelAdmin):
    list_display = ("reminder_working_days",)
