# AMG Shift Central: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A deployable Django project that signs people in through Practice HR, feeds people from HR's read API, holds teams, departments, manager access, staff profiles with hours and allowances, and the FindMyShift-style shell — everything managers need to start data set-up in early December.

**Architecture:** A separate Django 5.2 project (`config`, `accounts`, `people`, `ui`), SQLite in WAL mode, every write through `people/services/` with a per-field `AuditEntry`. Sign-in is `mozilla-django-oidc` against Practice HR, binding a user to a `Person` by the `employee_id` claim and taking all-teams managers from the `admin` claim. `hr_sync` polls HR's `/api/v1/people` every fifteen minutes. Pages are Django templates; one Vite-built Preact island (the colour picker) proves the frontend pipeline whose output is committed under `static/dist/`.

**Tech Stack:** Python 3.13, Django 5.2.17, mozilla-django-oidc 4.0.1, django-unfold 0.104.1, whitenoise 6.12.0, gunicorn 26.0.0, pytest 9 + pytest-django 4.12, ruff 0.16.6 (pyflakes only); Node 22, Vite 6, Preact 10, TypeScript 5.

**Spec:** `docs/superpowers/specs/2026-10-29-foundation-design.md` — read it first. The practice manager's requirements are in `docs/requirements/`; the spec cites them by ID (PEOPLE-04, ACC-09 …).

## Global Constraints

- Django 5.2 LTS, Python 3.13, SQLite WAL with `transaction_mode: IMMEDIATE`. Unfold for the Django admin (superuser only).
- **Secrets from the environment only.** No key, token or password in any file in the repository or in any log line. Tests never reach the network.
- **All writes to `people` go through `people/services/`**, never a view, a form's `save()` or the admin directly. Every service call that changes a field writes one `AuditEntry` per field via `people.services.audit.record`.
- **No third-party request from a page**: fonts, scripts and styles are served from this app. Content-Security-Policy on every HTML page (`config/middleware.py`).
- **Frontend source in `frontend/`; its build output `static/dist/` is committed.** CI fails if the committed output is stale. No node on the VPS.
- Every colour from `static/css/tokens.css`. Brand: navy `#143D5C`, amber `#F2A33A`, white `#FFFFFF`, pale grey-blue `#DDE7EE`. Manrope self-hosted as woff2, fallbacks Segoe UI, Arial.
- `TIME_ZONE = "Europe/London"`, `LANGUAGE_CODE = "en-gb"`, `USE_TZ = True`.
- Sessions: `SESSION_COOKIE_AGE = 600`, `SESSION_SAVE_EVERY_REQUEST = True` (ACC-09).
- Code style: match the rota and HR repositories — module docstrings that say why, comments that explain a non-obvious choice, no type-annotation ceremony, tests named as sentences.
- Commit after every task with a message in the form `Area: what changed` (see the other two repositories' logs). Attribution lines as the session's instructions require.
- Run `ruff check .` and `python -m pytest -q` before every commit; both must be clean.

**One deliberate deviation from the spec:** section 7 says a `mail.py` is copied from HR "wired now". Nothing in this release sends mail, so the EMAIL settings are wired (Task 1) and `mail.py` arrives with spec 3's first sender. Dead code is not shipped.

---

## File structure

| Path | Responsibility |
|---|---|
| `config/settings.py` | All settings; environment in, nothing secret in the file |
| `config/urls.py` | Root URL map |
| `config/middleware.py` | Request log, private pages (no-store), Content-Security-Policy |
| `config/apps.py` | Admin site config (Unfold, superuser-only) |
| `config/admin_site.py` | `ShiftCentralAdminSite`: superusers only |
| `accounts/models.py` | `User` (email login, `oidc_sub`, `is_all_teams_manager`), `LoginEvent` |
| `accounts/oidc.py` | `PracticeAccountBackend` — bind by `sub`, then `email`; bind `Person` by `employee_id`; `admin` claim |
| `accounts/views.py` | `LoginForm` (refuses passwords when HR is configured), `LogoutView` (on to HR's sign-out), `not_on_rota` |
| `accounts/signals.py` | `LoginEvent` on `user_logged_in` |
| `accounts/client_ip.py` | Cloudflare's client address (copied from the rota) |
| `accounts/urls.py`, `accounts/admin.py` | Routes; superuser's view of logins |
| `people/models/{team,person,allowance,department,manager,audit,sync}.py` | One model per file, re-exported from `people/models/__init__.py` |
| `people/services/audit.py` | `record(actor, obj, changes, note="")`, `SYNC_ACTOR` |
| `people/services/access.py` | `role`, `managed_teams`, `can_manage`, `can_manage_team`, `is_self`, decorators |
| `people/services/profiles.py` | `update_display`, `update_hours`, `set_allowance`, `set_notes` |
| `people/services/departments.py` | `create`, `update` |
| `people/services/managers.py` | `grant`, `revoke` |
| `people/services/hr_client.py` | `HRClient.people()` — one GET, bearer token, opener injection |
| `people/services/hr_sync.py` | `sync(client=None)` — upsert, never delete, `SyncRun` |
| `people/services/health.py` | The Health card's figures |
| `people/management/commands/hr_sync.py` | The command the timer runs |
| `people/forms.py` | `DisplayForm`, `HoursForm`, `AllowanceForm`, `NotesForm`, `DepartmentForm` |
| `people/views/{staff,profile,departments,permissions,activity}.py` | Pages and dialogs |
| `people/urls.py` | `/staff/…`, `/departments/…`, `/activity/…` |
| `ui/context_processors.py` | `shell(request)`: nav items and role flags for `base.html` |
| `ui/views.py` | `home` (redirect to `/staff/`) |
| `templates/base.html`, `templates/ui/_sidebar.html`, `templates/ui/_dialog.html` | The shell |
| `templates/people/…`, `templates/accounts/…` | Pages and dialogs |
| `static/css/{tokens,fonts,components}.css`, `static/fonts/manrope-latin.woff2`, `static/js/{modal,shell}.js` | Hand-written assets |
| `frontend/` (`package.json`, `vite.config.ts`, `tsconfig.json`, `src/main.ts`, `src/colour-picker.tsx`) | Built island source |
| `static/dist/main.js`, `static/dist/main.css` | Committed build output |
| `deploy/` | `gunicorn.service`, `shift-central-hr-sync.{service,timer}`, `shift-central-clearsessions.{service,timer}`, `shift-central-backup.{service,timer}`, `shift-central-pbs.service`, `shift-central-backup-pbs.conf`, `backup.sh`, `pbs-push.sh`, `manage` |
| `.github/workflows/tests.yml` | ruff, migrations check, pytest, collectstatic + check --deploy, frontend build check, 3.14 job |
| `tests/` | `conftest.py`, `factories.py`, `fixtures/hr_people.json`, one `test_*.py` per task |
| `docs/admin/{README,people,departments,access,sync,setup}.md`, `README.md` | Admin guide and the repo README |

---

### Task 1: Project skeleton, settings, User model, middleware, CI

**Files:**
- Create: `manage.py`, `requirements.txt`, `ruff.toml`, `pytest.ini`, `.gitignore`, `config/__init__.py`, `config/settings.py`, `config/urls.py`, `config/wsgi.py`, `config/apps.py`, `config/admin_site.py`, `config/middleware.py`, `accounts/__init__.py`, `accounts/apps.py`, `accounts/models.py`, `accounts/client_ip.py`, `accounts/admin.py`, `accounts/urls.py`, `ui/__init__.py`, `ui/apps.py`, `ui/views.py`, `people/__init__.py`, `people/apps.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/test_skeleton.py`, `tests/test_csp.py`, `.github/workflows/tests.yml`
- Test: `tests/test_skeleton.py`, `tests/test_csp.py`

**Interfaces:**
- Produces: `accounts.models.User` (`email`, `oidc_sub`, `is_all_teams_manager`, `is_superuser`; `User.objects.create_user(email, password=None, **extra)`, `create_superuser`); `accounts.client_ip.client_ip(request)`; settings names `PRACTICE_HR_URL`, `HR_API_TOKEN`, `OIDC_RP_CLIENT_ID`, `OIDC_RP_CLIENT_SECRET`, `CSP_REPORT_ONLY`, `TRUSTED_PROXY_IPS`; `request.csp_nonce`.

- [ ] **Step 1: Write the failing tests**

`tests/conftest.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

User = get_user_model()


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(email="root@example.org", password="pw")


@pytest.fixture
def root_client(superuser):
    client = Client()
    client.force_login(superuser)
    return client


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(email="sam@example.org")


@pytest.fixture
def staff_client(staff_user):
    client = Client()
    client.force_login(staff_user)
    return client


@pytest.fixture
def all_teams_user(db):
    return User.objects.create_user(email="boss@example.org", is_all_teams_manager=True)


@pytest.fixture
def all_teams_client(all_teams_user):
    client = Client()
    client.force_login(all_teams_user)
    return client


@pytest.fixture
def oidc_on(settings):
    settings.PRACTICE_HR_URL = "https://hr.example"
    settings.OIDC_RP_CLIENT_ID = "abc"
```

`tests/test_skeleton.py`:

```python
"""The project starts, the user model is email-only, and the root redirects."""

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()
pytestmark = pytest.mark.django_db


def test_a_user_is_made_from_an_email_alone():
    u = User.objects.create_user(email="Sam@Example.org")
    assert u.email == "Sam@Example.org" and not u.has_usable_password()
    assert not u.is_all_teams_manager and not u.is_staff and not u.is_superuser


def test_emails_are_unique_ignoring_case():
    from django.db import IntegrityError
    User.objects.create_user(email="sam@example.org")
    with pytest.raises(IntegrityError):
        User.objects.create_user(email="SAM@example.org")


def test_a_superuser_can_use_the_admin_and_nobody_else_can(client, superuser, staff_user):
    client.force_login(superuser)
    assert client.get("/admin/").status_code == 200
    client.force_login(staff_user)
    assert client.get("/admin/").status_code in (302, 403)


def test_the_root_sends_a_signed_out_visitor_to_login(client):
    r = client.get("/", follow=False)
    assert r.status_code == 302 and r["Location"].startswith("/accounts/login/")


def test_sessions_last_ten_minutes_from_the_last_request(settings):
    assert settings.SESSION_COOKIE_AGE == 600 and settings.SESSION_SAVE_EVERY_REQUEST is True


def test_signed_in_pages_are_never_cached(staff_client):
    r = staff_client.get("/", follow=True)
    assert "no-store" in r["Cache-Control"]
```

`tests/test_csp.py`:

```python
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
```

- [ ] **Step 2: Create the project files**

`requirements.txt`:

```
asgiref==3.12.1
cffi==2.1.1
cryptography==50.0.1
Django==5.2.17
django-unfold==0.104.1
gunicorn==26.0.0
iniconfig==2.3.0
mozilla-django-oidc==4.0.1
packaging==26.2
pluggy==1.6.0
pycparser==3.0
Pygments==2.20.0
pytest==9.1.1
pytest-django==4.12.0
sqlparse==0.6.0
whitenoise==6.12.0
```

(`mozilla-django-oidc` pulls `josepy`, `requests` and their dependencies; after `pip install -r requirements.txt` in a fresh venv run `pip freeze` and add the resolved pins so the file is complete, as the rota's is.)

`ruff.toml`:

```toml
# CI runs `ruff check` with exactly this configuration. Only pyflakes:
# undefined names, unused imports and variables — the bug class a test can
# miss in a branch it never runs. Style is not linted.
extend-exclude = ["migrations", ".venv", "staticfiles", "frontend", "static/dist"]

[lint]
select = ["F"]
```

`pytest.ini`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = test_*.py
filterwarnings =
    ignore:No directory at.*:UserWarning
```

`.gitignore`:

```
.venv/
__pycache__/
*.pyc
db.sqlite3
db.sqlite3-*
staticfiles/
backups/
.superpowers/
graphify-out/
.dev_secret_key
frontend/node_modules/
```

`manage.py` — Django's standard file with `DJANGO_SETTINGS_MODULE` set to `config.settings`.

`config/wsgi.py` — Django's standard file.

`config/settings.py`:

```python
"""Every setting, with every secret and host from the environment. The
layout follows the rota and HR projects: DEBUG defaults off; with DEBUG off
a missing SECRET_KEY refuses to start; a dev box gets a checkout-local key."""

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Running under pytest. The suite must not need a SECRET_KEY, a relay or HR.
_TESTING = "pytest" in sys.modules

DEBUG = os.environ.get("DEBUG", "0") == "1"

if not os.environ.get("SECRET_KEY") and not _TESTING and not DEBUG:
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured(
        "SECRET_KEY env var must be set. Generate one with:\n"
        "  python -c \"from django.core.management.utils import "
        "get_random_secret_key as k; print(k())\"")


def _dev_secret_key():
    """A development key private to this checkout: random, written once to a
    git-ignored file beside manage.py, stable across restarts."""
    path = BASE_DIR / ".dev_secret_key"
    try:
        return path.read_text().strip()
    except FileNotFoundError:
        from django.core.management.utils import get_random_secret_key
        key = get_random_secret_key()
        path.touch(mode=0o600)
        path.write_text(key)
        return key


SECRET_KEY = os.environ.get("SECRET_KEY") or (
    "test-only-key-not-used-outside-pytest" if _TESTING else _dev_secret_key())

ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "unfold.apps.BasicAppConfig",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "config.apps.ShiftCentralAdminConfig",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "mozilla_django_oidc",
    "accounts",
    "people",
    "ui",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "config.middleware.RequestLogMiddleware",
    "config.middleware.ContentSecurityPolicyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.middleware.PrivatePagesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "ui.context_processors.shell",
    ]},
}]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    # Production keeps the database out of the code tree (deploy/gunicorn.service).
    "NAME": os.environ.get("DB_PATH") or BASE_DIR / "db.sqlite3",
    "OPTIONS": {
        # WAL lets readers and the single writer proceed together; IMMEDIATE
        # takes the write lock at BEGIN so writers queue instead of failing.
        "init_command": "PRAGMA journal_mode=WAL;",
        "transaction_mode": "IMMEDIATE",
    },
}}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/staff/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Ten minutes from the last request (ACC-09): the rota is used on shared
# reception PCs. SAVE_EVERY_REQUEST makes the ten minutes slide.
SESSION_COOKIE_AGE = 600
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_HTTPONLY = True

UNFOLD = {
    "SITE_TITLE": "Shift Central admin",
    "SITE_HEADER": "AMG Shift Central",
    "SITE_URL": "/staff/",
    "SITE_SYMBOL": "calendar_view_week",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "SIDEBAR": {"show_search": False, "show_all_applications": True},
}

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if (DEBUG or _TESTING)
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "accounts.oidc.PracticeAccountBackend",
]

# Addresses whose CF-Connecting-IP header is believed: loopback, where
# cloudflared connects (accounts/client_ip.py).
TRUSTED_PROXY_IPS = frozenset(
    h.strip() for h in os.environ.get("TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",")
    if h.strip())

# Outgoing mail. Wired now, used from spec 3. EMAIL_HOST set is what
# "email is configured" means.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "webmaster@localhost")

if not DEBUG:
    SECURE_SSL_REDIRECT = not _TESTING
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# The Content-Security-Policy (config/middleware.py) is enforced unless this
# is set, when it is only reported.
CSP_REPORT_ONLY = os.environ.get("CSP_REPORT_ONLY", "0") == "1"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(levelname)s %(name)s: %(message)s"}},
    "handlers": {"stderr": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["stderr"], "level": "WARNING"},
    "loggers": {
        "django": {"level": "WARNING"},
        "django.request": {"level": "ERROR"},
        "django.security": {"level": "INFO"},
        "shiftcentral": {"level": "INFO"},
        "accounts": {"level": "INFO"},
        "people": {"level": "INFO"},
    },
}

# Practice HR: the OpenID Connect provider and the people feed. Every value
# from /etc/shift-central.env; with no PRACTICE_HR_URL the login page shows
# only the superuser's password form, and hr_sync refuses to run.
PRACTICE_HR_URL = os.environ.get("PRACTICE_HR_URL", "").rstrip("/")
HR_API_TOKEN = os.environ.get("HR_API_TOKEN", "").strip()
OIDC_RP_CLIENT_ID = os.environ.get("OIDC_RP_CLIENT_ID", "")
OIDC_RP_CLIENT_SECRET = os.environ.get("OIDC_RP_CLIENT_SECRET", "")
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_RP_SCOPES = "openid email"
OIDC_OP_AUTHORIZATION_ENDPOINT = f"{PRACTICE_HR_URL}/o/authorize/"
OIDC_OP_TOKEN_ENDPOINT = f"{PRACTICE_HR_URL}/o/token/"
OIDC_OP_USER_ENDPOINT = f"{PRACTICE_HR_URL}/o/userinfo/"
OIDC_OP_JWKS_ENDPOINT = f"{PRACTICE_HR_URL}/o/.well-known/jwks.json"
OIDC_USE_PKCE = True
OIDC_CREATE_USER = True
# Kept so signing out can hand it to HR's sign-out as id_token_hint.
OIDC_STORE_ID_TOKEN = True
```

`config/apps.py`:

```python
from django.contrib.admin.apps import AdminConfig


class ShiftCentralAdminConfig(AdminConfig):
    """admin.site becomes our Unfold site with the superuser-only rule."""
    default_site = "config.admin_site.ShiftCentralAdminSite"
```

`config/admin_site.py`:

```python
"""The Django admin is for the superuser's setup and break-glass only
(spec, section 5). Every day-to-day screen is the app's own."""

from unfold.sites import UnfoldAdminSite


class ShiftCentralAdminSite(UnfoldAdminSite):
    def has_permission(self, request):
        return bool(request.user.is_active and request.user.is_superuser)
```

`config/middleware.py` — copy the rota's `config/middleware.py` verbatim (`RequestLogMiddleware`, `PrivatePagesMiddleware`, `ContentSecurityPolicyMiddleware`, `POLICY`, `_practice_hr_origin`) with these edits: the access logger is `shiftcentral.access`; drop the `_RESET_TOKEN` redaction and its use (there are no password links here — log `request.path` as is); `img-src 'self' data:` stays (the colour swatches are data URIs). Keep every docstring; they explain the choices.

`config/urls.py`:

```python
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
```

`ui/apps.py`, `people/apps.py`, `accounts/apps.py` — standard `AppConfig` classes (`name = "ui"` etc.). `people/urls.py` for now:

```python
from django.urls import path

urlpatterns = []
```

`ui/views.py`:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


@login_required
def home(request):
    return redirect("/staff/")
```

`ui/context_processors.py` for now:

```python
def shell(request):
    return {}
```

`accounts/client_ip.py` — copy the rota's file verbatim (its docstring is the reason it exists).

`accounts/models.py`:

```python
"""Login accounts. Nobody has a password here but the superuser: everyone
signs in with the practice account (accounts/oidc.py)."""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


class UserManager(BaseUserManager):
    def _create(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, email):
        return self.get(email__iexact=email)

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self._create(email, password, **extra)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    # HR's `admin` claim for this app, set at every sign-in: the practice
    # manager and the assistant managers (spec, section 2).
    is_all_teams_manager = models.BooleanField(
        "all-teams manager", default=False,
        help_text="Set on Practice HR: Login accounts › Apps › Admin of shift-central. "
                  "Updated at each sign-in.")
    # HR's `sub`, stored at the first sign-in; later sign-ins match on it.
    oidc_sub = models.CharField(
        "practice account id", max_length=255, blank=True, default="", db_index=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta(AbstractUser.Meta):
        verbose_name = "login account"
        verbose_name_plural = "login accounts"
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique",
                                    violation_error_message="A login with this email exists."),
        ]

    def save(self, *args, **kwargs):
        # is_staff keeps Django's meaning, "can open the admin": superusers only.
        self.is_staff = self.is_superuser
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class LoginEvent(models.Model):
    """One row per sign-in (ACC-07). Never deleted in this release."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="login_events")
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    ip = models.CharField(max_length=45, blank=True, default="")
    user_agent = models.CharField(max_length=200, blank=True, default="")

    class Meta:
        ordering = ["-at"]
```

`accounts/admin.py`:

```python
from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import LoginEvent, User


@admin.register(User)
class UserAdmin(ModelAdmin):
    list_display = ("email", "is_all_teams_manager", "is_superuser", "is_active", "oidc_sub")
    search_fields = ("email",)
    fields = ("email", "is_active", "is_superuser", "oidc_sub")
    readonly_fields = ("oidc_sub",)


@admin.register(LoginEvent)
class LoginEventAdmin(ModelAdmin):
    list_display = ("user", "at", "ip")
    readonly_fields = ("user", "at", "ip", "user_agent")
```

