import json
import os
import subprocess
import sys
from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from reviews import views
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

    def test_new_review_defaults_to_site_source(self):
        review = make_review()
        review.save()
        self.assertEqual(review.source, Review.Source.SITE)
        self.assertIsNone(review.external_id)

    def test_many_site_reviews_without_external_id_allowed(self):
        make_review().save()
        make_review().save()  # two NULL external_ids must not clash
        self.assertEqual(Review.objects.count(), 2)


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
        self.assertEqual(set(review), {"name", "text", "stay_month", "stay_year", "source"})

    def test_payload_includes_source(self):
        make_review(text="מאירבנבי עם מקור", is_approved=True, source=Review.Source.AIRBNB, external_id="42").save()
        sources = {r["text"]: r["source"] for r in self.client.get(reverse("reviews:api")).json()["reviews"]}
        self.assertEqual(sources, {"מאושרת ומומלצת מאוד": "site", "מאירבנבי עם מקור": "airbnb"})

    def test_cors_header_allows_only_site_origin(self):
        response = self.client.get(reverse("reviews:api"))
        self.assertEqual(response["Access-Control-Allow-Origin"], "https://alma-hosting.co.il")

    def test_not_cached_so_approval_shows_immediately(self):
        self.assertEqual(self.client.get(reverse("reviews:api"))["Cache-Control"], "no-cache")

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post(reverse("reviews:api")).status_code, 405)


