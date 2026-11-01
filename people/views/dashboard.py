from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from people.services import access, dashboard


@login_required
@access.manager_required
def index(request):
    return render(request, "people/dashboard.html", {"page_title": "Dashboard", "cards": dashboard.build(request.user)})
