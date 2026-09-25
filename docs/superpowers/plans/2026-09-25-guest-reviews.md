# Guest Recommendations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a guest recommendations section to the Alma site: guests sign in with Google on a small Django backend, submit text + stay month/year, owner approves in Django admin, approved reviews appear as cards on the static site.

**Architecture:** The static site (`site/`, Cloudflare Workers static assets) stays as is and gains one section that `fetch()`es `GET https://api.alma-hosting.co.il/api/reviews/`. A new Django project in `backend/` runs on Railway with Railway Postgres; it owns Google login (django-allauth), the write form (server-rendered), and the admin. The write flow lives entirely on the API domain, so no cross-site cookies or cross-origin POSTs.

**Tech Stack:** Python 3.13, Django 5.2 LTS, django-allauth (Google provider), dj-database-url, psycopg 3, gunicorn, whitenoise, Railway + Railway Postgres, vanilla JS/CSS on the static site.

**Spec:** `docs/superpowers/specs/2026-09-25-guest-reviews-design.md`

## Before You Start (decide with the owner)

- The old `django-major-update` branch (Django CMS) was deleted on 2026-09-25; this plan builds on master's static site. Its leftover untracked folders were deleted too.
- `git push` from this machine failed on 2026-09-25 (credentials are for GitHub user `ben-bershit`, no write access to `Toxice/alma-beit-shean-site`). Fix credentials before Task 5.
- The repo root holds many **untracked** files (screenshots, notes). **Never use `git add -A` / `git add .`** — only the explicit paths listed in each commit step.

## Global Constraints

- Sign-in: **Google only**. Local username/password signup must be closed.
- Review fields: `text` 10–1000 chars, `stay_month` 1–12, `stay_year` 2020–current year; stay date not in the future.
- New reviews: `is_approved=False`. Public API returns only approved reviews.
- Public API payload keys exactly: `name`, `avatar`, `text`, `stay_month`, `stay_year`. No email, no user id.
- Review text and names rendered on the site with `textContent` only. Never `innerHTML`.
- Secrets (`SECRET_KEY`, `GOOGLE_CLIENT_SECRET`) only in Railway variables / local env. Never committed.
- Production API domain: `https://api.alma-hosting.co.il`. Site origin: `https://alma-hosting.co.il`.
- UI copy (Hebrew, RTL): kicker "המלצות", title "מה האורחים שלנו מספרים", meta "התארחו ב<חודש> <שנה>", buttons "כתבו המלצה" / "עוד המלצות", empty "עוד אין המלצות באתר — היו הראשונים להמליץ!", thanks "תודה! ההמלצה תפורסם לאחר אישור", consent "השם והתמונה מחשבון Google שלכם יוצגו ליד ההמלצה".
- Work on branch `feature/guest-reviews`.

## Review Focus

1. **Stored XSS**: a review whose text is `<img src=x onerror=alert(1)>` must display as literal text on the site. (Task 4, Step 4 manual check.)
2. **API down / CORS wrong**: the reviews section stays hidden and the rest of the page works; no console-breaking error elsewhere. (Task 4, Step 5.)
3. **Future or out-of-range stay date**: rejected by the form with a Hebrew error, nothing saved. (Task 1 model tests + Task 3 view test.)
4. **Personal data leak**: API returns no email or user id. (Task 2 exact-keys test.)
5. **Back-door local signup** at `/accounts/signup/`: must show "signup closed". (Task 3 test.)

## File Structure

```
backend/
  manage.py                 Django entry point
  requirements.txt          pinned deps
  .python-version           3.13 (Railway/Railpack reads it)
  railway.json              start + pre-deploy commands
  config/
    __init__.py
    settings.py             env-driven settings (local = SQLite/DEBUG, Railway = Postgres/secure)
    urls.py                 admin, allauth, reviews
    wsgi.py
  reviews/
    __init__.py
    apps.py
    models.py               Review model + validation
    admin.py                approve with one click (list_editable)
    adapters.py             close local signup, keep Google signup open
    forms.py                ReviewForm (text, month, year selects)
    views.py                reviews_api, login_page, write_review, thanks
    urls.py
    tests.py
    migrations/             generated
  templates/reviews/
    base.html               RTL page shell in Alma colors
    login.html              "sign in with Google" button
    write.html              review form
    thanks.html             confirmation
site/
  index.html                + reviews section, + <script src="reviews.js">
  styles.css                + reviews block
  reviews.js                fetch + render cards (new)
.gitignore                  + backend artifacts
```

---

### Task 1: Django project scaffold + Review model + admin