`accounts/urls.py` for now (Task 3 fills it):

```python
from django.contrib.auth import views as auth_views
from django.urls import path

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"),
         name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
```

`templates/registration/login.html` for now (Task 6 restyles it, Task 3 adds the practice-account button):

```html
<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Log in</title></head>
<body><h1>Log in</h1>
<form method="post" id="login-form">{% csrf_token %}{{ form.as_p }}<button type="submit">Log in</button></form>
</body></html>
```

- [ ] **Step 3: Make the migrations and run the tests**

Run: `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt ruff==0.16.6`
Run: `DEBUG=1 python manage.py makemigrations accounts`
Run: `python -m pytest -q`
Expected: every test in `test_skeleton.py` and `test_csp.py` PASSES. (`test_the_admin_is_left_alone` needs the CSP middleware to skip `/admin/`; `test_form_action_admits_the_hr_system_when_configured` needs `_practice_hr_origin`.)

- [ ] **Step 4: Add the CI workflow**

`.github/workflows/tests.yml`:

```yaml
# The suite, on every pull request and every push to main. Nothing here
# needs a secret: config/settings.py special-cases pytest, and the suite
# never reaches Practice HR or a mail relay.
name: tests
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
      - run: pip install -r requirements.txt ruff==0.16.6
      - run: ruff check .
      - run: DEBUG=1 python manage.py makemigrations --check --dry-run
      - run: python -m pytest -q
      - run: python manage.py collectstatic --noinput && python manage.py check --deploy
        env:
          DEBUG: "0"
          SECRET_KEY: ci-only-4f8c1e2b9a7d3f6e0c5b8a1d2e4f7a9c3b6d8e0f1a2c4e6b8d0f2a4c6e8b0d1f3a
          ALLOWED_HOSTS: ci
          CSRF_TRUSTED_ORIGINS: https://ci
          EMAIL_HOST: smtp.example
          DEFAULT_FROM_EMAIL: Shift Central <shift-central@example.org>

  tests-next-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.14"
          cache: pip
      - run: pip install -r requirements.txt
      - run: python -m pytest -q
```

(Task 11 adds the `frontend` job.)

- [ ] **Step 5: Lint and commit**

Run: `ruff check . && python -m pytest -q`

```bash
git add -A
git commit -m "Foundation: project skeleton, settings, login accounts, middleware, CI"
```

---

### Task 2: People models and the audit service

**Files:**
- Create: `people/models/__init__.py`, `people/models/team.py`, `people/models/person.py`, `people/models/allowance.py`, `people/models/department.py`, `people/models/manager.py`, `people/models/audit.py`, `people/models/sync.py`, `people/services/__init__.py`, `people/services/audit.py`, `people/admin.py`, `people/migrations/0001_initial.py` (generated), `people/migrations/0002_seed_departments.py`, `tests/factories.py`, `tests/test_models.py`, `tests/test_audit.py`
- Test: `tests/test_models.py`, `tests/test_audit.py`

**Interfaces:**
- Consumes: `accounts.models.User`.
- Produces: models `Team(name, display_order, active)`, `Person(hr_employee_id, first_name, last_name, name, email, team, start_date, end_date, is_gp, last_seen_from_hr, job_title, name_colour, display_order, display_on_rota, show_to_other_staff, can_see_other_staff, weekly_hours, days_per_week, notes, user)` with `Person.average_day` (property) and `Person.current(on)`, `Person.objects.current(on=None)`; `Allowance(person, leave_year, annual_hours, bank_holiday_hours)`; `Department(name, colour, display_order, archived)`; `TeamManager(person, team, granted_by, granted_at)`; `AuditEntry(actor, actor_email, at, kind, model, object_id, field, before, after, note)`; `SyncRun(started_at, finished_at, ok, people_seen, message)`; `people.services.audit.record(actor, obj, changes, note="") -> list[AuditEntry]`, `audit.SYNC_ACTOR_EMAIL = "practice-hr"`; `tests.factories.make_team(name="Reception")`, `make_person(**overrides)`, `make_manager_user(person)`.

- [ ] **Step 1: Write the failing tests**

`tests/factories.py`:

```python
"""Short builders for the suite. Every default is a plausible receptionist."""

from datetime import date

from accounts.models import User
from people.models import Person, Team, TeamManager

_next_id = iter(range(1000, 100000))


def make_team(name="Reception", **kw):
    team, _ = Team.objects.get_or_create(name=name, defaults=kw)
    return team


def make_person(**kw):
    kw.setdefault("hr_employee_id", next(_next_id))
    kw.setdefault("first_name", "Sam")
    kw.setdefault("last_name", "Patel")
    kw.setdefault("name", f"{kw['first_name']} {kw['last_name']}")
    kw.setdefault("email", f"{kw['first_name'].lower()}.{kw['hr_employee_id']}@example.org")
    kw.setdefault("team", make_team())
    kw.setdefault("start_date", date(2024, 1, 8))
    return Person.objects.create(**kw)


def make_user_for(person, **kw):
    user = User.objects.create_user(email=person.email, **kw)
    person.user = user
    person.save(update_fields=["user"])
    return user


def make_team_manager(person, team, granted_by=None):
    return TeamManager.objects.create(person=person, team=team, granted_by=granted_by)
```

`tests/test_models.py`:

```python
from datetime import date
from decimal import Decimal

import pytest
from django.db import IntegrityError

from people.models import Allowance, Department, Person, Team
from tests.factories import make_person, make_team

pytestmark = pytest.mark.django_db


def test_average_day_is_weekly_hours_over_days(db):
    p = make_person(weekly_hours=Decimal("30.00"), days_per_week=5)
    assert p.average_day == Decimal("6")


def test_average_day_is_none_without_hours_or_days(db):
    assert make_person().average_day is None
    assert make_person(weekly_hours=Decimal("30.00")).average_day is None


def test_current_reads_the_employment_dates(db):
    p = make_person(start_date=date(2026, 1, 5), end_date=date(2026, 6, 30))
    assert not p.current(date(2026, 1, 4))
    assert p.current(date(2026, 1, 5)) and p.current(date(2026, 6, 30))
    assert not p.current(date(2026, 7, 1))
    assert make_person(start_date=date(2026, 1, 5)).current(date(2030, 1, 1))


def test_current_queryset_matches_the_method(db):
    here = make_person(start_date=date(2026, 1, 5))
    gone = make_person(start_date=date(2025, 1, 5), end_date=date(2026, 1, 31))
    soon = make_person(start_date=date(2026, 9, 1))
    assert set(Person.objects.current(on=date(2026, 3, 1))) == {here}
    assert gone not in Person.objects.current(on=date(2026, 3, 1))
    assert soon not in Person.objects.current(on=date(2026, 3, 1))


def test_hr_employee_id_is_unique(db):
    make_person(hr_employee_id=7)
    with pytest.raises(IntegrityError):
        make_person(hr_employee_id=7)


def test_one_allowance_per_person_per_leave_year(db):
    p = make_person()
    Allowance.objects.create(person=p, leave_year=date(2027, 1, 1),
                             annual_hours=Decimal("172.50"), bank_holiday_hours=Decimal("60.00"))
    with pytest.raises(IntegrityError):
        Allowance.objects.create(person=p, leave_year=date(2027, 1, 1),
                                 annual_hours=Decimal("1"), bank_holiday_hours=Decimal("1"))


def test_the_seventeen_departments_are_seeded(db):
    names = set(Department.objects.values_list("name", flat=True))
    assert names == {"Reception AG", "Reception PMC", "Cleaning PMC", "Prescriptions",
                     "Private Income", "Workflow", "VAS/Enhanced", "Scanning", "Pharmacy",
                     "Secretarial", "Management", "Salaried GP", "Nursing", "HCA",
                     "Phlebotomist", "Pharmacist", "Pharmacy Technician"}
    assert len({d.colour for d in Department.objects.all()}) == 17, "distinct default colours"


def test_teams_order_by_display_order_then_name(db):
    make_team("Pharmacy", display_order=20)
    make_team("Admin/Secretarial", display_order=10)
    make_team("Nursing", display_order=10)
    assert [t.name for t in Team.objects.all()] == [
        "Admin/Secretarial", "Nursing", "Pharmacy"]
```

`tests/test_audit.py`:

```python
import pytest

from people.models import AuditEntry
from people.services import audit
from tests.factories import make_person

pytestmark = pytest.mark.django_db


def test_record_writes_one_row_per_changed_field(all_teams_user):
    p = make_person()
    rows = audit.record(all_teams_user, p, {"job_title": ("", "Receptionist"),
                                            "weekly_hours": (None, "22.50"),
                                            "display_order": (100, 100)}, note="first fill")
    assert len(rows) == 2
    row = AuditEntry.objects.get(field="job_title")
    assert row.actor == all_teams_user and row.actor_email == "boss@example.org"
    assert row.model == "people.person" and row.object_id == p.pk
    assert (row.before, row.after, row.note) == ("", "Receptionist", "first fill")
    assert row.kind == AuditEntry.Kind.CHANGE


def test_the_sync_writes_as_practice_hr(db):
    p = make_person()
    audit.record(None, p, {"end_date": ("None", "2026-12-31")}, note=audit.SYNC_NOTE)
    row = AuditEntry.objects.get()
    assert row.actor is None and row.actor_email == audit.SYNC_ACTOR_EMAIL
    assert row.note == "from Practice HR"


def test_nothing_changed_writes_nothing(all_teams_user):
    assert audit.record(all_teams_user, make_person(), {"job_title": ("a", "a")}) == []
    assert not AuditEntry.objects.exists()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_models.py tests/test_audit.py -q`
Expected: ImportError on `people.models`.

- [ ] **Step 3: Write the models**

`people/models/team.py`:

```python
from django.db import models


class Team(models.Model):
    """Mirrors Practice HR's teams: created by the sync when a new name
    arrives; the order and active flag are edited here."""
    name = models.CharField(max_length=60, unique=True)
    display_order = models.PositiveIntegerField(default=100)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name
```

`people/models/person.py`:

```python
"""One row per Practice HR employee. The HR-owned fields are overwritten by
every sync and never edited here; the typed fields are the profile's."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .team import Team

HEX_COLOUR = r"^#[0-9a-fA-F]{6}$"


class PersonQuerySet(models.QuerySet):
    def current(self, on=None):
        on = on or timezone.localdate()
        return self.filter(start_date__lte=on).filter(Q(end_date__isnull=True) | Q(end_date__gte=on))


class Person(models.Model):
    # --- from Practice HR -----------------------------------------------
    hr_employee_id = models.PositiveIntegerField(unique=True)
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.PROTECT,
                             related_name="people")
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    # HR's contract unit is "sessions": a GP, whose sessions come from the
    # rota app (spec 2) and who has no weekly hours here.
    is_gp = models.BooleanField(default=False)
    last_seen_from_hr = models.DateTimeField(null=True, blank=True)

    # --- typed here, on the profile ------------------------------------
    job_title = models.CharField(max_length=80, blank=True, default="")
    name_colour = models.CharField(max_length=7, default="#143D5C",
                                   validators=[RegexValidator(HEX_COLOUR)])
    display_order = models.PositiveIntegerField(default=100)
    display_on_rota = models.BooleanField(default=True)
    show_to_other_staff = models.BooleanField(default=True)
    can_see_other_staff = models.BooleanField(default=True)
    weekly_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    days_per_week = models.PositiveSmallIntegerField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="person")

    objects = PersonQuerySet.as_manager()

    class Meta:
        ordering = ["team__display_order", "team__name", "display_order", "last_name", "first_name"]
        verbose_name_plural = "people"

    def __str__(self):
        return self.name

    @property
    def average_day(self):
        """Weekly hours over days per week (PAT-05); None until both are set."""
        if self.weekly_hours is None or not self.days_per_week:
            return None
        return (self.weekly_hours / Decimal(self.days_per_week)).normalize()

    def current(self, on=None):
        on = on or timezone.localdate()
        return self.start_date <= on and (self.end_date is None or self.end_date >= on)

    @property
    def initials(self):
        return (self.first_name[:1] + self.last_name[:1]).upper()
```

`people/models/allowance.py`:

```python
from django.db import models

from .person import Person


class Allowance(models.Model):
    """The two full-year figures a manager types (LEAVE-01), per leave year.
    Stored in this release; spec 3 uses them. `leave_year` is the year's
    first day, so a per-person leave year can follow without a rebuild."""
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="allowances")
    leave_year = models.DateField()
    annual_hours = models.DecimalField(max_digits=6, decimal_places=2)
    bank_holiday_hours = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["person", "leave_year"],
                                               name="one_allowance_per_person_per_year")]
        ordering = ["leave_year"]
```

`people/models/department.py`:

```python
from django.core.validators import RegexValidator
from django.db import models

from .person import HEX_COLOUR


class Department(models.Model):
    """The one combined list of teams, roles and tasks a shift is tagged
    with (ROTA-02). Archived, never deleted: spec 2's shifts reference it."""
    name = models.CharField(max_length=60, unique=True)
    colour = models.CharField(max_length=7, validators=[RegexValidator(HEX_COLOUR)])
    display_order = models.PositiveIntegerField(default=100)
    archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name
```

`people/models/manager.py`:

```python
from django.conf import settings
from django.db import models

from .person import Person
from .team import Team


class TeamManager(models.Model):
    """Manager access for one team (PEOPLE-04): the lead nurse for Nursing,
    the head pharmacist for Pharmacy. All-teams managers are HR's `admin`
    claim, not rows here."""
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="manager_of")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="managers")
    granted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["person", "team"],
                                               name="one_grant_per_person_per_team")]
```

`people/models/audit.py`:

```python
from django.conf import settings
from django.db import models


class AuditEntry(models.Model):
    """One row per field changed by a service, and the activity log's
    source (ACC-08, LEAVE-31). Never edited or deleted."""

    class Kind(models.TextChoices):
        CHANGE = "change"
        VIEWED = "viewed"

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="+")
    actor_email = models.CharField(max_length=254, blank=True, default="")
    at = models.DateTimeField(auto_now_add=True, db_index=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.CHANGE)
    model = models.CharField(max_length=60, db_index=True)
    object_id = models.PositiveBigIntegerField(db_index=True)
    field = models.CharField(max_length=60)
    before = models.TextField(blank=True, default="")
    after = models.TextField(blank=True, default="")
    note = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-at", "-pk"]
        verbose_name_plural = "audit entries"
```

`people/models/sync.py`:

```python
from django.db import models


class SyncRun(models.Model):
    """One row per hr_sync run. `message` is an error's text, never a
    record's values."""
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=False)
    people_seen = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=300, blank=True, default="")

    class Meta:
        ordering = ["-started_at"]
```

`people/models/__init__.py`:

```python
from .allowance import Allowance
from .audit import AuditEntry
from .department import Department
from .manager import TeamManager
from .person import HEX_COLOUR, Person
from .sync import SyncRun
from .team import Team

__all__ = ["Allowance", "AuditEntry", "Department", "HEX_COLOUR", "Person", "SyncRun",
           "Team", "TeamManager"]
```

`people/services/__init__.py` — empty.

`people/services/audit.py`:

```python
"""The one writer of AuditEntry. Every service in people calls record()
after a change. The sync has no user; it writes as SYNC_ACTOR_EMAIL."""

from people.models import AuditEntry

SYNC_ACTOR_EMAIL = "practice-hr"
SYNC_NOTE = "from Practice HR"


def _label(obj):
    return f"{obj._meta.app_label}.{obj._meta.model_name}"


def record(actor, obj, changes, note=""):
    """changes is {field: (before, after)}; unchanged pairs are skipped.
    actor None means the sync."""
    email = getattr(actor, "email", "") if actor is not None else SYNC_ACTOR_EMAIL
    rows = [
        AuditEntry(actor=actor, actor_email=email, kind=AuditEntry.Kind.CHANGE, model=_label(obj),
                   object_id=obj.pk, field=field, before=str(before), after=str(after), note=note)
        for field, (before, after) in changes.items() if before != after
    ]
    return AuditEntry.objects.bulk_create(rows)
```

`people/admin.py`:

```python
from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Allowance, AuditEntry, Department, Person, SyncRun, Team, TeamManager


@admin.register(Team)
class TeamAdmin(ModelAdmin):
    list_display = ("name", "display_order", "active")


@admin.register(Person)
class PersonAdmin(ModelAdmin):
    list_display = ("name", "team", "email", "start_date", "end_date", "is_gp", "last_seen_from_hr")
    search_fields = ("name", "email")
    readonly_fields = ("hr_employee_id", "first_name", "last_name", "name", "email", "team",
                       "start_date", "end_date", "is_gp", "last_seen_from_hr")


@admin.register(Allowance)
class AllowanceAdmin(ModelAdmin):
    list_display = ("person", "leave_year", "annual_hours", "bank_holiday_hours")


@admin.register(Department)
class DepartmentAdmin(ModelAdmin):
    list_display = ("name", "colour", "display_order", "archived")


@admin.register(TeamManager)
class TeamManagerAdmin(ModelAdmin):
    list_display = ("person", "team", "granted_by", "granted_at")


@admin.register(AuditEntry)
class AuditEntryAdmin(ModelAdmin):
    list_display = ("at", "actor_email", "model", "object_id", "field", "before", "after")
    readonly_fields = [f.name for f in AuditEntry._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SyncRun)
class SyncRunAdmin(ModelAdmin):
    list_display = ("started_at", "finished_at", "ok", "people_seen", "message")
```

- [ ] **Step 4: Generate the migration and the seed**

Run: `DEBUG=1 python manage.py makemigrations people`

`people/migrations/0002_seed_departments.py`:

```python
"""ROTA-02's initial list, each with a distinct default colour managers
can change on the Departments page."""

from django.db import migrations

DEPARTMENTS = [
    ("Reception AG", "#2F6FB3"), ("Reception PMC", "#5B8FD6"), ("Cleaning PMC", "#8C7B6B"),
    ("Prescriptions", "#D98E2C"), ("Private Income", "#B6568A"), ("Workflow", "#5E9E5E"),
    ("VAS/Enhanced", "#C94C4C"), ("Scanning", "#8A8A3A"), ("Pharmacy", "#3A8A8A"),
    ("Secretarial", "#7A5EB3"), ("Management", "#143D5C"), ("Salaried GP", "#2A7F62"),
    ("Nursing", "#D96C8A"), ("HCA", "#E0A030"), ("Phlebotomist", "#9A4C8A"),
    ("Pharmacist", "#3A6E8A"), ("Pharmacy Technician", "#6AA2C2"),
]


def seed(apps, schema_editor):
    Department = apps.get_model("people", "Department")
    for order, (name, colour) in enumerate(DEPARTMENTS, start=10):
        Department.objects.get_or_create(name=name, defaults={"colour": colour,
                                                              "display_order": order})


class Migration(migrations.Migration):
    dependencies = [("people", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_models.py tests/test_audit.py -q`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
ruff check . && python -m pytest -q
git add -A
git commit -m "People: teams, people, allowances, departments, manager access, audit"
```

---

### Task 3: Sign-in through Practice HR, log-in log, sessions

**Files:**
- Create: `accounts/oidc.py`, `accounts/views.py`, `accounts/signals.py`, `templates/accounts/not_on_rota.html`, `tests/test_signin.py`
- Modify: `accounts/urls.py`, `accounts/apps.py` (import signals in `ready()`), `templates/registration/login.html`

**Interfaces:**
- Consumes: `User`, `LoginEvent`, `Person` (`people.models`), `client_ip`.
- Produces: `accounts.oidc.PracticeAccountBackend` (binds `sub`, `email`, `employee_id`, `admin`), `accounts.oidc.practice_hr_logout_url(request, id_token=None)`, `accounts.views.PRACTICE_ACCOUNT_ONLY`, URL names `login`, `logout`, `not_on_rota`; a `LoginEvent` per sign-in.

- [ ] **Step 1: Write the failing tests**

`tests/test_signin.py`:

```python
"""Who a sign-in is: HR's sub, bound at first sight; the person, bound by
employee_id; all-teams manager from the admin claim; and the log-in log."""

