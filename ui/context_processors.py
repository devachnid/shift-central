"""What base.html needs: the role flags and this release's nav items. An
item appears only when its spec has built it; later specs append here."""

from django.conf import settings

from people.services import access


def _items(request, role):
    path = request.path
    items = [{"key": "rota", "label": "Rota", "icon": "calendar", "url": "/rota/",
              "active": path.startswith("/rota/"),
              "children": [{"label": "Who's in today", "url": "/rota/today/"}] if role != "staff" else []},
             {"key": "staff", "label": "Staff", "icon": "people", "url": "/staff/",
              "active": path.startswith("/staff/"), "children": []}]
    if role != "staff":
        items.append({"key": "departments", "label": "Departments", "icon": "tag",
                      "url": "/departments/", "active": path.startswith("/departments/"),
                      "children": []})
    items.append({"key": "reports", "label": "Reports", "icon": "report", "url": "/reports/hours/",
                  "active": path.startswith("/reports/"), "children": [{"label": "Hours", "url": "/reports/hours/"}]})
    if role != "staff":
        children = [{"label": "Activity log", "url": "/activity/"}]
        if role == "all":
            children.append({"label": "Log in logs", "url": "/activity/logins/"})
        items.append({"key": "activity", "label": "Activity logs", "icon": "history",
                      "url": "/activity/", "active": path.startswith("/activity/"),
                      "children": children})
    return items


def shell(request):
    user = getattr(request, "user", None)
    role = access.role(user) if user is not None and user.is_authenticated else "staff"
    return {
        "settings_practice_hr_url": settings.PRACTICE_HR_URL,
        "role": role,
        "is_manager": role != "staff",
        "is_all_teams": role == "all",
        "nav_items": _items(request, role) if user is not None and user.is_authenticated else [],
    }
