# Editable Gallery & FAQ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the owner add, edit, delete and drag-reorder gallery tabs, gallery photos and FAQ items in the Django admin, and have the static site show them live.

**Architecture:** New Django app `content` (3 models, sortable admin, one read-only JSON endpoint, a media route, a one-time seed command). Photos are resized to web JPEGs on save and stored under `MEDIA_ROOT` (a Railway volume in production). The static site keeps its current gallery/FAQ HTML as fallback and replaces it with API data via a new `site/content.js`.

**Tech Stack:** Django 5.2, Pillow, django-admin-sortable2 2.3, plain JS (no framework), Railway volume.

**Spec:** `docs/superpowers/specs/2026-09-30-editable-gallery-faq-design.md`

## Global Constraints

- Owner = admin = one person; all writes go through the existing Django admin at `/alma-manage-x7/`, POST + login + CSRF only.
- `/api/content/` is GET-only (`@require_GET`), with `Access-Control-Allow-Origin: settings.SITE_ORIGIN`, like `/api/reviews/`.
- Photos: max upload **15 MB**; output JPEG, longest side ≤ **1600 px**, quality **82**, progressive; EXIF orientation applied; file name `gallery/<uuid4 hex>.jpg`.
- `alt_text` required, max 150 chars. Tab title max 60. Question max 200. Answer max 1000 (`MaxLengthValidator`).
- Media served at `/media/` with `Cache-Control: public, max-age=31536000, immutable`.
- `MEDIA_ROOT` = env `MEDIA_ROOT` or `BASE_DIR / "media"`; production `/data/media`.
- `seed_content` runs only when all three tables are empty; runs in the Railway **start command** (volumes are not mounted during pre-deploy).
- Site JS: plain JS, `createElement`/`textContent` only, never `innerHTML` with API data; 5 s fetch timeout; any failure leaves the static fallback untouched.
- Hebrew for every owner-facing label and error message.
- **Nothing is pushed.** Commits stay local until the owner approves the local review (Task 6). Deployment steps at the end run only after approval.
- Run backend commands from `backend/` with `.venv/Scripts/python.exe` (Windows venv). Baseline: `python manage.py test` → 41 tests OK.

## Review Focus

Inputs the spec implies but that the main tests don't pin; each has a test in its owning task.

1. **Transparent PNG upload** (logo-style image, RGBA): must become a JPEG on a **white** background, not black. Test in Task 1.
2. **Small photo** (smaller than 1600 px): must keep its size, never be upscaled. Test in Task 1.
3. **Owner edits only the alt text** of an existing photo and saves: the image file must stay the same (no re-processing, no deletion). Test in Task 1.
4. **iPhone HEIC or other unsupported file**: must be rejected with a clear Hebrew message, nothing saved. Test in Task 1.
5. **Owner types HTML or line breaks in a Q&A answer** (`<b>`, `<script>`, Enter): site must show it as plain text, and line breaks must be visible. API test in Task 3 (raw text returned); site check in Task 5 step 7.

## File Structure

| File | Responsibility |
|---|---|
| `backend/content/__init__.py`, `apps.py` | App registration. |
| `backend/content/images.py` | Upload validation + resize-to-web-JPEG. No Django models. |
| `backend/content/models.py` | `GalleryTab`, `GalleryPhoto`, `FaqItem`; photo save pipeline + file cleanup. |
| `backend/content/admin.py` | Sortable admin for tabs (with photo inline) and FAQ. |
| `backend/content/views.py` | `content_api` JSON view, `media` file view. |
| `backend/content/urls.py` | Routes for the two views. |
| `backend/content/management/commands/seed_content.py` | One-time import of current site content. |
| `backend/content/seed/content.json` + 15 JPEGs | Seed data (copied from `site/`). |
| `backend/content/tests.py` | All `content` tests. |
| `backend/config/settings.py`, `urls.py` | Register app, media settings, include routes. |
| `backend/requirements.txt`, `railway.json`, `.gitignore` | Deps, start command, ignore local media. |
| `site/content.js` | Fetch API, rebuild gallery + FAQ. |
| `site/script.js` | Expose `initCarousel` / `initReveal` (refactor only). |
| `site/index.html`, `site/styles.css` | Hooks for `content.js`; FAQ line breaks. |

