from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(authentication_form=views.LoginForm),
         name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("not-on-rota/", views.not_on_rota, name="not_on_rota"),
]
