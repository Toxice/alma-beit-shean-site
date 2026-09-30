import shutil
import tempfile
from io import BytesIO
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image

from content.images import MAX_BYTES, to_web_jpeg, validate_upload
from content.models import FaqItem, GalleryPhoto, GalleryTab

TEMP_MEDIA = tempfile.mkdtemp()


def tearDownModule():
    shutil.rmtree(TEMP_MEDIA, ignore_errors=True)


def image_upload(size=(2400, 1200), fmt="JPEG", mode="RGB", color=(200, 100, 50), name="photo.jpg", exif=None):
    buf = BytesIO()
    kwargs = {"exif": exif} if exif is not None else {}
    Image.new(mode, size, color).save(buf, fmt, **kwargs)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


def make_photo(tab=None, **overrides):
    tab = tab or GalleryTab.objects.create(title="חדרי שינה")
    fields = dict(tab=tab, alt_text="חדר שינה זוגי", image=image_upload())
    fields.update(overrides)
    photo = GalleryPhoto(**fields)
    photo.save()
    return photo


def media_path(name):
    return Path(TEMP_MEDIA) / name


class ImagePipelineTests(TestCase):
    def test_large_photo_shrunk_to_1600_longest_side(self):
        content, width, height = to_web_jpeg(image_upload(size=(4000, 2000)))
        self.assertEqual((width, height), (1600, 800))
        with Image.open(content) as img:
            self.assertEqual(img.format, "JPEG")
            self.assertEqual(img.size, (1600, 800))

    def test_small_photo_not_upscaled(self):
        _, width, height = to_web_jpeg(image_upload(size=(800, 600)))
        self.assertEqual((width, height), (800, 600))

    def test_exif_rotation_applied(self):
        exif = Image.Exif()
        exif[0x0112] = 6  # "rotate 90° clockwise to view" - how phones store portrait shots
        _, width, height = to_web_jpeg(image_upload(size=(400, 200), exif=exif))
        self.assertEqual((width, height), (200, 400))

    def test_transparent_png_gets_white_background(self):
        upload = image_upload(size=(100, 100), fmt="PNG", mode="RGBA", color=(0, 0, 0, 0), name="logo.png")
        content, _, _ = to_web_jpeg(upload)
        with Image.open(content) as img:
            r, g, b = img.getpixel((50, 50))
        self.assertGreater(min(r, g, b), 240)

    def test_oversized_file_rejected(self):
        upload = SimpleUploadedFile("big.jpg", b"\xff" * (MAX_BYTES + 1), content_type="image/jpeg")
        with self.assertRaisesMessage(ValidationError, "15MB"):
            validate_upload(upload)

    def test_non_image_rejected_with_hebrew_message(self):
        heic_like = SimpleUploadedFile("IMG_0001.HEIC", b"\x00\x00\x00\x18ftypheic" + b"\x00" * 64)
        with self.assertRaisesMessage(ValidationError, "JPG או PNG"):
            validate_upload(heic_like)

    def test_valid_image_passes_and_file_is_rewound(self):
        upload = image_upload()
        validate_upload(upload)
        self.assertEqual(upload.tell(), 0)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class GalleryPhotoTests(TestCase):
    def test_save_stores_web_jpeg_with_unique_name_and_size(self):
        photo = make_photo(image=image_upload(size=(3200, 1600)))
        self.assertRegex(photo.image.name, r"^gallery/[0-9a-f]{32}\.jpg$")
        self.assertEqual((photo.width, photo.height), (1600, 800))
        self.assertTrue(media_path(photo.image.name).exists())

    def test_alt_text_only_edit_keeps_same_file(self):
        photo = make_photo()
        name = photo.image.name
        photo.alt_text = "תיאור חדש"
        photo.save()
        photo.refresh_from_db()
        self.assertEqual(photo.image.name, name)
        self.assertTrue(media_path(name).exists())

    def test_replacing_image_deletes_old_file(self):
        photo = make_photo()
        old = photo.image.name
        photo.image = image_upload(color=(10, 200, 10))
        photo.save()
        self.assertNotEqual(photo.image.name, old)
        self.assertFalse(media_path(old).exists())
        self.assertTrue(media_path(photo.image.name).exists())

    def test_deleting_photo_deletes_file(self):
        photo = make_photo()
        name = photo.image.name
        photo.delete()
        self.assertFalse(media_path(name).exists())

    def test_deleting_tab_deletes_its_photo_files(self):
        tab = GalleryTab.objects.create(title="בחוץ")
        names = [make_photo(tab=tab).image.name for _ in range(2)]
        tab.delete()
        self.assertEqual(GalleryPhoto.objects.count(), 0)
        for name in names:
            self.assertFalse(media_path(name).exists())


class FaqItemTests(TestCase):
    def test_answer_over_1000_chars_rejected(self):
        item = FaqItem(question="שאלה?", answer="א" * 1001)
        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_items_ordered_by_order_field(self):
        FaqItem.objects.create(question="שנייה?", answer="ב", order=2)
        FaqItem.objects.create(question="ראשונה?", answer="א", order=1)
        self.assertEqual([f.question for f in FaqItem.objects.all()], ["ראשונה?", "שנייה?"])


