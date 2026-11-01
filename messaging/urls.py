from django.urls import path

from messaging.views import app, messages, notices, push
from messaging.views import outbox as outbox_views

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
    path("outbox/", outbox_views.index, name="outbox"),
    path("notices/", notices.board, name="notices"),
    path("notices/new/", notices.new, name="notice-new"),
    path("notices/<int:pk>/edit/", notices.edit, name="notice-edit"),
    path("notices/<int:pk>/remove/", notices.remove, name="notice-remove"),
]