from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import SuspiciousOperation
from django.test import Client

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
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_signin.py -q`
Expected: ImportError on `accounts.oidc`.

- [ ] **Step 3: Write the backend, views and signal**

`accounts/oidc.py`:

```python
"""Sign in with the practice account: Practice HR is the OpenID Connect
provider.

Who a sign-in is: HR's `sub`, once seen. The first time, the `email` claim
is matched to a user not yet bound to a sub, case-insensitively; every
later sign-in matches on `sub` alone, so an email edited on the HR side
cannot move someone into another account (the rota's rule, kept).

Which person they are: HR's `employee_id` names the Person with that
hr_employee_id (people/models/person.py). It is applied at every sign-in:
the person is bound to this user and taken from any other.

All-teams manager is HR's `admin` claim for this client, set at every
sign-in; only a JSON true counts."""

from urllib.parse import urlencode

from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from .models import User


class PracticeAccountBackend(OIDCAuthenticationBackend):
    def filter_users_by_claims(self, claims):
        sub = str(claims.get("sub") or "")
        email = claims.get("email")
        if sub and User.objects.filter(oidc_sub=sub).exists():
            return User.objects.filter(oidc_sub=sub)
        if email:
            return User.objects.filter(email__iexact=email, oidc_sub="")
        return User.objects.none()

    def create_user(self, claims):
        if User.objects.filter(email__iexact=claims["email"]).exists():
            raise SuspiciousOperation("practice-account sign-in refused: the email belongs "
                                      "to an account this sign-in may not use")
        user = User(email=claims["email"], oidc_sub=str(claims.get("sub") or ""),
                    is_all_teams_manager=_is_admin(claims))
        user.set_unusable_password()
        user.save()
        _bind_person(user, claims)
        return user

    def update_user(self, user, claims):
        changed = []
        sub = str(claims.get("sub") or "")
        if sub and not user.oidc_sub:
            user.oidc_sub = sub
            changed.append("oidc_sub")
        if user.is_all_teams_manager != _is_admin(claims):
            user.is_all_teams_manager = _is_admin(claims)
            changed.append("is_all_teams_manager")
        if changed:
            user.save(update_fields=changed)
        _bind_person(user, claims)
        return user


def _is_admin(claims):
    return claims.get("admin") is True


def _bind_person(user, claims):
    """Person.user follows HR's employee_id. Nothing happens when the claim
    is missing or names nobody here yet; the next hr_sync usually resolves
    that, and the holding page (accounts/views.py) says so meanwhile."""
    from people.models import Person
    employee_id = claims.get("employee_id")
    if not isinstance(employee_id, int):
        return
    try:
        person = Person.objects.get(hr_employee_id=employee_id)
    except Person.DoesNotExist:
        return
    if person.user_id == user.pk:
        return
    Person.objects.filter(user=user).exclude(pk=person.pk).update(user=None)
    person.user = user
    person.save(update_fields=["user"])


def practice_hr_logout_url(request, id_token=None):
    """HR's RP-initiated logout, so signing out here ends the HR session
    too — on a shared PC the next person must not be signed straight in."""
    if not settings.PRACTICE_HR_URL:
        return None
    params = {"post_logout_redirect_uri": request.build_absolute_uri(settings.LOGIN_URL),
              "client_id": settings.OIDC_RP_CLIENT_ID}
    if id_token:
        params["id_token_hint"] = id_token
    return f"{settings.PRACTICE_HR_URL}/o/logout/?{urlencode(params)}"
```

`accounts/views.py`:

```python
"""The login page (the practice account, or the superuser's password form
when HR is not configured), sign-out that goes on to HR, and the holding
page for a sign-in that names no person here."""

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect
from django.shortcuts import render

from .oidc import practice_hr_logout_url

PRACTICE_ACCOUNT_ONLY = "Sign in with the practice account."


class LoginForm(AuthenticationForm):
    """With HR configured every password sign-in is refused here, before
    authenticate() runs, and the refusal reads the same for every address."""

    def clean(self):
        if settings.PRACTICE_HR_URL:
            raise ValidationError(PRACTICE_ACCOUNT_ONLY, code="practice_account")
        return super().clean()


class LogoutView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        id_token = request.session.get("oidc_id_token")
        response = super().post(request, *args, **kwargs)
        onward = practice_hr_logout_url(request, id_token)
        return HttpResponseRedirect(onward) if onward else response


@login_required
def not_on_rota(request):
    """A signed-in account with no Person: HR has not sent them yet, or
    their login is not linked to an employee there."""
    if hasattr(request.user, "person"):
        return HttpResponseRedirect(settings.LOGIN_REDIRECT_URL)
    return render(request, "accounts/not_on_rota.html")
```

`accounts/signals.py`:

```python
from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .client_ip import client_ip
from .models import LoginEvent


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    LoginEvent.objects.create(user=user, ip=client_ip(request) or "",
                              user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:200])
```

`accounts/apps.py`:

```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "accounts"

    def ready(self):
        from . import signals  # noqa: F401
```

`accounts/urls.py`:

```python
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(authentication_form=views.LoginForm),
         name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("not-on-rota/", views.not_on_rota, name="not_on_rota"),
]
```

`templates/registration/login.html` (plain for now; Task 6 restyles it):

```html
{% extends "base.html" %}
{% block title %}Log in{% endblock %}
{% block content %}
<div class="auth-card">
  <h1>Log in</h1>
  {% for error in form.non_field_errors %}<p class="field-error" role="alert">{{ error }}</p>{% endfor %}
  {% if settings_practice_hr_url %}
  <p><a class="btn btn-primary" href="{% url 'oidc_authentication_init' %}">Sign in with the practice account</a></p>
  {% else %}
  <form method="post" id="login-form">{% csrf_token %}{{ form.as_p }}<button type="submit" class="btn btn-primary">Log in</button></form>
  {% endif %}
</div>
{% endblock %}
```

Until Task 6 writes `templates/base.html`, create a minimal one so the login page renders:

```html
{% load static %}<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{% block title %}Shift Central{% endblock %}</title></head>
<body><main>{% block content %}{% endblock %}</main></body></html>
```

and make `ui/context_processors.py` provide `settings_practice_hr_url`:

```python
from django.conf import settings


def shell(request):
    return {"settings_practice_hr_url": settings.PRACTICE_HR_URL}
```

**The holding-page redirect.** Add to `config/middleware.py`:

```python
class PersonRequiredMiddleware:
    """A signed-in account with no Person reaches only the holding page,
    the admin and sign-out (spec, section 2). Superusers pass: setup
    happens before anyone is synced."""

    EXEMPT = ("/accounts/", "/admin/", "/oidc/", "/static/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (user.is_authenticated and not user.is_superuser
                and not request.path.startswith(self.EXEMPT)
                and not hasattr(user, "person")):
            from django.shortcuts import redirect
            return redirect("not_on_rota")
        return self.get_response(request)
```

and list it in `MIDDLEWARE` straight after `PrivatePagesMiddleware`. `hasattr(user, "person")` raises `RelatedObjectDoesNotExist` (an `AttributeError` subclass) when unbound, so `hasattr` is the right test.

`templates/accounts/not_on_rota.html`:

```html
{% extends "base.html" %}
{% block title %}Not yet on the rota{% endblock %}
{% block content %}
<div class="auth-card">
  <h1>You're not yet on the rota</h1>
  <p>You've signed in as <strong>{{ user.email }}</strong>, but Shift Central hasn't received your record from Practice HR yet. Records arrive every fifteen minutes once your employee record is linked to your login there.</p>
  <p>If this carries on, ask the practice manager to check your record in Practice HR.</p>
  <form method="post" action="{% url 'logout' %}">{% csrf_token %}<button class="btn">Log out</button></form>
</div>
{% endblock %}
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_signin.py -q`
Expected: PASS. (`test_the_holding_page_is_the_only_page_such_a_user_reaches` and `test_a_user_with_a_person_passes_through` need `/staff/` to exist; add a placeholder to `people/urls.py` and `people/views/__init__.py` for now:

```python
# people/views/__init__.py
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


@login_required
def staff(request):
    return HttpResponse("staff")
```

```python
# people/urls.py
from django.urls import path

from . import views

urlpatterns = [path("staff/", views.staff, name="staff")]
```

Task 7 replaces both.)

- [ ] **Step 5: Lint and commit**

```bash
ruff check . && python -m pytest -q
git add -A
git commit -m "Accounts: sign in with the practice account, bind the person, log every sign-in"
```

---

### Task 4: Roles and access rules

**Files:**
- Create: `people/services/access.py`, `tests/test_access.py`

**Interfaces:**
- Consumes: `User.is_all_teams_manager`, `TeamManager`, `Person`.
- Produces: `access.role(user) -> "staff" | "team" | "all"`, `access.managed_teams(user) -> QuerySet[Team]`, `access.can_manage_team(user, team) -> bool`, `access.can_manage(user, person) -> bool`, `access.is_self(user, person) -> bool`, `access.is_manager(user) -> bool`, decorators `access.manager_required(view)` and `access.all_teams_required(view)` (403 otherwise), `access.managed_people(user) -> QuerySet[Person]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_access.py`:

```python
"""The one place that answers who may manage whom (spec, section 2)."""

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from people.models import Team
from people.services import access
from tests.factories import make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def world(db):
    nursing, reception = make_team("Nursing"), make_team("Reception")
    nurse = make_person(team=nursing)
    lead = make_person(team=nursing, first_name="Lead")
    receptionist = make_person(team=reception)
    boss = make_person(team=make_team("Management"), first_name="Boss")
    users = {
        "nurse": make_user_for(nurse), "lead": make_user_for(lead),
        "receptionist": make_user_for(receptionist),
        "boss": make_user_for(boss, is_all_teams_manager=True),
    }
    make_team_manager(lead, nursing)
    return {"nursing": nursing, "reception": reception, "nurse": nurse, "lead": lead,
            "receptionist": receptionist, "boss": boss, **users}


def test_roles(world):
    assert access.role(world["nurse"]) == "staff"
    assert access.role(world["lead"]) == "team"
    assert access.role(world["boss"]) == "all"


def test_managed_teams(world):
    assert list(access.managed_teams(world["nurse"])) == []
    assert list(access.managed_teams(world["lead"])) == [world["nursing"]]
    assert set(access.managed_teams(world["boss"])) == set(Team.objects.all())


def test_can_manage_follows_the_persons_team(world):
    assert access.can_manage(world["lead"], world["nurse"])
    assert not access.can_manage(world["lead"], world["receptionist"])
    assert access.can_manage(world["boss"], world["receptionist"])
    assert not access.can_manage(world["nurse"], world["nurse"]), "nobody manages themselves"


def test_a_lead_manages_their_own_team_but_is_self_for_themselves(world):
    assert access.is_self(world["lead"], world["lead"])
    assert not access.can_manage(world["lead"], world["lead"])


def test_managed_people(world):
    assert set(access.managed_people(world["lead"])) == {world["nurse"], world["lead"]}
    assert access.managed_people(world["boss"]).count() == 4
    assert not access.managed_people(world["nurse"]).exists()


def test_a_person_with_no_team_is_managed_by_all_teams_managers_only(world):
    loose = make_person(team=None)
    assert access.can_manage(world["boss"], loose) and not access.can_manage(world["lead"], loose)


def test_the_decorators(world):
    rf = RequestFactory()

    @access.manager_required
    def managers_only(request):
        return HttpResponse("ok")

    @access.all_teams_required
    def all_teams_only(request):
        return HttpResponse("ok")

    for user, m, a in ((world["nurse"], 403, 403), (world["lead"], 200, 403),
                       (world["boss"], 200, 200)):
        req = rf.get("/")
        req.user = user
        assert managers_only(req).status_code == m
        assert all_teams_only(req).status_code == a


def test_a_user_with_no_person_is_staff_and_manages_nobody(staff_user):
    assert access.role(staff_user) == "staff"
    assert not access.managed_people(staff_user).exists()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_access.py -q`
Expected: ImportError on `people.services.access`.

- [ ] **Step 3: Write the service**

`people/services/access.py`:

```python
"""Who may manage whom. Roles are decided at request time, never stored on
the person: all-teams manager is the user's flag from HR's admin claim;
team manager is a TeamManager row for the user's person."""

from functools import wraps

from django.core.exceptions import PermissionDenied

from people.models import Person, Team, TeamManager


def _person(user):
    return getattr(user, "person", None) if user.is_authenticated else None


def is_all_teams(user):
    return bool(user.is_authenticated and user.is_all_teams_manager)


def managed_teams(user):
    if is_all_teams(user):
        return Team.objects.all()
    person = _person(user)
    if person is None:
        return Team.objects.none()
    return Team.objects.filter(managers__person=person).distinct()


def role(user):
    if is_all_teams(user):
        return "all"
    person = _person(user)
    if person is not None and TeamManager.objects.filter(person=person).exists():
        return "team"
    return "staff"


def is_manager(user):
    return role(user) != "staff"


def is_self(user, person):
    me = _person(user)
    return me is not None and me.pk == person.pk


def can_manage_team(user, team):
    if is_all_teams(user):
        return True
    return team is not None and managed_teams(user).filter(pk=team.pk).exists()


def can_manage(user, person):
    """Managing a person: their team is one the user manages, and the
    person is not the user themselves (spec 3 relies on this for leave)."""
    if is_self(user, person):
        return False
    if is_all_teams(user):
        return True
    return person.team_id is not None and can_manage_team(user, person.team)


def managed_people(user):
    """Everyone the user has manager access over, themselves included where
    they manage their own team (the lead nurse sees Nursing's list in full);
    can_manage() is the per-person rule and excludes self."""
    if is_all_teams(user):
        return Person.objects.all()
    teams = managed_teams(user)
    if not teams.exists():
        return Person.objects.none()
    return Person.objects.filter(team__in=teams)


