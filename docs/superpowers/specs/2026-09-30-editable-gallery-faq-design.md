# Editable Gallery & FAQ — Design

**Date:** 2026-09-30
**Status:** Design agreed in brainstorming, awaiting written-spec review.

## Goal

Let the site owner manage two sections of the Alma site from the existing Django admin panel, without touching code:

1. **"הצצה פנימה" (gallery):** add, edit, delete and reorder tabs, and the photos inside each tab.
2. **"כדאי לדעת לפני שמזמינים" (FAQ):** add, edit, delete and reorder question/answer pairs.

Success = the owner does all of the above in the admin, and the public site reflects the change on the next page load, with no deploy.

## Decisions (agreed)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Scope of control | Add, edit, delete **and reorder** tabs, photos and Q&A. |
| 2 | Photo storage | **Railway volume** attached to the existing backend service. No bucket, no extra Cloudflare configuration. |
| 3 | How the site shows content | **Plain JS fetch** (`site/content.js`), same pattern as `reviews.js`. No framework. Current HTML stays as fallback. |
| 4 | Reordering UX | **Drag and drop** via `django-admin-sortable2`. |
| 5 | Admin | The existing Django admin at `/alma-manage-x7/` (owner = admin = same person). |
| 6 | Workflow | Build and test locally; push only after owner approval. |

## Out of scope

- Server-side rendering of gallery/FAQ (Cloudflare Worker or rebuild-on-save). Search engines keep seeing the static fallback content; later additions are visible to Google only via JS rendering.
- Moving the site to a framework (Astro etc.). Separate project if ever wanted.
- Managing the "attractions" carousel, features, or any other section.
- Image formats other than JPEG output (no WebP/AVIF variants).
- Multiple image sizes (`srcset`).

## Architecture

```
Owner ──POST (login + CSRF)──▶ Django admin /alma-manage-x7/content/...  ──▶ Postgres (rows)
                                                                         └─▶ Railway volume /data/media (JPEG files)

Visitor ──GET──▶ alma-hosting.co.il (static, Cloudflare)
          └─ content.js ──GET──▶ api.alma-hosting.co.il/api/content/   (JSON)
                          └─GET──▶ api.alma-hosting.co.il/media/...    (photos)
```

Two paths, never mixed:
- **Write path:** the Django admin, reached by the owner only. Every save/delete/reorder is a POST to an admin URL (the same address that shows the form), requiring a logged-in staff session and Django's CSRF token. HTML forms cannot send PUT, so the admin never uses it.
- **Read path:** one public, read-only JSON endpoint plus the photo files. No login. Everything returned is already public on the site.

The existing Cloudflare proxy in front of `api.alma-hosting.co.il` stays exactly as it is (the `ORIGIN_AUTH_SECRET` check depends on it). Nothing is added to it.

## Backend

### New app: `content`

Separate from `reviews` (different responsibility). Registered in `INSTALLED_APPS` together with `adminsortable2`.

### Models

| Model | Fields | Notes |
|---|---|---|
| `GalleryTab` | `title` CharField(60), `order` PositiveIntegerField (default 0, indexed) | `Meta.ordering = ["order"]`. Hebrew verbose names ("לשונית גלריה" / "לשוניות גלריה"). |
| `GalleryPhoto` | `tab` FK → GalleryTab (CASCADE, related_name `photos`), `image` ImageField, `alt_text` CharField(150, required), `width`/`height` PositiveIntegerField (filled on save), `order` | `Meta.ordering = ["order"]`. |
| `FaqItem` | `question` CharField(200), `answer` TextField (max 1000, enforced with `MaxLengthValidator` like `Review.text`), `order` | `Meta.ordering = ["order"]`. Verbose "שאלה נפוצה" / "שאלות נפוצות". |

### Photo processing (on `GalleryPhoto` save, when the image changed)

