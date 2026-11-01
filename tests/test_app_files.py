"""The installable app (spec 5, section 4): a manifest, a service worker that
stores no data, and an offline page, all public."""

import json
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client

from tests.factories import client_for, make_person

pytestmark = pytest.mark.django_db


def test_the_manifest_is_public_json_with_both_icons():
    r = Client().get("/manifest.webmanifest")
    assert r.status_code == 200 and r["Content-Type"].startswith("application/manifest+json")
    assert r["Cache-Control"] == "no-cache"
    data = json.loads(r.content)
    assert data["name"] == "AMG Shift Central" and data["short_name"] == "Shift Central"
    assert data["display"] == "standalone" and data["start_url"] == "/rota/" and data["scope"] == "/"
    assert {i["sizes"] for i in data["icons"]} == {"192x192", "512x512"}


def test_the_service_worker_is_served_from_the_root_with_its_own_cache_header():
    for client in (Client(), client_for(make_person())):         # signed out and signed in
        r = client.get("/sw.js")
        assert r.status_code == 200 and r["Content-Type"].startswith("application/javascript")
        assert r["Cache-Control"] == "no-cache"


def test_the_service_worker_handles_push_and_clicks_and_stores_no_pages():
    body = Client().get("/sw.js").content.decode()
    assert 'addEventListener("push"' in body and 'addEventListener("notificationclick"' in body
    assert 'addEventListener("fetch"' in body
    assert ".put(" not in body and "addAll" not in body, "only the offline page is ever stored"


def test_the_offline_page_needs_no_sign_in_and_is_self_contained():
    r = Client().get("/offline/")
    assert r.status_code == 200 and b"offline" in r.content.lower()
    assert b"<link" not in r.content and b"<script" not in r.content


def test_every_page_links_the_manifest():
    body = client_for(make_person()).get("/rota/").content.decode()
    assert '<link rel="manifest" href="/manifest.webmanifest">' in body


def test_the_policy_allows_the_worker_and_the_manifest_from_our_own_origin():
    policy = Client().get("/accounts/login/")["Content-Security-Policy"]
    assert "worker-src 'self'" in policy and "manifest-src 'self'" in policy


def test_the_icons_are_in_the_static_folder():
    for name in ("icon-192.png", "icon-512.png"):
        assert (Path(settings.BASE_DIR) / "static" / "img" / name).is_file()