def manager_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_manager(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def all_teams_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not is_all_teams(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_access.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
ruff check . && python -m pytest -q
git add -A
git commit -m "People: roles and the access rules"
```

---

### Task 5: The HR client and `hr_sync`

**Files:**
- Create: `people/services/hr_client.py`, `people/services/hr_sync.py`, `people/management/__init__.py`, `people/management/commands/__init__.py`, `people/management/commands/hr_sync.py`, `tests/fixtures/hr_people.json`, `tests/test_hr_sync.py`

**Interfaces:**
- Consumes: `Person`, `Team`, `SyncRun`, `audit.record`, settings `PRACTICE_HR_URL`, `HR_API_TOKEN`.
- Produces: `HRClient(base_url, token, *, opener=None, timeout=10).people() -> list[dict]`, `HRError`; `hr_sync.sync(client=None) -> SyncRun`; `hr_sync.NEVER_SEEN_AFTER = timedelta(days=1)`; command `manage.py hr_sync`.

- [ ] **Step 1: Write the fixture and the failing tests**

`tests/fixtures/hr_people.json` — the shape HR's `/api/v1/people` sends (`practice-hr/api/views.py`):

```json
{"people": [
  {"id": 1, "first_name": "Sam", "last_name": "Patel", "name": "Sam Patel",
   "email": "sam@example.org", "contract_type": "Reception", "unit": "hours",
   "employment": {"start": "2024-01-08", "end": null},
   "positions": [{"title": "Receptionist", "team": "Reception"}]},
  {"id": 2, "first_name": "Priya", "last_name": "Shah", "name": "Priya Shah",
   "email": "priya@example.org", "contract_type": "Practice nurse", "unit": "hours",
   "employment": {"start": "2021-03-01", "end": null},
   "positions": [{"title": "Lead nurse", "team": "Nursing"}]},
  {"id": 3, "first_name": "Ade", "last_name": "Okoro", "name": "Ade Okoro",
   "email": "ade@example.org", "contract_type": "Salaried GP", "unit": "sessions",
   "employment": {"start": "2022-09-01", "end": null},
   "positions": [{"title": "Salaried GP", "team": "GPs"}]},
  {"id": 4, "first_name": "Jo", "last_name": "Lee", "name": "Jo Lee",
   "email": "jo@example.org", "contract_type": "Administration", "unit": "hours",
   "employment": {"start": "2020-05-11", "end": "2026-10-14"},
   "positions": [{"title": "Secretary", "team": "Admin/Secretarial"}]},
  {"id": 5, "first_name": "Kim", "last_name": "Nguyen", "name": "Kim Nguyen",
   "email": "kim@example.org", "contract_type": null, "unit": null,
   "employment": {"start": "2027-01-04", "end": null},
   "positions": []},
  {"id": 6, "first_name": "Pat", "last_name": "Evans", "name": "Pat Evans",
   "email": "pat@example.org", "contract_type": "Management", "unit": "hours",
   "employment": {"start": "2019-01-07", "end": null},
   "positions": [{"title": "Practice manager", "team": "Management"}]}
]}
```

`tests/test_hr_sync.py`:

```python
"""People come from Practice HR: upsert by employee id, never delete, HR's
fields overwritten, the typed fields untouched, every change audited."""

import io
import json
import urllib.error
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from people.models import AuditEntry, Person, SyncRun, Team
from people.services import hr_sync
from people.services.hr_client import HRClient, HRError

pytestmark = pytest.mark.django_db
FIXTURE = Path(__file__).parent / "fixtures" / "hr_people.json"


class FakeClient:
    def __init__(self, payload=None, error=None):
        self.payload = payload if payload is not None else json.loads(FIXTURE.read_text())
        self.error = error

    def people(self):
        if self.error:
            raise self.error
        return self.payload["people"]


def test_a_feed_of_six_makes_six_people_and_their_teams():
    run = hr_sync.sync(FakeClient())
    assert run.ok and run.people_seen == 6 and run.finished_at
    assert Person.objects.count() == 6
    assert set(Team.objects.values_list("name", flat=True)) == {
        "Reception", "Nursing", "GPs", "Admin/Secretarial", "Management"}
    sam = Person.objects.get(hr_employee_id=1)
    assert (sam.name, sam.email, sam.team.name) == ("Sam Patel", "sam@example.org", "Reception")
    assert sam.start_date == date(2024, 1, 8) and sam.end_date is None and not sam.is_gp
    assert Person.objects.get(hr_employee_id=3).is_gp
    assert Person.objects.get(hr_employee_id=4).end_date == date(2026, 10, 14)
    assert Person.objects.get(hr_employee_id=5).team is None
    assert all(p.last_seen_from_hr for p in Person.objects.all())


def test_a_second_identical_run_changes_nothing_and_audits_nothing():
    hr_sync.sync(FakeClient())
    before = AuditEntry.objects.count()
    hr_sync.sync(FakeClient())
    assert AuditEntry.objects.count() == before


def test_the_first_run_audits_nothing_but_creation():
    hr_sync.sync(FakeClient())
    assert AuditEntry.objects.filter(field="created").count() == 6


def test_changes_from_hr_are_applied_and_audited_as_practice_hr():
    hr_sync.sync(FakeClient())
    payload = json.loads(FIXTURE.read_text())
    sam = payload["people"][0]
    sam["email"] = "sam.patel@example.org"
    sam["employment"]["end"] = "2026-12-31"
    sam["positions"][0]["team"] = "Admin/Secretarial"
    hr_sync.sync(FakeClient(payload))
    p = Person.objects.get(hr_employee_id=1)
    assert p.email == "sam.patel@example.org" and p.end_date == date(2026, 12, 31)
    assert p.team.name == "Admin/Secretarial"
    rows = AuditEntry.objects.filter(object_id=p.pk, model="people.person").exclude(field="created")
    assert {r.field for r in rows} == {"email", "end_date", "team"}
    assert all(r.actor_email == "practice-hr" and r.note == "from Practice HR" for r in rows)


def test_typed_fields_survive_a_sync():
    hr_sync.sync(FakeClient())
    p = Person.objects.get(hr_employee_id=1)
    p.job_title, p.weekly_hours, p.days_per_week, p.name_colour = "Receptionist", Decimal("22.5"), 3, "#AA0000"
    p.save()
    hr_sync.sync(FakeClient())
    p.refresh_from_db()
    assert (p.job_title, p.weekly_hours, p.days_per_week, p.name_colour) == (
        "Receptionist", Decimal("22.50"), 3, "#AA0000")


def test_a_person_missing_from_the_feed_is_kept():
    hr_sync.sync(FakeClient())
    payload = json.loads(FIXTURE.read_text())
    del payload["people"][0]
    first = Person.objects.get(hr_employee_id=1).last_seen_from_hr
    hr_sync.sync(FakeClient(payload))
    p = Person.objects.get(hr_employee_id=1)
    assert p.last_seen_from_hr == first and Person.objects.count() == 6
    assert p in hr_sync.not_seen_recently(now=first + hr_sync.NEVER_SEEN_AFTER * 2)
    assert p not in hr_sync.not_seen_recently(now=first)


def test_an_error_leaves_the_data_untouched_and_records_a_failed_run():
    hr_sync.sync(FakeClient())
    run = hr_sync.sync(FakeClient(error=HRError("Practice HR returned 500 for people")))
    assert not run.ok and run.message == "Practice HR returned 500 for people"
    assert Person.objects.count() == 6 and SyncRun.objects.count() == 2


def test_a_malformed_record_fails_the_run_without_values_in_the_message():
    payload = {"people": [{"id": 1, "first_name": "Sam", "email": "sam@example.org"}]}
    run = hr_sync.sync(FakeClient(payload))
    assert not run.ok and "sam" not in run.message.lower() and "id 1" in run.message
    assert Person.objects.count() == 0


def test_a_team_rename_in_hr_makes_a_new_team_and_moves_the_person():
    hr_sync.sync(FakeClient())
    payload = json.loads(FIXTURE.read_text())
    payload["people"][1]["positions"][0]["team"] = "Nursing team"
    hr_sync.sync(FakeClient(payload))
    assert Person.objects.get(hr_employee_id=2).team.name == "Nursing team"
    assert Team.objects.filter(name="Nursing").exists(), "the old team is kept, not deleted"


# --- the client ------------------------------------------------------------------

def _opener(status=200, body=b'{"people": []}'):
    calls = []

    def open_(req):
        calls.append(req)
        if status != 200:
            raise urllib.error.HTTPError(req.full_url, status, "x", {}, io.BytesIO(b"boom"))
        return io.BytesIO(body)
    open_.calls = calls
    return open_


def test_the_client_gets_people_with_a_bearer_token():
    op = _opener()
    assert HRClient("https://hr.example", "t0k", opener=op).people() == []
    req = op.calls[0]
    assert req.full_url == "https://hr.example/api/v1/people" and req.get_method() == "GET"
    assert req.get_header("Authorization") == "Bearer t0k"


def test_an_http_error_is_an_hrerror_without_the_token_in_it():
    with pytest.raises(HRError) as e:
        HRClient("https://hr.example", "t0k", opener=_opener(500)).people()
    assert "500" in str(e.value) and "t0k" not in str(e.value)


def test_a_non_json_body_is_an_hrerror():
    with pytest.raises(HRError):
        HRClient("https://hr.example", "t0k", opener=_opener(body=b"<html>")).people()


def test_the_token_is_not_sent_over_plain_http(settings):
    settings.DEBUG = False
    op = _opener()
    with pytest.raises(HRError):
        HRClient("http://hr.example", "t0k", opener=op).people()
    assert op.calls == []


def test_the_command_refuses_without_a_token(settings, capsys):
    from django.core.management import CommandError, call_command
    settings.PRACTICE_HR_URL, settings.HR_API_TOKEN = "https://hr.example", ""
    with pytest.raises(CommandError, match="HR_API_TOKEN"):
        call_command("hr_sync")
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_hr_sync.py -q`
Expected: ImportError.

- [ ] **Step 3: Write the client, the sync and the command**

`people/services/hr_client.py`:

```python
"""A read-only client for Practice HR's people feed, on the standard library.

GET {PRACTICE_HR_URL}/api/v1/people with `Authorization: Bearer <token>`
(practice-hr/api/auth.py). The token never travels over plain http
outside DEBUG, never appears in a log line or an error, and the response
is never logged: it is everyone's name and email."""

import json
import logging
import urllib.error
import urllib.request
from urllib.parse import urlparse

from django.conf import settings

log = logging.getLogger("people.hr_sync")


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_RefuseRedirects)


class HRError(Exception):
    pass


class HRClient:
    def __init__(self, base_url, token, *, opener=None, timeout=10):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._open = opener or (lambda req: _OPENER.open(req, timeout=timeout))

    def people(self):
        url = f"{self.base_url}/api/v1/people"
        if urlparse(url).scheme != "https" and not settings.DEBUG:
            raise HRError("PRACTICE_HR_URL is not https; the token was not sent")
        req = urllib.request.Request(url, method="GET", headers={
            "Accept": "application/json", "Authorization": f"Bearer {self._token}"})
        try:
            with self._open(req) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            log.warning("hr people -> %s", e.code)
            raise HRError(f"Practice HR returned {e.code} for people") from None
        except (urllib.error.URLError, OSError) as e:
            log.warning("hr people unreachable: %s", e.__class__.__name__)
            raise HRError("Practice HR unreachable") from None
        try:
            body = json.loads(raw)
        except ValueError:
            raise HRError("Practice HR returned a non-JSON body for people") from None
        people = body.get("people") if isinstance(body, dict) else None
        if not isinstance(people, list):
            raise HRError("Practice HR's people response has no 'people' list")
        return people

    @classmethod
    def from_settings(cls):
        return cls(settings.PRACTICE_HR_URL, settings.HR_API_TOKEN)
```

`people/services/hr_sync.py`:

```python
"""Pull people from Practice HR (spec, section 3). One transaction: upsert
by employee id, overwrite the HR-owned fields, never touch the typed ones,
never delete. A person absent from the feed keeps their last_seen_from_hr,
which the Health card reads."""

import logging
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from people.models import Person, SyncRun, Team
from people.services import audit
from people.services.hr_client import HRClient, HRError

log = logging.getLogger("people.hr_sync")

NEVER_SEEN_AFTER = timedelta(days=1)
HR_FIELDS = ("first_name", "last_name", "name", "email", "team", "start_date", "end_date", "is_gp")


class BadRecord(Exception):
    pass


def _date(value):
    return date.fromisoformat(value) if value else None


def _parse(record):
    """The fields Person takes from one feed record. Names only in the
    error, never values."""
    try:
        employee_id = int(record["id"])
        employment = record["employment"]
        positions = record.get("positions") or []
        team_name = positions[0]["team"] if positions else ""
        return employee_id, {
            "first_name": record["first_name"], "last_name": record["last_name"],
            "name": record["name"], "email": record["email"],
            "start_date": _date(employment["start"]), "end_date": _date(employment.get("end")),
            "is_gp": record.get("unit") == "sessions", "team_name": team_name,
        }
    except (KeyError, TypeError, ValueError, IndexError) as e:
        ident = record.get("id", "?") if isinstance(record, dict) else "?"
        raise BadRecord(f"record id {ident}: missing or bad {e.__class__.__name__}: {e}") from None


def _team(name, cache):
    if not name:
        return None
    if name not in cache:
        cache[name], _ = Team.objects.get_or_create(name=name)
    return cache[name]


def _apply(records, seen_at):
    teams = {}
    for record in records:
        employee_id, fields = _parse(record)
        if fields["start_date"] is None:
            raise BadRecord(f"record id {employee_id}: no employment start")
        team = _team(fields.pop("team_name"), teams)
        fields["team"] = team
        person = Person.objects.filter(hr_employee_id=employee_id).first()
        if person is None:
            person = Person.objects.create(hr_employee_id=employee_id, last_seen_from_hr=seen_at,
                                           **fields)
            audit.record(None, person, {"created": ("", f"employee {employee_id}")},
                         note=audit.SYNC_NOTE)
            continue
        changes = {}
        for field in HR_FIELDS:
            before, after = getattr(person, field), fields[field]
            if before != after:
                changes[field] = (before, after)
                setattr(person, field, after)
        person.last_seen_from_hr = seen_at
        person.save()
        if changes:
            audit.record(None, person, {k: (str(b), str(a)) for k, (b, a) in changes.items()},
                         note=audit.SYNC_NOTE)


def sync(client=None):
    """Run one sync and return its SyncRun. Never raises: a failure is the
    run's message, and the previous data stands."""
    client = client or HRClient.from_settings()
    run = SyncRun.objects.create()
    try:
        records = client.people()
        with transaction.atomic():
            _apply(records, timezone.now())
        run.ok, run.people_seen = True, len(records)
    except (HRError, BadRecord) as e:
        run.message = str(e)[:300]
        log.warning("hr_sync failed: %s", run.message)
    run.finished_at = timezone.now()
    run.save()
    return run


def not_seen_recently(now=None):
    """People the last day's syncs did not include — gone from HR's feed."""
    now = now or timezone.now()
    return Person.objects.filter(last_seen_from_hr__lt=now - NEVER_SEEN_AFTER)


def last_run():
    return SyncRun.objects.first()
```

`people/management/commands/hr_sync.py`:

```python
"""Read people from Practice HR. Run by shift-central-hr-sync.timer every
fifteen minutes, and by the Staff page's Sync now button."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from people.services import hr_sync


class Command(BaseCommand):
    help = "Read people from Practice HR into Shift Central"

    def handle(self, *args, **options):
        if not settings.PRACTICE_HR_URL:
            raise CommandError("PRACTICE_HR_URL is not set; nothing to read from")
        if not settings.HR_API_TOKEN:
            raise CommandError("HR_API_TOKEN is not set; Practice HR would refuse the request")
        run = hr_sync.sync()
        if not run.ok:
            raise CommandError(f"hr_sync failed: {run.message}")
        self.stdout.write(f"{run.people_seen} people read from Practice HR")
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_hr_sync.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
ruff check . && python -m pytest -q
git add -A
git commit -m "People: read people from Practice HR every fifteen minutes"
```

---

### Task 6: The shell — tokens, fonts, base template, side panel, top bar, dialogs

**Files:**
- Create: `static/css/tokens.css`, `static/css/fonts.css`, `static/css/components.css`, `static/fonts/manrope-latin.woff2`, `static/fonts/OFL.txt`, `static/js/shell.js`, `static/js/modal.js`, `static/img/icons.svg`, `static/img/logo-dark.svg`, `static/img/icon.svg`, `static/img/favicon-32.png`, `static/img/apple-touch-icon.png`, `templates/base.html`, `templates/ui/_sidebar.html`, `templates/ui/_dialog.html`, `templates/403.html`, `templates/404.html`, `templates/500.html`, `tests/test_shell.py`
- Modify: `ui/context_processors.py`, `templates/registration/login.html`, `templates/accounts/not_on_rota.html`

**Interfaces:**
- Consumes: `access.role`, `access.is_manager`, `access.is_all_teams`.
- Produces: `base.html` blocks `title`, `page_title`, `topbar_actions`, `content`; context `nav_items` (list of `{"key","label","icon","url","active","children":[{"label","url"}]}`), `role`, `is_manager`, `is_all_teams`, `settings_practice_hr_url`; the `#dialog` element every pop-up renders into via `hx-get`-free fetch (`static/js/modal.js`: an `<a data-dialog href>` or `<button data-dialog data-url>` fetches the URL and puts the HTML in `#dialog`; a `<form data-dialog-form>` inside posts by fetch and replaces the dialog body with the response, or follows a JSON `{"redirect": url}`); CSS classes `.btn`, `.btn-primary` (amber), `.btn-dark`, `.table`, `.chip`, `.field`, `.dialog`, `.dialog-head`, `.tabs`, `.tab`, `.auth-card`, `.health`, `.flash`.

- [ ] **Step 1: Write the failing tests**

`tests/test_shell.py`:

```python
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
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_shell.py -q`
Expected: FAIL (no `data-nav`, placeholder staff page).

- [ ] **Step 3: The assets**

Copy the brand files: `docs/brand/amg-shift-central-logo-dark.svg` → `static/img/logo-dark.svg`; `docs/brand/amg-shift-central-icon.svg` → `static/img/icon.svg`; `docs/brand/amg-shift-central-icon-32.png` → `static/img/favicon-32.png`; `docs/brand/amg-shift-central-icon-180.png` → `static/img/apple-touch-icon.png`.

Manrope: download the variable latin woff2 that Google Fonts serves for `Manrope:wght@200..800` (fetch `https://fonts.googleapis.com/css2?family=Manrope:wght@200..800&display=swap` with a modern browser user agent, take the `latin` `src` URL, download it to `static/fonts/manrope-latin.woff2`) and `OFL.txt` from the Manrope repository. The font is OFL 1.1; the licence file ships beside it.

`static/css/fonts.css`:

```css
/* Manrope, self-hosted: no request to a font host from a practice app.
   One variable file covers every weight. Licence: SIL OFL 1.1, OFL.txt. */
@font-face {
  font-family: "Manrope";
  font-style: normal;
  font-weight: 200 800;
  font-display: swap;
  src: url("../fonts/manrope-latin.woff2") format("woff2");
  unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
}
```

`static/css/tokens.css`:

```css
/* Design tokens. Every colour in components.css comes from here. The brand
   (docs/requirements/README.md): navy, amber, white, pale grey-blue. The
   rest are the greys FindMyShift's white pages use, chosen to pass AA on
   white, and the swatches managers pick tile and name colours from. */
:root {
  --navy:        #143D5C;
  --navy-deep:   #0E2C43;   /* flyouts and the active item */
  --navy-soft:   #1F527A;   /* hover on the panel */
  --amber:       #F2A33A;
  --amber-ink:   #1B1F27;
  --pale:        #DDE7EE;   /* secondary text on navy */
  --white:       #FFFFFF;

  --ink:         #1B1F27;
  --ink-soft:    #454C5A;
  --muted:       #6B7280;   /* 4.8:1 on white */
  --ground:      #F5F7F9;   /* the page behind white tables */
  --surface:     #FFFFFF;
  --hairline:    #E3E7EC;
  --field-border:#8A91A0;   /* 3.1:1, WCAG 1.4.11 */
  --today:       #FFF7E6;   /* today's column, spec 2 */

  --danger:      #A03A24;  --danger-soft: #FDEAE6;
  --warning:     #855B1B;  --warning-soft: #FCF2E2;
  --ok:          #23604A;  --ok-soft: #E4F2EC;

  --shadow: rgb(20 61 92 / 18%);

  --font: "Manrope", "Segoe UI", Arial, sans-serif;
  --fs-xs: 11.5px; --fs-sm: 12.5px; --fs-md: 13.5px; --fs-lg: 15px; --fs-xl: 20px;
  --sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px; --sp-5: 24px; --sp-6: 32px;
  --radius: 4px;
  --sidebar-w: 220px;
  --sidebar-w-collapsed: 56px;
  --topbar-h: 48px;
}

/* The swatches offered for a person's name and a department (frontend/src/
   colour-picker.tsx reads the same list from its data attribute). */
:root {
  --swatches: #C94C4C,#D96C8A,#B6568A,#9A4C8A,#7A5EB3,#2F6FB3,#5B8FD6,#3A6E8A,#3A8A8A,#6AA2C2,#2A7F62,#5E9E5E,#8A8A3A,#E0A030,#D98E2C,#8C7B6B,#143D5C,#6B7280;
}
```

`static/css/components.css` — the shell and the shared widgets. Write it in full; the structure below is what the templates and tests rely on (class names are the contract; the values follow FindMyShift's density: 13.5 px type, 32 px table rows, 1 px hairlines):

```css
*, *::before, *::after { box-sizing: border-box; }
html { font: var(--fs-md)/1.4 var(--font); color: var(--ink); background: var(--ground); }
body { margin: 0; min-height: 100vh; }
a { color: var(--navy); }

/* --- layout: panel left, bar top, page below ---------------------------- */
.app { display: grid; grid-template-columns: var(--sidebar-w) 1fr; min-height: 100vh; }
.app.is-collapsed { grid-template-columns: var(--sidebar-w-collapsed) 1fr; }
.sidebar { background: var(--navy); color: var(--white); display: flex; flex-direction: column; position: sticky; top: 0; height: 100vh; }
.sidebar-logo { padding: var(--sp-3) var(--sp-4); }
.sidebar-logo img { width: 100%; max-width: 180px; display: block; }
.is-collapsed .sidebar-logo img { content: url("../img/icon.svg"); max-width: 32px; }
.sidebar-nav { flex: 1; display: flex; flex-direction: column; padding: var(--sp-2) 0; }
.nav-item { position: relative; }
.nav-link { display: flex; align-items: center; gap: var(--sp-3); padding: 10px var(--sp-4); color: var(--pale); text-decoration: none; font-size: var(--fs-md); }
.nav-link:hover, .nav-item.is-active > .nav-link { background: var(--navy-soft); color: var(--white); }
.nav-item.is-active > .nav-link { background: var(--navy-deep); }
.nav-icon { width: 18px; height: 18px; flex: none; }
.is-collapsed .nav-label { display: none; }
.nav-count { margin-left: auto; background: var(--amber); color: var(--amber-ink); border-radius: 10px; padding: 0 7px; font-size: var(--fs-xs); font-weight: 700; }
.nav-flyout { display: none; position: absolute; left: 100%; top: 0; min-width: 180px; background: var(--navy-deep); box-shadow: 2px 2px 8px var(--shadow); z-index: 20; padding: var(--sp-1) 0; }
.nav-item:hover > .nav-flyout, .nav-item:focus-within > .nav-flyout { display: block; }
.nav-flyout a { display: block; padding: 8px var(--sp-4); color: var(--pale); text-decoration: none; white-space: nowrap; }
.nav-flyout a:hover { background: var(--navy-soft); color: var(--white); }
.sidebar-foot { padding: var(--sp-2) 0; border-top: 1px solid var(--navy-soft); }
.sidebar-foot form { margin: 0; }
.sidebar-foot button { all: unset; cursor: pointer; display: flex; gap: var(--sp-3); align-items: center; width: 100%; padding: 10px var(--sp-4); color: var(--pale); }
.sidebar-foot button:hover { background: var(--navy-soft); color: var(--white); }

.topbar { height: var(--topbar-h); background: var(--surface); border-bottom: 1px solid var(--hairline); display: flex; align-items: center; gap: var(--sp-4); padding: 0 var(--sp-4); position: sticky; top: 0; z-index: 10; }
.topbar-title { font-size: var(--fs-lg); font-weight: 700; margin: 0 var(--sp-4) 0 0; }
.topbar-actions { display: flex; gap: var(--sp-4); align-items: center; flex: 1; }
.topbar-action { color: var(--navy); text-decoration: none; font-size: var(--fs-sm); display: inline-flex; gap: 6px; align-items: center; background: none; border: 0; cursor: pointer; font-family: inherit; }
.topbar-action.is-primary { color: var(--amber-ink); background: var(--amber); padding: 5px 10px; border-radius: var(--radius); font-weight: 700; }
.topbar-end { margin-left: auto; display: flex; gap: var(--sp-3); align-items: center; color: var(--muted); font-size: var(--fs-sm); }
.collapse-toggle { all: unset; cursor: pointer; padding: 4px; color: var(--muted); }
.page { padding: var(--sp-4); }

/* --- tables, buttons, fields, chips ----------------------------------- */
.table { width: 100%; border-collapse: collapse; background: var(--surface); font-size: var(--fs-md); }
.table th, .table td { text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--hairline); height: 32px; vertical-align: middle; }
.table th { font-weight: 700; color: var(--ink-soft); background: var(--ground); position: sticky; top: var(--topbar-h); }
.table tr:hover td { background: var(--ground); }
.chip { display: inline-block; padding: 2px 8px; border-radius: 3px; color: var(--white); font-weight: 700; font-size: var(--fs-sm); }
.btn { font: inherit; border: 1px solid var(--field-border); background: var(--surface); color: var(--ink); padding: 6px 12px; border-radius: var(--radius); cursor: pointer; text-decoration: none; display: inline-block; }
.btn-primary { background: var(--amber); border-color: var(--amber); color: var(--amber-ink); font-weight: 700; }
.btn-dark { background: var(--navy); border-color: var(--navy); color: var(--white); font-weight: 700; width: 100%; padding: 10px; }
.btn-quiet { border-color: transparent; color: var(--navy); }
.field { position: relative; margin: 0 0 var(--sp-4); }
.field label { display: block; font-size: var(--fs-xs); color: var(--muted); margin-bottom: 2px; }
.field input, .field select, .field textarea { width: 100%; font: inherit; padding: 8px 10px; border: 1px solid var(--field-border); border-radius: var(--radius); background: var(--surface); }
.field input[type="checkbox"] { width: auto; }
.field-help { font-size: var(--fs-xs); color: var(--muted); }
.field-error { color: var(--danger); font-size: var(--fs-sm); margin: 2px 0 0; }
.field.has-error input { border-color: var(--danger); }
.flash { padding: var(--sp-2) var(--sp-3); border-radius: var(--radius); margin-bottom: var(--sp-3); background: var(--ok-soft); color: var(--ok); }
.flash-error { background: var(--danger-soft); color: var(--danger); }
.flash-warning { background: var(--warning-soft); color: var(--warning); }
.filters { display: flex; gap: var(--sp-3); align-items: center; margin-bottom: var(--sp-3); font-size: var(--fs-sm); }

/* --- dialogs (FindMyShift's pop-ups) ---------------------------------- */
#dialog:empty { display: none; }
#dialog { position: fixed; inset: 0; background: rgb(0 0 0 / 35%); display: flex; align-items: flex-start; justify-content: center; padding-top: 6vh; z-index: 50; }
.dialog { background: var(--surface); width: min(560px, 94vw); border-radius: 6px; box-shadow: 0 8px 30px var(--shadow); max-height: 88vh; overflow: auto; }
.dialog-head { background: var(--navy); color: var(--white); padding: 10px var(--sp-4); display: flex; align-items: center; gap: var(--sp-3); font-weight: 700; }
.dialog-head .close { margin-left: auto; all: unset; cursor: pointer; color: var(--pale); font-size: 18px; line-height: 1; }
.dialog-body { padding: var(--sp-4); }
.dialog-links { display: flex; gap: var(--sp-4); padding: 0 var(--sp-4) var(--sp-4); font-size: var(--fs-sm); }
.tabs { display: flex; border-bottom: 1px solid var(--hairline); margin-bottom: var(--sp-4); }
.tab { padding: 8px 12px; color: var(--muted); text-decoration: none; border-bottom: 2px solid transparent; }
.tab.is-active { color: var(--navy); border-bottom-color: var(--amber); font-weight: 700; }
.avatar { width: 48px; height: 48px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; color: var(--white); font-weight: 800; font-size: var(--fs-lg); }

/* --- health card ---------------------------------------------------------- */
.health { background: var(--surface); border: 1px solid var(--hairline); border-radius: 6px; padding: var(--sp-3) var(--sp-4); margin-bottom: var(--sp-4); display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: var(--sp-3); font-size: var(--fs-sm); }
.health h2 { grid-column: 1 / -1; margin: 0; font-size: var(--fs-md); }
.health-item strong { display: block; font-size: var(--fs-lg); }
.health-item.is-warning strong { color: var(--warning); }
.health-item.is-bad strong { color: var(--danger); }

/* --- signed-out pages ------------------------------------------------------ */
.auth-wrap { min-height: 100vh; display: grid; place-items: center; background: var(--navy); }
.auth-card { background: var(--surface); padding: var(--sp-6); border-radius: 8px; width: min(420px, 92vw); }
.auth-card img { width: 220px; display: block; margin: 0 auto var(--sp-5); }

/* --- phone ------------------------------------------------------------------- */
@media (max-width: 767px) {
  .app, .app.is-collapsed { grid-template-columns: 1fr; }
  .sidebar { position: fixed; bottom: 0; top: auto; height: 56px; width: 100%; flex-direction: row; z-index: 30; }
  .sidebar-logo, .sidebar-foot, .nav-flyout, .collapse-toggle { display: none; }
  .sidebar-nav { flex-direction: row; justify-content: space-around; padding: 0; }
  .nav-link { flex-direction: column; gap: 2px; font-size: var(--fs-xs); padding: 6px; }
  .page { padding-bottom: 72px; }
  .topbar { flex-wrap: wrap; height: auto; padding: var(--sp-2) var(--sp-3); }
}
```

`static/js/shell.js`:

```js
/* The side panel's collapse state, per browser; and the Log out form on
 * the panel's last item. No inline handlers: the CSP forbids them. */
(function () {
  var app = document.querySelector(".app");
  var toggle = document.getElementById("collapse-toggle");
  if (!app || !toggle) { return; }
  var KEY = "shift-central.sidebar";
  try { if (localStorage.getItem(KEY) === "collapsed") { app.classList.add("is-collapsed"); } } catch (e) {}
  toggle.addEventListener("click", function () {
    app.classList.toggle("is-collapsed");
    try { localStorage.setItem(KEY, app.classList.contains("is-collapsed") ? "collapsed" : "open"); } catch (e) {}
  });
})();
```

`static/js/modal.js`:

```js
/* Pop-ups (FindMyShift's profile, time-off and department windows) are
 * HTML the server renders, fetched into #dialog.
 *
 *  - <a data-dialog href="…"> or <button data-dialog data-url="…"> fetches
 *    the URL (GET, same origin, X-Requested-With) and puts the body in
 *    #dialog, focusing the first field.
 *  - <form data-dialog-form> inside posts by fetch. A 200 replaces the
 *    dialog with the response (a form shown again with its errors); a JSON
 *    {"redirect": url} follows it; anything else shows a flash.
 *  - [data-dialog-close], Escape and a click on the backdrop close it.
 *  - Tab stays inside while it is open; focus returns to the opener after.
 */
(function () {
  var dialog = document.getElementById("dialog");
  if (!dialog) { return; }
  var FOCUSABLE = 'a[href], button:not([disabled]), select:not([disabled]), textarea:not([disabled]), input:not([type="hidden"]):not([disabled]), [tabindex]:not([tabindex="-1"])';
  var opener = null;
  var csrf = document.querySelector('meta[name="csrf-token"]').content;

  function open() { return dialog.childElementCount > 0; }
  function close() { dialog.innerHTML = ""; if (opener && opener.isConnected) { opener.focus({ preventScroll: true }); } opener = null; }
  function focusFirst() {
    var first = dialog.querySelector("[autofocus]") || dialog.querySelector(FOCUSABLE);
    if (first) { first.focus(); }
  }
  function show(html) { dialog.innerHTML = html; focusFirst(); }

  function load(url, from) {
    opener = from;
    fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
      .then(function (r) { return r.text(); }).then(show);
  }

  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("[data-dialog]");
    if (t) { e.preventDefault(); load(t.getAttribute("href") || t.dataset.url, t); return; }
    if (e.target.closest && e.target.closest("[data-dialog-close]")) { e.preventDefault(); close(); return; }
    if (e.target === dialog) { close(); }
  });

  document.addEventListener("submit", function (e) {
    var form = e.target.closest && e.target.closest("form[data-dialog-form]");
    if (!form) { return; }
    e.preventDefault();
    var data = new FormData(form);
    if (e.submitter && e.submitter.name) { data.append(e.submitter.name, e.submitter.value); }
    fetch(form.action, { method: "POST", body: data, credentials: "same-origin",
                         headers: { "X-CSRFToken": csrf, "X-Requested-With": "fetch" } })
      .then(function (r) {
        var type = r.headers.get("Content-Type") || "";
        if (type.indexOf("application/json") === 0) {
          return r.json().then(function (j) { if (j.redirect) { window.location.assign(j.redirect); } });
        }
        return r.text().then(show);
      });
  });

  document.addEventListener("keydown", function (e) {
    if (!open()) { return; }
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key !== "Tab") { return; }
    var items = [].filter.call(dialog.querySelectorAll(FOCUSABLE), function (el) { return el.offsetParent !== null; });
    if (!items.length) { return; }
    var first = items[0], last = items[items.length - 1];
    if (!dialog.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  // Tabs inside a dialog (the profile's General / Display / …) load their
  // panel the same way, keeping the dialog open.
  document.addEventListener("click", function (e) {
    var tab = e.target.closest && e.target.closest("#dialog a.tab");
    if (tab) { e.preventDefault(); fetch(tab.href, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" }).then(function (r) { return r.text(); }).then(show); }
  });
})();
```

- [ ] **Step 4: The templates and the context processor**

`ui/context_processors.py`:

```python
"""What base.html needs: the role flags and this release's nav items. An
item appears only when its spec has built it; later specs append here."""

from django.conf import settings

from people.services import access


def _items(request, role):
    path = request.path
    items = [{"key": "staff", "label": "Staff", "icon": "people", "url": "/staff/",
              "active": path.startswith("/staff/"), "children": []}]
    if role != "staff":
        items.append({"key": "departments", "label": "Departments", "icon": "tag",
                      "url": "/departments/", "active": path.startswith("/departments/"),
                      "children": []})
        children = [{"label": "Activity log", "url": "/activity/"}]
        if role == "all":
            children.append({"label": "Log in logs", "url": "/activity/logins/"})
        items.append({"key": "activity", "label": "Activity logs", "icon": "history",
                      "url": "/activity/", "active": path.startswith("/activity/"),
                      "children": children})
    return items


def shell(request):
    user = getattr(request, "user", None)
    role = access.role(user) if user is not None and user.is_authenticated else "staff"
    return {
        "settings_practice_hr_url": settings.PRACTICE_HR_URL,
        "role": role,
        "is_manager": role != "staff",
        "is_all_teams": role == "all",
        "nav_items": _items(request, role) if user is not None and user.is_authenticated else [],
    }
```

`templates/base.html` — the topbar is inlined here rather than included, because Django blocks (`page_title`, `topbar_actions`) do not cross an `{% include %}`:

```html
{% load static %}<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="csrf-token" content="{{ csrf_token }}">
<title>{% block title %}AMG Shift Central{% endblock %}</title>
<link rel="icon" href="{% static 'img/favicon-32.png' %}" sizes="32x32" type="image/png">
<link rel="apple-touch-icon" href="{% static 'img/apple-touch-icon.png' %}">
<meta name="theme-color" content="#143D5C">
<link rel="preload" href="{% static 'fonts/manrope-latin.woff2' %}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{% static 'css/fonts.css' %}">
<link rel="stylesheet" href="{% static 'css/tokens.css' %}">
<link rel="stylesheet" href="{% static 'css/components.css' %}">
<link rel="stylesheet" href="{% static 'dist/main.css' %}">
<script src="{% static 'js/shell.js' %}" defer></script>
<script src="{% static 'js/modal.js' %}" defer></script>
<script src="{% static 'dist/main.js' %}" defer></script>
</head>
<body>
{% if user.is_authenticated %}
<div class="app" id="app">
  {% include "ui/_sidebar.html" %}
  <div class="app-main">
    <header class="topbar">
      <h1 class="topbar-title">{% block page_title %}{{ page_title|default:"" }}{% endblock %}</h1>
      <div class="topbar-actions">{% block topbar_actions %}{% endblock %}</div>
      <div class="topbar-end">
        <span>{{ user.person.name|default:user.email }}</span>
        <button type="button" class="collapse-toggle" id="collapse-toggle" aria-label="Collapse the side panel">⟨</button>
      </div>
    </header>
    <main class="page">
      {% if messages %}{% for m in messages %}<div class="flash flash-{{ m.level_tag }}">{{ m }}</div>{% endfor %}{% endif %}
      {% block content %}{% endblock %}
    </main>
  </div>
</div>
<div id="dialog" role="dialog" aria-modal="true"></div>
{% else %}
<div class="auth-wrap">{% block auth %}{% endblock %}</div>
{% endif %}
</body>
</html>
```

Signed-out pages (login, the holding page) fill `block auth`; signed-in pages fill `content`. The holding page is reached signed in, so it fills `content` with the card and the `.auth-card` styling applies inside the shell.

`templates/ui/_sidebar.html`:

```html
{% load static %}
<aside class="sidebar">
  <div class="sidebar-logo"><a href="/staff/"><img src="{% static 'img/logo-dark.svg' %}" alt="AMG Shift Central"></a></div>
  <nav class="sidebar-nav" aria-label="Sections">
    {% for item in nav_items %}
    <div class="nav-item{% if item.active %} is-active{% endif %}" data-nav="{{ item.key }}">
      <a class="nav-link" href="{{ item.url }}">
        <svg class="nav-icon" aria-hidden="true"><use href="{% static 'img/icons.svg' %}#{{ item.icon }}"></use></svg>
        <span class="nav-label">{{ item.label }}</span>
      </a>
      {% if item.children %}
      <div class="nav-flyout">{% for child in item.children %}<a href="{{ child.url }}">{{ child.label }}</a>{% endfor %}</div>
      {% endif %}
    </div>
    {% endfor %}
  </nav>
  <div class="sidebar-foot">
    <form method="post" action="{% url 'logout' %}">{% csrf_token %}
      <button type="submit"><svg class="nav-icon" aria-hidden="true"><use href="{% static 'img/icons.svg' %}#logout"></use></svg><span class="nav-label">Log out</span></button>
    </form>
  </div>
</aside>
```

`static/img/icons.svg` — an SVG sprite with `<symbol id="people">`, `tag`, `history`, `logout`, `chevron` (simple 18×18 line icons; draw them with `stroke="currentColor"`, `fill="none"`). Later specs add symbols.

`templates/ui/_dialog.html` — the frame every pop-up extends:

```html
<div class="dialog">
  <div class="dialog-head">
    <span>{% block dialog_title %}{% endblock %}</span>
    <button type="button" class="close" data-dialog-close aria-label="Close">×</button>
  </div>
  <div class="dialog-body">{% block dialog_body %}{% endblock %}</div>
  {% block dialog_links %}{% endblock %}
</div>
```

`templates/registration/login.html`:

```html
{% extends "base.html" %}{% load static %}
{% block title %}Log in · AMG Shift Central{% endblock %}
{% block auth %}
<div class="auth-card">
  <img src="{% static 'img/logo-dark.svg' %}" alt="AMG Shift Central" style="background:#143D5C;border-radius:6px;padding:12px">
  <h1>Log in</h1>
  {% for error in form.non_field_errors %}<p class="field-error" role="alert">{{ error }}</p>{% endfor %}
  {% if settings_practice_hr_url %}
  <p><a class="btn btn-primary" href="{% url 'oidc_authentication_init' %}">Sign in with the practice account</a></p>
  {% else %}
  <form method="post" id="login-form">{% csrf_token %}
    <div class="field"><label for="id_username">Email</label>{{ form.username }}</div>
    <div class="field"><label for="id_password">Password</label>{{ form.password }}</div>
    <button type="submit" class="btn btn-primary">Log in</button>
  </form>
  {% endif %}
</div>
{% endblock %}
```

Rewrite `templates/accounts/not_on_rota.html` to extend `base.html`, filling `block content` with the same `.auth-card` (the person is signed in, so the shell shows; its nav holds only Staff, which redirects back here). Add `templates/403.html`, `404.html`, `500.html` extending `base.html` with a one-line message in `block content` (500 must not use `{% url %}` or context; keep it static).

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_shell.py tests/test_signin.py -q`
Expected: PASS except the staff-page tests that need Task 7 (`topbar-title` "Staff"): have the placeholder `people.views.staff` render `people/staff.html` with `page_title = "Staff"` and an empty table for now.

`static/dist/main.css` and `static/dist/main.js` do not exist until Task 12; create both as empty files now so `{% static %}` resolves and `collectstatic` passes.

- [ ] **Step 6: Lint and commit**

```bash
ruff check . && python -m pytest -q
git add -A
git commit -m "UI: the shell — navy side panel, flyouts, top bar, dialogs, brand tokens"
```

---

### Task 7: Staff list, Health card, Sync now

**Files:**
- Create: `people/services/health.py`, `people/views/__init__.py` (replace), `people/views/staff.py`, `templates/people/staff.html`, `templates/people/_health.html`, `templates/people/add_staff_dialog.html`, `tests/test_staff_page.py`
- Modify: `people/urls.py`

**Interfaces:**
- Consumes: `access`, `hr_sync.sync`, `hr_sync.not_seen_recently`, `hr_sync.last_run`, `Person.objects.current`.
- Produces: URLs `staff` (`/staff/`), `staff-sync` (`POST /staff/sync/`), `staff-add` (`/staff/add/`, a dialog); `health.figures(user) -> dict(last_run, needs_setup, not_seen, leaving_soon)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_staff_page.py`:

```python
"""The Staff list (FMS item 27), the Health card and Sync now."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.utils import timezone

from people.models import SyncRun
from tests.factories import make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


def _client(person, **kw):
    c = Client()
    c.force_login(make_user_for(person, **kw))
    return c


def test_staff_see_current_people_with_name_title_and_team_only():
    me = make_person(job_title="Receptionist")
    make_person(first_name="Gone", end_date=date(2020, 1, 1), start_date=date(2019, 1, 1))
    body = _client(me).get("/staff/").content.decode()
    assert "Sam Patel" in body and "Receptionist" in body and "Reception" in body
    assert "Gone" not in body
    assert me.email not in body, "staff do not see emails"
    assert "health" not in body


def test_managers_see_emails_start_dates_and_the_health_card():
    boss = make_person()
    body = _client(boss, is_all_teams_manager=True).get("/staff/").content.decode()
    assert boss.email in body and "8 Jan 2024" in body
    assert 'class="health"' in body


def test_the_filter_shows_left_and_starting_people():
    boss = make_person()
    make_person(first_name="Gone", start_date=date(2019, 1, 1), end_date=date(2020, 1, 1))
    make_person(first_name="Soon", start_date=timezone.localdate() + timedelta(days=30))
    c = _client(boss, is_all_teams_manager=True)
    assert "Gone" not in c.get("/staff/").content.decode()
    assert "Gone" in c.get("/staff/?show=left").content.decode()
    assert "Soon" in c.get("/staff/?show=starting").content.decode()


def test_team_filter():
    boss = make_person()
    make_person(first_name="Nina", team=make_team("Nursing"))
    c = _client(boss, is_all_teams_manager=True)
    body = c.get("/staff/?team=Nursing").content.decode()
    assert "Nina" in body and "Sam Patel" not in body


def test_health_card_figures():
    from people.services import health
    boss = make_person(weekly_hours=Decimal("37.5"), days_per_week=5)
    user = make_user_for(boss, is_all_teams_manager=True)
    make_person(first_name="New")                        # no hours yet
    make_person(first_name="Leaving", end_date=timezone.localdate() + timedelta(days=10))
    stale = make_person(first_name="Stale")
    stale.last_seen_from_hr = timezone.now() - timedelta(days=3)
    stale.save()
    SyncRun.objects.create(ok=True, people_seen=4, finished_at=timezone.now())
    f = health.figures(user)
    assert f["last_run"].ok and f["last_run"].people_seen == 4
    assert {p.first_name for p in f["needs_setup"]} == {"New", "Leaving", "Stale"}
    assert [p.first_name for p in f["not_seen"]] == ["Stale"]
    assert [p.first_name for p in f["leaving_soon"]] == ["Leaving"]


def test_gps_do_not_need_hours():
    from people.services import health
    boss = make_person(weekly_hours=Decimal("37.5"), days_per_week=5)
    user = make_user_for(boss, is_all_teams_manager=True)
    make_person(first_name="Doc", is_gp=True)
    assert not health.figures(user)["needs_setup"].exists()


def test_a_team_manager_sees_only_their_teams_figures():
    from people.services import health
    nursing = make_team("Nursing")
    lead = make_person(team=nursing, weekly_hours=Decimal("30"), days_per_week=4)
    make_team_manager(lead, nursing)
    make_person(first_name="Nurse", team=nursing)
    make_person(first_name="Rec")
    assert {p.first_name for p in health.figures(make_user_for(lead))["needs_setup"]} == {"Nurse"}


def test_sync_now_runs_the_sync_and_reports(monkeypatch):
    from people.services import hr_sync
    boss = make_person()
    c = _client(boss, is_all_teams_manager=True)
    monkeypatch.setattr(hr_sync, "sync", lambda client=None: SyncRun.objects.create(
        ok=True, people_seen=12, finished_at=timezone.now()))
    r = c.post("/staff/sync/", follow=True)
    assert "12 people read from Practice HR" in r.content.decode()


def test_staff_cannot_sync():
    assert _client(make_person()).post("/staff/sync/").status_code == 403


def test_add_staff_points_at_practice_hr(oidc_on):
    boss = make_person()
    body = _client(boss, is_all_teams_manager=True).get("/staff/add/").content.decode()
    assert "Practice HR" in body and 'href="https://hr.example/admin/people/employee/add/"' in body
    assert 'action="/staff/sync/"' in body
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_staff_page.py -q`
Expected: FAIL.

- [ ] **Step 3: Write the service and the views**

`people/services/health.py`:

```python
"""The Health card on the Staff page: what a manager should glance at."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from people.services import access, hr_sync

LEAVING_WINDOW = timedelta(days=30)


def figures(user):
    today = timezone.localdate()
    people = access.managed_people(user).current(on=today) | access.managed_people(user).filter(
        start_date__gt=today)
    people = people.distinct()
    needs_setup = people.filter(is_gp=False).filter(
        Q(weekly_hours__isnull=True) | Q(days_per_week__isnull=True))
    return {
        "last_run": hr_sync.last_run(),
        "needs_setup": needs_setup.order_by("name"),
        "not_seen": hr_sync.not_seen_recently().filter(pk__in=people).order_by("name"),
        "leaving_soon": people.filter(end_date__gte=today, end_date__lte=today + LEAVING_WINDOW)
                              .order_by("end_date"),
    }
```

`people/views/__init__.py`:

```python
from .staff import add_staff, staff, sync_now  # noqa: F401
```

`people/views/staff.py`:

```python
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from people.models import Person, Team
from people.services import access, health, hr_sync


@login_required
def staff(request):
    today = timezone.localdate()
    show = request.GET.get("show", "current")
    people = Person.objects.select_related("team")
    manager = access.is_manager(request.user)
    if show == "left" and manager:
        people = people.filter(end_date__lt=today)
    elif show == "starting" and manager:
        people = people.filter(start_date__gt=today)
    else:
        show = "current"
        people = people.current(on=today)
    me = getattr(request.user, "person", None)
    if not manager:
        people = people.filter(show_to_other_staff=True)
        if me is not None:
            people = people | people.model.objects.filter(pk=me.pk)
    team = request.GET.get("team", "")
    if team:
        people = people.filter(team__name=team)
    return render(request, "people/staff.html", {
        "page_title": "Staff", "people": people.distinct(), "show": show, "team": team,
        "teams": Team.objects.filter(active=True),
        "health": health.figures(request.user) if manager else None,
        "managed": {p.pk for p in access.managed_people(request.user)} if manager else set(),
        "me_pk": me.pk if me is not None else None,
    })


@login_required
@access.manager_required
@require_POST
def sync_now(request):
    run = hr_sync.sync()
    if run.ok:
        messages.success(request, f"{run.people_seen} people read from Practice HR.")
    else:
        messages.error(request, f"Practice HR could not be read: {run.message}")
    return redirect("staff")


@login_required
@access.manager_required
def add_staff(request):
    return render(request, "people/add_staff_dialog.html")
```

`people/urls.py`:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("staff/", views.staff, name="staff"),
    path("staff/sync/", views.sync_now, name="staff-sync"),
    path("staff/add/", views.add_staff, name="staff-add"),
]
```

`templates/people/staff.html`:

```html
{% extends "base.html" %}
{% block title %}Staff · AMG Shift Central{% endblock %}
{% block topbar_actions %}
  {% if is_manager %}
  <a class="topbar-action is-primary" href="{% url 'staff-add' %}" data-dialog>Add staff +</a>
  <a class="topbar-action" href="?show={{ show }}&amp;team={{ team }}&amp;download=1">Download</a>
  {% endif %}
{% endblock %}
{% block content %}
{% if health %}{% include "people/_health.html" %}{% endif %}
<form class="filters" method="get">
  {% if is_manager %}
  <label>Show <select name="show">
    <option value="current"{% if show == "current" %} selected{% endif %}>Current</option>
    <option value="starting"{% if show == "starting" %} selected{% endif %}>Starting</option>
    <option value="left"{% if show == "left" %} selected{% endif %}>Left</option>
  </select></label>
  {% endif %}
  <label>Team <select name="team">
    <option value="">All teams</option>
    {% for t in teams %}<option value="{{ t.name }}"{% if t.name == team %} selected{% endif %}>{{ t.name }}</option>{% endfor %}
  </select></label>
  <button class="btn btn-quiet" type="submit">Filter</button>
</form>
<table class="table">
  <thead><tr><th>Name</th><th>Job title</th><th>Team</th>{% if is_manager %}<th>Email</th><th>Start date</th><th>Finish date</th>{% endif %}</tr></thead>
  <tbody>
  {% for p in people %}
  <tr>
    <td>{% if p.pk in managed or p.pk == me_pk %}<a href="{% url 'profile' p.pk %}" data-dialog class="chip" style="background:{{ p.name_colour }}">{{ p.name }}</a>{% else %}<span class="chip" style="background:{{ p.name_colour }}">{{ p.name }}</span>{% endif %}</td>
    <td>{{ p.job_title }}</td>
    <td>{{ p.team.name|default:"—" }}</td>
    {% if is_manager %}<td>{{ p.email }}</td><td>{{ p.start_date|date:"j M Y" }}</td><td>{{ p.end_date|date:"j M Y"|default:"" }}</td>{% endif %}
  </tr>
  {% empty %}<tr><td colspan="6">Nobody matches.</td></tr>{% endfor %}
  </tbody>
</table>
{% endblock %}
```

(`{% url 'profile' p.pk %}` exists from Task 8; until then use `href="#"`. The Download action: in `staff()`, when `request.GET.get("download")` and the user is a manager, return a `text/csv` response of the same rows — Name, Job title, Team, Email, Start, Finish — with `Content-Disposition: attachment; filename="staff.csv"`; add a test `test_managers_can_download_the_visible_rows_as_csv` asserting the header row and one person.)

`templates/people/_health.html`:

```html
<section class="health" aria-label="Health">
  <h2>Health</h2>
  <div class="health-item{% if not health.last_run or not health.last_run.ok %} is-bad{% endif %}">
    Practice HR
    <strong>{% if health.last_run %}{% if health.last_run.ok %}{{ health.last_run.people_seen }} people, {{ health.last_run.finished_at|date:"j M H:i" }}{% else %}failed {{ health.last_run.finished_at|date:"j M H:i" }}{% endif %}{% else %}never read{% endif %}</strong>
    {% if health.last_run and not health.last_run.ok %}<span>{{ health.last_run.message }}</span>{% endif %}
    <form method="post" action="{% url 'staff-sync' %}">{% csrf_token %}<button class="btn btn-quiet">Sync now</button></form>
  </div>
  <div class="health-item{% if health.needs_setup %} is-warning{% endif %}">Needs hours and allowances<strong>{{ health.needs_setup.count }}</strong>
    {% for p in health.needs_setup|slice:":5" %}<a href="{% url 'profile' p.pk %}" data-dialog>{{ p.name }}</a>{% if not forloop.last %}, {% endif %}{% endfor %}</div>
  <div class="health-item{% if health.not_seen %} is-bad{% endif %}">Not in Practice HR's feed for a day<strong>{{ health.not_seen.count }}</strong>
    {% for p in health.not_seen|slice:":5" %}{{ p.name }}{% if not forloop.last %}, {% endif %}{% endfor %}</div>
  <div class="health-item{% if health.leaving_soon %} is-warning{% endif %}">Leaving in the next 30 days<strong>{{ health.leaving_soon.count }}</strong>
    {% for p in health.leaving_soon %}{{ p.name }} ({{ p.end_date|date:"j M" }}){% if not forloop.last %}, {% endif %}{% endfor %}</div>
</section>
```

`templates/people/add_staff_dialog.html`:

```html
{% extends "ui/_dialog.html" %}
{% block dialog_title %}Add staff{% endblock %}
{% block dialog_body %}
<p>People come from <strong>Practice HR</strong>. Add the new starter there — <a href="{{ settings_practice_hr_url }}/admin/people/employee/add/" target="_blank" rel="noopener">Employees › Add</a> — and they appear here within fifteen minutes, ready for their hours and allowances.</p>
<form method="post" action="{% url 'staff-sync' %}">{% csrf_token %}<button class="btn btn-dark">Sync now</button></form>
{% endblock %}
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/test_staff_page.py tests/test_shell.py -q`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
ruff check . && python -m pytest -q
git add -A
git commit -m "People: the Staff list, the Health card and Sync now"
```

---

### Task 8: The profile pop-up — General, Display, Pay & time off, Notes, History

**Files:**
- Create: `people/services/profiles.py`, `people/forms.py`, `people/views/profile.py`, `templates/people/profile_dialog.html`, `templates/people/_profile_general.html`, `templates/people/_profile_display.html`, `templates/people/_profile_hours.html`, `templates/people/_profile_notes.html`, `templates/people/history_dialog.html`, `tests/test_profile.py`
- Modify: `people/views/__init__.py`, `people/urls.py`, `templates/people/staff.html` (the name links)

**Interfaces:**
- Consumes: `access.can_manage`, `access.is_self`, `audit.record`, `Allowance`, `HEX_COLOUR`.
- Produces: services `profiles.update_display(actor, person, **fields)`, `profiles.update_hours(actor, person, weekly_hours, days_per_week)`, `profiles.set_allowance(actor, person, leave_year, annual_hours, bank_holiday_hours, note)` (raises `ValueError("A reason is needed…")` when an existing figure changes without a note), `profiles.set_notes(actor, person, notes)`; forms `DisplayForm`, `HoursForm`, `AllowanceForm`, `NotesForm`; URLs `profile` (`/staff/<pk>/profile/`, `?tab=general|display|hours|notes`), `profile-history` (`/staff/<pk>/history/`); `profiles.leave_years(today) -> [this year's 1 Jan, next year's 1 Jan]`.

- [ ] **Step 1: Write the failing tests**

`tests/test_profile.py`:

```python
"""The profile pop-up (FMS items 15–18, 21, 22, 24) and the services behind it."""

from datetime import date
from decimal import Decimal

import pytest
from django.test import Client

from people.models import Allowance, AuditEntry
from people.services import profiles
from tests.factories import make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def years_2026_2027(monkeypatch):
    """The hours tab's year fields follow today's date; pin them so the
    field names below hold whenever the suite runs."""
    monkeypatch.setattr(profiles, "leave_years",
                        lambda today=None: [date(2026, 1, 1), date(2027, 1, 1)])


@pytest.fixture
def world(db):
    nursing = make_team("Nursing")
    nurse = make_person(team=nursing, first_name="Nina")
    lead = make_person(team=nursing, first_name="Lead")
    make_team_manager(lead, nursing)
    rec = make_person(first_name="Rec")
    boss = make_person(first_name="Boss")
    clients = {}
    for key, person, kw in (("nurse", nurse, {}), ("lead", lead, {}), ("rec", rec, {}),
                            ("boss", boss, {"is_all_teams_manager": True})):
        c = Client()
        c.force_login(make_user_for(person, **kw))
        clients[key] = c
    return {"nurse": nurse, "lead": lead, "rec": rec, "boss": boss, "c": clients}


# --- who sees which tabs ---------------------------------------------------------

def test_own_profile_shows_general_and_display_read_only_no_notes(world):
    body = world["c"]["nurse"].get(f"/staff/{world['nurse'].pk}/profile/").content.decode()
    assert "Your profile" in body and "Nina" in body
    assert "?tab=notes" not in body, "notes are managers only"
    assert "?tab=hours" in body, "own hours and allowances are readable"
    assert 'name="job_title"' not in body, "staff cannot edit the display fields"


def test_a_colleagues_profile_is_not_opened_by_staff(world):
    assert world["c"]["rec"].get(f"/staff/{world['nurse'].pk}/profile/").status_code == 403


def test_a_team_manager_edits_their_teams_people_only(world):
    c = world["c"]["lead"]
    body = c.get(f"/staff/{world['nurse'].pk}/profile/?tab=display").content.decode()
    assert "Nina's profile" in body and 'name="job_title"' in body and "?tab=notes" in body
    assert c.get(f"/staff/{world['rec'].pk}/profile/").status_code == 403


def test_the_general_tab_shows_hr_fields_read_only(world):
    body = world["c"]["boss"].get(f"/staff/{world['nurse'].pk}/profile/").content.decode()
    assert "from Practice HR" in body and world["nurse"].email in body
    assert 'name="email"' not in body


# --- display ---------------------------------------------------------------------

def test_the_display_form_saves_and_audits(world):
    c, nurse = world["c"]["boss"], world["nurse"]
    r = c.post(f"/staff/{nurse.pk}/profile/?tab=display", {
        "job_title": "Practice nurse", "name_colour": "#C94C4C", "display_order": "20",
        "display_on_rota": "on", "show_to_other_staff": "on"})
    assert r.status_code == 200 and "Saved" in r.content.decode()
    nurse.refresh_from_db()
    assert (nurse.job_title, nurse.name_colour, nurse.display_order) == ("Practice nurse", "#C94C4C", 20)
    assert nurse.display_on_rota and nurse.show_to_other_staff and not nurse.can_see_other_staff
    assert {a.field for a in AuditEntry.objects.filter(object_id=nurse.pk)} == {
        "job_title", "name_colour", "display_order", "can_see_other_staff"}


def test_a_bad_colour_is_refused(world):
    c, nurse = world["c"]["boss"], world["nurse"]
    r = c.post(f"/staff/{nurse.pk}/profile/?tab=display", {
        "job_title": "x", "name_colour": "red", "display_order": "20"})
    assert r.status_code == 200 and "field-error" in r.content.decode()
    nurse.refresh_from_db()
    assert nurse.name_colour == "#143D5C"


# --- hours and allowances ----------------------------------------------------------

def test_leave_years_are_this_year_and_next(monkeypatch):
    monkeypatch.undo()
    assert profiles.leave_years(date(2026, 11, 20)) == [date(2026, 1, 1), date(2027, 1, 1)]


def test_the_hours_tab_saves_hours_days_and_both_years_allowances(world):
    c, nurse = world["c"]["boss"], world["nurse"]
    r = c.post(f"/staff/{nurse.pk}/profile/?tab=hours", {
        "weekly_hours": "30", "days_per_week": "4",
        "annual_2027": "138", "bank_holiday_2027": "48", "note": ""})
    assert r.status_code == 200 and "Saved" in r.content.decode()
    nurse.refresh_from_db()
    assert (nurse.weekly_hours, nurse.days_per_week, nurse.average_day) == (Decimal("30.00"), 4, Decimal("7.5"))
    a = Allowance.objects.get(person=nurse, leave_year=date(2027, 1, 1))
    assert (a.annual_hours, a.bank_holiday_hours) == (Decimal("138.00"), Decimal("48.00"))
    assert not Allowance.objects.filter(person=nurse, leave_year=date(2026, 1, 1)).exists(), "blank year not created"


def test_changing_an_existing_allowance_needs_a_reason(world):
    nurse, boss = world["nurse"], world["boss"].user
    profiles.set_allowance(boss, nurse, date(2027, 1, 1), Decimal("138"), Decimal("48"), note="")
    with pytest.raises(ValueError, match="reason"):
        profiles.set_allowance(boss, nurse, date(2027, 1, 1), Decimal("140"), Decimal("48"), note="")
    rows = profiles.set_allowance(boss, nurse, date(2027, 1, 1), Decimal("140"), Decimal("48"),
                                  note="extra bank holiday 2027")
    assert [(r.field, r.before, r.after, r.note) for r in rows] == [
        ("annual_hours", "138.00", "140.00", "extra bank holiday 2027")]


def test_the_hours_form_refuses_a_change_without_a_reason(world):
    c, nurse = world["c"]["boss"], world["nurse"]
    profiles.set_allowance(world["boss"].user, nurse, date(2027, 1, 1), Decimal("138"), Decimal("48"), note="")
    r = c.post(f"/staff/{nurse.pk}/profile/?tab=hours", {
        "weekly_hours": "30", "days_per_week": "4", "annual_2027": "140", "bank_holiday_2027": "48", "note": ""})
    assert "reason" in r.content.decode().lower()
    assert Allowance.objects.get(person=nurse, leave_year=date(2027, 1, 1)).annual_hours == Decimal("138.00")


def test_a_gp_has_no_hours_fields(world):
    doc = make_person(first_name="Doc", is_gp=True, team=make_team("GPs"))
    body = world["c"]["boss"].get(f"/staff/{doc.pk}/profile/?tab=hours").content.decode()
    assert 'name="weekly_hours"' not in body and "sessions, from the GP rota" in body
    assert 'name="annual_2027"' in body


def test_staff_see_their_own_hours_tab_read_only(world):
    nurse = world["nurse"]
    profiles.update_hours(world["boss"].user, nurse, Decimal("30"), 4)
    body = world["c"]["nurse"].get(f"/staff/{nurse.pk}/profile/?tab=hours").content.decode()
    assert "30" in body and 'name="weekly_hours"' not in body


# --- notes and history ---------------------------------------------------------------

def test_notes_are_managers_only(world):
    c, nurse = world["c"]["lead"], world["nurse"]
    assert c.post(f"/staff/{nurse.pk}/profile/?tab=notes", {"notes": "Prefers Tuesdays"}).status_code == 200
    nurse.refresh_from_db()
    assert nurse.notes == "Prefers Tuesdays"
    assert world["c"]["nurse"].get(f"/staff/{nurse.pk}/profile/?tab=notes").status_code == 403


def test_history_lists_the_persons_audit_entries_for_managers(world):
    nurse = world["nurse"]
    profiles.update_display(world["boss"].user, nurse, job_title="Practice nurse")
    body = world["c"]["lead"].get(f"/staff/{nurse.pk}/history/").content.decode()
    assert "job_title" in body and "Practice nurse" in body and "boss" in body
    assert world["c"]["nurse"].get(f"/staff/{nurse.pk}/history/").status_code == 403
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_profile.py -q`
Expected: FAIL.

- [ ] **Step 3: Write the services**

`people/services/profiles.py`:

```python
"""Every write to a person's typed fields and allowances (spec, sections 3
and 6). Each change is audited per field; an allowance that already
exists needs a typed reason to change (LEAVE-31)."""

from datetime import date
from decimal import Decimal

from django.utils import timezone

from people.models import Allowance
from people.services import audit

DISPLAY_FIELDS = ("job_title", "name_colour", "display_order", "display_on_rota",
                  "show_to_other_staff", "can_see_other_staff")


def leave_years(today=None):
    today = today or timezone.localdate()
    return [date(today.year, 1, 1), date(today.year + 1, 1, 1)]


def _apply(actor, person, fields, note=""):
    changes = {}
    for name, after in fields.items():
        before = getattr(person, name)
        if before != after:
            changes[name] = (before, after)
            setattr(person, name, after)
    if changes:
        person.save(update_fields=list(changes))
    return audit.record(actor, person, changes, note=note)


def update_display(actor, person, **fields):
    unknown = set(fields) - set(DISPLAY_FIELDS)
    if unknown:
        raise ValueError(f"not display fields: {sorted(unknown)}")
    return _apply(actor, person, fields)


def update_hours(actor, person, weekly_hours, days_per_week):
    if person.is_gp:
        raise ValueError("a GP's sessions come from the GP rota")
    weekly_hours = Decimal(weekly_hours).quantize(Decimal("0.01")) if weekly_hours is not None else None
    return _apply(actor, person, {"weekly_hours": weekly_hours, "days_per_week": days_per_week})


def set_allowance(actor, person, leave_year, annual_hours, bank_holiday_hours, note=""):
    annual_hours = Decimal(annual_hours).quantize(Decimal("0.01"))
    bank_holiday_hours = Decimal(bank_holiday_hours).quantize(Decimal("0.01"))
    allowance = Allowance.objects.filter(person=person, leave_year=leave_year).first()
    if allowance is None:
        allowance = Allowance.objects.create(person=person, leave_year=leave_year,
                                             annual_hours=annual_hours,
                                             bank_holiday_hours=bank_holiday_hours)
        return audit.record(actor, allowance, {"annual_hours": ("", str(annual_hours)),
                                               "bank_holiday_hours": ("", str(bank_holiday_hours))},
                            note=note or f"allowance set for {leave_year.year}")
    changes = {}
    for field, after in (("annual_hours", annual_hours), ("bank_holiday_hours", bank_holiday_hours)):
        before = getattr(allowance, field)
        if before != after:
            changes[field] = (before, after)
    if not changes:
        return []
    if not note.strip():
        raise ValueError("A reason is needed to change an allowance that is already set")
    for field, (_, after) in changes.items():
        setattr(allowance, field, after)
    allowance.save(update_fields=list(changes))
    return audit.record(actor, allowance, changes, note=note.strip())


def set_notes(actor, person, notes):
    return _apply(actor, person, {"notes": notes})
```

`people/forms.py`:

```python
from django import forms
from django.core.validators import RegexValidator

from people.models import HEX_COLOUR


class DisplayForm(forms.Form):
    job_title = forms.CharField(max_length=80, required=False)
    name_colour = forms.CharField(max_length=7, validators=[RegexValidator(HEX_COLOUR, "Choose a colour.")])
    display_order = forms.IntegerField(min_value=0, initial=100)
    display_on_rota = forms.BooleanField(required=False)
    show_to_other_staff = forms.BooleanField(required=False)
    can_see_other_staff = forms.BooleanField(required=False)


class HoursForm(forms.Form):
    """Weekly hours and days per week, plus the two allowances for each of
    the two leave years. The year fields are added in __init__ from
    profiles.leave_years(); the note is required only when the view finds
    an existing allowance changed (the service enforces it)."""
    weekly_hours = forms.DecimalField(max_digits=5, decimal_places=2, min_value=0, required=False)
    days_per_week = forms.IntegerField(min_value=1, max_value=7, required=False)
    note = forms.CharField(max_length=300, required=False, label="Reason for the change")

    def __init__(self, *args, years, is_gp=False, **kwargs):
        super().__init__(*args, **kwargs)
        if is_gp:
            del self.fields["weekly_hours"], self.fields["days_per_week"]
        self.years = years
        for year in years:
            self.fields[f"annual_{year.year}"] = forms.DecimalField(
                max_digits=6, decimal_places=2, min_value=0, required=False,
                label=f"Annual leave allowance {year.year} (hours)")
            self.fields[f"bank_holiday_{year.year}"] = forms.DecimalField(
                max_digits=6, decimal_places=2, min_value=0, required=False,
                label=f"Bank holiday allowance {year.year} (hours)")

    def clean(self):
        data = super().clean()
        for year in self.years:
            a, b = data.get(f"annual_{year.year}"), data.get(f"bank_holiday_{year.year}")
            if (a is None) != (b is None):
                self.add_error(f"annual_{year.year}", "Give both allowances for the year, or neither.")
        return data

    def allowances(self):
        """[(leave_year, annual, bank_holiday)] for the years both are given."""
        return [(y, self.cleaned_data[f"annual_{y.year}"], self.cleaned_data[f"bank_holiday_{y.year}"])
                for y in self.years if self.cleaned_data.get(f"annual_{y.year}") is not None]


class NotesForm(forms.Form):
    notes = forms.CharField(widget=forms.Textarea, required=False)


class DepartmentForm(forms.Form):
    name = forms.CharField(max_length=60)
    colour = forms.CharField(max_length=7, validators=[RegexValidator(HEX_COLOUR, "Choose a colour.")])
    display_order = forms.IntegerField(min_value=0, initial=100)
    archived = forms.BooleanField(required=False)
```

- [ ] **Step 4: Write the view and templates**

`people/views/profile.py`:

```python
"""The profile pop-up: one dialog, four tabs, each a GET to render and a
POST to save. Who may see which tab is decided here from access.*."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from people.forms import DisplayForm, HoursForm, NotesForm
from people.models import AuditEntry, Person
from people.services import access, profiles