**Files:**
- Create: `backend/manage.py`, `backend/requirements.txt`, `backend/.python-version`, `backend/config/__init__.py`, `backend/config/settings.py`, `backend/config/urls.py`, `backend/config/wsgi.py`, `backend/reviews/__init__.py`, `backend/reviews/apps.py`, `backend/reviews/models.py`, `backend/reviews/admin.py`, `backend/reviews/adapters.py`, `backend/reviews/urls.py`, `backend/reviews/tests.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `reviews.models.Review` with fields `user, author_name, avatar_url, text, stay_month, stay_year, is_approved, created_at`; `reviews.models.FIRST_YEAR = 2020`; default ordering newest stay first. `settings.SITE_ORIGIN` (str). `reviews/urls.py` with `app_name = "reviews"` (routes added in Tasks 2–3).

- [ ] **Step 1: Create branch and install deps**

```powershell
git checkout -b feature/guest-reviews
```

`backend/requirements.txt`:
```
Django>=5.2.8,<5.3
django-allauth[socialaccount]>=65.0
dj-database-url>=2.2
psycopg[binary]>=3.2
gunicorn>=23.0
whitenoise>=6.7
```

`backend/.python-version`:
```
3.13
```

```powershell
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

- [ ] **Step 2: Write project files**

`backend/manage.py`:
```python
#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
```

`backend/config/__init__.py`: empty file.

`backend/config/wsgi.py`:
```python
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
application = get_wsgi_application()
```

`backend/config/settings.py`:
```python
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
    # Railway terminates TLS at its proxy; trust its header so OAuth callback URLs are https.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    ACCOUNT_DEFAULT_HTTP_PROTOCOL = "https"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }
```

`backend/config/urls.py`:
```python
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "עלמה – ניהול המלצות"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("reviews.urls")),
]
```

`backend/reviews/__init__.py`: empty file.

`backend/reviews/apps.py`:
```python
from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    name = "reviews"
    verbose_name = "המלצות"
```

`backend/reviews/adapters.py`:
```python
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class NoSignupAccountAdapter(DefaultAccountAdapter):
    """No local username/password accounts. Google is the only way in."""

    def is_open_for_signup(self, request):
        return False


class GoogleSignupAdapter(DefaultSocialAccountAdapter):
    """Social signup would otherwise inherit the closed account adapter."""

    def is_open_for_signup(self, request, sociallogin):
        return True
```

`backend/reviews/urls.py` (routes added in Tasks 2–3):
```python
app_name = "reviews"

urlpatterns = []
```

`.gitignore` — append:
```
__pycache__/
backend/db.sqlite3
backend/staticfiles/
```

- [ ] **Step 3: Write the failing model tests**

`backend/reviews/tests.py`:
```python
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from reviews.models import Review


def make_user(username="guest"):
    return get_user_model().objects.create_user(username=username)


def make_review(user, **overrides):
    fields = dict(
        user=user,
        author_name="דנה כהן",
        avatar_url="https://lh3.googleusercontent.com/a/photo",
        text="היה מקסים, נקי ושקט. נחזור!",
        stay_month=8,
        stay_year=2025,
    )
    fields.update(overrides)
    return Review(**fields)


class ReviewModelTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_valid_review_passes_and_defaults_to_pending(self):
        review = make_review(self.user)
        review.full_clean()
        review.save()
        self.assertFalse(review.is_approved)

    def test_future_stay_date_rejected(self):
        today = date.today()
        year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        with self.assertRaises(ValidationError):
            make_review(self.user, stay_year=year, stay_month=month).full_clean()

    def test_current_month_allowed(self):
        today = date.today()
        make_review(self.user, stay_year=today.year, stay_month=today.month).full_clean()

    def test_text_too_short_rejected(self):
        with self.assertRaises(ValidationError):
            make_review(self.user, text="קצר").full_clean()

    def test_text_too_long_rejected(self):
        with self.assertRaises(ValidationError):
            make_review(self.user, text="א" * 1001).full_clean()

    def test_month_out_of_range_rejected(self):
        with self.assertRaises(ValidationError):
            make_review(self.user, stay_month=13).full_clean()

    def test_year_before_first_year_rejected(self):
        with self.assertRaises(ValidationError):
            make_review(self.user, stay_year=2019).full_clean()

    def test_ordering_newest_stay_first(self):
        make_review(self.user, stay_year=2024, stay_month=5).save()
        make_review(self.user, stay_year=2025, stay_month=1).save()
        make_review(self.user, stay_year=2024, stay_month=11).save()
        got = [(r.stay_year, r.stay_month) for r in Review.objects.all()]
        self.assertEqual(got, [(2025, 1), (2024, 11), (2024, 5)])
```

- [ ] **Step 4: Run tests to verify they fail**

Run (from `backend/`): `python manage.py test reviews -v 2`
Expected: FAIL / ImportError — `cannot import name 'Review' from 'reviews.models'`.

- [ ] **Step 5: Write the model and admin**