---

### Task 1: `content` app, models and photo pipeline

**Files:**
- Create: `backend/content/__init__.py` (empty), `backend/content/apps.py`, `backend/content/images.py`, `backend/content/models.py`, `backend/content/tests.py`, `backend/content/migrations/__init__.py` (empty)
- Modify: `backend/config/settings.py`, `backend/requirements.txt`, `.gitignore`

**Interfaces:**
- Produces: `content.images.validate_upload(file) -> None` (raises `ValidationError`), `content.images.to_web_jpeg(file) -> (ContentFile, int width, int height)`, `MAX_SIDE = 1600`, `MAX_BYTES = 15 * 1024 * 1024`.
- Produces models: `GalleryTab(title, order)`, `GalleryPhoto(tab, image, alt_text, width, height, order)` with `related_name="photos"`, `FaqItem(question, answer, order)`. All `Meta.ordering = ["order"]`.
- Produces test helpers in `content/tests.py`: `TEMP_MEDIA`, `image_upload(...)`, `make_photo(...)`, `media_path(name)` (later tasks append tests to this file and reuse them).

- [ ] **Step 1: Install dependencies**

Append to `backend/requirements.txt`:

```
Pillow>=12.0
django-admin-sortable2>=2.3,<2.4
```

Run (from `backend/`): `.venv/Scripts/python.exe -m pip install -r requirements.txt`
Expected: installs Pillow 12.x and django-admin-sortable2 2.3.x.

- [ ] **Step 2: Register the app and media settings**

Create `backend/content/apps.py`:

```python
from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "content"
    verbose_name = "תוכן האתר"
```

In `backend/config/settings.py`, change `INSTALLED_APPS` to end with:

```python
    "django.contrib.staticfiles",
    "adminsortable2",
    "reviews",
    "content",
]
```

and after `STATIC_ROOT = BASE_DIR / "staticfiles"` add:

```python
# Owner-uploaded gallery photos. Production: a Railway volume mounted at /data (MEDIA_ROOT=/data/media).
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))
```

Append to the repo-root `.gitignore`:

```
backend/media/
```

- [ ] **Step 3: Write failing tests for the image pipeline and models**

Create `backend/content/tests.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe manage.py test content`
Expected: error `ModuleNotFoundError: No module named 'content.images'` (or `content.models`).

- [ ] **Step 5: Implement `images.py`**

Create `backend/content/images.py`:

```python
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1600
MAX_BYTES = 15 * 1024 * 1024


def validate_upload(file):
    """Reject files over 15 MB or that Pillow cannot read (e.g. iPhone HEIC)."""
    if file.size > MAX_BYTES:
        raise ValidationError("התמונה גדולה מדי. הגודל המרבי הוא 15MB.")
    try:
        with Image.open(file) as img:
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValidationError("הקובץ אינו תמונה נתמכת. יש להעלות תמונה בפורמט JPG או PNG.")
    finally:
        file.seek(0)


def to_web_jpeg(file):
    """Return (ContentFile, width, height): upright, RGB on white, longest side <= MAX_SIDE, JPEG q82."""
    file.seek(0)
    with Image.open(file) as original:
        img = ImageOps.exif_transpose(original)
        if img.mode in ("RGBA", "LA", "P"):
            rgba = img.convert("RGBA")
            img = Image.new("RGB", rgba.size, (255, 255, 255))
            img.paste(rgba, mask=rgba.getchannel("A"))
        else:
            img = img.convert("RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)  # shrinks only, never upscales
        buf = BytesIO()
        img.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    return ContentFile(buf.getvalue()), img.width, img.height
```

- [ ] **Step 6: Implement `models.py`**

Create `backend/content/models.py`:

```python
from uuid import uuid4

from django.core.validators import MaxLengthValidator
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver

from content.images import to_web_jpeg, validate_upload


class GalleryTab(models.Model):
    title = models.CharField("כותרת הלשונית", max_length=60)
    order = models.PositiveIntegerField("סדר", default=0, db_index=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "לשונית גלריה"
        verbose_name_plural = "לשוניות גלריה"

    def __str__(self):
        return self.title


class GalleryPhoto(models.Model):
    tab = models.ForeignKey(GalleryTab, on_delete=models.CASCADE, related_name="photos", verbose_name="לשונית")
    image = models.ImageField("תמונה", upload_to="gallery/", validators=[validate_upload])
    alt_text = models.CharField("תיאור התמונה (לנגישות)", max_length=150)
    width = models.PositiveIntegerField(default=0, editable=False)
    height = models.PositiveIntegerField(default=0, editable=False)
    order = models.PositiveIntegerField("סדר", default=0, db_index=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "תמונה"
        verbose_name_plural = "תמונות"

    def __str__(self):
        return self.alt_text

    def save(self, *args, **kwargs):
        old_name = None
        if self.pk:
            old_name = GalleryPhoto.objects.filter(pk=self.pk).values_list("image", flat=True).first()
        if self.image and not self.image._committed:  # a new upload, not an alt-text-only edit
            content, self.width, self.height = to_web_jpeg(self.image)
            # Unique name per upload: a replaced photo gets a new URL, so no cache shows the old one.
            self.image.save(f"{uuid4().hex}.jpg", content, save=False)
        super().save(*args, **kwargs)
        if old_name and old_name != self.image.name:
            self.image.storage.delete(old_name)


@receiver(post_delete, sender=GalleryPhoto)
def delete_photo_file(sender, instance, **kwargs):
    # Also fires for each photo when its tab is deleted (cascade).
    if instance.image:
        instance.image.storage.delete(instance.image.name)


class FaqItem(models.Model):
    question = models.CharField("שאלה", max_length=200)
    answer = models.TextField("תשובה", max_length=1000, validators=[MaxLengthValidator(1000)])
    order = models.PositiveIntegerField("סדר", default=0, db_index=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "שאלה נפוצה"
        verbose_name_plural = "שאלות נפוצות"

    def __str__(self):
        return self.question
```

- [ ] **Step 7: Create the migration**

Run: `.venv/Scripts/python.exe manage.py makemigrations content`
Expected: `content/migrations/0001_initial.py` with `Create model FaqItem`, `Create model GalleryTab`, `Create model GalleryPhoto`.

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe manage.py test content`
Expected: all 14 tests OK.

Run: `.venv/Scripts/python.exe manage.py test`
Expected: 55 tests OK (41 existing + 14).

- [ ] **Step 9: Commit (local only)**

```bash
git add .gitignore backend/requirements.txt backend/config/settings.py backend/content
git commit -m "Add content app with gallery and FAQ models and photo pipeline"
```

---

### Task 2: Sortable admin

**Files:**
- Create: `backend/content/admin.py`
- Modify: `backend/content/tests.py` (append)

**Interfaces:**
- Consumes: models from Task 1, `make_photo`, `TEMP_MEDIA` test helpers.
- Produces: admin URL names `admin:content_gallerytab_changelist`, `admin:content_gallerytab_add`, `admin:content_gallerytab_change`, `admin:content_faqitem_changelist`, `admin:content_faqitem_add`.

- [ ] **Step 1: Write failing admin tests**

Append to `backend/content/tests.py`:

```python
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
        self.assertContains(response, photo.image.url)

    def test_anonymous_redirected_to_login(self):
        for url in [reverse("admin:content_gallerytab_changelist"), reverse("admin:content_faqitem_changelist")]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe manage.py test content.tests.ContentAdminTests`
Expected: FAIL with `NoReverseMatch: Reverse for 'content_gallerytab_changelist' not found`.

- [ ] **Step 3: Implement the admin**

Create `backend/content/admin.py`:

```python
from adminsortable2.admin import SortableAdminMixin, SortableTabularInline
from django.contrib import admin
from django.utils.html import format_html

from content.models import FaqItem, GalleryPhoto, GalleryTab


class GalleryPhotoInline(SortableTabularInline):
    model = GalleryPhoto
    extra = 1
    readonly_fields = ("preview",)

    @admin.display(description="תצוגה מקדימה")
    def preview(self, obj):
        if not obj.pk or not obj.image:
            return ""
        return format_html('<img src="{}" alt="" style="height:64px;border-radius:6px;">', obj.image.url)


