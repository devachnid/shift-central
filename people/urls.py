from django.urls import path

from . import views

urlpatterns = [
    path("staff/", views.staff, name="staff"),
    path("staff/sync/", views.sync_now, name="staff-sync"),
    path("staff/add/", views.add_staff, name="staff-add"),
    path("staff/<int:pk>/profile/", views.profile, name="profile"),
    path("staff/<int:pk>/history/", views.history, name="profile-history"),
    path("staff/<int:pk>/permissions/", views.permissions, name="permissions"),
    path("departments/", views.departments.index, name="departments"),
    path("departments/add/", views.departments.add, name="department-add"),
    path("departments/<int:pk>/edit/", views.departments.edit, name="department-edit"),
    path("activity/", views.activity, name="activity"),
    path("activity/logins/", views.logins, name="activity-logins"),
]
