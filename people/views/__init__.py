from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def staff(request):
    # A shell for now: the table is filled by the staff list task.
    return render(request, "people/staff.html", {"page_title": "Staff"})
