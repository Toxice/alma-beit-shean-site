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
