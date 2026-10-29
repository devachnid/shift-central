"""The FindMyShift-style shell: navy side panel, flyouts, top bar, and only
this release's items."""

import re

import pytest
from django.test import Client

from tests.factories import make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db
ROOT_URL = re.compile(r"""(href|src)=["']https?://""")


def _client_for(person, **kw):
    c = Client()
    c.force_login(make_user_for(person, **kw))
    return c


def test_staff_see_staff_and_nothing_managerial():
    body = _client_for(make_person()).get("/staff/").content.decode()
    assert 'data-nav="staff"' in body
    assert 'data-nav="departments"' not in body and 'data-nav="activity"' not in body
    assert "Log out" in body


def test_team_managers_see_departments_and_the_activity_log_not_login_logs():
    nursing = make_team("Nursing")
    lead = make_person(team=nursing)
    make_team_manager(lead, nursing)
    body = _client_for(lead).get("/staff/").content.decode()
    assert 'data-nav="departments"' in body and 'href="/activity/"' in body
    assert 'href="/activity/logins/"' not in body


def test_all_teams_managers_see_everything_in_this_release():
    body = _client_for(make_person(), is_all_teams_manager=True).get("/staff/").content.decode()
    for item in ("staff", "departments", "activity"):
        assert f'data-nav="{item}"' in body
    assert 'href="/activity/logins/"' in body
    for later in ("rota", "time-off", "messages", "reports", "settings"):
        assert f'data-nav="{later}"' not in body, "later specs add their items"


def test_the_page_pulls_nothing_from_another_origin():
    body = _client_for(make_person()).get("/staff/").content.decode()
    assert not ROOT_URL.search(body)
    assert "fonts.googleapis" not in body


def test_the_top_bar_carries_the_page_title_and_the_dialog_target():
    body = _client_for(make_person()).get("/staff/").content.decode()
    assert '<h1 class="topbar-title">Staff</h1>' in body
    assert 'id="dialog"' in body


def test_the_logo_and_brand_colours_are_in_place():
    from pathlib import Path
    tokens = Path("static/css/tokens.css").read_text()
    for colour in ("#143D5C", "#F2A33A", "#DDE7EE"):
        assert colour in tokens
    body = _client_for(make_person()).get("/staff/").content.decode()
    assert "img/logo-dark.svg" in body


def test_the_login_page_uses_the_shell_without_the_side_panel(client):
    body = client.get("/accounts/login/").content.decode()
    assert "auth-card" in body and 'class="sidebar"' not in body
