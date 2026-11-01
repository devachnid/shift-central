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
    "shifts",
    "messaging",
    "uploads",
    "leave",
    "absence",
    "payroll",
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
    "config.middleware.PersonRequiredMiddleware",
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

# Uploaded documents (spec 5). Outside anything the web server serves; the
# app writes here and the download view reads it. By default a "media" folder
# beside the database: /var/lib/shift-central/media in production, where
# deploy/backup.sh archives it each night with the database.
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT") or Path(DATABASES["default"]["NAME"]).parent / "media")
UPLOAD_MAX_BYTES = int(os.environ.get("UPLOAD_MAX_BYTES", str(10 * 1024 * 1024)))
OUTBOX_BODY_MONTHS = int(os.environ.get("OUTBOX_BODY_MONTHS", "12"))
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

# Web push (spec 5). Push is off unless all three are set and the key file
# exists. The private key is a file, never an environment line (a PEM folded
# onto one line arrives broken), readable by the app's group only.
VAPID_PRIVATE_KEY_FILE = os.environ.get("VAPID_PRIVATE_KEY_FILE", "").strip()
VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "").strip()
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "").strip()
# The only hosts a phone may register as its push address (the server calls
# whatever address is stored, so it must not be a person's choice of host).
# Each entry matches the host itself and its subdomains; add more here.
PUSH_ENDPOINT_HOSTS = ("fcm.googleapis.com", "push.services.mozilla.com", "push.apple.com", "notify.windows.com") + tuple(
    h.strip() for h in os.environ.get("PUSH_ENDPOINT_HOSTS", "").split(",") if h.strip())

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
        "shifts": {"level": "INFO"},
        "messaging": {"level": "INFO"},
        "uploads": {"level": "INFO"},
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
# Every sign-in asks Practice HR to check who is at the keyboard. On a shared
# surgery PC the ten-minute timeout here ends this app's session, but HR's own
# session (twelve hours, consent skipped) would otherwise sign the next person
# straight in as the last one. django-oauth-toolkit sends an authenticated
# prompt=login to its login form, which asks for the password or passkey again.
OIDC_AUTH_REQUEST_EXTRA_PARAMS = {"prompt": "login"}
# Kept so signing out can hand it to HR's sign-out as id_token_hint.
OIDC_STORE_ID_TOKEN = True
# A callback whose state is already spent (the installed Android app and the
# browser tab both loading HR's redirect) moves on instead of a 400.
OIDC_CALLBACK_CLASS = "accounts.views.CallbackView"

# The GP rota app's sessions feed (shifts/services/gp_sync.py). Both from
# /etc/shift-central.env; either empty means no GP feed, and the Health
# card says so.
ROTA_URL = os.environ.get("ROTA_URL", "").rstrip("/")
ROTA_API_TOKEN = os.environ.get("ROTA_API_TOKEN", "").strip()

# The GP leave feed the GP rota app reads (leave/views/api.py). Comma-separated
# bearer tokens; unset means nothing is served. See leave/api_auth.py.
LEAVE_API_TOKENS = frozenset(t.strip() for t in os.environ.get("LEAVE_API_TOKENS", "").split(",") if t.strip())
API_RATE_LIMIT_PER_MINUTE = int(os.environ.get("API_RATE_LIMIT_PER_MINUTE", "600"))
