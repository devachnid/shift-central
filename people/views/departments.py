from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from people.forms import DepartmentForm
from people.models import Department
from people.services import access, departments


@login_required
@access.manager_required
def index(request):
    return render(request, "people/departments.html", {
        "page_title": "Departments",
        "active": Department.objects.filter(archived=False),
        "archived": Department.objects.filter(archived=True)})


def _save(request, department):
    form = DepartmentForm(request.POST)
    if form.is_valid():
        name = form.cleaned_data["name"]
        clash = Department.objects.filter(name__iexact=name).exclude(pk=getattr(department, "pk", None))
        if clash.exists():
            form.add_error("name", "A department with this name already exists.")
        elif department is None:
            departments.create(request.user, name, form.cleaned_data["colour"],
                               form.cleaned_data["display_order"])
            return form, True
        else:
            departments.update(request.user, department, **form.cleaned_data)
            return form, True
    return form, False


@login_required
@access.manager_required
def add(request):
    if request.method == "POST":
        form, ok = _save(request, None)
        if ok:
            return JsonResponse({"redirect": reverse("departments")})
    else:
        form = DepartmentForm(initial={"colour": "#2F6FB3"})
    return render(request, "people/department_dialog.html", {"form": form, "department": None})


@login_required
@access.manager_required
def edit(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == "POST":
        form, ok = _save(request, department)
        if ok:
            return JsonResponse({"redirect": reverse("departments")})
    else:
        form = DepartmentForm(initial={f: getattr(department, f) for f in departments.FIELDS})
    return render(request, "people/department_dialog.html", {"form": form, "department": department})
