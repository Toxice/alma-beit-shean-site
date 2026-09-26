import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from reviews.models import Review

VALID_POST = {"author_name": "נועה לוי", "text": "חופשה נהדרת, המקום מאובזר ונקי.", "stay_month": 7, "stay_year": 2025}


def make_review(**overrides):
    fields = dict(
        author_name="דנה כהן",
        text="היה מקסים, נקי ושקט. נחזור!",
        stay_month=8,
        stay_year=2025,
    )
    fields.update(overrides)
    return Review(**fields)


class ReviewModelTests(TestCase):
    def test_valid_review_passes_and_defaults_to_pending(self):
        review = make_review()
        review.full_clean()
        review.save()
        self.assertFalse(review.is_approved)

    def test_future_stay_date_rejected(self):
        today = date.today()
        year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        with self.assertRaises(ValidationError):
            make_review(stay_year=year, stay_month=month).full_clean()

    def test_current_month_allowed(self):
        today = date.today()
        make_review(stay_year=today.year, stay_month=today.month).full_clean()

    def test_text_too_short_rejected(self):
        with self.assertRaises(ValidationError):
            make_review(text="קצר").full_clean()

    def test_text_too_long_rejected(self):
        with self.assertRaises(ValidationError):
            make_review(text="א" * 1001).full_clean()

    def test_month_out_of_range_rejected(self):
        with self.assertRaises(ValidationError):
            make_review(stay_month=13).full_clean()

    def test_year_before_first_year_rejected(self):
        with self.assertRaises(ValidationError):
            make_review(stay_year=2019).full_clean()

    def test_name_required(self):
        with self.assertRaises(ValidationError):
            make_review(author_name="").full_clean()

    def test_ordering_newest_stay_first(self):
        make_review(stay_year=2024, stay_month=5).save()
        make_review(stay_year=2025, stay_month=1).save()
        make_review(stay_year=2024, stay_month=11).save()
        got = [(r.stay_year, r.stay_month) for r in Review.objects.all()]
        self.assertEqual(got, [(2025, 1), (2024, 11), (2024, 5)])


@override_settings(SITE_ORIGIN="https://alma-hosting.co.il")
class ReviewsApiTests(TestCase):
    def setUp(self):
        make_review(text="מאושרת ומומלצת מאוד", is_approved=True).save()
        make_review(text="ממתינה לאישור עדיין").save()

    def test_returns_only_approved(self):
        data = self.client.get(reverse("reviews:api")).json()
        self.assertEqual([r["text"] for r in data["reviews"]], ["מאושרת ומומלצת מאוד"])

    def test_payload_has_exact_keys_no_personal_data(self):
        review = self.client.get(reverse("reviews:api")).json()["reviews"][0]
        self.assertEqual(set(review), {"name", "text", "stay_month", "stay_year"})

    def test_cors_header_allows_only_site_origin(self):
        response = self.client.get(reverse("reviews:api"))
        self.assertEqual(response["Access-Control-Allow-Origin"], "https://alma-hosting.co.il")

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post(reverse("reviews:api")).status_code, 405)


class WriteReviewTests(TestCase):
    def test_form_open_without_login(self):
        response = self.client.get(reverse("reviews:write"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="author_name"')

    def test_submit_creates_pending_review(self):
        response = self.client.post(reverse("reviews:write"), VALID_POST)
        self.assertRedirects(response, reverse("reviews:thanks"))
        review = Review.objects.get()
        self.assertEqual(review.author_name, "נועה לוי")
        self.assertFalse(review.is_approved)

    def test_cannot_self_approve(self):
        self.client.post(reverse("reviews:write"), {**VALID_POST, "is_approved": "on"})
        self.assertFalse(Review.objects.get().is_approved)

    def test_future_date_shows_hebrew_error_and_saves_nothing(self):
        response = self.client.post(
            reverse("reviews:write"), {**VALID_POST, "stay_month": 12, "stay_year": date.today().year + 1}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "תאריך השהות לא יכול להיות בעתיד.")
        self.assertFalse(Review.objects.exists())

    def test_honeypot_filled_is_silently_dropped(self):
        response = self.client.post(reverse("reviews:write"), {**VALID_POST, "website": "http://spam"})
        self.assertRedirects(response, reverse("reviews:thanks"))
        self.assertFalse(Review.objects.exists())

    def test_thanks_page(self):
        self.assertContains(self.client.get(reverse("reviews:thanks")), "תודה! ההמלצה תפורסם לאחר אישור")


class ManagePanelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("owner", password="pw-owner-123", is_staff=True)
        self.guest = User.objects.create_user("guest", password="pw-guest-123")
        self.review = make_review()
        self.review.save()

    def test_anonymous_redirected_to_themed_login(self):
        response = self.client.get(reverse("reviews:manage"))
        self.assertRedirects(response, "/reviews/manage/login/?next=/reviews/manage/", fetch_redirect_response=False)
        self.assertTemplateUsed(self.client.get("/reviews/manage/login/"), "reviews/manage_login.html")

    def test_non_staff_forbidden(self):
        self.client.force_login(self.guest)
        # 403, not a redirect: login page would bounce a logged-in user straight back (loop).
        self.assertEqual(self.client.get(reverse("reviews:manage")).status_code, 403)

    def test_owner_sees_pending_review(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("reviews:manage"))
        self.assertContains(response, self.review.text)

    def test_owner_login_with_password(self):
        response = self.client.post("/reviews/manage/login/", {"username": "owner", "password": "pw-owner-123"})
        self.assertRedirects(response, reverse("reviews:manage"), fetch_redirect_response=False)

    def test_approve_hide_delete(self):
        self.client.force_login(self.owner)
        url = reverse("reviews:manage_action", args=[self.review.pk])
        self.client.post(url, {"action": "approve"})
        self.review.refresh_from_db()
        self.assertTrue(self.review.is_approved)
        self.client.post(url, {"action": "hide"})
        self.review.refresh_from_db()
        self.assertFalse(self.review.is_approved)
        self.client.post(url, {"action": "delete"})
        self.assertFalse(Review.objects.exists())

    def test_action_requires_post_and_staff(self):
        url = reverse("reviews:manage_action", args=[self.review.pk])
        self.client.force_login(self.guest)
        self.client.post(url, {"action": "approve"})
        self.review.refresh_from_db()
        self.assertFalse(self.review.is_approved)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_logout(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("reviews:manage_logout"))
        self.assertEqual(self.client.get(reverse("reviews:manage")).status_code, 302)


class ProdSettingsTests(TestCase):
    """Load settings the way Railway does; the test runner overrides some settings in-process."""

    def test_railway_healthcheck_host_allowed(self):
        env = dict(
            os.environ,
            RAILWAY_ENVIRONMENT_NAME="production",
            SECRET_KEY="test-secret",
            ALLOWED_HOSTS="api.alma-hosting.co.il",
            DJANGO_SETTINGS_MODULE="config.settings",
        )
        code = "import json, django; django.setup(); from django.conf import settings as s; print(json.dumps(s.ALLOWED_HOSTS))"
        out = subprocess.run(
            [sys.executable, "-c", code], env=env, cwd=Path(__file__).resolve().parent.parent,
            capture_output=True, text=True, check=True,
        )
        self.assertIn("healthcheck.railway.app", json.loads(out.stdout))
