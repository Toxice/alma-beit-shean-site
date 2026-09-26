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
                "reviews.views.site_url",
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

LANGUAGE_CODE = "he"
TIME_ZONE = "Asia/Jerusalem"
USE_I18N = True
USE_TZ = True

# Largest legit POST is a 1000-char review; cap bodies well below Django's 2.5 MB default.
DATA_UPLOAD_MAX_MEMORY_SIZE = 64 * 1024

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Only the owner logs in (staff user), to the themed panel at /reviews/manage/.
LOGIN_URL = "/reviews/manage/login/"
LOGIN_REDIRECT_URL = "/reviews/manage/"

if IS_PROD:
    # Railway's deploy healthcheck sends this Host header.
    ALLOWED_HOSTS.append("healthcheck.railway.app")
    # Railway terminates TLS at its proxy; trust its header so request.is_secure() is right.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365  # api subdomain only, no includeSubDomains
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
