"""Who a sign-in is: HR's sub, bound at first sight; the person, bound by
employee_id; all-teams manager from the admin claim; and the log-in log."""

from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import SuspiciousOperation

from accounts.models import LoginEvent
from accounts.oidc import PracticeAccountBackend
from tests.factories import make_person

User = get_user_model()
pytestmark = pytest.mark.django_db
ONLY_HR = "Sign in with the practice account."


def _sign_in(claims, monkeypatch):
    b = PracticeAccountBackend()
    monkeypatch.setattr(b, "get_userinfo", lambda *a: claims)
    return b.get_or_create_user("access", "id", {})


# --- the login page ----------------------------------------------------------

def test_the_login_page_offers_only_the_practice_account_when_configured(client, oidc_on):
    body = client.get("/accounts/login/").content.decode()
    assert "Sign in with the practice account" in body and "/oidc/authenticate/" in body
    assert 'name="password"' not in body


def test_the_practice_account_link_carries_the_page_to_return_to(client, oidc_on):
    body = client.get("/accounts/login/?next=/departments/").content.decode()
    assert 'href="/oidc/authenticate/?next=%2Fdepartments%2F"' in body


def test_without_a_next_the_practice_account_link_is_bare(client, oidc_on):
    assert 'href="/oidc/authenticate/"' in client.get("/accounts/login/").content.decode()


def test_another_sites_next_is_not_carried(client, oidc_on):
    body = client.get("/accounts/login/?next=https://evil.example/").content.decode()
    assert "evil.example" not in body


def test_every_sign_in_asks_practice_hr_to_check_who_is_there(settings):
    """A shared PC: HR's own twelve-hour session must not sign the next
    person in as the last (django-oauth-toolkit sends prompt=login to its
    login form)."""
    assert settings.OIDC_AUTH_REQUEST_EXTRA_PARAMS == {"prompt": "login"}


def test_the_authorisation_request_says_prompt_login(client, oidc_on, settings):
    settings.OIDC_OP_AUTHORIZATION_ENDPOINT = "https://hr.example/o/authorize/"
    r = client.get("/oidc/authenticate/?next=/departments/")
    assert r.status_code == 302 and parse_qs(urlsplit(r["Location"]).query)["prompt"] == ["login"]
    assert client.session["oidc_login_next"] == "/departments/"


def test_the_dialogs_sign_in_link_returns_to_the_page():
    from pathlib import Path
    js = (Path(__file__).parent.parent / "static" / "js" / "modal.js").read_text()
    assert '"/accounts/login/?next=" + encodeURIComponent(location.pathname + location.search)' in js


def test_without_hr_the_superusers_password_form_shows(client, settings):
    settings.PRACTICE_HR_URL = ""
    body = client.get("/accounts/login/").content.decode()
    assert 'id="login-form"' in body and "practice account" not in body


def test_with_hr_nobody_uses_a_password(client, oidc_on, superuser):
    r = client.post("/accounts/login/", {"username": "root@example.org", "password": "pw"})
    assert r.status_code == 200 and "_auth_user_id" not in client.session
    assert ONLY_HR in r.content.decode()


# --- binding --------------------------------------------------------------------

def test_the_first_sign_in_binds_the_sub(monkeypatch):
    u = User.objects.create_user(email="tom@example.org")
    assert _sign_in({"sub": "12", "email": "Tom@Example.org"}, monkeypatch) == u
    u.refresh_from_db()
    assert u.oidc_sub == "12"


def test_later_sign_ins_match_on_sub_whatever_the_email_says(monkeypatch):
    u = User.objects.create_user(email="tom@example.org", oidc_sub="12")
    assert _sign_in({"sub": "12", "email": "tom.h@example.org"}, monkeypatch) == u
    assert User.objects.count() == 1


def test_an_edited_email_cannot_take_over_a_bound_account(monkeypatch):
    boss = User.objects.create_user(email="boss@example.org", oidc_sub="1")
    with pytest.raises(SuspiciousOperation):
        _sign_in({"sub": "99", "email": "boss@example.org"}, monkeypatch)
    boss.refresh_from_db()
    assert boss.oidc_sub == "1" and User.objects.count() == 1