@admin.register(GalleryTab)
class GalleryTabAdmin(SortableAdminMixin, admin.ModelAdmin):
    list_display = ("title", "photo_count")
    inlines = [GalleryPhotoInline]

    @admin.display(description="מספר תמונות")
    def photo_count(self, obj):
        return obj.photos.count()


@admin.register(FaqItem)
class FaqItemAdmin(SortableAdminMixin, admin.ModelAdmin):
    list_display = ("question",)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe manage.py test content`
Expected: 17 tests OK.

- [ ] **Step 5: Manual smoke check of drag and drop**

Run: `.venv/Scripts/python.exe manage.py migrate` then `.venv/Scripts/python.exe manage.py runserver 8000`.
Log in at `http://localhost:8000/reviews/manage/login/` with an existing staff user (or create one: `.venv/Scripts/python.exe manage.py createsuperuser`), open `http://localhost:8000/alma-manage-x7/content/`.
Expected: "לשוניות גלריה" and "שאלות נפוצות" listed; add 2 FAQ items, drag one above the other in the list, reload: order kept. Add a tab with 2 photos, drag photos in the inline, save, reopen: order kept, thumbnails shown. Newly added items appear at the end of the list. Then delete the test rows.

- [ ] **Step 6: Commit (local only)**

```bash
git add backend/content/admin.py backend/content/tests.py
git commit -m "Add sortable admin for gallery tabs, photos and FAQ"
```

---

### Task 3: Public API and media route

**Files:**
- Create: `backend/content/views.py`, `backend/content/urls.py`
- Modify: `backend/config/urls.py`, `backend/content/tests.py` (append)

**Interfaces:**
- Consumes: models, `make_photo`, `TEMP_MEDIA`.
- Produces: `GET /api/content/` (URL name `content:api`) returning `{"gallery": [{"title": str, "photos": [{"url": str, "alt": str, "width": int, "height": int}]}], "faq": [{"q": str, "a": str}]}`; `GET /media/<path>` (URL name `content:media`).

- [ ] **Step 1: Write failing API and media tests**

Append to `backend/content/tests.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe manage.py test content.tests.ContentApiTests`
Expected: FAIL with `NoReverseMatch: 'content' is not a registered namespace`.

- [ ] **Step 3: Implement views and routes**

Create `backend/content/views.py`:

```python
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.static import serve

from content.models import FaqItem, GalleryTab


@require_GET
def content_api(request):
    gallery = []
    for tab in GalleryTab.objects.prefetch_related("photos"):
        photos = [
            {
                "url": request.build_absolute_uri(photo.image.url),
                "alt": photo.alt_text,
                "width": photo.width,
                "height": photo.height,
            }
            for photo in tab.photos.all()
        ]
        if photos:  # never show an empty tab on the site
            gallery.append({"title": tab.title, "photos": photos})
    faq = [{"q": item.question, "a": item.answer} for item in FaqItem.objects.all()]
    response = JsonResponse({"gallery": gallery, "faq": faq})
    response["Access-Control-Allow-Origin"] = settings.SITE_ORIGIN
    return response


@require_GET
def media(request, path):
    # ponytail: Django serves the photos itself; fine for ~60 images on a small site.
    # If traffic grows, move them to a bucket or let Cloudflare cache /media/.
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    response["Cache-Control"] = "public, max-age=31536000, immutable"  # safe: every upload has a unique name
    return response
```

Create `backend/content/urls.py`:

```python
from django.urls import path, re_path

from content import views

app_name = "content"

urlpatterns = [
    path("api/content/", views.content_api, name="api"),
    re_path(r"^media/(?P<path>.+)$", views.media, name="media"),
]
```

In `backend/config/urls.py`, change the last lines of `urlpatterns` to:

```python
    path("alma-manage-x7/", admin.site.urls),
    path("", include("content.urls")),
    path("", include("reviews.urls")),
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe manage.py test`
Expected: 65 tests OK (41 + 24).

- [ ] **Step 5: Commit (local only)**

```bash
git add backend/content/views.py backend/content/urls.py backend/config/urls.py backend/content/tests.py
git commit -m "Add public content API and cached media route"
```

---

### Task 4: Seed command and Railway start command