`backend/reviews/models.py`:
```python
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
)
from django.db import models

FIRST_YEAR = 2020


class Review(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    # Snapshot of the Google profile at submit time.
    author_name = models.CharField("שם", max_length=100)
    avatar_url = models.URLField("תמונה", max_length=500, blank=True)
    # TextField max_length is not enforced by model validation, hence the validator.
    text = models.TextField(
        "המלצה",
        max_length=1000,
        validators=[MinLengthValidator(10), MaxLengthValidator(1000)],
    )
    stay_month = models.PositiveSmallIntegerField(
        "חודש שהות", validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    stay_year = models.PositiveSmallIntegerField(
        "שנת שהות", validators=[MinValueValidator(FIRST_YEAR)]
    )
    is_approved = models.BooleanField("מאושר לפרסום", default=False)
    created_at = models.DateTimeField("נשלח", auto_now_add=True)

    class Meta:
        ordering = ["-stay_year", "-stay_month", "-created_at"]
        verbose_name = "המלצה"
        verbose_name_plural = "המלצות"

    def clean(self):
        today = date.today()
        if self.stay_year and self.stay_month:
            if (self.stay_year, self.stay_month) > (today.year, today.month):
                raise ValidationError("תאריך השהות לא יכול להיות בעתיד.")

    def __str__(self):
        return f"{self.author_name} ({self.stay_month}/{self.stay_year})"
```

`backend/reviews/admin.py`:
```python
from django.contrib import admin

from reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("author_name", "short_text", "stay_month", "stay_year", "created_at", "is_approved")
    list_editable = ("is_approved",)
    list_filter = ("is_approved",)
    search_fields = ("author_name", "text")
    readonly_fields = ("user", "created_at")

    @admin.display(description="המלצה")
    def short_text(self, obj):
        return obj.text[:60] + ("…" if len(obj.text) > 60 else "")
```

```powershell
cd backend
python manage.py makemigrations reviews
```

- [ ] **Step 6: Run tests + checks**

Run: `python manage.py check` — Expected: `System check identified no issues`. If allauth reports a missing setting/app (versions differ), fix per its message before continuing.
Run: `python manage.py test reviews -v 2` — Expected: 8 tests PASS.

- [ ] **Step 7: Commit**

```powershell
git add .gitignore backend/manage.py backend/requirements.txt backend/.python-version backend/config backend/reviews
git commit -m "Add Django backend with Review model and admin"
```

---

### Task 2: Public reviews API

**Files:**
- Create: `backend/reviews/views.py`
- Modify: `backend/reviews/urls.py`, `backend/reviews/tests.py`

**Interfaces:**
- Consumes: `Review`, `settings.SITE_ORIGIN`.
- Produces: `GET /api/reviews/` (url name `reviews:api`) → `{"reviews": [{"name": str, "avatar": str, "text": str, "stay_month": int, "stay_year": int}, ...]}`, header `Access-Control-Allow-Origin: <SITE_ORIGIN>`, `Cache-Control: public, max-age=300`. Task 4's JS consumes this exact shape.

- [ ] **Step 1: Write the failing tests** — append to `backend/reviews/tests.py`:

```python
from django.test import override_settings
from django.urls import reverse


@override_settings(SITE_ORIGIN="https://alma-hosting.co.il")
class ReviewsApiTests(TestCase):
    def setUp(self):
        user = make_user()
        make_review(user, text="מאושרת ומומלצת מאוד", is_approved=True).save()
        make_review(user, text="ממתינה לאישור עדיין").save()

    def test_returns_only_approved(self):
        data = self.client.get(reverse("reviews:api")).json()
        self.assertEqual([r["text"] for r in data["reviews"]], ["מאושרת ומומלצת מאוד"])

    def test_payload_has_exact_keys_no_personal_data(self):
        review = self.client.get(reverse("reviews:api")).json()["reviews"][0]
        self.assertEqual(set(review), {"name", "avatar", "text", "stay_month", "stay_year"})

    def test_cors_header_allows_only_site_origin(self):
        response = self.client.get(reverse("reviews:api"))
        self.assertEqual(response["Access-Control-Allow-Origin"], "https://alma-hosting.co.il")

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post(reverse("reviews:api")).status_code, 405)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test reviews -v 2`
Expected: FAIL — `NoReverseMatch: 'api' is not a valid view function or pattern name`.

- [ ] **Step 3: Implement**

`backend/reviews/views.py`:
```python
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from reviews.models import Review


@require_GET
def reviews_api(request):
    reviews = [
        {
            "name": r.author_name,
            "avatar": r.avatar_url,
            "text": r.text,
            "stay_month": r.stay_month,
            "stay_year": r.stay_year,
        }
        for r in Review.objects.filter(is_approved=True)
    ]
    response = JsonResponse({"reviews": reviews})
    response["Access-Control-Allow-Origin"] = settings.SITE_ORIGIN
    response["Cache-Control"] = "public, max-age=300"
    return response
```