def test_a_new_person_is_created_bound_to_their_sub_with_no_password(monkeypatch):
    u = _sign_in({"sub": "40", "email": "new@example.org"}, monkeypatch)
    assert u.oidc_sub == "40" and not u.has_usable_password() and not u.is_all_teams_manager


def test_employee_id_binds_the_person(monkeypatch):
    p = make_person(hr_employee_id=7, email="sam@example.org")
    u = _sign_in({"sub": "40", "email": "sam@example.org", "employee_id": 7}, monkeypatch)
    p.refresh_from_db()
    assert p.user == u


def test_a_changed_employee_id_rebinds_and_unbinds_the_old_person(monkeypatch):
    old = make_person(hr_employee_id=7)
    new = make_person(hr_employee_id=8)
    u = User.objects.create_user(email="sam@example.org", oidc_sub="40")
    old.user = u
    old.save()
    _sign_in({"sub": "40", "email": "sam@example.org", "employee_id": 8}, monkeypatch)
    old.refresh_from_db()
    new.refresh_from_db()
    assert old.user is None and new.user == u


def test_an_employee_id_naming_nobody_here_still_signs_in(monkeypatch):
    u = _sign_in({"sub": "40", "email": "sam@example.org", "employee_id": 999}, monkeypatch)
    assert u.pk and not hasattr(u, "person")


def test_a_user_whose_person_is_bound_elsewhere_is_moved_not_duplicated(monkeypatch):
    """Two users cannot share a person: a sign-in with that employee_id
    takes it from the user that had it."""
    p = make_person(hr_employee_id=7)
    other = User.objects.create_user(email="old@example.org", oidc_sub="1")
    p.user = other
    p.save()
    u = _sign_in({"sub": "40", "email": "sam@example.org", "employee_id": 7}, monkeypatch)
    p.refresh_from_db()
    assert p.user == u


def test_the_employee_id_is_kept_on_a_new_user(monkeypatch):
    u = _sign_in({"sub": "40", "email": "new@example.org", "employee_id": 7}, monkeypatch)
    u.refresh_from_db()
    assert u.hr_employee_id == 7


def test_the_employee_id_follows_the_claim_at_every_sign_in(monkeypatch):
    u = User.objects.create_user(email="sam@example.org", oidc_sub="40")
    for claim, kept in ((7, 7), (8, 8), (None, None), (True, None)):
        claims = {"sub": "40", "email": "sam@example.org"}
        if claim is not None:
            claims["employee_id"] = claim
        _sign_in(claims, monkeypatch)
        u.refresh_from_db()
        assert u.hr_employee_id == kept


def test_a_json_true_employee_id_binds_nobody(monkeypatch):
    p = make_person(hr_employee_id=1)
    _sign_in({"sub": "40", "email": "sam@example.org", "employee_id": True}, monkeypatch)
    p.refresh_from_db()
    assert p.user is None


# --- the admin claim -----------------------------------------------------------

def test_the_admin_claim_makes_an_all_teams_manager_both_ways(monkeypatch):
    u = User.objects.create_user(email="tom@example.org", oidc_sub="12")
    _sign_in({"sub": "12", "email": "tom@example.org", "admin": True}, monkeypatch)
    u.refresh_from_db()
    assert u.is_all_teams_manager and not u.is_staff
    _sign_in({"sub": "12", "email": "tom@example.org", "admin": False}, monkeypatch)
    u.refresh_from_db()
    assert not u.is_all_teams_manager


@pytest.mark.parametrize("claim", [None, "true", 1])
def test_only_a_true_claim_makes_a_manager(monkeypatch, claim):
    assert not _sign_in({"sub": "40", "email": "new@example.org", "admin": claim},
                        monkeypatch).is_all_teams_manager


def test_nothing_is_saved_when_nothing_changed(monkeypatch):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    User.objects.create_user(email="tom@example.org", oidc_sub="12", is_all_teams_manager=True)
    with CaptureQueriesContext(connection) as queries:
        _sign_in({"sub": "12", "email": "tom@example.org", "admin": True}, monkeypatch)
    assert not [q for q in queries if q["sql"].startswith("UPDATE")]


# --- the holding page ----------------------------------------------------------