from django.contrib.auth import get_user_model
from django.urls import reverse


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ContentAdminTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser("owner", "owner@example.com", "pw-123456")

    def test_owner_sees_gallery_and_faq_pages(self):
        self.client.force_login(self.owner)
        photo = make_photo()
        for url in [
            reverse("admin:content_gallerytab_changelist"),
            reverse("admin:content_gallerytab_add"),
            reverse("admin:content_gallerytab_change", args=[photo.tab.pk]),
            reverse("admin:content_faqitem_changelist"),
            reverse("admin:content_faqitem_add"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_tab_page_shows_photo_thumbnail(self):
        self.client.force_login(self.owner)
        photo = make_photo()
        response = self.client.get(reverse("admin:content_gallerytab_change", args=[photo.tab.pk]))
        # The <img> itself, not just Django's "currently: <link>" text for the file field.
        self.assertContains(response, f'<img src="{photo.image.url}"')

    def test_anonymous_redirected_to_login(self):
        for url in [reverse("admin:content_gallerytab_changelist"), reverse("admin:content_faqitem_changelist")]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)


import json

from django.conf import settings


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ContentApiTests(TestCase):
    def get_json(self):
        response = self.client.get(reverse("content:api"))
        self.assertEqual(response.status_code, 200)
        return response, json.loads(response.content)

    def test_shape_order_and_absolute_urls(self):
        second = GalleryTab.objects.create(title="חדרי רחצה", order=2)
        first = GalleryTab.objects.create(title="חדרי שינה", order=1)
        make_photo(tab=first, alt_text="שנייה", order=2)
        make_photo(tab=first, alt_text="ראשונה", order=1)
        make_photo(tab=second, alt_text="אמבטיה")
        FaqItem.objects.create(question="ב?", answer="2", order=2)
        FaqItem.objects.create(question="א?", answer="1", order=1)

        _, data = self.get_json()

        self.assertEqual([t["title"] for t in data["gallery"]], ["חדרי שינה", "חדרי רחצה"])
        photos = data["gallery"][0]["photos"]
        self.assertEqual([p["alt"] for p in photos], ["ראשונה", "שנייה"])
        self.assertTrue(photos[0]["url"].startswith("http://testserver/media/gallery/"))
        self.assertEqual((photos[0]["width"], photos[0]["height"]), (1600, 800))
        self.assertEqual(data["faq"], [{"q": "א?", "a": "1"}, {"q": "ב?", "a": "2"}])

    def test_empty_tab_omitted(self):
        GalleryTab.objects.create(title="ריקה")
        make_photo()
        _, data = self.get_json()
        self.assertEqual([t["title"] for t in data["gallery"]], ["חדרי שינה"])

    def test_answer_text_returned_raw(self):
        FaqItem.objects.create(question="<b>שאלה</b>?", answer="שורה 1\nשורה 2 <script>x</script>")
        _, data = self.get_json()
        self.assertEqual(data["faq"][0]["a"], "שורה 1\nשורה 2 <script>x</script>")

    def test_cors_header_is_site_origin(self):
        response, _ = self.get_json()
        self.assertEqual(response["Access-Control-Allow-Origin"], settings.SITE_ORIGIN)

    def test_post_not_allowed(self):
        self.assertEqual(self.client.post(reverse("content:api")).status_code, 405)

    def test_media_served_with_long_cache(self):
        photo = make_photo()
        response = self.client.get(photo.image.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "public, max-age=31536000, immutable")
        self.assertTrue(b"".join(response.streaming_content))

    def test_missing_media_is_404(self):
        self.assertEqual(self.client.get("/media/gallery/missing.jpg").status_code, 404)


from io import StringIO

from django.core.management import call_command


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class SeedContentTests(TestCase):
    def seed(self):
        out = StringIO()
        call_command("seed_content", stdout=out)
        return out.getvalue()

    def test_seeds_current_site_content_in_order(self):
        self.seed()
        self.assertEqual(
            [t.title for t in GalleryTab.objects.all()],
            ["פנים הבית", "חדרי שינה", "חדרי רחצה", "בחוץ"],
        )
        self.assertEqual(GalleryPhoto.objects.count(), 15)
        self.assertEqual(FaqItem.objects.count(), 5)
        first = GalleryTab.objects.first().photos.first()
        self.assertEqual(first.alt_text, "סלון יחידה א׳")
        self.assertLessEqual(max(first.width, first.height), 1600)
        self.assertTrue(media_path(first.image.name).exists())
        self.assertEqual(FaqItem.objects.last().question, "האם יש בתי כנסת בקרבת המתחם?")

    def test_second_run_changes_nothing(self):
        self.seed()
        names = sorted(GalleryPhoto.objects.values_list("image", flat=True))
        self.assertIn("already seeded", self.seed())
        self.assertEqual(sorted(GalleryPhoto.objects.values_list("image", flat=True)), names)
        self.assertEqual(FaqItem.objects.count(), 5)

    def test_skips_when_owner_already_added_content(self):
        FaqItem.objects.create(question="שאלה של הבעלים?", answer="תשובה")
        self.assertIn("already seeded", self.seed())
        self.assertEqual(GalleryTab.objects.count(), 0)
        self.assertEqual(FaqItem.objects.count(), 1)
