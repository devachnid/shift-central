from django.urls import path

from messaging.views import app, push

urlpatterns = [
    path("manifest.webmanifest", app.manifest, name="manifest"),
    path("sw.js", app.service_worker, name="service-worker"),
    path("offline/", app.offline, name="offline"),
    path("notifications/", push.notifications, name="notifications"),
    path("push/subscribe/", push.subscribe, name="push-subscribe"),
    path("push/unsubscribe/", push.unsubscribe, name="push-unsubscribe"),
    path("push/devices/<int:pk>/remove/", push.remove_device, name="push-device-remove"),
]