TABS = ("general", "display", "hours", "notes")


def _person_for(request, pk):
    person = get_object_or_404(Person.objects.select_related("team"), pk=pk)
    if not (access.is_self(request.user, person) or access.can_manage(request.user, person)):
        raise PermissionDenied
    return person


@login_required
def profile(request, pk):
    person = _person_for(request, pk)
    manages = access.can_manage(request.user, person)
    tab = request.GET.get("tab", "general")
    if tab not in TABS:
        raise Http404
    if tab == "notes" and not manages:
        raise PermissionDenied
    context = {"person": person, "tab": tab, "manages": manages, "saved": False,
               "title": "Your profile" if access.is_self(request.user, person) else f"{person.name}'s profile"}
    if tab == "display":
        _display(request, person, manages, context)
    elif tab == "hours":
        _hours(request, person, manages, context)
    elif tab == "notes":
        _notes(request, person, context)
    return render(request, "people/profile_dialog.html", context)


def _display(request, person, manages, context):
    initial = {f: getattr(person, f) for f in profiles.DISPLAY_FIELDS}
    if request.method == "POST" and manages:
        form = DisplayForm(request.POST)
        if form.is_valid():
            profiles.update_display(request.user, person, **form.cleaned_data)
            context["saved"] = True
            form = DisplayForm(initial={f: getattr(person, f) for f in profiles.DISPLAY_FIELDS})
    else:
        form = DisplayForm(initial=initial)
    context["form"] = form