class WriteReviewTests(TestCase):
    def test_form_open_without_login(self):
        response = self.client.get(reverse("reviews:write"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="author_name"')
        self.assertNotContains(response, "אישור")

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
        response = self.client.get(reverse("reviews:thanks"))
        self.assertContains(response, "תודה על ההמלצה!")
        self.assertNotContains(response, "אישור")


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

    def test_panel_links_to_gallery_and_faq_editing(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("reviews:manage"))
        self.assertContains(response, f'href="{reverse("admin:content_gallerytab_changelist")}"')
        self.assertContains(response, f'href="{reverse("admin:content_faqitem_changelist")}"')

    def test_admin_links_back_to_panel(self):
        self.owner.is_superuser = True
        self.owner.save()
        self.client.force_login(self.owner)
        response = self.client.get(reverse("admin:content_faqitem_changelist"))
        self.assertContains(response, f'href="{reverse("reviews:manage")}"')

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


class AbuseLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        get_user_model().objects.create_user("owner", password="pw-owner-123", is_staff=True)

    def test_write_capped_per_hour_nothing_saved(self):
        Review.objects.bulk_create([make_review() for _ in range(views.REVIEWS_PER_HOUR)])
        response = self.client.post(reverse("reviews:write"), VALID_POST)
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, VALID_POST["text"], status_code=429)  # typed text not lost
        self.assertEqual(Review.objects.count(), views.REVIEWS_PER_HOUR)

    def test_write_cap_ignores_older_reviews(self):
        Review.objects.bulk_create([make_review() for _ in range(views.REVIEWS_PER_HOUR)])
        Review.objects.update(created_at=timezone.now() - timedelta(hours=2))
        self.assertRedirects(self.client.post(reverse("reviews:write"), VALID_POST), reverse("reviews:thanks"))

    def test_login_locked_after_failures_even_with_right_password(self):
        url = reverse("reviews:manage_login")
        for _ in range(views.LOGIN_FAILURES_LIMIT):
            self.assertEqual(self.client.post(url, {"username": "owner", "password": "wrong"}).status_code, 200)
        response = self.client.post(url, {"username": "owner", "password": "pw-owner-123"})
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_failure_after_counter_expired_starts_fresh(self):
        url = reverse("reviews:manage_login")
        self.client.post(url, {"username": "owner", "password": "wrong"})
        cache.delete(views.LOGIN_FAILURES_KEY)  # expired or evicted
        self.assertEqual(self.client.post(url, {"username": "owner", "password": "wrong"}).status_code, 200)
        self.assertEqual(cache.get(views.LOGIN_FAILURES_KEY), 1)

    def test_successful_login_not_counted(self):
        url = reverse("reviews:manage_login")
        for _ in range(views.LOGIN_FAILURES_LIMIT + 1):
            self.assertEqual(self.client.post(url, {"username": "owner", "password": "pw-owner-123"}).status_code, 302)
            self.client.logout()

    def test_admin_login_goes_through_throttled_page(self):
        response = self.client.get("/alma-manage-x7/login/?next=/alma-manage-x7/")
        self.assertRedirects(response, "/reviews/manage/login/?next=/alma-manage-x7/", fetch_redirect_response=False)

    def test_admin_served_at_private_path(self):
        self.client.login(username="owner", password="pw-owner-123")
        self.assertEqual(self.client.get("/alma-manage-x7/").status_code, 200)

    def test_short_manage_url_redirects_to_panel(self):
        for path in ("/manage", "/manage/"):
            self.assertRedirects(self.client.get(path), "/reviews/manage/", fetch_redirect_response=False)

    def test_default_admin_path_not_found(self):
        self.assertEqual(self.client.get("/admin/").status_code, 404)


@override_settings(ORIGIN_AUTH_SECRET="s3cret-from-cloudflare")
class OriginAuthTests(TestCase):
    """Only Cloudflare knows the secret header, so direct hits on Railway are refused."""

    def test_request_without_header_refused(self):
        self.assertEqual(self.client.get(reverse("reviews:api")).status_code, 403)

    def test_wrong_header_refused(self):
        self.assertEqual(self.client.get(reverse("reviews:api"), HTTP_X_ORIGIN_AUTH="nope").status_code, 403)

    def test_right_header_allowed(self):
        response = self.client.get(reverse("reviews:api"), HTTP_X_ORIGIN_AUTH="s3cret-from-cloudflare")
        self.assertEqual(response.status_code, 200)

    @override_settings(ALLOWED_HOSTS=["healthcheck.railway.app"])
    def test_railway_healthcheck_exempt(self):
        response = self.client.get(reverse("reviews:api"), HTTP_HOST="healthcheck.railway.app")
        self.assertEqual(response.status_code, 200)

    @override_settings(ORIGIN_AUTH_SECRET="")
    def test_disabled_when_secret_unset(self):
        self.assertEqual(self.client.get(reverse("reviews:api")).status_code, 200)


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
        code = "import json, django; django.setup(); from django.conf import settings as s; print(json.dumps([s.ALLOWED_HOSTS, s.SECURE_HSTS_SECONDS, s.DATA_UPLOAD_MAX_MEMORY_SIZE]))"
        out = subprocess.run(
            [sys.executable, "-c", code], env=env, cwd=Path(__file__).resolve().parent.parent,
            capture_output=True, text=True, check=True,
        )
        hosts, hsts, body_cap = json.loads(out.stdout)
        self.assertIn("healthcheck.railway.app", hosts)
        self.assertGreater(hsts, 0)
        self.assertLessEqual(body_cap, 64 * 1024)


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "apify_sample.json"
IMPORT_URLOPEN = "reviews.management.commands.import_airbnb_reviews.urlopen"


def apify_returns(payload):
    """Patch urlopen so the command receives `payload` as the Apify response body."""
    fake = mock.patch(IMPORT_URLOPEN)
    urlopen = fake.start()
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    urlopen.return_value.__enter__.return_value.read.return_value = body
    return fake, urlopen


def sample_items():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@mock.patch.dict(os.environ, {"APIFY_TOKEN": "test-token"})
class ImportAirbnbReviewsTests(TestCase):
    def run_import(self, payload):
        fake, urlopen = apify_returns(payload)
        self.addCleanup(fake.stop)
        out = StringIO()
        call_command("import_airbnb_reviews", stdout=out, stderr=StringIO())
        return out.getvalue(), urlopen

    def test_imports_new_reviews_published_with_airbnb_source(self):
        out, _ = self.run_import(sample_items())
        self.assertEqual(Review.objects.count(), 3)
        self.assertTrue(all(r.is_approved and r.source == Review.Source.AIRBNB for r in Review.objects.all()))
        dana = Review.objects.get(external_id="1100000000000000001")
        self.assertEqual((dana.author_name, dana.stay_month, dana.stay_year), ("Dana", 8, 2026))
        self.assertIn("fetched 3, created 3, skipped 0", out)

    def test_numeric_id_stored_as_string(self):
        self.run_import(sample_items())
        self.assertTrue(Review.objects.filter(external_id="1100000000000000002").exists())

    def test_second_run_creates_nothing(self):
        self.run_import(sample_items())
        out, _ = self.run_import(sample_items())
        self.assertEqual(Review.objects.count(), 3)
        self.assertIn("created 0, skipped 3", out)

    def test_hidden_review_stays_hidden_after_reimport(self):
        self.run_import(sample_items())
        Review.objects.filter(external_id="1100000000000000001").update(is_approved=False)
        self.run_import(sample_items())
        self.assertFalse(Review.objects.get(external_id="1100000000000000001").is_approved)

    def test_long_text_cut_to_1000_with_ellipsis(self):
        item = dict(sample_items()[0], text="א" * 1500)
        self.run_import([item])
        text = Review.objects.get().text
        self.assertEqual(len(text), 1000)
        self.assertTrue(text.endswith("…"))

    def test_long_name_cut_to_100(self):
        item = dict(sample_items()[0], reviewer={"firstName": "ש" * 150})
        self.run_import([item])
        self.assertEqual(len(Review.objects.get().author_name), 100)

    def test_unusable_items_skipped(self):
        good = sample_items()[0]
        items = [
            good,
            dict(good, id=None),
            dict(good, id="no-text", text="   "),
            "not-a-dict",
        ]
        out, _ = self.run_import(items)
        self.assertEqual(list(Review.objects.values_list("external_id", flat=True)), ["1100000000000000001"])
        self.assertIn("created 1, skipped 3", out)

    def test_item_with_bad_date_skipped_others_imported(self):
        good, other = sample_items()[:2]
        self.run_import([dict(good, createdAt="yesterday"), other])
        self.assertEqual(list(Review.objects.values_list("external_id", flat=True)), ["1100000000000000002"])

    def test_duplicate_id_in_one_response_created_once(self):
        item = sample_items()[0]
        self.run_import([item, dict(item)])
        self.assertEqual(Review.objects.count(), 1)

    def test_empty_response_changes_nothing(self):
        make_review(is_approved=True).save()
        out, _ = self.run_import([])
        self.assertEqual(Review.objects.count(), 1)
        self.assertIn("fetched 0, created 0, skipped 0", out)

    def test_apify_http_error_raises_and_saves_nothing(self):
        fake = mock.patch(IMPORT_URLOPEN, side_effect=URLError("boom"))
        fake.start()
        self.addCleanup(fake.stop)
        with self.assertRaises(CommandError):
            call_command("import_airbnb_reviews", stdout=StringIO(), stderr=StringIO())
        self.assertFalse(Review.objects.exists())

    def test_invalid_json_raises_and_saves_nothing(self):
        with self.assertRaises(CommandError):
            self.run_import(b"<html>gateway error</html>")
        self.assertFalse(Review.objects.exists())

    def test_non_list_response_raises_and_saves_nothing(self):
        with self.assertRaises(CommandError):
            self.run_import({"error": {"type": "run-failed"}})
        self.assertFalse(Review.objects.exists())

    def test_sends_token_as_header_and_listing_url_in_body(self):
        _, urlopen = self.run_import([])
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer test-token")
        self.assertNotIn("test-token", request.full_url)
        self.assertIn("1771157482793114563", request.data.decode())

    @mock.patch.dict(os.environ, {"APIFY_TOKEN": ""})
    def test_missing_token_raises_clear_error(self):
        with self.assertRaisesMessage(CommandError, "APIFY_TOKEN"):
            call_command("import_airbnb_reviews", stdout=StringIO(), stderr=StringIO())
