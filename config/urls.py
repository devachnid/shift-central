from django.contrib import admin
from django.urls import include, path

from ui.views import home

urlpatterns = [
    path("admin/", admin.site.urls),
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("accounts/", include("accounts.urls")),
    path("", include("people.urls")),
    path("", home, name="home"),
]