`backend/reviews/urls.py`:
```python
from django.urls import path

from reviews import views

app_name = "reviews"

urlpatterns = [
    path("api/reviews/", views.reviews_api, name="api"),
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python manage.py test reviews -v 2` — Expected: 12 tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/reviews/views.py backend/reviews/urls.py backend/reviews/tests.py
git commit -m "Add public approved-reviews JSON API with CORS for the site"
```

---

### Task 3: Google sign-in + write review flow

**Files:**
- Create: `backend/reviews/forms.py`, `backend/templates/reviews/base.html`, `backend/templates/reviews/login.html`, `backend/templates/reviews/write.html`, `backend/templates/reviews/thanks.html`
- Modify: `backend/reviews/views.py`, `backend/reviews/urls.py`, `backend/reviews/tests.py`

**Interfaces:**
- Consumes: `Review`, `FIRST_YEAR`, allauth Google provider, `settings.SITE_ORIGIN`.
- Produces: `/reviews/login/` (`reviews:login`), `/reviews/write/` (`reviews:write`, login required), `/reviews/thanks/` (`reviews:thanks`). Task 4's "כתבו המלצה" button links to `/reviews/write/`.

- [ ] **Step 1: Write the failing tests** — append to `backend/reviews/tests.py`:

```python
from allauth.socialaccount.models import SocialAccount


class WriteReviewTests(TestCase):
    def setUp(self):
        self.user = make_user("googler")
        SocialAccount.objects.create(
            user=self.user,
            provider="google",
            uid="123",
            extra_data={"name": "נועה לוי", "picture": "https://lh3.googleusercontent.com/a/noa"},
        )

    def test_anonymous_redirected_to_login_page(self):
        response = self.client.get(reverse("reviews:write"))
        self.assertRedirects(response, "/reviews/login/?next=/reviews/write/", fetch_redirect_response=False)

    def test_login_page_offers_google(self):
        response = self.client.get(reverse("reviews:login"))
        self.assertContains(response, "/accounts/google/login/")

    def test_submit_creates_pending_review_with_google_identity(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("reviews:write"),
            {"text": "חופשה נהדרת, המקום מאובזר ונקי.", "stay_month": 7, "stay_year": 2025},
        )
        self.assertRedirects(response, reverse("reviews:thanks"))
        review = Review.objects.get()
        self.assertEqual(review.author_name, "נועה לוי")
        self.assertEqual(review.avatar_url, "https://lh3.googleusercontent.com/a/noa")
        self.assertEqual(review.user, self.user)
        self.assertFalse(review.is_approved)

    def test_future_date_shows_error_and_saves_nothing(self):
        self.client.force_login(self.user)
        today = date.today()
        response = self.client.post(
            reverse("reviews:write"),
            {"text": "חופשה נהדרת, המקום מאובזר ונקי.", "stay_month": 12, "stay_year": today.year + 1},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Review.objects.exists())

    def test_thanks_page(self):
        self.assertContains(self.client.get(reverse("reviews:thanks")), "תודה! ההמלצה תפורסם לאחר אישור")


class SignupClosedTests(TestCase):
    def test_local_signup_is_closed(self):
        response = self.client.get("/accounts/signup/")
        self.assertTemplateUsed(response, "account/signup_closed.html")
```

Note: the future-date test posts `stay_year = today.year + 1`, which is also outside the year `<select>` choices, so the form rejects it either way; the model's `clean()` future check is covered in Task 1 tests.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test reviews -v 2`
Expected: FAIL — `NoReverseMatch` for `reviews:write` / `reviews:login` / `reviews:thanks`. `SignupClosedTests` may already pass (adapter from Task 1) — that is fine.

- [ ] **Step 3: Implement the form**

`backend/reviews/forms.py`:
```python
from datetime import date

from django import forms

from reviews.models import FIRST_YEAR, Review

HEBREW_MONTHS = [
    "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
    "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
]


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["text", "stay_month", "stay_year"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 6, "maxlength": 1000, "minlength": 10}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stay_month"].widget = forms.Select(
            choices=[(i, name) for i, name in enumerate(HEBREW_MONTHS, start=1)]
        )
        years = range(date.today().year, FIRST_YEAR - 1, -1)
        self.fields["stay_year"].widget = forms.Select(choices=[(y, y) for y in years])
```

- [ ] **Step 4: Implement the views and urls**

