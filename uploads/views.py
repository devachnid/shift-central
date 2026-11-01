"""The shared Uploads page, a person's documents, and the download."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from people.models import Person
from people.services import access
from uploads import services
from uploads.forms import UploadForm
from uploads.models import UploadedFile


def _handle_upload(request, kind, person=None):
    """The POST of either page: True on success (a flash is queued)."""
    form = UploadForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            services.add(request.user, form.cleaned_data["file"], form.cleaned_data["title"], kind, person)
            messages.success(request, "The document is added.")
            return form, True
        except services.UploadError as e:
            form.add_error("file", e.message)
    return form, False


@login_required
def shared(request):
    form = UploadForm()
    if request.method == "POST":
        if not access.is_manager(request.user):
            raise PermissionDenied
        form, ok = _handle_upload(request, UploadedFile.Kind.SHARED)
        if ok:
            return redirect("uploads")
    return render(request, "uploads/list.html", {
        "page_title": "Uploads", "files": services.shared_files(), "form": form, "is_manager": access.is_manager(request.user),
        "all_teams": access.is_all_teams(request.user)})


@login_required
def person(request, pk):
    owner = get_object_or_404(Person, pk=pk)
    files = services.person_files(request.user, owner)        # 404 unless the user manages them
    form = UploadForm()
    if request.method == "POST":
        form, ok = _handle_upload(request, UploadedFile.Kind.PERSON, owner)
        if ok:
            return redirect("person-uploads", pk=owner.pk)
    return render(request, "uploads/person.html", {"page_title": f"{owner.name}: documents", "owner": owner, "files": files, "form": form})


@login_required
def download(request, pk):
    return services.open_file(request.user, get_object_or_404(UploadedFile, pk=pk))


@login_required
@require_POST
def delete(request, pk):
    uploaded = get_object_or_404(UploadedFile, pk=pk)
    owner_pk = uploaded.person_id
    services.remove(request.user, uploaded)
    messages.success(request, "The document is removed.")
    return redirect("person-uploads", pk=owner_pk) if owner_pk else redirect("uploads")
