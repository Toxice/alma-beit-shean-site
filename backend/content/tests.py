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