Append to `backend/reviews/views.py`:
```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from reviews.forms import ReviewForm


def google_identity(user):
    """Name + photo from the user's Google account, never the email."""
    account = user.socialaccount_set.filter(provider="google").first()
    data = account.extra_data if account else {}
    name = data.get("name") or user.get_full_name() or "אורח/ת"
    return name[:100], data.get("picture", "")


def login_page(request):
    if request.user.is_authenticated:
        return redirect("reviews:write")
    next_url = request.GET.get("next", "/reviews/write/")
    return render(request, "reviews/login.html", {"next": next_url, "site_url": settings.SITE_ORIGIN})


@login_required
def write_review(request):
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.user = request.user
        review.author_name, review.avatar_url = google_identity(request.user)
        review.save()
        return redirect("reviews:thanks")
    name, avatar = google_identity(request.user)
    return render(
        request,
        "reviews/write.html",
        {"form": form, "name": name, "avatar": avatar, "site_url": settings.SITE_ORIGIN},
    )


def thanks(request):
    return render(request, "reviews/thanks.html", {"site_url": settings.SITE_ORIGIN})
```

`backend/reviews/urls.py`:
```python
from django.urls import path

from reviews import views

app_name = "reviews"

urlpatterns = [
    path("api/reviews/", views.reviews_api, name="api"),
    path("reviews/login/", views.login_page, name="login"),
    path("reviews/write/", views.write_review, name="write"),
    path("reviews/thanks/", views.thanks, name="thanks"),
]
```

- [ ] **Step 5: Write the templates**

`backend/templates/reviews/base.html`:
```html
<!doctype html>
<html lang="he" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{% block title %}המלצה – עלמה{% endblock %}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Rubik:wght@400;500;700&family=Secular+One&display=swap" rel="stylesheet">
  <style>
    :root{--bg:hsl(30 25% 94%);--fg:hsl(25 30% 15%);--card:hsl(30 20% 90%);--muted:hsl(25 20% 38%);
      --border:hsl(25 20% 78%);--primary:hsl(25 65% 45%);--radius:1rem;--shadow:0 18px 36px -12px hsla(25,30%,20%,.16);}
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);color:var(--fg);font-family:"Rubik","Segoe UI",sans-serif;line-height:1.6;
      min-height:100vh;display:grid;place-items:center;padding:20px}
    .panel{width:100%;max-width:520px;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
      box-shadow:var(--shadow);padding:2rem 1.6rem;text-align:center}
    h1{font-family:"Secular One","Segoe UI",sans-serif;font-weight:400;font-size:1.7rem;margin:0 0 .6rem}
    p{margin:.4rem 0 1.2rem;color:var(--muted)}
    .btn{display:inline-flex;align-items:center;gap:.6rem;padding:.8rem 1.5rem;border-radius:999px;font:inherit;
      font-weight:700;border:1px solid var(--border);background:#fff;color:var(--fg);cursor:pointer;text-decoration:none}
    .btn-primary{background:var(--fg);color:#fff;border-color:var(--fg)}
    .avatar{width:64px;height:64px;border-radius:50%;object-fit:cover;margin:0 auto .5rem;display:block}
    form{text-align:right}
    label{display:block;font-weight:700;margin:.9rem 0 .3rem}
    textarea,select{width:100%;font:inherit;padding:.7rem;border:1px solid var(--border);border-radius:.6rem;background:#fff}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:.8rem}
    .errors{color:#a4262c;font-size:.92rem}
    .actions{text-align:center;margin-top:1.4rem}
    .back{display:inline-block;margin-top:1rem;color:var(--muted)}
  </style>
</head>
<body>
  <main class="panel">{% block content %}{% endblock %}</main>
</body>
</html>
```

`backend/templates/reviews/login.html`:
```html
{% extends "reviews/base.html" %}
{% load socialaccount %}
{% block content %}
  <h1>כתבו המלצה על עלמה</h1>
  <p>כדי שנדע מי כתב, התחברו עם חשבון Google.<br>השם והתמונה מחשבון Google שלכם יוצגו ליד ההמלצה.</p>
  <form method="post" action="{% provider_login_url 'google' next=next %}" style="text-align:center">
    {% csrf_token %}
    <button type="submit" class="btn">
      <svg width="20" height="20" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3.1l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 38.2 44 33 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>
      התחברות עם Google
    </button>
  </form>
  <a class="back" href="{{ site_url }}">חזרה לאתר</a>
{% endblock %}
```

