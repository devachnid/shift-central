"""The Django admin is for the superuser's setup and break-glass only
(spec, section 5). Every day-to-day screen is the app's own."""

from unfold.sites import UnfoldAdminSite


class ShiftCentralAdminSite(UnfoldAdminSite):
    def has_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)
