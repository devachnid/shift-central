"""The notice board (spec 5, section 5)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from messaging.forms import NoticeForm
from messaging.services import notices as svc
from people.services import access


@login_required
def board(request):
    return render(request, "messaging/notices.html", {
        "page_title": "Notice board", "notices": svc.visible_to(request.user), "is_manager": access.is_manager(request.user),
        "editable": svc.editable(request.user) if access.is_manager(request.user) else []})


def _editable_notice(request, pk):
    return get_object_or_404(svc.editable(request.user), pk=pk)


def _dialog(request, notice=None):
    initial = {}
    if notice is not None:
        initial = {"title": notice.title, "body": notice.body, "everyone": notice.everyone, "teams": notice.teams.all(),
                   "pinned": notice.pinned, "show_until": notice.show_until}
    form = NoticeForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        team_ids = [t.pk for t in d["teams"]]
        try:
            if notice is None:
                svc.post(request.user, d["title"], d["body"], d["everyone"], team_ids, d["pinned"], d["show_until"],
                         d["notify"], base_url=request.build_absolute_uri("/"))
            else:
                svc.edit(request.user, notice, d["title"], d["body"], d["everyone"], team_ids, d["pinned"], d["show_until"])
            return JsonResponse({"refresh": True})
        except svc.NoticeError as e:
            form.add_error(None, e.message)
    return render(request, "messaging/notice_dialog.html", {"form": form, "notice": notice})


@login_required
@access.manager_required
def new(request):
    return _dialog(request)


@login_required
def edit(request, pk):
    if not access.is_manager(request.user):
        raise Http404
    return _dialog(request, _editable_notice(request, pk))


@login_required
@require_POST
def remove(request, pk):
    notice = _editable_notice(request, pk)
    try:
        svc.remove(request.user, notice)
        messages.success(request, "The notice is removed.")
    except PermissionDenied:
        raise Http404 from None
    return redirect("notices")