`backend/templates/reviews/write.html`:
```html
{% extends "reviews/base.html" %}
{% block content %}
  {% if avatar %}<img class="avatar" src="{{ avatar }}" alt="" referrerpolicy="no-referrer">{% endif %}
  <h1>שלום {{ name }}</h1>
  <p>השם והתמונה מחשבון Google שלכם יוצגו ליד ההמלצה.</p>
  <form method="post">
    {% csrf_token %}
    {% if form.non_field_errors %}<div class="errors">{{ form.non_field_errors }}</div>{% endif %}
    <label for="{{ form.text.id_for_label }}">ההמלצה שלכם</label>
    {{ form.text }}
    {% if form.text.errors %}<div class="errors">{{ form.text.errors }}</div>{% endif %}
    <div class="row">
      <div>
        <label for="{{ form.stay_month.id_for_label }}">חודש השהות</label>
        {{ form.stay_month }}
      </div>
      <div>
        <label for="{{ form.stay_year.id_for_label }}">שנה</label>
        {{ form.stay_year }}
        {% if form.stay_year.errors %}<div class="errors">{{ form.stay_year.errors }}</div>{% endif %}
      </div>
    </div>
    <div class="actions"><button type="submit" class="btn btn-primary">שליחת ההמלצה</button></div>
  </form>
  <a class="back" href="{{ site_url }}">חזרה לאתר</a>
{% endblock %}
```

`backend/templates/reviews/thanks.html`:
```html
{% extends "reviews/base.html" %}
{% block content %}
  <h1>תודה! ההמלצה תפורסם לאחר אישור</h1>
  <p>שמחנו לארח אתכם בעלמה.</p>
  <a class="btn btn-primary" href="{{ site_url }}">חזרה לאתר</a>
{% endblock %}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python manage.py test reviews -v 2` — Expected: 18 tests PASS.

- [ ] **Step 7: Manual check of the pages (no Google keys needed)**

```powershell
python manage.py migrate
python manage.py runserver
```
Open `http://localhost:8000/reviews/login/` — Google button visible, RTL, Alma colors. (Real Google login is verified in Task 5.)

- [ ] **Step 8: Commit**

```powershell
git add backend/reviews backend/templates
git commit -m "Add Google sign-in and write-review flow with pending approval"
```

---

### Task 4: Reviews section on the static site

**Files:**
- Create: `site/reviews.js`
- Modify: `site/index.html` (insert section before the FAQ `<section>` — the one containing `שאלות נפוצות`; add script tag after `<script src="script.js"></script>`), `site/styles.css` (append block)

**Interfaces:**
- Consumes: `GET {API}/api/reviews/` shape from Task 2; `{API}/reviews/write/` from Task 3.
- Produces: nothing downstream.

- [ ] **Step 1: Add the section HTML**

Insert in `site/index.html` immediately before `<section class="wrap">` that contains `<span class="kicker" ...>שאלות נפוצות</span>`:
```html
  <section class="wrap" id="reviews" hidden>
    <div class="section-head">
      <span class="kicker" style="font-size:clamp(1.6rem,3.4vw,2.3rem);color:hsl(var(--foreground));">המלצות</span>
      <h2>מה האורחים שלנו מספרים</h2>
    </div>
    <p class="reviews-empty" data-reviews-empty hidden>עוד אין המלצות באתר — היו הראשונים להמליץ!</p>
    <div class="reviews-grid" data-reviews-grid></div>
    <div class="reviews-actions">
      <button type="button" class="btn btn-outline" data-reviews-more hidden>עוד המלצות</button>
      <a class="btn btn-primary" data-reviews-write href="https://api.alma-hosting.co.il/reviews/write/">כתבו המלצה</a>
    </div>
  </section>
```

After `<script src="script.js"></script>` add:
```html
<script src="reviews.js"></script>
```

- [ ] **Step 2: Add the JS**

`site/reviews.js`:
```js
(function () {
  var section = document.getElementById('reviews');
  if (!section) return;

  var local = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  var API = local ? 'http://localhost:8000' : 'https://api.alma-hosting.co.il';
  var PAGE = 6;
  var grid = section.querySelector('[data-reviews-grid]');
  var more = section.querySelector('[data-reviews-more]');
  var empty = section.querySelector('[data-reviews-empty]');

  section.querySelectorAll('[data-reviews-write]').forEach(function (a) {
    a.href = API + '/reviews/write/';
  });

  // textContent only: review text comes from users (stored-XSS guard).
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  }

  function initials(name) {
    return name.trim().split(/\s+/).slice(0, 2).map(function (w) { return w.charAt(0); }).join('');
  }

  function avatar(review) {
    var fallback = el('span', 'review-avatar review-initials', initials(review.name));
    if (!review.avatar) return fallback;
    var img = el('img', 'review-avatar');
    img.alt = '';
    img.loading = 'lazy';
    img.referrerPolicy = 'no-referrer'; // Google photo URLs can 403 with a referrer
    img.addEventListener('error', function () { img.replaceWith(fallback); });
    img.src = review.avatar;
    return img;
  }

  function stayLabel(month, year) {
    return 'התארחו ב' + new Date(year, month - 1, 1).toLocaleDateString('he-IL', { month: 'long', year: 'numeric' });
  }

  function card(review) {
    var article = el('article', 'review-card');
    article.append(
      avatar(review),
      el('h3', 'review-name', review.name),
      el('p', 'review-meta', stayLabel(review.stay_month, review.stay_year)),
      el('p', 'review-text', review.text)
    );
    return article;
  }

  fetch(API + '/api/reviews/')
    .then(function (res) {
      if (!res.ok) throw new Error('reviews ' + res.status);
      return res.json();
    })
    .then(function (data) {
      var list = data.reviews;
      if (!list.length) empty.hidden = false;
      list.forEach(function (review, i) {
        var c = card(review);
        if (i >= PAGE) c.hidden = true;
        grid.append(c);
      });
      if (list.length > PAGE) {
        more.hidden = false;
        grid.classList.add('is-collapsed');
        more.addEventListener('click', function () {
          grid.querySelectorAll('.review-card[hidden]').forEach(function (c) { c.hidden = false; });
          grid.classList.remove('is-collapsed');
          more.hidden = true;
        });
      }
      section.hidden = false;
    })
    .catch(function () {
      section.hidden = true; // API down: hide the section, rest of the site unaffected
    });
})();
```

