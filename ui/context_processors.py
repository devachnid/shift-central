"""What base.html needs: the role flags and this release's nav items. An
item appears only when its spec has built it; later specs append here."""

from django.conf import settings

from people.services import access


def _items(request, role):
    path = request.path
    rota_children = [{"label": "Open shifts", "url": "/rota/open/"}]
    if role != "staff":
        rota_children += [{"label": "Who's in today", "url": "/rota/today/"}, {"label": "Time off…", "url": "/time-off/add/", "dialog": True}]
    items = [{"key": "rota", "label": "Rota", "icon": "calendar", "url": "/rota/",
              "active": path.startswith("/rota/"), "children": rota_children},
             {"key": "staff", "label": "Staff", "icon": "people", "url": "/staff/",
              "active": path.startswith("/staff/"), "children": []}]
    if role != "staff":
        items.append({"key": "departments", "label": "Departments", "icon": "tag",
                      "url": "/departments/", "active": path.startswith("/departments/"),
                      "children": []})
    leave_children = [{"label": "Requests", "url": "/time-off/"}, {"label": "My leave", "url": "/time-off/mine/"},
                {"label": "Year planner", "url": "/time-off/planner/"}]
    if role != "staff":
        leave_children += [{"label": "Waiting for approval", "url": "/time-off/approve/"}, {"label": "Bank holidays", "url": "/time-off/bank-holidays/"},
                     {"label": "Blackouts", "url": "/time-off/blackouts/"},
                     {"label": "Past schedule", "url": "/time-off/past/"},
                     {"label": "Year end", "url": "/time-off/year-end/"}]
    items.insert(1, {"key": "time-off", "label": "Time off", "icon": "calendar-off", "url": "/time-off/",
                     "active": path.startswith("/time-off/"), "children": leave_children})
    report_children = [{"label": "Hours", "url": "/reports/hours/"}, {"label": "Leave", "url": "/reports/leave/"}]
    if role != "staff":
        report_children += [{"label": "Payroll", "url": "/reports/payroll/"}, {"label": "Sickness summary", "url": "/reports/sickness/"},
                            {"label": "Leave summary", "url": "/reports/leave-summary/"}]
    items.append({"key": "reports", "label": "Reports", "icon": "report", "url": "/reports/hours/",
                  "active": path.startswith("/reports/"), "children": report_children})
    if role != "staff":
        children = [{"label": "Activity log", "url": "/activity/"}]
        if role == "all":
            children.append({"label": "Log in logs", "url": "/activity/logins/"})
        items.append({"key": "activity", "label": "Activity logs", "icon": "history",
                      "url": "/activity/", "active": path.startswith("/activity/"),
                      "children": children})
        items.append({"key": "settings", "label": "Settings", "icon": "settings", "url": "/settings/leave-types/",
                      "active": path.startswith("/settings/"),
                      "children": [{"label": "Leave types", "url": "/settings/leave-types/"}, {"label": "Leave settings", "url": "/settings/leave/"}]})
    items.append({"key": "notifications", "label": "Notifications", "icon": "bell", "url": "/notifications/",
                  "active": path.startswith("/notifications/"), "children": []})
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