**Files:**
- Create: `backend/content/management/__init__.py` (empty), `backend/content/management/commands/__init__.py` (empty), `backend/content/management/commands/seed_content.py`, `backend/content/seed/content.json`, `backend/content/seed/*.jpg` (15 files)
- Modify: `backend/railway.json`, `backend/content/tests.py` (append)

**Interfaces:**
- Consumes: models from Task 1.
- Produces: `python manage.py seed_content` (idempotent; prints `content already seeded, skipping` when any content row exists; otherwise `seeded N tabs, N photos, N FAQ items`).

- [ ] **Step 1: Copy the 15 seed photos**

Run from the repo root:

```bash
mkdir -p backend/content/seed
cd site/images && cp living-room-1.jpg living-room-2.jpg dining-nook.jpg kitchen.jpg bedroom-1.jpg bedroom-2.jpg bedroom-2-evening.jpg bedroom-twin.jpg bathroom-1.jpg bathroom-2.jpg bathroom-3.jpg bathroom-4.jpg terrace-dining.jpg balcony.jpg welcome-tray.jpg ../../backend/content/seed/
ls ../../backend/content/seed/*.jpg | wc -l
```

Expected: `15`.

- [ ] **Step 2: Write the seed data file**

Create `backend/content/seed/content.json` (exact copy of the current site content, in site order):

```json
{
  "gallery": [
    {"title": "פנים הבית", "photos": [
      {"file": "living-room-1.jpg", "alt": "סלון יחידה א׳"},
      {"file": "living-room-2.jpg", "alt": "סלון יחידה ב׳"},
      {"file": "dining-nook.jpg", "alt": "פינת אוכל פנימית"},
      {"file": "kitchen.jpg", "alt": "מטבח מאובזר"}
    ]},
    {"title": "חדרי שינה", "photos": [
      {"file": "bedroom-1.jpg", "alt": "חדר שינה זוגי, יחידה א׳"},
      {"file": "bedroom-2.jpg", "alt": "חדר שינה זוגי, יחידה ב׳"},
      {"file": "bedroom-2-evening.jpg", "alt": "חדר שינה זוגי בתאורת ערב"},
      {"file": "bedroom-twin.jpg", "alt": "חדר שינה עם שתי מיטות יחיד"}
    ]},
    {"title": "חדרי רחצה", "photos": [
      {"file": "bathroom-1.jpg", "alt": "חדר רחצה עם כיור עומד ומראה זהב"},
      {"file": "bathroom-2.jpg", "alt": "חדר רחצה עם מקלחת גשם"},
      {"file": "bathroom-3.jpg", "alt": "חדר רחצה, יחידה ב׳"},
      {"file": "bathroom-4.jpg", "alt": "כיור וחדר רחצה מעוצב"}
    ]},
    {"title": "בחוץ", "photos": [
      {"file": "terrace-dining.jpg", "alt": "פינת ישיבה משותפת בחצר, שולחן עץ ארוך"},
      {"file": "balcony.jpg", "alt": "מרפסת פרטית עם נוף פתוח"},
      {"file": "welcome-tray.jpg", "alt": "מגש קבלת פנים — פירות ויין"}
    ]}
  ],
  "faq": [
    {"q": "כמה יחידות יש, ומה יש בכל אחת?", "a": "יש 2 יחידות אירוח נפרדות. בכל יחידה 2 חדרי שינה, סלון, מטבח מאובזר, חדר רחצה ומרפסת פרטית."},
    {"q": "יש בריכה?", "a": "ביחידות עצמן אין בריכה, אך המקום קרוב לבריכות הטבעיות של גן השלושה (סחנה)."},
    {"q": "איך מזמינים?", "a": "הכי פשוט בוואטסאפ בלחיצה אחת, או בטלפון למספר 050-653-3940 — נשמח לתאם ולענות על כל שאלה."},
    {"q": "איפה זה בדיוק?", "a": "בבית שאן, בלב עמק המעיינות — פרטי ההגעה המדויקים נשלחים לאחר התיאום."},
    {"q": "האם יש בתי כנסת בקרבת המתחם?", "a": "סמוך למתחם במרחק הליכה, יש מספר בתי כנסת עם מניינים בכל ימות השנה."}
  ]
}
```

- [ ] **Step 3: Write failing seed tests**

