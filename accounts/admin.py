from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import LoginEvent, User


@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ("email", "is_all_teams_manager", "is_superuser", "is_active", "oidc_sub")
    search_fields = ("email",)
    fields = ("email", "is_active", "is_superuser", "oidc_sub")
    readonly_fields = ("oidc_sub",)


@admin.register(LoginEvent)
class LoginEventAdmin(ModelAdmin):
    list_display = ("user", "at", "ip")
    readonly_fields = ("user", "at", "ip", "user_agent")