- [ ] **Step 3: Add the CSS** — append to `site/styles.css`:

```css
/* ---------- reviews ---------- */
.reviews-grid{position:relative;display:grid;grid-template-columns:repeat(3,1fr);gap:1.2rem;align-items:start;}
.review-card{
  background:hsl(var(--card));
  border:1px solid hsl(var(--border));
  border-radius:var(--radius);
  box-shadow:var(--shadow-card);
  padding:1.6rem 1.4rem;
  text-align:center;
}
.review-avatar{width:56px;height:56px;border-radius:50%;object-fit:cover;margin:0 auto .7rem;}
.review-initials{
  display:flex;align-items:center;justify-content:center;
  background:hsl(var(--primary));color:hsl(var(--primary-foreground));
  font-weight:700;font-size:1.2rem;
}
.review-name{font-family:var(--font-body);font-weight:700;font-size:1.08rem;}
.review-meta{margin:.2rem 0 .8rem;color:hsl(var(--muted-foreground));font-size:.85rem;}
.review-text{margin:0;font-size:.97rem;line-height:1.75;}
.reviews-grid.is-collapsed::after{
  content:"";position:absolute;inset-inline:0;bottom:0;height:120px;pointer-events:none;
  background:linear-gradient(to bottom, hsla(30,25%,94%,0), hsl(var(--background)));
}
.reviews-empty{text-align:center;color:hsl(var(--muted-foreground));font-size:1.05rem;}
.reviews-actions{display:flex;flex-wrap:wrap;justify-content:center;gap:.8rem;margin-top:1.6rem;}
.btn-outline{background:transparent;color:hsl(var(--foreground));border-color:hsl(var(--border-strong));}
@media (max-width:820px){ .reviews-grid{grid-template-columns:repeat(2,1fr);} }
@media (max-width:560px){ .reviews-grid{grid-template-columns:1fr;} }
```

- [ ] **Step 4: Manual check with seeded data (includes XSS check)**

Terminal 1 (from `backend/`):
```powershell
python manage.py migrate
python manage.py shell -c "from django.contrib.auth.models import User; from reviews.models import Review; u,_=User.objects.get_or_create(username='seed'); [Review.objects.create(user=u, author_name=f'אורח {i}', avatar_url='' if i%2 else 'https://invalid.example/x.jpg', text='חופשה מקסימה, נקי ושקט, ממליצים בחום! '*(1+i%3), stay_month=1+i%12, stay_year=2025, is_approved=True) for i in range(8)]; Review.objects.create(user=u, author_name='<b>bold</b>', text='<img src=x onerror=alert(1)> test', stay_month=1, stay_year=2025, is_approved=True)"
python manage.py runserver
```
Terminal 2 (repo root): `npx wrangler dev` → open `http://localhost:8787/#reviews`.

Expected:
- Section between attractions and FAQ; 3 columns; 6 cards visible, bottom fade, "עוד המלצות" button; click reveals all 9 and removes fade.
- Card with `<img src=x onerror=alert(1)> test` shows that literal text, **no alert**. Name `<b>bold</b>` shows literally.
- Broken avatar URLs show initials circles.
- Meta line reads e.g. "התארחו בינואר 2025".
- Resize to 800px → 2 columns; 400px → 1 column.
- "כתבו המלצה" href is `http://localhost:8000/reviews/write/`.

- [ ] **Step 5: Manual check — API down and empty state**

- Stop `runserver`, reload page → reviews section absent; carousel, a11y widget, WhatsApp button still work.
- Start `runserver`, run `python manage.py shell -c "from reviews.models import Review; Review.objects.all().delete()"`, reload → section shows empty message + "כתבו המלצה" only.