Append to `backend/content/tests.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe manage.py test content.tests.SeedContentTests`
Expected: FAIL with `CommandError: Unknown command: 'seed_content'`.

- [ ] **Step 5: Implement the command**

Create `backend/content/management/commands/seed_content.py`:

```python
import json
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from content.models import FaqItem, GalleryPhoto, GalleryTab

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"


class Command(BaseCommand):
    help = "Load the site's original gallery and FAQ. Does nothing if any content already exists."

    def handle(self, *args, **options):
        if GalleryTab.objects.exists() or GalleryPhoto.objects.exists() or FaqItem.objects.exists():
            self.stdout.write("content already seeded, skipping")
            return
        data = json.loads((SEED_DIR / "content.json").read_text(encoding="utf-8"))
        with transaction.atomic():
            for tab_order, tab_data in enumerate(data["gallery"], start=1):
                tab = GalleryTab.objects.create(title=tab_data["title"], order=tab_order)
                for photo_order, photo in enumerate(tab_data["photos"], start=1):
                    with open(SEED_DIR / photo["file"], "rb") as fh:
                        GalleryPhoto(
                            tab=tab, alt_text=photo["alt"], order=photo_order, image=File(fh, name=photo["file"])
                        ).save()
            for order, item in enumerate(data["faq"], start=1):
                FaqItem.objects.create(question=item["q"], answer=item["a"], order=order)
        self.stdout.write(
            f"seeded {GalleryTab.objects.count()} tabs, {GalleryPhoto.objects.count()} photos, "
            f"{FaqItem.objects.count()} FAQ items"
        )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe manage.py test`
Expected: 68 tests OK.

- [ ] **Step 7: Add the command to the Railway start command**

In `backend/railway.json`, replace the `startCommand` value with:

```json
    "startCommand": "python manage.py collectstatic --noinput && python manage.py seed_content && gunicorn config.wsgi --bind 0.0.0.0:$PORT --workers 2",
```

(Not `preDeployCommand`: Railway does not mount volumes during pre-deploy.)

- [ ] **Step 8: Seed the local database**

Run: `.venv/Scripts/python.exe manage.py migrate && .venv/Scripts/python.exe manage.py seed_content`
Expected: `seeded 4 tabs, 15 photos, 5 FAQ items`; `backend/media/gallery/` holds 15 JPEGs; `git status` does not list `backend/media/`.

- [ ] **Step 9: Commit (local only)**

```bash
git add backend/content/management backend/content/seed backend/content/tests.py backend/railway.json
git commit -m "Add seed_content command with current gallery and FAQ"
```

---

### Task 5: Site loads gallery and FAQ from the API

**Files:**
- Create: `site/content.js`
- Modify: `site/script.js:1-86` (carousel + reveal blocks), `site/index.html` (gallery wrapper, FAQ hook, script tag), `site/styles.css:222`

**Interfaces:**
- Consumes: `GET /api/content/` from Task 3.
- Produces: `window.initCarousel(carouselEl)`, `window.initReveal(elements)` in `script.js`.

Note on the spec: the API returns `width`/`height`, but `content.js` does not set them as `<img>` attributes. The carousel CSS already fixes every slide to `width:100%; aspect-ratio:3/2`, which reserves the space; an explicit `height` attribute would override that aspect ratio and break the slide size.

- [ ] **Step 1: Refactor `script.js` carousel block**

In `site/script.js`, change the first block's opening from:

```js
(function () {
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  document.querySelectorAll('[data-carousel]').forEach(function (car) {
```

to:

```js
(function () {
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Exposed so content.js can set up carousels it inserts after load.
  window.initCarousel = function (car) {
```

and change the end of that block from:

```js
    center(slides[n], false);
    markActive();
  });
})();
```

to:

```js
    center(slides[n], false);
    markActive();
  };

  document.querySelectorAll('[data-carousel]').forEach(window.initCarousel);
})();
```

- [ ] **Step 2: Refactor `script.js` reveal block**

Replace the whole reveal block:

```js
(function () {
  if (!('IntersectionObserver' in window)) return;
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
    });
  }, { rootMargin: '0px 0px -8% 0px' });
  // Siblings in a group cascade via --i; JS-only class so content shows without JS.
  document.querySelectorAll('.section-head, .feature, .gal-group, .attractions-carousel, .faq-item, .cta-band, .fact').forEach(function (el) {
    el.classList.add('reveal');
    el.style.setProperty('--i', Array.prototype.indexOf.call(el.parentNode.children, el) % 5);
    io.observe(el);
  });
})();
```

with:

```js
(function () {
  var io = 'IntersectionObserver' in window && new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
    });
  }, { rootMargin: '0px 0px -8% 0px' });
  // Siblings in a group cascade via --i; JS-only class so content shows without JS.
  // Exposed so content.js can animate elements it inserts after load.
  window.initReveal = function (elements) {
    if (!io) return;
    Array.prototype.forEach.call(elements, function (el) {
      el.classList.add('reveal');
      el.style.setProperty('--i', Array.prototype.indexOf.call(el.parentNode.children, el) % 5);
      io.observe(el);
    });
  };
  window.initReveal(document.querySelectorAll('.section-head, .feature, .gal-group, .attractions-carousel, .faq-item, .cta-band, .fact'));
})();
```

- [ ] **Step 3: Check the refactor changed nothing**

Serve the site (`cd site && python -m http.server 8765`), open `http://localhost:8765/` with the backend stopped, hard refresh.
Expected: gallery carousels scroll and loop as before, sections fade in on scroll, console has only failed-fetch errors (reviews).

- [ ] **Step 4: Add hooks in `index.html` and FAQ line breaks in CSS**