def _hours(request, person, manages, context):
    years = profiles.leave_years()
    existing = {a.leave_year: a for a in person.allowances.filter(leave_year__in=years)}
    initial = {"weekly_hours": person.weekly_hours, "days_per_week": person.days_per_week}
    for y, a in existing.items():
        initial[f"annual_{y.year}"] = a.annual_hours
        initial[f"bank_holiday_{y.year}"] = a.bank_holiday_hours
    if request.method == "POST" and manages:
        form = HoursForm(request.POST, years=years, is_gp=person.is_gp)
        if form.is_valid():
            try:
                if not person.is_gp:
                    profiles.update_hours(request.user, person, form.cleaned_data["weekly_hours"],
                                          form.cleaned_data["days_per_week"])
                for year, annual, bank in form.allowances():
                    profiles.set_allowance(request.user, person, year, annual, bank,
                                           note=form.cleaned_data["note"])
                context["saved"] = True
            except ValueError as e:
                form.add_error("note", str(e))
    else:
        form = HoursForm(initial=initial, years=years, is_gp=person.is_gp)
    context.update({"form": form, "years": years, "existing": existing})


def _notes(request, person, context):
    if request.method == "POST":
        form = NotesForm(request.POST)
        if form.is_valid():
            profiles.set_notes(request.user, person, form.cleaned_data["notes"])
            context["saved"] = True
    else:
        form = NotesForm(initial={"notes": person.notes})
    context["form"] = form