- [ ] **Step 6: Run link checker and commit**

Run: `node check-links.js` — Expected: no new broken links.

```powershell
git add site/index.html site/styles.css site/reviews.js
git commit -m "Add guest recommendations section to the site"
```

---

### Task 5: Deploy — Google OAuth, Railway + Postgres, DNS

Mostly dashboard steps the owner performs; the agent guides and verifies.

**Files:**
- Create: `backend/railway.json`

- [ ] **Step 1: Railway config file**

`backend/railway.json`:
```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "deploy": {
    "preDeployCommand": ["python manage.py migrate --noinput"],
    "startCommand": "python manage.py collectstatic --noinput && gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 2",
    "healthcheckPath": "/api/reviews/"
  }
}
```
(`collectstatic` runs in the start command, not pre-deploy: pre-deploy runs in a separate container whose files are discarded.)

```powershell
git add backend/railway.json
git commit -m "Add Railway deploy config"
git push -u origin feature/guest-reviews
```

- [ ] **Step 2: Google OAuth client** (console.cloud.google.com, owner's Google account)

1. Create project "Alma Reviews".
2. Google Auth Platform → Branding: app name "עלמה", support email, authorized domain `alma-hosting.co.il`, homepage `https://alma-hosting.co.il`.
3. Audience: External → **Publish app** (In production). In "Testing" only listed test users can sign in. Basic scopes (`profile`, `email`) need no Google verification.
4. Clients → Create client → Web application. Authorized redirect URIs:
   - `https://api.alma-hosting.co.il/accounts/google/login/callback/`
   - `http://localhost:8000/accounts/google/login/callback/`
5. Copy Client ID + Client secret (keep secret out of git and chat).

Local real-login test (optional): set `$env:GOOGLE_CLIENT_ID` / `$env:GOOGLE_CLIENT_SECRET` in the terminal, `runserver`, open `http://localhost:8000/reviews/write/`, sign in, submit → thanks page; review appears in `/admin/` as not approved.

- [ ] **Step 3: Railway project + Postgres** (railway.com)

1. New Project → Deploy from GitHub repo → this repo, branch `feature/guest-reviews` (switch to `master` after merge). Service Settings → **Root Directory** = `backend`.
2. In the same project: `+ New` → Database → **PostgreSQL**.
3. Django service → Variables:
   ```
   DATABASE_URL = ${{Postgres.DATABASE_URL}}
   SECRET_KEY = <output of: python -c "import secrets; print(secrets.token_urlsafe(50))">
   ALLOWED_HOSTS = api.alma-hosting.co.il
   SITE_ORIGIN = https://alma-hosting.co.il
   GOOGLE_CLIENT_ID = <from Step 2>
   GOOGLE_CLIENT_SECRET = <from Step 2>
   ```
4. Deploy; logs must show migrations applied and gunicorn listening.

- [ ] **Step 4: Custom domain + DNS**

1. Django service → Settings → Networking → Custom Domain → `api.alma-hosting.co.il`.
2. Cloudflare DNS for `alma-hosting.co.il`: add every record Railway shows (CNAME `api` → target; TXT verification if shown). Set the CNAME to **DNS only** (grey cloud).
3. Wait until Railway shows the domain as active (certificate issued).

- [ ] **Step 5: Admin user**

```powershell
railway login
railway link          # pick the project + Django service
railway ssh
python manage.py createsuperuser
```

- [ ] **Step 6: Production smoke test**

```powershell
curl.exe -i https://api.alma-hosting.co.il/api/reviews/
```
Expected: `200`, body `{"reviews": []}`, header `Access-Control-Allow-Origin: https://alma-hosting.co.il`.

Then:
1. Merge `feature/guest-reviews` into `master` and push (site deploys via the existing Cloudflare flow; switch Railway's branch to `master`).
2. On `https://alma-hosting.co.il` → reviews section shows empty state → "כתבו המלצה" → Google sign-in → submit → thanks page.
3. `https://api.alma-hosting.co.il/admin/` → tick "מאושר לפרסום" → Save.
4. Within 5 minutes (API cache) the card appears on the live site with Google name + photo.

---

## Self-Review Notes

- Spec coverage: Google-only (T1 adapters, T3), Railway + Postgres (T1 settings, T5), text + stay date (T1, T3, T4), approval (T1 default, T1 admin, T2 filter, T5 step 6), gool-style grid + show more (T4), empty state and API-down (T4), XSS (T4), no secrets committed (T1 env settings, T5). Guest verification and Facebook intentionally absent (spec: deferred).
- Known ceiling: API response cached 5 minutes, so an approved review can take up to 5 minutes to appear. Lower `max-age` in `reviews_api` if that bothers the owner.
