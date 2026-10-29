from django.contrib.admin.apps import AdminConfig


class ShiftCentralAdminConfig(AdminConfig):
    """admin.site becomes our Unfold site with the superuser-only rule."""
    default_site = "config.admin_site.ShiftCentralAdminSite"