def test_a_signed_in_user_with_no_person_lands_on_the_holding_page(staff_client):
    r = staff_client.get("/", follow=True)
    assert r.redirect_chain[-1][0].startswith("/accounts/not-on-rota/")
    assert "not yet on the rota" in r.content.decode()


def test_the_holding_page_is_the_only_page_such_a_user_reaches(staff_client):
    assert staff_client.get("/staff/").status_code == 302


def test_the_holding_page_resolves_once_the_sync_brings_the_person(client):
    """Signed in before HR's record arrived: the next page load after the
    sync binds the person, with no second sign-in."""
    user = User.objects.create_user(email="sam@example.org", hr_employee_id=7)
    client.force_login(user)
    assert client.get("/staff/")["Location"] == "/accounts/not-on-rota/"
    person = make_person(hr_employee_id=7, email="sam@example.org")
    assert client.get("/staff/").status_code == 200
    person.refresh_from_db()
    assert person.user == user


def test_reloading_the_holding_page_checks_again(client, settings):
    user = User.objects.create_user(email="sam@example.org", hr_employee_id=7)
    client.force_login(user)
    assert client.get("/accounts/not-on-rota/").status_code == 200
    make_person(hr_employee_id=7)
    r = client.get("/accounts/not-on-rota/")
    assert r.status_code == 302 and r["Location"] == settings.LOGIN_REDIRECT_URL


def test_the_holding_page_says_it_checks_on_reload(client):
    client.force_login(User.objects.create_user(email="sam@example.org"))
    body = client.get("/accounts/not-on-rota/").content.decode()
    assert "this page checks each time you reload it" in body and "Log out" in body


def test_a_person_bound_to_someone_else_is_not_taken_on_a_page_load(client):
    """Moving a person between accounts is a sign-in's job, on HR's fresh claim."""
    person = make_person(hr_employee_id=7)
    other = User.objects.create_user(email="old@example.org")
    person.user = other
    person.save()
    client.force_login(User.objects.create_user(email="sam@example.org", hr_employee_id=7))
    assert client.get("/staff/")["Location"] == "/accounts/not-on-rota/"
    person.refresh_from_db()
    assert person.user == other


def test_a_user_with_no_employee_id_costs_no_person_lookup(client):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    client.force_login(User.objects.create_user(email="sam@example.org"))
    with CaptureQueriesContext(connection) as queries:
        client.get("/staff/")
    assert sum('"people_person"' in q["sql"] for q in queries) == 1, "only the hasattr check"


def test_a_user_with_a_person_passes_through(client, db):
    p = make_person()
    from tests.factories import make_user_for
    client.force_login(make_user_for(p))
    assert client.get("/staff/").status_code == 200


# --- the log-in log -------------------------------------------------------------

def test_every_sign_in_is_logged_with_the_cloudflare_address(client, settings, db):
    settings.PRACTICE_HR_URL = ""
    User.objects.create_user(email="sam@example.org", password="a-long-Passw0rd!")
    client.post("/accounts/login/", {"username": "sam@example.org", "password": "a-long-Passw0rd!"},
                REMOTE_ADDR="127.0.0.1", HTTP_CF_CONNECTING_IP="203.0.113.10",
                HTTP_USER_AGENT="x" * 300)
    e = LoginEvent.objects.get()
    assert e.user.email == "sam@example.org" and e.ip == "203.0.113.10"
    assert len(e.user_agent) == 200


# --- signing out -----------------------------------------------------------------

