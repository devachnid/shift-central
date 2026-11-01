from django.urls import path

from messaging.views import app, messages, push

urlpatterns = [
    path("manifest.webmanifest", app.manifest, name="manifest"),
    path("sw.js", app.service_worker, name="service-worker"),
    path("offline/", app.offline, name="offline"),
    path("notifications/", push.notifications, name="notifications"),
    path("push/subscribe/", push.subscribe, name="push-subscribe"),
    path("push/unsubscribe/", push.unsubscribe, name="push-unsubscribe"),
    path("push/devices/<int:pk>/remove/", push.remove_device, name="push-device-remove"),
    path("messages/", messages.inbox, name="messages-inbox"),
    path("messages/new/", messages.new, name="message-new"),
    path("messages/sent/", messages.sent, name="messages-sent"),
    path("messages/<int:pk>/", messages.detail, name="message"),
]
