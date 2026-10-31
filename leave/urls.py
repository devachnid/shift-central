from django.urls import path

from leave import views

urlpatterns = [
    path("time-off/", views.time_off, name="time-off"),
    path("time-off/add/", views.add, name="time-off-add"),
    path("time-off/request/", views.request_time_off, name="time-off-request"),
    path("time-off/mine/", views.mine, name="time-off-mine"),
    path("time-off/<int:pk>/", views.view, name="time-off-view"),
    path("time-off/<int:pk>/edit/", views.edit, name="time-off-edit"),
    path("time-off/<int:pk>/cancel/", views.cancel, name="time-off-cancel"),
]
