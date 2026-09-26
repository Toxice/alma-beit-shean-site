import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# Railway sets RAILWAY_ENVIRONMENT_NAME on every deploy; locally it is absent.
IS_PROD = "RAILWAY_ENVIRONMENT_NAME" in os.environ
DEBUG = not IS_PROD
SECRET_KEY = os.environ["SECRET_KEY"] if IS_PROD else "dev-insecure-key"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS] if IS_PROD else []

# The static site allowed to read the public reviews API (CORS).
# Local default = `npx wrangler dev` port.
SITE_ORIGIN = os.environ.get("SITE_ORIGIN", "http://localhost:8787")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "reviews",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Railway: DATABASE_URL points at Railway Postgres. Locally: SQLite file.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=600
    )
}

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LANGUAGE_CODE = "he"
TIME_ZONE = "Asia/Jerusalem"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth: Google only ---
LOGIN_URL = "/reviews/login/"
LOGIN_REDIRECT_URL = "/reviews/write/"
ACCOUNT_ADAPTER = "reviews.adapters.NoSignupAccountAdapter"
SOCIALACCOUNT_ADAPTER = "reviews.adapters.GoogleSignupAdapter"
ACCOUNT_EMAIL_VERIFICATION = "none"
# No mail server: allauth's password-reset/email pages must not try SMTP (would 500).
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS = False
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "APP": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "key": "",
        },
    }
}

if IS_PROD:
    # Railway's deploy healthcheck sends this Host header.
    ALLOWED_HOSTS.append("healthcheck.railway.app")
    # Railway terminates TLS at its proxy; trust its header so OAuth callback URLs are https.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
