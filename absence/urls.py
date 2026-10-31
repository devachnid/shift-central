from django.urls import path

from absence import views

urlpatterns = [
    path("time-off/<int:pk>/convert/", views.convert_view, name="time-off-convert"),
    path("time-off/past/", views.past_index, name="time-off-past"),
    path("time-off/past/add/", views.past_add, name="time-off-past-add"),
]