def test_logging_out_goes_on_to_hrs_sign_out(client, oidc_on, db):
    client.force_login(User.objects.create_user(email="sam@example.org"))
    session = client.session
    session["oidc_id_token"] = "the.id.token"
    session.save()
    r = client.post("/accounts/logout/")
    url = urlsplit(r["Location"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == "https://hr.example/o/logout/"
    assert parse_qs(url.query) == {"post_logout_redirect_uri": ["http://testserver/accounts/login/"],
                                   "client_id": ["abc"], "id_token_hint": ["the.id.token"]}
    assert "_auth_user_id" not in client.session and r["Clear-Site-Data"] == '"cache"'


def test_without_hr_logout_is_unchanged(client, settings, db):
    settings.PRACTICE_HR_URL = ""
    client.force_login(User.objects.create_user(email="sam@example.org"))
    assert client.post("/accounts/logout/")["Location"] == "/accounts/login/"


# --- sessions ------------------------------------------------------------------------

def test_a_request_at_599_seconds_extends_the_session(client, db, monkeypatch):
    import datetime
    from django.utils import timezone
    from tests.factories import make_user_for
    client.force_login(make_user_for(make_person()))
    start = timezone.now()
    monkeypatch.setattr("django.utils.timezone.now", lambda: start + datetime.timedelta(seconds=599))
    assert client.get("/staff/").status_code == 200
    # 1,198 seconds after sign-in, but 599 after the last request.
    monkeypatch.setattr("django.utils.timezone.now", lambda: start + datetime.timedelta(seconds=1198))
    assert client.get("/staff/").status_code == 200


def test_a_request_after_ten_minutes_is_signed_out(client, db, monkeypatch):
    import datetime
    from django.utils import timezone
    from tests.factories import make_user_for
    client.force_login(make_user_for(make_person()))
    assert client.get("/staff/").status_code == 200
    later = timezone.now() + datetime.timedelta(seconds=601)
    # The db session backend reads expire_date against timezone.now(); the
    # session was stamped at force_login, 601 seconds ago by this clock.
    monkeypatch.setattr("django.utils.timezone.now", lambda: later)
    assert client.get("/staff/").status_code == 302


# --- a callback that comes back twice ------------------------------------------
# On Android the installed app shares Chrome's cookies, and Practice HR's
# redirect to /oidc/callback/ can load in the browser tab and in the app at
# once. The first load spends the state; the second, and any reload of the
# address, must land somewhere useful rather than on a 400.

def _with_states(client, states):
    session = client.session
    session["oidc_states"] = states
    session.save()


def test_a_spent_callback_while_signed_in_goes_on_into_the_app(staff_client, oidc_on):
    _with_states(staff_client, {})
    r = staff_client.get("/oidc/callback/?code=used&state=spent")
    assert r.status_code == 302 and r["Location"] == "/"
    assert "_auth_user_id" in staff_client.session


def test_a_spent_callback_before_the_sign_in_lands_waits_and_tries_again(client, oidc_on):
    """The race: the other load is still fetching the token, so wait a
    moment and go home, which by then is signed in (or asks to sign in)."""
    _with_states(client, {"other": {"nonce": "n", "code_verifier": None}})
    r = client.get("/oidc/callback/?code=used&state=spent")
    body = r.content.decode()
    assert r.status_code == 200
    assert '<meta http-equiv="refresh" content="2;url=/">' in body
    assert 'href="/"' in body


def test_a_callback_with_no_sign_in_started_waits_and_tries_again(client, oidc_on):
    r = client.get("/oidc/callback/?code=used&state=spent")
    assert r.status_code == 200 and 'content="2;url=/"' in r.content.decode()


def test_a_spent_callback_signs_nobody_in(client, oidc_on, monkeypatch):
    import mozilla_django_oidc.views as oidc_views
    called = []
    monkeypatch.setattr(oidc_views.auth, "authenticate", lambda **kw: called.append(kw))
    _with_states(client, {"other": {"nonce": "n", "code_verifier": None}})
    client.get("/oidc/callback/?code=used&state=spent")
    assert called == [] and "_auth_user_id" not in client.session


def test_a_live_callback_still_signs_in(client, oidc_on, monkeypatch, staff_user):
    import mozilla_django_oidc.views as oidc_views
    seen = []

    def authenticate(**kwargs):
        seen.append(kwargs["nonce"])
        staff_user.backend = "accounts.oidc.PracticeAccountBackend"  # as authenticate() sets it
        return staff_user
    monkeypatch.setattr(oidc_views.auth, "authenticate", authenticate)
    _with_states(client, {"live": {"nonce": "n1", "code_verifier": "v"}})
    r = client.get("/oidc/callback/?code=fresh&state=live")
    assert seen == ["n1"] and r.status_code == 302
    assert client.session["_auth_user_id"] == str(staff_user.pk)
    assert "live" not in client.session["oidc_states"]
