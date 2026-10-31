"""Leave types and leave settings (LEAVE-25, 28), for managers: a list of
types with Add and Edit pop-ups, and the one settings form."""

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from leave.forms import SettingsForm, TypeForm
from leave.models import LeaveType
from leave.services import settings as leave_settings_service
from people.services import access

LIST = "/settings/leave-types/"


@login_required
@access.manager_required
def types_index(request):
    return render(request, "leave/types.html", {"page_title": "Leave types", "rows": LeaveType.objects.all()})


def _dialog(request, row=None):
    form = TypeForm(request.POST or None, row=row)
    if request.method == "POST" and form.is_valid():
        form.save(request.user)
        return JsonResponse({"redirect": LIST})
    return render(request, "leave/type_dialog.html", {"form": form, "row": row})


@login_required
@access.manager_required
def type_add(request):
    return _dialog(request)


@login_required
@access.manager_required
def type_edit(request, pk):
    return _dialog(request, get_object_or_404(LeaveType, pk=pk))


@login_required
@access.manager_required
def leave_settings(request):
    current = leave_settings_service.get()
    form = SettingsForm(request.POST or None, initial={"reminder_working_days": current.reminder_working_days})
    saved = False
    if request.method == "POST" and form.is_valid():
        leave_settings_service.update(request.user, form.cleaned_data["reminder_working_days"])
        saved = True
    return render(request, "leave/settings.html", {"page_title": "Leave settings", "form": form, "saved": saved})