@login_required
def history(request, pk):
    person = get_object_or_404(Person, pk=pk)
    if not access.can_manage(request.user, person):
        raise PermissionDenied
    allowance_ids = list(person.allowances.values_list("pk", flat=True))
    entries = AuditEntry.objects.filter(model="people.person", object_id=person.pk) | \
        AuditEntry.objects.filter(model="people.allowance", object_id__in=allowance_ids)
    return render(request, "people/history_dialog.html",
                  {"person": person, "entries": entries.order_by("-at")[:200]})
```

Add to `people/views/__init__.py`: `from .profile import history, profile  # noqa: F401`. Add to `people/urls.py`:

```python
    path("staff/<int:pk>/profile/", views.profile, name="profile"),
    path("staff/<int:pk>/history/", views.history, name="profile-history"),
```

`templates/people/profile_dialog.html`:

```html
{% extends "ui/_dialog.html" %}
{% block dialog_title %}{{ title }}{% endblock %}
{% block dialog_body %}
<div style="display:flex;gap:12px;align-items:center;margin-bottom:12px">
  <span class="avatar" style="background:{{ person.name_colour }}">{{ person.initials }}</span>
  <div><strong>{{ person.name }}</strong><br><span class="field-help">{{ person.team.name|default:"No team" }}{% if person.job_title %} · {{ person.job_title }}{% endif %}</span></div>
</div>
<nav class="tabs">
  <a class="tab{% if tab == 'general' %} is-active{% endif %}" href="{% url 'profile' person.pk %}?tab=general">General</a>
  <a class="tab{% if tab == 'display' %} is-active{% endif %}" href="{% url 'profile' person.pk %}?tab=display">Display</a>
  <a class="tab{% if tab == 'hours' %} is-active{% endif %}" href="{% url 'profile' person.pk %}?tab=hours">Pay &amp; time off</a>
  {% if manages %}<a class="tab{% if tab == 'notes' %} is-active{% endif %}" href="{% url 'profile' person.pk %}?tab=notes">Notes</a>{% endif %}
</nav>
{% if saved %}<div class="flash">Saved.</div>{% endif %}
{% if tab == "general" %}{% include "people/_profile_general.html" %}
{% elif tab == "display" %}{% include "people/_profile_display.html" %}
{% elif tab == "hours" %}{% include "people/_profile_hours.html" %}
{% elif tab == "notes" %}{% include "people/_profile_notes.html" %}{% endif %}
{% endblock %}
{% block dialog_links %}
{% if manages %}
<div class="dialog-links">
  {% if is_all_teams %}<a href="{% url 'permissions' person.pk %}" data-dialog>Permissions</a>{% endif %}
  <a href="{% url 'profile-history' person.pk %}" data-dialog>History</a>
</div>
{% endif %}
{% endblock %}
```

(`{% url 'permissions' … %}` exists from Task 10; until then leave the link out.)

`templates/people/_profile_general.html`:

```html
<dl class="defs">
  <dt>Name</dt><dd>{{ person.name }} <span class="field-help">from Practice HR</span></dd>
  <dt>Email</dt><dd>{{ person.email }}</dd>
  <dt>Team</dt><dd>{{ person.team.name|default:"—" }}</dd>
  <dt>Start date</dt><dd>{{ person.start_date|date:"j M Y" }}</dd>
  {% if person.end_date %}<dt>Finish date</dt><dd>{{ person.end_date|date:"j M Y" }}</dd>{% endif %}
</dl>
<p class="field-help">Name, email, team and dates are kept in Practice HR and updated here every fifteen minutes.</p>
```

