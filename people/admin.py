from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Allowance, AuditEntry, Department, Person, SyncRun, Team, TeamManager


@admin.register(Team)
class TeamAdmin(ModelAdmin):
    list_display = ("name", "display_order", "active")


@admin.register(Person)
class PersonAdmin(ModelAdmin):
    list_display = ("name", "team", "email", "start_date", "end_date", "is_gp", "last_seen_from_hr")
    search_fields = ("name", "email")
    readonly_fields = ("hr_employee_id", "first_name", "last_name", "name", "email", "team",
                       "start_date", "end_date", "is_gp", "last_seen_from_hr")


@admin.register(Allowance)
class AllowanceAdmin(ModelAdmin):
    list_display = ("person", "leave_year", "annual_hours", "bank_holiday_hours")


@admin.register(Department)
class DepartmentAdmin(ModelAdmin):
    list_display = ("name", "colour", "display_order", "archived")


@admin.register(TeamManager)
class TeamManagerAdmin(ModelAdmin):
    list_display = ("person", "team", "granted_by", "granted_at")


@admin.register(AuditEntry)
class AuditEntryAdmin(ModelAdmin):
    list_display = ("at", "actor_email", "model", "object_id", "field", "before", "after")
    readonly_fields = [f.name for f in AuditEntry._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SyncRun)
class SyncRunAdmin(ModelAdmin):
    list_display = ("started_at", "finished_at", "ok", "people_seen", "message")
