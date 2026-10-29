"""The Content-Security-Policy (config/middleware.py): on every page the app
renders, no script but the app's own files."""

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def _policy(resp):
    return {d.split()[0]: d.split()[1:] for d in resp["Content-Security-Policy"].split("; ")}


def test_the_login_page_carries_the_policy():
    policy = _policy(Client().get("/accounts/login/"))
    scripts = policy["script-src"]
    assert scripts[0] == "'self'" and scripts[1].startswith("'nonce-") and len(scripts) == 2
    assert policy["object-src"] == ["'none'"] and policy["base-uri"] == ["'none'"]
    assert policy["frame-ancestors"] == ["'none'"]


def test_the_nonce_is_new_every_time():
    c = Client()
    assert _policy(c.get("/accounts/login/"))["script-src"][1] != _policy(c.get("/accounts/login/"))["script-src"][1]


def test_the_admin_is_left_alone(root_client):
    assert "Content-Security-Policy" not in root_client.get("/admin/")


def test_report_only_is_the_way_back(settings):
    settings.CSP_REPORT_ONLY = True
    r = Client().get("/accounts/login/")
    assert "Content-Security-Policy" not in r
    assert "script-src 'self' 'nonce-" in r["Content-Security-Policy-Report-Only"]


def test_form_action_admits_the_hr_system_when_configured(oidc_on):
    assert "form-action 'self' https://hr.example;" in Client().get("/accounts/login/")["Content-Security-Policy"]
