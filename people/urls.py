from django.urls import path

from . import views

urlpatterns = [
    path("staff/", views.staff, name="staff"),
    path("staff/sync/", views.sync_now, name="staff-sync"),
    path("staff/add/", views.add_staff, name="staff-add"),
]
