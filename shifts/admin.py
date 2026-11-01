"""Setup and repair only: every edit happens on the grid, through the
services, so it is audited. A superuser may delete a stray entry or template."""

from django.contrib import admin

from people.admin import ReadOnlyModelAdmin

from .models import DayChange, Entry, GpSession, GridOptions, OpenShift, OpenShiftClaim, Template


@admin.register(Entry)
class EntryAdmin(ReadOnlyModelAdmin):
    deletable = True
    list_display = ("person", "day", "position", "kind", "start", "finish", "break_minutes",
                    "department", "overtime", "wfh")
    list_filter = ("kind", "overtime")
    search_fields = ("person__name",)
    date_hierarchy = "day"


@admin.register(Template)
class TemplateAdmin(ReadOnlyModelAdmin):
    deletable = True
    list_display = ("name", "created_by", "created_at")


@admin.register(DayChange)
class DayChangeAdmin(ReadOnlyModelAdmin):
    list_display = ("person", "day", "at")


@admin.register(GpSession)
class GpSessionAdmin(ReadOnlyModelAdmin):
    list_display = ("person", "day", "part", "label", "site", "synced_at")
    date_hierarchy = "day"


@admin.register(GridOptions)
class GridOptionsAdmin(ReadOnlyModelAdmin):
    list_display = ("user",)


@admin.register(OpenShift)
class OpenShiftAdmin(ReadOnlyModelAdmin):
    list_display = ("day", "start", "finish", "team", "state")


@admin.register(OpenShiftClaim)
class OpenShiftClaimAdmin(ReadOnlyModelAdmin):
    list_display = ("open_shift", "person", "state", "created_at")
