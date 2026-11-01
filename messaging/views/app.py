"""The three public files of the installable app. They hold nothing
personal, so none needs a sign-in (a service worker is fetched without one
when a session has ended)."""

import json
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.templatetags.static import static


def _no_cache(response):
    response["Cache-Control"] = "no-cache"
    return response


def manifest(request):
    data = {
        "name": "AMG Shift Central", "short_name": "Shift Central",
        "start_url": "/rota/", "scope": "/", "display": "standalone",
        "background_color": "#ffffff", "theme_color": "#143D5C",
        "icons": [{"src": static("img/icon-192.png"), "sizes": "192x192", "type": "image/png"},
                  {"src": static("img/icon-512.png"), "sizes": "512x512", "type": "image/png"}],
    }
    return _no_cache(HttpResponse(json.dumps(data), content_type="application/manifest+json"))


def service_worker(request):
    source = (Path(settings.BASE_DIR) / "static" / "js" / "sw.js").read_text()
    return _no_cache(HttpResponse(source, content_type="application/javascript"))


def offline(request):
    return _no_cache(render(request, "messaging/offline.html"))