In `site/index.html`, wrap the four gallery groups (everything after the "הצצה פנימה" `section-head` div, up to the section's closing `</section>`) in a container:

```html
    <div class="section-head">
      <h2>הצצה פנימה</h2>
    </div>

    <div data-content="gallery">
    <div class="gal-group">
      <h3>פנים הבית</h3>
      <!-- ...all four existing .gal-group blocks, unchanged... -->
    </div>
    </div>
  </section>
```

Change `<div class="faq">` to `<div class="faq" data-content="faq">`.

After `<script src="reviews.js"></script>` add:

```html
<script src="content.js"></script>
```

In `site/styles.css`, change line 222 from:

```css
.faq-item p{margin:0;color:var(--muted);font-size:1rem;max-width:60ch;}
```

to:

```css
.faq-item p{margin:0;color:var(--muted);font-size:1rem;max-width:60ch;white-space:pre-line;}
```

- [ ] **Step 5: Write `content.js`**

Create `site/content.js`:

```js
(function () {
  var gallery = document.querySelector('[data-content="gallery"]');
  var faq = document.querySelector('[data-content="faq"]');
  if (!gallery && !faq) return;

  var local = location.hostname === 'localhost' || location.hostname === '127.0.0.1';
  var API = local ? 'http://localhost:8000' : 'https://api.alma-hosting.co.il';

  // textContent only: all text comes from the admin, never parsed as HTML.
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text) node.textContent = text;
    return node;
  }

  function galleryGroup(tab) {
    var track = el('div', 'carousel-track');
    tab.photos.forEach(function (p) {
      var img = document.createElement('img');
      img.src = p.url;
      img.alt = p.alt;
      img.loading = 'lazy';
      img.decoding = 'async';
      track.append(img);
    });
    var viewport = el('div', 'carousel-viewport');
    viewport.append(track);
    var carousel = el('div', 'carousel');
    carousel.setAttribute('data-carousel', '');
    carousel.append(viewport);
    var group = el('div', 'gal-group');
    group.append(el('h3', null, tab.title), carousel);
    return group;
  }

  function faqItem(item) {
    var node = el('div', 'faq-item');
    node.append(el('h3', null, item.q), el('p', null, item.a));
    return node;
  }

  function replace(container, nodes) {
    container.replaceChildren.apply(container, nodes);
    if (window.initReveal) window.initReveal(nodes);
  }

  var ctrl = 'AbortController' in window ? new AbortController() : null;
  var timer = ctrl && setTimeout(function () { ctrl.abort(); }, 5000);

  fetch(API + '/api/content/', ctrl ? { signal: ctrl.signal } : {})
    .then(function (res) {
      if (!res.ok) throw new Error('content ' + res.status);
      return res.json();
    })
    .then(function (data) {
      clearTimeout(timer);
      if (gallery && data.gallery && data.gallery.length) {
        var groups = data.gallery.map(galleryGroup);
        replace(gallery, groups);
        if (window.initCarousel) {
          groups.forEach(function (g) { window.initCarousel(g.querySelector('[data-carousel]')); });
        }
      }
      if (faq && data.faq && data.faq.length) replace(faq, data.faq.map(faqItem));
    })
    .catch(function () {
      clearTimeout(timer); // API down or slow: the static gallery and FAQ stay as they are
    });
})();
```

- [ ] **Step 6: Verify against the local backend**

Terminal 1 (from `backend/`, PowerShell): `$env:SITE_ORIGIN='http://localhost:8765'; .venv/Scripts/python.exe manage.py runserver 8000`
(Git Bash: `SITE_ORIGIN=http://localhost:8765 .venv/Scripts/python.exe manage.py runserver 8000`.)
Terminal 2: `cd site && python -m http.server 8765`.
Open `http://localhost:8765/`, hard refresh (Ctrl+F5).
Expected: in DevTools Network, `GET /api/content/` 200 and gallery images load from `http://localhost:8000/media/gallery/...`; gallery looks identical to before (4 tabs, 15 photos, carousels loop); FAQ shows the same 5 items; no new console errors.

- [ ] **Step 7: Verify owner edits and the Review Focus text case**

In the admin (`http://localhost:8000/alma-manage-x7/content/`):
1. Add a tab "בדיקה" with 2 photos, drag it to the top of the tab list.
2. Add a FAQ item with question `<b>בדיקה</b>?` and a two-line answer whose second line is `<script>alert(1)</script>`. Drag it to the top.
Reload the site.
Expected: "בדיקה" tab is first with its 2 photos; the new FAQ is first, shows the literal text `<b>בדיקה</b>?`, the answer shows on two lines, the `<script>` text is shown as text and no alert appears. Then delete the test tab and FAQ item in the admin.

- [ ] **Step 8: Verify fallback**

Stop the backend (Terminal 1), hard refresh the site.
Expected: original gallery and FAQ from `index.html` shown, carousels work, only failed-fetch errors in the console.

- [ ] **Step 9: Commit (local only)**

```bash
git add site/content.js site/script.js site/index.html site/styles.css
git commit -m "Load gallery and FAQ from the content API with static fallback"
```

---

### Task 6: Owner review (local)

**Files:** none.

- [ ] **Step 1: Full test run**

Run (from `backend/`): `.venv/Scripts/python.exe manage.py test`
Expected: 68 tests OK.

- [ ] **Step 2: Start both servers for the owner**

Backend on :8000 with `SITE_ORIGIN=http://localhost:8765`, site on :8765 (as in Task 5 Step 6).

- [ ] **Step 3: Hand over for review**

Tell the owner: admin at `http://localhost:8000/alma-manage-x7/content/` (log in via `/reviews/manage/login/`), site at `http://localhost:8765/`. List the local commits (`git log origin/master..`). **Stop and wait for explicit approval. Do not push.**

---

## Deployment (only after the owner approves Task 6)

Ask the owner before each production change.

1. **Railway volume:** on the backend service, create a volume mounted at `/data` (Railway tool `create-volume`, or dashboard → service → Volumes).
2. **Variable:** set `MEDIA_ROOT=/data/media` on the backend service.
3. **Push:** `git push origin master`. Cloudflare redeploys the site; Railway redeploys the backend (pre-deploy runs `migrate`, start command runs `seed_content`).
4. **Verify:**
   - Railway deploy logs contain `seeded 4 tabs, 15 photos, 5 FAQ items`.
   - `curl -s https://api.alma-hosting.co.il/api/content/` returns 4 tabs and 5 FAQ items with `https://api.alma-hosting.co.il/media/gallery/...` URLs.
   - One photo URL returns 200 with `Cache-Control: public, max-age=31536000, immutable`.
   - `https://alma-hosting.co.il/` shows the gallery and FAQ loaded from the API (Network tab).
   - Redeploy once more (Railway `redeploy`): logs show `content already seeded, skipping` and photos still load, which proves the volume persists.

Steps 1–2 must happen before step 3, or the first seed writes photos to the temporary disk.