- Reject files over **15 MB** and non-images, with Hebrew validation messages (validator on the field).
- Open with Pillow, apply EXIF orientation (`ImageOps.exif_transpose`, so phone photos are not sideways), convert to RGB, shrink so the longest side is at most **1600 px** (never upscale), save as **JPEG quality 82, progressive**.
- File name: `gallery/<uuid4 hex>.jpg`. Unique names mean a replaced photo is a new URL, so caches never show the old one.
- Store resulting `width` and `height` on the row.
- **Orphan cleanup:** when a photo row is deleted, or its image is replaced, delete the old file from storage (`post_delete` signal + compare-on-save). Deleting a tab cascades to its photos, and their files are removed the same way.

New dependency: **Pillow** (required by `ImageField`).

### Admin

Using `django-admin-sortable2`:

- **"לשוניות גלריה"** — `SortableAdminMixin` list: drag rows to reorder tabs (saved immediately by a background POST). Opening a tab shows a `SortableTabularInline` of its photos: thumbnail preview (read-only), image upload, alt text, drag handle. Add/delete photos in the inline; the new photo order saves with "שמירה".
- **"שאלות נפוצות"** — `SortableAdminMixin` list with question as the display column; drag to reorder.

### API: `GET /api/content/`

Response:

```json
{
  "gallery": [
    { "title": "חדרי שינה",
      "photos": [ { "url": "https://api.alma-hosting.co.il/media/gallery/ab12….jpg",
                    "alt": "חדר שינה זוגי, יחידה א׳", "width": 1600, "height": 1067 } ] }
  ],
  "faq": [ { "q": "יש בריכה?", "a": "ביחידות עצמן אין בריכה…" } ]
}
```

- Order follows the admin order. Tabs with zero photos are omitted.
- `@require_GET` (anything else → 405).
- `Access-Control-Allow-Origin: settings.SITE_ORIGIN`, same as `/api/reviews/`.
- Absolute photo URLs built with `request.build_absolute_uri` (the site is on a different domain).
- Queries: `prefetch_related("photos")` so the whole response is 2 queries regardless of size.

### Serving photos

- `MEDIA_URL = "/media/"`. `MEDIA_ROOT` = env var `MEDIA_ROOT` if set, else `BASE_DIR / "media"`. In production `MEDIA_ROOT=/data/media`.
- A URL route serves `/media/<path>` with `django.views.static.serve` in both dev and production, wrapped to add `Cache-Control: public, max-age=31536000, immutable` (safe because names are unique).
- Code comment (ponytail): Django-served media is fine at this scale; if traffic grows, move photos to a bucket or let Cloudflare cache them.
- `backend/media/` is added to `.gitignore`.

### Seeding current content

Management command `seed_content`:

- Runs only if **all three tables are empty**; otherwise prints "already seeded" and exits. Never overwrites owner edits.
- Creates the current **4 tabs** (פנים הבית, חדרי שינה, חדרי רחצה, בחוץ), their **15 photos** with the current alt texts, and the current **5 Q&A**, in the current order.
- Photo sources: copies of the 15 gallery JPEGs stored in `backend/content/seed/`. They go through the same resize pipeline on import.
- Runs in the Railway **start command**, not `preDeployCommand`: Railway does not mount volumes during pre-deploy (confirmed in Railway docs, "Volume availability"). New start command:
  `python manage.py collectstatic --noinput && python manage.py seed_content && gunicorn ...`

### Upload limits

`DATA_UPLOAD_MAX_MEMORY_SIZE` (64 KB) covers non-file form data only, so admin forms fit. File size is capped by the 15 MB validator. No settings change needed.

## Site

### `site/content.js` (new)

