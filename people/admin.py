"""The admin shows people's data for setup and repair. Every edit happens
on the app's own pages, through the services, so it is audited; so here the
audited models are read-only. Deleting a person who has left HR's feed is
the one act left to the superuser here; their allowances and manager grants
go with them, so those two admins allow a delete too (Django refuses a
cascade into a model whose admin refuses it), though never an add or edit."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Allowance, AuditEntry, Department, Person, SyncRun, Team, TeamManager


class ReadOnlyModelAdmin(ModelAdmin):
    deletable = False

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return self.deletable and super().has_delete_permission(request, obj)


@admin.register(Team)
class TeamAdmin(ModelAdmin):
    list_display = ("name", "display_order", "active")


@admin.register(Person)
class PersonAdmin(ReadOnlyModelAdmin):
    deletable = True
    list_display = ("name", "team", "email", "start_date", "end_date", "is_gp", "last_seen_from_hr")
    search_fields = ("name", "email")
    readonly_fields = ("hr_employee_id", "first_name", "last_name", "name", "email", "team",
                       "start_date", "end_date", "is_gp", "last_seen_from_hr")


@admin.register(Allowance)
class AllowanceAdmin(ReadOnlyModelAdmin):
    deletable = True
    list_display = ("person", "leave_year", "annual_hours", "bank_holiday_hours")


@admin.register(Department)
class DepartmentAdmin(ReadOnlyModelAdmin):
    list_display = ("name", "colour", "display_order", "archived")


@admin.register(TeamManager)
class TeamManagerAdmin(ReadOnlyModelAdmin):
    deletable = True
    list_display = ("person", "team", "granted_by", "granted_at")


@admin.register(AuditEntry)
class AuditEntryAdmin(ReadOnlyModelAdmin):
    list_display = ("at", "actor_email", "model", "object_id", "field", "before", "after")
    readonly_fields = [f.name for f in AuditEntry._meta.fields]


@admin.register(SyncRun)
class SyncRunAdmin(ReadOnlyModelAdmin):
    list_display = ("started_at", "finished_at", "ok", "people_seen", "message")
