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


import json
import os
import subprocess
import sys
from pathlib import Path


class ProdSettingsTests(TestCase):
    """Load settings the way Railway does; the test runner overrides some settings in-process."""

    def prod_settings(self):
        env = dict(
            os.environ,
            RAILWAY_ENVIRONMENT_NAME="production",
            SECRET_KEY="test-secret",
            ALLOWED_HOSTS="api.alma-hosting.co.il",
            DJANGO_SETTINGS_MODULE="config.settings",
        )
        code = (
            "import json, django; django.setup(); from django.conf import settings as s; "
            "print(json.dumps({'hosts': s.ALLOWED_HOSTS, 'email': s.EMAIL_BACKEND, "
            "'unknown': getattr(s, 'ACCOUNT_EMAIL_UNKNOWN_ACCOUNTS', True)}))"
        )
        out = subprocess.run(
            [sys.executable, "-c", code], env=env, cwd=Path(__file__).resolve().parent.parent,
            capture_output=True, text=True, check=True,
        )
        return json.loads(out.stdout)

    def test_railway_healthcheck_host_allowed(self):
        self.assertIn("healthcheck.railway.app", self.prod_settings()["hosts"])

    def test_no_smtp_so_allauth_email_pages_cannot_500(self):
        s = self.prod_settings()
        self.assertEqual(s["email"], "django.core.mail.backends.console.EmailBackend")
        self.assertFalse(s["unknown"])