- Loaded after `script.js`. Same API base logic as `reviews.js` (`localhost:8000` locally, `https://api.alma-hosting.co.il` otherwise).
- Fetch `/api/content/` with a **5-second timeout** (`AbortController`).
- On success with non-empty data:
  - Replace the gallery groups inside the "הצצה פנימה" section with rebuilt `.gal-group > h3 + .carousel[data-carousel] > .carousel-viewport > .carousel-track > img` markup (same classes, so no CSS change).
  - Replace the `.faq` list with rebuilt `.faq-item > h3 + p` items.
  - Build DOM with `createElement` / `textContent` / `setAttribute` only — never `innerHTML` with API data.
  - Images get `loading="lazy"`, `decoding="async"`, `width`, `height`, `alt`.
  - Call the carousel and reveal initialisers for the new nodes.
- If `gallery` is empty, leave the gallery fallback in place; same for `faq` independently.
- On error, timeout or non-200: do nothing. The static fallback stays; no error shown.

### `site/script.js` (refactor, no behaviour change)

- Extract the per-carousel setup into `window.initCarousel(el)`; the page-load loop calls it for each `[data-carousel]`.
- Extract the reveal setup into `window.initReveal(elements)`; the page-load code calls it with the current selector list.
- `content.js` calls both for the elements it inserts.

### `site/index.html`

- Add `<script src="content.js" defer></script>` after `script.js`.
- Mark the gallery container and FAQ list with `data-content="gallery"` / `data-content="faq"` so `content.js` finds them without relying on headings.
- Existing gallery and FAQ markup stays unchanged as the fallback.

## Error handling summary

| Situation | Result |
|---|---|
| API down / slow / error | Static fallback shown; no visible error. |
| Tab with no photos | Omitted from API, not shown. |
| Upload > 15 MB or not an image | Admin form error in Hebrew; nothing saved. |
| Photo deleted/replaced | Old file removed from volume. |
| `seed_content` on non-empty DB | No-op. |

## Testing

**Automated (Django `TestCase`, in `content/tests.py`):**
- Upload pipeline: large image shrunk to ≤1600 px, saved as JPEG, EXIF rotation applied, width/height stored.
- Validation: >15 MB rejected, non-image rejected.
- File cleanup: deleting a photo, replacing its image, and deleting a tab each remove the old file(s).
- API: correct shape, admin order respected, empty tab omitted, POST → 405, CORS header equals `SITE_ORIGIN`, absolute URLs.
- Media route: serves a file with the long `Cache-Control` header.
- `seed_content`: creates 4 tabs / 15 photos / 5 Q&A on empty DB; second run changes nothing; skips if owner already added anything.
- Admin: changelist pages return 200 for staff, redirect to login for anonymous.
- Existing `reviews` tests still pass.

Tests use a temporary `MEDIA_ROOT` (`override_settings` + temp dir) so they never touch real files.

**Manual (local browser, backend on :8000 + site on :8765):**
1. Log in to admin, add a tab, upload photos (including a large phone photo), drag to reorder, add a Q&A, reorder Q&A.
2. Reload the site: new tab and Q&A appear in the chosen order; carousels scroll; fade-in works.
3. Stop the backend, reload: fallback content shown, no breakage beyond the failed fetch.

**Owner review locally → approval → push.**

## Deployment (after approval only)

1. Create a Railway volume on the backend service, mounted at `/data`. Set `MEDIA_ROOT=/data/media`. (Claude asks before doing this with the Railway tool.)
2. Push to `master` (site deploys via Cloudflare; backend deploys via Railway).
3. First start runs `seed_content`, which fills the database and volume with the current content.
4. Verify `https://api.alma-hosting.co.il/api/content/` and the live gallery/FAQ.

Order matters: the volume and `MEDIA_ROOT` must exist before the first deploy that runs `seed_content`, or seeded photos land on the ephemeral disk.

## Files touched

- New: `backend/content/` (app: `models.py`, `admin.py`, `views.py`, `urls.py`, `images.py`, `tests.py`, `management/commands/seed_content.py`, `migrations/`, `seed/*.jpg`), `site/content.js`.
- Changed: `backend/config/settings.py`, `backend/config/urls.py`, `backend/requirements.txt`, `backend/railway.json`, `.gitignore`, `site/script.js`, `site/index.html`.