`templates/people/_profile_display.html` — a `form[data-dialog-form]` posting to `{% url 'profile' person.pk %}?tab=display` with each field in a `.field` div (`has-error` and the `field-error` text when `form.errors`), the colour field as `<input type="hidden" name="name_colour" id="id_name_colour" value="{{ form.name_colour.value }}">` followed by `<div data-component="colour-picker" data-input="id_name_colour"></div>` (Task 12's island; until then the hidden input alone, plus a visible `<input type="text">` bound to the same name is fine for the test), job title, display order, and the three tick boxes; `<button class="btn btn-dark">Update profile</button>`. When `not manages`, render the same values as a `<dl>` with no form.

`templates/people/_profile_hours.html` — same pattern: for a non-GP, `weekly_hours` and `days_per_week` and the computed average day (`{{ person.average_day }}` h) as help text; for a GP the sentence "Hours: sessions, from the GP rota (4 h 10 min each)"; then for each year in `years` the two allowance fields; the `note` field with help "Needed when changing an allowance that is already set"; `Update profile`. Read-only `<dl>` when `not manages`.

`templates/people/_profile_notes.html` — a textarea form, managers only (the view already refuses others).

`templates/people/history_dialog.html` — extends `_dialog.html`, title "History — {{ person.name }}", a `.table` with When, Who, What, From, To, Reason for each entry (`entry.at|date:"j M Y H:i"`, `entry.actor_email`, `entry.model|cut:"people."` + ` ` + `entry.field`, `entry.before`, `entry.after`, `entry.note`).

Update `templates/people/staff.html` so names link to `{% url 'profile' p.pk %}` with `data-dialog` when `p.pk in managed or p.pk == me_pk`.

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_profile.py tests/test_staff_page.py -q`
Expected: PASS.

- [ ] **Step 6: Lint and commit**

```bash
ruff check . && python -m pytest -q
git add -A
git commit -m "People: the profile pop-up — display, hours and allowances, notes, history"
```

---

### Task 9: Departments

**Files:**
- Create: `people/services/departments.py`, `people/views/departments.py`, `templates/people/departments.html`, `templates/people/department_dialog.html`, `tests/test_departments.py`
- Modify: `people/views/__init__.py`, `people/urls.py`

**Interfaces:**
- Consumes: `Department`, `DepartmentForm`, `audit.record`, `access.manager_required`.
- Produces: `departments.create(actor, name, colour, display_order=100) -> Department`, `departments.update(actor, department, **fields)`; URLs `departments` (`/departments/`), `department-add` (`/departments/add/`), `department-edit` (`/departments/<pk>/edit/`).

- [ ] **Step 1: Write the failing tests**

`tests/test_departments.py`:

```python
import pytest
from django.test import Client

from people.models import AuditEntry, Department
from people.services import departments
from tests.factories import make_person, make_user_for

pytestmark = pytest.mark.django_db


@pytest.fixture
def boss_client(db):
    c = Client()
    c.force_login(make_user_for(make_person(), is_all_teams_manager=True))
    return c


def test_the_page_lists_departments_with_colours_for_managers(boss_client):
    body = boss_client.get("/departments/").content.decode()
    assert "Reception AG" in body and "#2F6FB3" in body and "Add department +" in body


def test_staff_cannot_open_the_page(db):
    c = Client()
    c.force_login(make_user_for(make_person()))
    assert c.get("/departments/").status_code == 403


def test_add_and_edit_through_the_dialog(boss_client):
    r = boss_client.post("/departments/add/", {"name": "Flu clinic", "colour": "#2A7F62", "display_order": "5"})
    assert r.status_code == 200 and r["Content-Type"].startswith("application/json")
    d = Department.objects.get(name="Flu clinic")
    assert d.colour == "#2A7F62" and d.display_order == 5
    r = boss_client.post(f"/departments/{d.pk}/edit/", {"name": "Flu clinic", "colour": "#C94C4C",
                                                         "display_order": "5", "archived": "on"})
    assert r.status_code == 200
    d.refresh_from_db()
    assert d.colour == "#C94C4C" and d.archived
    assert {a.field for a in AuditEntry.objects.filter(model="people.department", object_id=d.pk)} == {
        "created", "colour", "archived"}


def test_a_duplicate_name_is_refused_in_the_form(boss_client):
    r = boss_client.post("/departments/add/", {"name": "Pharmacy", "colour": "#2A7F62", "display_order": "5"})
    assert r.status_code == 200 and "already exists" in r.content.decode()


def test_archived_departments_are_listed_apart(boss_client):
    d = Department.objects.get(name="Scanning")
    departments.update(None, d, archived=True)
    body = boss_client.get("/departments/").content.decode()
    assert body.index("Archived") < body.index("Scanning")
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `python -m pytest tests/test_departments.py -q`

- [ ] **Step 3: Write the service, view and templates**

`people/services/departments.py`:

```python
from people.models import Department
from people.services import audit

FIELDS = ("name", "colour", "display_order", "archived")


def create(actor, name, colour, display_order=100):
    d = Department.objects.create(name=name, colour=colour, display_order=display_order)
    audit.record(actor, d, {"created": ("", name)})
    return d


def update(actor, department, **fields):
    changes = {}
    for name, after in fields.items():
        if name not in FIELDS:
            raise ValueError(f"not a department field: {name}")
        before = getattr(department, name)
        if before != after:
            changes[name] = (before, after)
            setattr(department, name, after)
    if changes:
        department.save(update_fields=list(changes))
    return audit.record(actor, department, changes)
```

`people/views/departments.py`:

```python
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from people.forms import DepartmentForm
from people.models import Department
from people.services import access, departments


@login_required
@access.manager_required
def index(request):
    return render(request, "people/departments.html", {
        "page_title": "Departments",
        "active": Department.objects.filter(archived=False),
        "archived": Department.objects.filter(archived=True)})


def _save(request, department):
    form = DepartmentForm(request.POST)
    if form.is_valid():
        name = form.cleaned_data["name"]
        clash = Department.objects.filter(name__iexact=name).exclude(pk=getattr(department, "pk", None))
        if clash.exists():
            form.add_error("name", "A department with this name already exists.")
        elif department is None:
            departments.create(request.user, name, form.cleaned_data["colour"],
                               form.cleaned_data["display_order"])
            return form, True
        else:
            departments.update(request.user, department, **form.cleaned_data)
            return form, True
    return form, False


@login_required
@access.manager_required
def add(request):
    if request.method == "POST":
        form, ok = _save(request, None)
        if ok:
            return JsonResponse({"redirect": reverse("departments")})
    else:
        form = DepartmentForm(initial={"colour": "#2F6FB3"})
    return render(request, "people/department_dialog.html", {"form": form, "department": None})


@login_required
@access.manager_required
def edit(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == "POST":
        form, ok = _save(request, department)
        if ok:
            return JsonResponse({"redirect": reverse("departments")})
    else:
        form = DepartmentForm(initial={f: getattr(department, f) for f in departments.FIELDS})
    return render(request, "people/department_dialog.html", {"form": form, "department": department})
```

Register in `people/views/__init__.py` (`from . import departments  # noqa: F401`) and `people/urls.py`:

```python
    path("departments/", views.departments.index, name="departments"),
    path("departments/add/", views.departments.add, name="department-add"),
    path("departments/<int:pk>/edit/", views.departments.edit, name="department-edit"),
```

`templates/people/departments.html` — extends `base.html`; `topbar_actions` has `<a class="topbar-action is-primary" href="{% url 'department-add' %}" data-dialog>Add department +</a>`; a `.table` of Name (as a chip in its colour), Colour (the hex), Order, Date added, Edit (`data-dialog` link to `department-edit`); then, if any, an `<h2>Archived</h2>` and the same table for `archived`.

`templates/people/department_dialog.html` — extends `_dialog.html`; title "Department"; `form[data-dialog-form]` posting to the add or edit URL with name, the colour (hidden input `id_colour` + `<div data-component="colour-picker" data-input="id_colour">`), display order, and — when editing — the archived tick; `<button class="btn btn-dark">{% if department %}Update department{% else %}Add department{% endif %}</button>`.

- [ ] **Step 4: Run the tests, lint and commit**

```bash
python -m pytest tests/test_departments.py -q && ruff check . && python -m pytest -q
git add -A
git commit -m "People: departments — the combined list, colours, archive"
```

---

### Task 10: Permissions — manager access per team

**Files:**
- Create: `people/services/managers.py`, `people/views/permissions.py`, `templates/people/permissions_dialog.html`, `tests/test_permissions.py`
- Modify: `people/views/__init__.py`, `people/urls.py`, `templates/people/profile_dialog.html` (the Permissions link)

**Interfaces:**
- Consumes: `TeamManager`, `Team`, `access.all_teams_required`, `audit.record`.
- Produces: `managers.grant(actor, person, team) -> TeamManager`, `managers.revoke(actor, person, team)`, `managers.set_teams(actor, person, teams)`; URL `permissions` (`/staff/<pk>/permissions/`).

- [ ] **Step 1: Write the failing tests**

`tests/test_permissions.py`:

```python
import pytest
from django.test import Client

from people.models import AuditEntry, TeamManager
from people.services import access, managers
from tests.factories import make_person, make_team, make_user_for

pytestmark = pytest.mark.django_db


def test_grant_and_revoke_are_audited(all_teams_user):
    nursing, pharmacy = make_team("Nursing"), make_team("Pharmacy")
    lead = make_person(team=nursing)
    managers.set_teams(all_teams_user, lead, [nursing, pharmacy])
    assert set(TeamManager.objects.filter(person=lead).values_list("team__name", flat=True)) == {"Nursing", "Pharmacy"}
    managers.set_teams(all_teams_user, lead, [nursing])
    assert list(TeamManager.objects.filter(person=lead).values_list("team__name", flat=True)) == ["Nursing"]
    rows = AuditEntry.objects.filter(model="people.person", object_id=lead.pk,
                                     field="manager_of").order_by("pk")
    assert [(r.before, r.after) for r in rows] == [("", "Nursing"), ("", "Pharmacy"), ("Pharmacy", "")]


def test_the_dialog_is_all_teams_only():
    nursing = make_team("Nursing")
    lead = make_person(team=nursing)
    boss = Client()
    boss.force_login(make_user_for(make_person(), is_all_teams_manager=True))
    body = boss.get(f"/staff/{lead.pk}/permissions/").content.decode()
    assert 'name="teams"' in body and "Nursing" in body
    r = boss.post(f"/staff/{lead.pk}/permissions/", {"teams": [nursing.pk]})
    assert r.status_code == 200 and access.can_manage_team(make_user_for(lead), nursing)
    team_lead = Client()
    team_lead.force_login(lead.user)
    assert team_lead.get(f"/staff/{lead.pk}/permissions/").status_code == 403


def test_an_all_teams_managers_own_dialog_says_it_is_set_in_hr():
    boss_person = make_person()
    boss = Client()
    boss.force_login(make_user_for(boss_person, is_all_teams_manager=True))
    other = make_person(first_name="Other")
    make_user_for(other, is_all_teams_manager=True)
    body = boss.get(f"/staff/{other.pk}/permissions/").content.decode()
    assert "all teams, set in Practice HR" in body
```

- [ ] **Step 2: Write the service, view and template**

`people/services/managers.py`:

```python
"""Manager access per team (PEOPLE-04): granted and revoked by all-teams
managers; every change audited on the person as `manager_of`."""

from people.models import TeamManager
from people.services import audit


def grant(actor, person, team):
    row, made = TeamManager.objects.get_or_create(person=person, team=team,
                                                  defaults={"granted_by": actor})
    if made:
        audit.record(actor, person, {"manager_of": ("", team.name)})
    return row


def revoke(actor, person, team):
    deleted, _ = TeamManager.objects.filter(person=person, team=team).delete()
    if deleted:
        audit.record(actor, person, {"manager_of": (team.name, "")})


def set_teams(actor, person, teams):
    wanted = {t.pk: t for t in teams}
    current = {r.team_id: r.team for r in TeamManager.objects.filter(person=person).select_related("team")}
    for pk, team in sorted(wanted.items(), key=lambda kv: kv[1].name):
        if pk not in current:
            grant(actor, person, team)
    for pk, team in current.items():
        if pk not in wanted:
            revoke(actor, person, team)
```

`people/views/permissions.py`:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from people.models import Person, Team
from people.services import access, managers


@login_required
@access.all_teams_required
def permissions(request, pk):
    person = get_object_or_404(Person, pk=pk)
    saved = False
    if request.method == "POST":
        teams = Team.objects.filter(pk__in=request.POST.getlist("teams"))
        managers.set_teams(request.user, person, teams)
        saved = True
    return render(request, "people/permissions_dialog.html", {
        "person": person, "teams": Team.objects.filter(active=True),
        "granted": set(person.manager_of.values_list("team_id", flat=True)),
        "is_all_teams_person": bool(person.user and person.user.is_all_teams_manager),
        "saved": saved})
```

Register (`from .permissions import permissions`) and route `path("staff/<int:pk>/permissions/", views.permissions, name="permissions")`. Add the Permissions link to `profile_dialog.html`'s links block for `is_all_teams`.

`templates/people/permissions_dialog.html` — extends `_dialog.html`, title "Permissions — {{ person.name }}"; if `is_all_teams_person`, the line "Manager access: **all teams, set in Practice HR** (Login accounts › Apps › Admin of shift-central)." and no form; otherwise a `form[data-dialog-form]` with a tick box per team (`name="teams" value="{{ t.pk }}"`, checked when `t.pk in granted`), the help "Manager access lets this person build and change the team's rota and approve its leave.", `Update permissions` (dark button), and "Saved." when `saved`.

- [ ] **Step 3: Run the tests, lint and commit**

```bash
python -m pytest tests/test_permissions.py -q && ruff check . && python -m pytest -q
git add -A
git commit -m "People: manager access per team, granted from the profile"
```

---

### Task 11: Activity log and log-in logs

**Files:**
- Create: `people/views/activity.py`, `templates/people/activity.html`, `templates/people/logins.html`, `tests/test_activity.py`
- Modify: `people/views/__init__.py`, `people/urls.py`

**Interfaces:**
- Consumes: `AuditEntry`, `LoginEvent`, `access.managed_people`, `access.manager_required`, `access.all_teams_required`.
- Produces: URLs `activity` (`/activity/`), `activity-logins` (`/activity/logins/`).

- [ ] **Step 1: Write the failing tests**

`tests/test_activity.py`:

```python
import pytest
from django.test import Client

from accounts.models import LoginEvent
from people.services import profiles
from tests.factories import make_person, make_team, make_team_manager, make_user_for

pytestmark = pytest.mark.django_db


def _client(person, **kw):
    c = Client()
    c.force_login(make_user_for(person, **kw))
    return c


def test_team_managers_see_their_teams_entries_only():
    nursing = make_team("Nursing")
    lead = make_person(team=nursing)
    make_team_manager(lead, nursing)
    nurse = make_person(first_name="Nina", team=nursing)
    rec = make_person(first_name="Rec")
    boss = make_user_for(make_person(first_name="Boss"), is_all_teams_manager=True)
    profiles.update_display(boss, nurse, job_title="Nurse")
    profiles.update_display(boss, rec, job_title="Receptionist")
    body = _client(lead).get("/activity/").content.decode()
    assert "Nurse" in body and "Receptionist" not in body


def test_filters_by_person_and_field():
    boss_person = make_person(first_name="Boss")
    c = _client(boss_person, is_all_teams_manager=True)
    p = make_person(first_name="Nina")
    profiles.update_display(boss_person.user, p, job_title="Nurse", display_order=5)
    body = c.get(f"/activity/?person={p.pk}&field=job_title").content.decode()
    assert "Nurse" in body and ">5<" not in body


def test_staff_get_403():
    assert _client(make_person()).get("/activity/").status_code == 403


def test_login_logs_are_all_teams_only():
    nursing = make_team("Nursing")
    lead = make_person(team=nursing)
    make_team_manager(lead, nursing)
    boss = make_person(first_name="Boss")
    LoginEvent.objects.create(user=make_user_for(boss, is_all_teams_manager=True), ip="203.0.113.9")
    c = Client()
    c.force_login(boss.user)
    body = c.get("/activity/logins/").content.decode()
    assert "203.0.113.9" in body and boss.user.email in body
    assert _client(lead).get("/activity/logins/").status_code == 403
```

- [ ] **Step 2: Write the views and templates**

`people/views/activity.py`:

```python
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from accounts.models import LoginEvent
from people.models import AuditEntry, Person
from people.services import access


@login_required
@access.manager_required
def activity(request):
    people = access.managed_people(request.user)
    ids = list(people.values_list("pk", flat=True))
    allowance_ids = [pk for pk in Person.objects.filter(pk__in=ids).values_list("allowances__pk", flat=True) if pk]
    entries = AuditEntry.objects.filter(
        Q(model="people.person", object_id__in=ids) | Q(model="people.allowance", object_id__in=allowance_ids)
        | Q(model="people.department"))
    person = request.GET.get("person")
    if person:
        p = people.filter(pk=person).first()
        if p is None:
            entries = entries.none()
        else:
            entries = entries.filter(Q(model="people.person", object_id=p.pk)
                                     | Q(model="people.allowance",
                                         object_id__in=p.allowances.values_list("pk", flat=True)))
    field = request.GET.get("field")
    if field:
        entries = entries.filter(field=field)
    return render(request, "people/activity.html", {
        "page_title": "Activity log", "entries": entries.select_related("actor")[:500],
        "people": people.order_by("name"), "person": person or "", "field": field or "",
        "names": {p.pk: p.name for p in people}})


@login_required
@access.all_teams_required
def logins(request):
    return render(request, "people/logins.html", {
        "page_title": "Log in logs",
        "events": LoginEvent.objects.select_related("user")[:1000]})
```

Routes: `path("activity/", views.activity, name="activity")`, `path("activity/logins/", views.logins, name="activity-logins")`; register both in `people/views/__init__.py`.

`templates/people/activity.html` — extends `base.html`; a `.filters` form with a person `<select name="person">` (from `people`) and a text `field` input; a `.table` with When, Who, Record, Field, From, To, Reason. The Record column shows the person's name for `people.person` rows (`names` by `object_id`), "allowance" for allowance rows and "department" otherwise.

`templates/people/logins.html` — extends `base.html`; a `.table` with When, Who, Address, Browser.

- [ ] **Step 3: Run the tests, lint and commit**

```bash
python -m pytest tests/test_activity.py tests/test_shell.py -q && ruff check . && python -m pytest -q
git add -A
git commit -m "People: the activity log and the log-in logs"
```

---

### Task 12: The frontend toolchain and the colour picker island

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/src/main.ts`, `frontend/src/registry.ts`, `frontend/src/colour-picker.tsx`, `frontend/src/colour-picker.css`, `static/dist/main.js` (built), `static/dist/main.css` (built), `tests/test_frontend_build.py`
- Modify: `.github/workflows/tests.yml` (the `frontend` job), `templates/people/_profile_display.html` and `templates/people/department_dialog.html` (mount the component), `README.md` (develop section)

**Interfaces:**
- Produces: a component registry keyed by `data-component`; `colour-picker` reading `data-input` (the id of the hidden input it writes) and the `--swatches` token.

- [ ] **Step 1: Write the failing test**

`tests/test_frontend_build.py`:

```python
"""The committed build is what the page loads; CI rebuilds and compares.
These pin what the templates rely on."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_built_files_exist_and_register_the_colour_picker():
    js = (ROOT / "static/dist/main.js").read_text()
    assert "colour-picker" in js and "data-component" in js
    assert (ROOT / "static/dist/main.css").exists()


def test_the_build_output_has_stable_names():
    names = sorted(p.name for p in (ROOT / "static/dist").iterdir())
    assert names == ["main.css", "main.js"], "no hashed names: templates reference these directly"


def test_the_lockfile_is_committed():
    assert (ROOT / "frontend/package-lock.json").exists()
```

- [ ] **Step 2: Write the toolchain**

`frontend/package.json`:

```json
{
  "name": "shift-central-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "build": "vite build",
    "check": "tsc --noEmit",
    "dev": "vite build --watch"
  },
  "dependencies": {
    "preact": "^10.26.0"
  },
  "devDependencies": {
    "@preact/preset-vite": "^2.10.0",
    "typescript": "^5.8.0",
    "vite": "^6.3.0"
  }
}
```

`frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "jsxImportSource": "preact",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"]
  },
  "include": ["src"]
}
```

`frontend/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

// Builds into static/dist with stable names: the Django templates reference
// main.js and main.css directly, and WhiteNoise's manifest storage adds the
// cache-busting hash at collectstatic. The output is committed (README).
export default defineConfig({
  plugins: [preact()],
  build: {
    outDir: "../static/dist",
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      input: "src/main.ts",
      output: { entryFileNames: "main.js", assetFileNames: "main[extname]" },
    },
  },
});
```

`frontend/src/registry.ts`:

```ts
import { h, render, type ComponentType } from "preact";

type Props = Record<string, string>;
const components = new Map<string, ComponentType<Props>>();

export function register(name: string, component: ComponentType<Props>) {
  components.set(name, component);
}

/** Mount every [data-component] under root whose name is registered,
 *  passing its data-* attributes as props. Called on load and after a
 *  dialog is fetched (modal.js dispatches "shift-central:mounted"). */
export function mountAll(root: ParentNode = document) {
  root.querySelectorAll<HTMLElement>("[data-component]").forEach((el) => {
    if (el.dataset.mounted) return;
    const component = components.get(el.dataset.component ?? "");
    if (!component) return;
    el.dataset.mounted = "1";
    render(h(component, { ...el.dataset } as Props), el);
  });
}
```

`frontend/src/colour-picker.tsx`:

```tsx
import { useState } from "preact/hooks";
import "./colour-picker.css";

/** The swatch grid and hex field for a person's name colour and a
 *  department's colour. Writes to the hidden input named by data-input. */
export function ColourPicker({ input }: { input: string }) {
  const target = document.getElementById(input) as HTMLInputElement | null;
  const swatches = getComputedStyle(document.documentElement)
    .getPropertyValue("--swatches").split(",").map((s) => s.trim()).filter(Boolean);
  const [value, setValue] = useState(target?.value || swatches[0] || "#143D5C");

  function choose(hex: string) {
    setValue(hex);
    if (target) target.value = hex;
  }

  return (
    <div class="colour-picker">
      <div class="colour-picker-swatches" role="listbox" aria-label="Colour">
        {swatches.map((hex) => (
          <button type="button" role="option" aria-selected={hex.toUpperCase() === value.toUpperCase()}
                  class="colour-picker-swatch" style={{ background: hex }} title={hex}
                  onClick={() => choose(hex)} />
        ))}
      </div>
      <label class="colour-picker-hex">
        <span class="colour-picker-preview" style={{ background: value }} />
        <input type="text" value={value} maxLength={7} pattern="#[0-9a-fA-F]{6}" aria-label="Hex colour"
               onInput={(e) => { const v = (e.target as HTMLInputElement).value; if (/^#[0-9a-fA-F]{6}$/.test(v)) choose(v); }} />
      </label>
    </div>
  );
}
```

`frontend/src/colour-picker.css`:

```css
.colour-picker { display: flex; flex-direction: column; gap: 8px; }
.colour-picker-swatches { display: grid; grid-template-columns: repeat(9, 24px); gap: 6px; }
.colour-picker-swatch { width: 24px; height: 24px; border-radius: 4px; border: 2px solid transparent; cursor: pointer; padding: 0; }
.colour-picker-swatch[aria-selected="true"] { border-color: var(--ink); outline: 2px solid var(--white); outline-offset: -4px; }
.colour-picker-hex { display: flex; gap: 8px; align-items: center; }
.colour-picker-preview { width: 24px; height: 24px; border-radius: 4px; border: 1px solid var(--hairline); }
.colour-picker-hex input { width: 110px; font-family: ui-monospace, monospace; }
```

`frontend/src/main.ts`:

```ts
import { register, mountAll } from "./registry";
import { ColourPicker } from "./colour-picker";

register("colour-picker", ColourPicker as never);
mountAll();
document.addEventListener("shift-central:mounted", (e) => mountAll((e as CustomEvent).detail ?? document));
```

In `static/js/modal.js`, after `show()` sets `dialog.innerHTML`, dispatch `document.dispatchEvent(new CustomEvent("shift-central:mounted", { detail: dialog }))` so islands inside a fetched dialog mount.

Mount points: in `templates/people/_profile_display.html` the colour field becomes

```html
<div class="field"><label>Name colour</label>
  <input type="hidden" name="name_colour" id="id_name_colour" value="{{ form.name_colour.value|default:person.name_colour }}">
  <div data-component="colour-picker" data-input="id_name_colour"></div>
  {% if form.name_colour.errors %}<p class="field-error">{{ form.name_colour.errors.0 }}</p>{% endif %}
</div>
```

and the same shape with `id_colour` in `department_dialog.html`.

- [ ] **Step 3: Build and commit the output**

Run: `cd frontend && npm install && npm run check && npm run build && cd ..`
Expected: `static/dist/main.js` and `static/dist/main.css` written; `frontend/package-lock.json` created.

Run: `python -m pytest tests/test_frontend_build.py -q`
Expected: PASS.

- [ ] **Step 4: The CI job**

Add to `.github/workflows/tests.yml`:

```yaml
  # The committed build must be what the source produces: a stale
  # static/dist fails here, not on the VPS (which has no node).
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
        working-directory: frontend
      - run: npm run check
        working-directory: frontend
      - run: npm run build
        working-directory: frontend
      - run: git diff --exit-code -- static/dist
```

Add to `README.md`'s Develop section: "The grid and the colour picker are built from `frontend/` with Vite: `cd frontend && npm install && npm run build` writes `static/dist/`, which is committed. Run the build before committing a frontend change; CI fails on a stale bundle. `npm run dev` rebuilds on save."

- [ ] **Step 5: Lint and commit**

```bash
ruff check . && python -m pytest -q
git add -A
git commit -m "Frontend: the Vite/Preact toolchain and the colour picker, build committed"
```

---

### Task 13: Deploy units, the manage wrapper, backups, docs

**Files:**
- Create: `deploy/gunicorn.service`, `deploy/manage`, `deploy/shift-central-hr-sync.service`, `deploy/shift-central-hr-sync.timer`, `deploy/shift-central-clearsessions.service`, `deploy/shift-central-clearsessions.timer`, `deploy/shift-central-backup.service`, `deploy/shift-central-backup.timer`, `deploy/backup.sh`, `deploy/shift-central-pbs.service`, `deploy/shift-central-backup-pbs.conf`, `deploy/pbs-push.sh`, `tests/test_deploy_units.py`, `docs/admin/README.md`, `docs/admin/people.md`, `docs/admin/departments.md`, `docs/admin/access.md`, `docs/admin/sync.md`, `docs/admin/setup.md`
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

`tests/test_deploy_units.py` — copy the rota's `tests/test_deploy_units.py` and change: the expected service list to `["gunicorn.service", "shift-central-backup.service", "shift-central-clearsessions.service", "shift-central-hr-sync.service", "shift-central-pbs.service"]`; the user and group to `shift-central`; `StateDirectory` to `shift-central`; `WorkingDirectory` to `/srv/shift-central`; `EnvironmentFile` to `/etc/shift-central.env`; the `ExecStart` assertions to the commands below; and add:

```python
def test_the_sync_timer_runs_every_fifteen_minutes():
    text = (DEPLOY / "shift-central-hr-sync.timer").read_text()
    assert "OnCalendar=*-*-* *:0/15:00" in text and "Persistent=true" in text


def test_the_manage_wrapper_names_this_app():
    text = (DEPLOY / "manage").read_text()
    assert "/etc/shift-central.env" in text and "--uid=shift-central" in text
    assert "rota" not in text.replace("shift-central", "")
```

- [ ] **Step 2: Write the units**

Copy each of the rota's units and scripts (`deploy/gunicorn.service`, `rota-findmyshift.{service,timer}` → `shift-central-hr-sync.*`, `rota-clearsessions.*`, `rota-backup.*`, `backup.sh`, `rota-pbs.service`, `rota-backup-pbs.conf`, `pbs-push.sh`, `manage`) replacing: `rota` → `shift-central` in every user, group, directory, env file and unit name; the description lines to name Shift Central; the gunicorn `--bind 127.0.0.1:8323` (the rota is 8321, HR 8322 — check `/etc/systemd/system/practice-hr.service` on the VPS and pick the next free port); `ExecStart=/srv/shift-central/.venv/bin/python manage.py hr_sync` in the sync service; the environment-file comment listing `PRACTICE_HR_URL`, `HR_API_TOKEN`, `OIDC_RP_CLIENT_ID`, `OIDC_RP_CLIENT_SECRET`, `EMAIL_*` in place of the FINDMYSHIFT_* lines; `--ns shift-central --backup-id shift-central` in `pbs-push.sh`; `/etc/pbs-backup/shift-central.{env,token,key}`. Keep the sandbox block identical in every unit (the test checks it) and keep the comments: they say why each line is there.

- [ ] **Step 3: The documentation**

`README.md` — replace the placeholder with the rota's README structure: what the app is (one paragraph, linking the requirements and the spec), **Develop** (venv, `DEBUG=1 python manage.py migrate`, `runserver`, `pytest`, the frontend build), **CI** (the four jobs), **Admin guide** (link to `docs/admin/`), **First-time setup** (the order in the spec's section 7, each step one line with its command), **Deploy (VPS + Cloudflare tunnel)** (the rota's Deploy section adapted: user, directories, env file with every variable, `deploy/manage`, units, the tunnel hostname, the HR side: `register_oidc_client --name shift-central --redirect-uri https://<host>/oidc/callback/` and a token added to HR's `HR_API_TOKENS`), **Backups**, **Restore**.

`docs/admin/README.md` — one paragraph and a list linking the five pages. Each page follows the HR admin guide's shape (every field, what depends on it, what goes wrong if it is set wrong):

- `people.md` — Teams (from HR; order and active); People (what HR owns and what is typed: job title, colour, order, the three display switches, weekly hours, days per week, the two allowances per leave year, notes); the profile pop-up's tabs and who sees each; the Staff list's filters and download.
- `departments.md` — the list, colours, order, archive (never delete; spec 2's shifts reference them).
- `access.md` — the three roles, where each is set (HR's Admin of shift-central box; the Permissions link), what each can see and do (ACC-06's rows this release has data for), sessions and sign-out.
- `sync.md` — the fifteen-minute feed, what it changes and never changes, the Health card's four figures and what to do about each, Sync now, `hr_sync` by hand.
- `setup.md` — the go-live order (register the client in HR → env file → migrate → superuser → `hr_sync` → tick the four managers in HR → each signs in → grant Nursing and Pharmacy → hours, days and allowances → departments' colours), backups and restore.

- [ ] **Step 4: Run the tests, lint and commit**

```bash
python -m pytest tests/test_deploy_units.py -q && ruff check . && python -m pytest -q
git add -A
git commit -m "Deploy: the units, the manage wrapper, backups; the admin guide and README"
```

---

## Self-review

**Spec coverage.** Section 1 (apps, layout, data flow) — Tasks 1, 5. Section 2 (sign-in, binding by `employee_id`, `admin` claim, roles, `access.py`, sessions, log-in log, holding page) — Tasks 1, 3, 4. Section 3 (`Team`, `Person`, `Allowance`, `hr_sync`, `SyncRun`, Health figures, leavers kept) — Tasks 2, 5, 7. Section 4 (departments seeded and edited; `TeamManager` and the Permissions link) — Tasks 2, 9, 10. Section 5 (shell, Staff list, profile tabs, Departments page, Activity log, Health card, no Settings page, admin read-mostly, tokens, the built island) — Tasks 6, 7, 8, 9, 11, 12. Section 6 (`AuditEntry`, `record`, sync actor, note required on an allowance change) — Tasks 2, 8. Section 7 (deploy layout, env, setup order, CI with the frontend job, backups) — Tasks 1, 12, 13. Section 8 (errors never raise into a page; the test list) — each task's tests; the session-expiry test is in Task 3. Documentation — Task 13.

**Known thin spots an executor should treat as part of the task, not as optional:** the CSV download in Task 7 (described, with its test named); the `{% url %}` references that land a task later (noted inline with the stop-gap to use meanwhile); the phone layout is CSS only (the spec's section 5 asks only that this release's pages be usable on a phone).

**Type consistency.** `audit.record(actor, obj, changes, note="")` is the one signature everywhere; `access.can_manage(user, person)` and `access.managed_people(user)` are used by Tasks 7, 8, 10, 11 as defined in Task 4; `profiles.set_allowance(actor, person, leave_year, annual_hours, bank_holiday_hours, note="")` matches its form and view; `hr_sync.sync(client=None)` returns a `SyncRun` in Tasks 5 and 7; `HoursForm(data, years=…, is_gp=…)` matches its view; the dialog contract (`data-dialog`, `data-dialog-form`, JSON `{"redirect"}`) is the same in Tasks 6, 8, 9, 10.
