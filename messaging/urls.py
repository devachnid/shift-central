from django.urls import path

from messaging.views import app

urlpatterns = [
    path("manifest.webmanifest", app.manifest, name="manifest"),
    path("sw.js", app.service_worker, name="service-worker"),
    path("offline/", app.offline, name="offline"),
]
