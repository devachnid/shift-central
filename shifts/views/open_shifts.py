"""Open shifts: the list, the post and claim pop-ups, the decision pop-up
and the detail page (spec 5, section 3). A post or claim the user may not
see is a 404, never a 403."""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from people.services import access
from shifts.forms import ClaimForm, DecideForm, OpenShiftForm
from shifts.models import OpenShift, OpenShiftClaim
from shifts.services import open_shifts

REFRESH = {"refresh": True}
WAITING = OpenShiftClaim.State.WAITING


def _visible_post(request, pk):
    return get_object_or_404(open_shifts.visible_to(request.user).select_related("team", "department"), pk=pk)


def _managed_claim(request, pk):
    """A claim on a post of a team the user manages, else 404."""
    claim = get_object_or_404(OpenShiftClaim.objects.select_related("open_shift__team", "open_shift__department", "person"), pk=pk)
    if not access.can_manage_team(request.user, claim.open_shift.team):
        raise Http404
    return claim


def _decorate(request, post):
    me = getattr(request.user, "person", None)
    claims = list(post.claims.all())
    post.can_claim = open_shifts.can_claim(request.user, post)
    post.my_claim = next((c for c in claims if me is not None and c.person_id == me.pk and c.state == WAITING), None)
    post.is_owner = access.can_manage_team(request.user, post.team)
    post.waiting = [c for c in claims if c.state == WAITING] if post.is_owner else []
    for c in post.waiting:
        c.clashes = open_shifts.clashes(c)
    post.audience_text = "Everyone" if post.everyone else ", ".join(t.name for t in post.audience.all())
    return post


@login_required
def open_list(request):
    today = timezone.localdate()
    posts = (open_shifts.visible_to(request.user).select_related("team", "department", "filled_by")
             .prefetch_related("audience", "claims__person"))
    live, past = [], []
    for post in posts:
        _decorate(request, post)
        if post.state == OpenShift.State.OPEN and not post.expired:
            live.append(post)
        elif post.day >= today - timedelta(days=30):
            past.append(post)
    past.sort(key=lambda p: (p.day, p.start), reverse=True)
    return render(request, "shifts/open_shifts.html", {
        "page_title": "Open shifts", "live": live, "past": past, "is_manager": access.is_manager(request.user)})


@login_required
@access.manager_required
def post_dialog(request):
    form = OpenShiftForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            open_shifts.post(request.user, d["team"], d["day"], d["start"], d["finish"], d["break_minutes"],
                             d["department"], d["comment"], d["everyone"], d["audience"],
                             base_url=request.build_absolute_uri("/"))
            return JsonResponse(REFRESH)
        except open_shifts.OpenShiftError as e:
            form.add_error(None, e.message)
    return render(request, "shifts/open_post_dialog.html", {"form": form})


@login_required
def claim_dialog(request, pk):
    post = _visible_post(request, pk)
    form = ClaimForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            open_shifts.claim(request.user, post, form.cleaned_data["overtime"], form.cleaned_data["note"],
                              base_url=request.build_absolute_uri("/"))
            return JsonResponse(REFRESH)
        except open_shifts.OpenShiftError as e:
            form.add_error(None, e.message)
        except PermissionDenied:
            raise Http404 from None
    return render(request, "shifts/open_claim_dialog.html", {"form": form, "post": post})


@login_required
@require_POST
def withdraw_claim(request, pk):
    claim = get_object_or_404(OpenShiftClaim, pk=pk, person__user=request.user)
    try:
        open_shifts.withdraw_claim(request.user, claim)
        messages.success(request, "Your claim is withdrawn.")
    except open_shifts.OpenShiftError as e:
        messages.error(request, e.message)
    return redirect("open-shifts")


@login_required
def detail(request, pk):
    post = _visible_post(request, pk)
    if not access.can_manage_team(request.user, post.team):
        raise Http404
    post = (OpenShift.objects.select_related("team", "department", "filled_by").prefetch_related("audience", "claims__person")
            .get(pk=post.pk))
    _decorate(request, post)
    post.history = [c for c in post.claims.all() if c.state != WAITING]
    return render(request, "shifts/open_detail.html", {"page_title": "Open shift", "post": post})


@login_required
def decide_dialog(request, pk):
    claim = _managed_claim(request, pk)
    form = DecideForm(request.POST or None, initial={"overtime": claim.overtime})
    if request.method == "POST" and form.is_valid():
        action = request.POST.get("action")
        try:
            if action == "approve":
                open_shifts.approve(request.user, claim, form.cleaned_data["overtime"],
                                    base_url=request.build_absolute_uri("/"))
            elif action == "decline":
                open_shifts.decline(request.user, claim, base_url=request.build_absolute_uri("/"))
            else:
                form.add_error(None, "Choose approve or decline.")
            if not form.errors:
                return JsonResponse(REFRESH)
        except open_shifts.OpenShiftError as e:
            form.add_error(None, e.message)
    return render(request, "shifts/open_decide_dialog.html", {
        "form": form, "claim": claim, "post": claim.open_shift, "clashes": open_shifts.clashes(claim)})


@login_required
@require_POST
def withdraw_post(request, pk):
    post = _visible_post(request, pk)
    try:
        open_shifts.withdraw(request.user, post, base_url=request.build_absolute_uri("/"))
        messages.success(request, "The open shift is withdrawn.")
    except open_shifts.OpenShiftError as e:
        messages.error(request, e.message)
    return redirect("open-shifts")
