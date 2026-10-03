# Airbnb Reviews Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import the Alma listing's Airbnb reviews daily into the existing `Review` table through an Apify scraper, publish them immediately, and label them "מ-Airbnb" on the site.

**Architecture:** A management command `import_airbnb_reviews` calls Apify's synchronous `run-sync-get-dataset-items` endpoint with `urllib`, maps each item to a `Review` row (`source="airbnb"`, `external_id` = Airbnb review ID) and creates only unknown IDs. A separate Railway cron service runs the command daily with its own config file. The API gains a `source` field, the site shows a label, and the owner panel can only hide (never delete) Airbnb rows, so they never come back.

**Tech Stack:** Django 5.2, Python 3.13, Postgres on Railway (SQLite locally), stdlib `urllib` + `json`, Apify actor `tri_angle/airbnb-reviews-scraper`, vanilla JS site.

**Spec:** `docs/superpowers/specs/2026-10-03-airbnb-reviews-import-design.md`

## Global Constraints

- No new Python dependency. HTTP uses `urllib.request` only.
- `APIFY_TOKEN` comes only from the environment. Never commit it, never put it in a URL (send it as `Authorization: Bearer`).
- `AIRBNB_LISTING_URL` defaults to `https://www.airbnb.com/rooms/1771157482793114563`.
- Actor ID constant: `tri_angle~airbnb-reviews-scraper` (fallback `cirkit~airbnb-reviews-scraper` only if Task 1 shows the first is unusable).
- Request timeout 300 seconds.
- Imported text: original language, stripped, max 1000 characters (999 + "…").
- Imported name: max 100 characters.
- Imported reviews: `is_approved=True`, `source="airbnb"`.
- The import never updates or deletes existing rows.
- Cron schedule `0 4 * * *`.
- The repo is public: the test fixture uses synthetic values in the real JSON structure, no real reviewer data.
- Never `git add -A` in this repo (the root has many untracked files). Add exact paths.
- Never `git push` from Claude. The user runs `git push origin master`. A push to master deploys the static site immediately.
- Run tests from `backend/`: `.venv/Scripts/python.exe manage.py test reviews`.

## Review Focus

- The same review ID appears twice in one Apify response → created once. (Task 3, `test_duplicate_id_in_one_response_created_once`)
- An item with a missing or unparseable date → that item is skipped, the rest still import. (Task 3, `test_item_with_bad_date_skipped_others_imported`)
- Apify answers with a JSON object instead of a list (actor error payload) → `CommandError`, nothing saved. (Task 3, `test_non_list_response_raises_and_saves_nothing`)
- Whitespace-only text or a non-dict item → skipped, not imported as an empty card. (Task 3, `test_unusable_items_skipped`)
- Owner deletes an Airbnb review from the Django admin (not the panel) → not possible, so it can't silently come back. (Task 4, `test_admin_cannot_delete_airbnb_review`)

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/reviews/models.py` | `Review.Source` choices, `source`, `external_id`. |
| `backend/reviews/migrations/0003_review_source_external_id.py` | Generated migration. |
| `backend/reviews/management/__init__.py`, `backend/reviews/management/commands/__init__.py` | Package markers (empty). |
| `backend/reviews/management/commands/import_airbnb_reviews.py` | Fetch from Apify, map items, create rows. |
| `backend/reviews/fixtures/apify_sample.json` | Synthetic items in the real Apify structure. |
| `backend/reviews/views.py` | `source` in API; delete-as-hide for Airbnb rows. |
| `backend/reviews/admin.py` | `source` column/filter; no admin delete for Airbnb rows. |
| `backend/templates/reviews/manage.html` | Airbnb label; no delete button for Airbnb rows. |
| `backend/reviews/tests.py` | All new tests. |
| `backend/railway.cron.json` | Cron service config. |
| `site/reviews.js`, `site/styles.css` | "מ-Airbnb" label on cards. |

---

### Task 1: Record a real Apify sample and build the fixture

Needs the user: an Apify account (free plan) and an API token from https://console.apify.com/settings/integrations. Ask the user to put it in the shell, never in a file in the repo.

**Files:**
- Create: `backend/reviews/fixtures/apify_sample.json`

**Interfaces:**
- Produces: the item keys the command reads. Expected (to verify in Step 2): `id` (string or number), `text` (string), `createdAt` (ISO 8601 string), `reviewer.firstName` (string). If the real keys differ, write the real ones into the "Confirmed keys" note at the bottom of this task and use them in Task 3 everywhere this plan says `id` / `text` / `createdAt` / `reviewer.firstName`.

- [ ] **Step 1: Run the actor once against the real listing**

The user runs this in Git Bash from `backend/` (token stays in their shell):

```bash
export APIFY_TOKEN=...   # user pastes their token
curl -s -X POST "https://api.apify.com/v2/acts/tri_angle~airbnb-reviews-scraper/run-sync-get-dataset-items" \
  -H "Authorization: Bearer $APIFY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"startUrls":[{"url":"https://www.airbnb.com/rooms/1771157482793114563"}]}' \
  -o "$TEMP/apify_raw.json"
python -m json.tool "$TEMP/apify_raw.json" | head -60
```

Expected: a JSON **list** with 5 items (the listing has 5 reviews). If the response is an object with an `error` key mentioning input, open https://apify.com/tri_angle/airbnb-reviews-scraper/input-schema, fix the input field name, and retry. If the actor returns nothing useful after the input is right, repeat with `cirkit~airbnb-reviews-scraper` and use that ID as the constant in Task 3.

The raw file stays in `$TEMP`, outside the repo.

- [ ] **Step 2: Confirm the keys**

```bash
python -c "import json,os; items=json.load(open(os.path.join(os.environ['TEMP'],'apify_raw.json'),encoding='utf-8')); print(len(items)); print(sorted(items[0])); print({k: items[0].get(k) for k in ('id','createdAt')}); print(items[0].get('reviewer'))"
```

Expected: keys include `id`, `text`, `createdAt`, `reviewer` (with `firstName`). Note any difference in "Confirmed keys" below.

- [ ] **Step 3: Write the fixture with synthetic values**

Same structure as the real items (keep every key the command reads, drop the rest), synthetic values. Create `backend/reviews/fixtures/apify_sample.json`:

```json
[
  {
    "id": "1100000000000000001",
    "text": "Lovely apartment, spotless and quiet. We will be back!",
    "createdAt": "2026-08-14T10:21:00Z",
    "reviewer": {"firstName": "Dana"}
  },
  {
    "id": 1100000000000000002,
    "text": "דירה מקסימה ומאובזרת, מארח זמין ונעים.",
    "createdAt": "2026-07-02T18:05:00Z",
    "reviewer": {"firstName": "יוסי"}
  },
  {
    "id": "1100000000000000003",
    "text": "Great place for families.",
    "createdAt": "2026-05-20T08:00:00Z",
    "reviewer": {"firstName": "Maria"}
  }
]
```

The second item's numeric `id` is deliberate: the command must store IDs as strings.

- [ ] **Step 4: Commit**

```bash
git add backend/reviews/fixtures/apify_sample.json
git commit -m "Add Apify review sample fixture"
```

**Confirmed keys:** _(fill in after Step 2 only if they differ from `id`, `text`, `createdAt`, `reviewer.firstName`)_

---

### Task 2: `source` and `external_id` on `Review`, `source` in the API

**Files:**
- Modify: `backend/reviews/models.py`
- Create: `backend/reviews/migrations/0003_review_source_external_id.py` (generated)
- Modify: `backend/reviews/views.py` (`reviews_api`)
- Test: `backend/reviews/tests.py`

**Interfaces:**
- Produces: `Review.Source` (`TextChoices`: `Review.Source.SITE == "site"`, `Review.Source.AIRBNB == "airbnb"`), `Review.source` (default `"site"`), `Review.external_id` (`str | None`, unique). API items: `{"name", "text", "stay_month", "stay_year", "source"}`.

- [ ] **Step 1: Write the failing tests**

In `backend/reviews/tests.py`, add to `ReviewModelTests`:

```python
    def test_new_review_defaults_to_site_source(self):
        review = make_review()
        review.save()
        self.assertEqual(review.source, Review.Source.SITE)
        self.assertIsNone(review.external_id)

    def test_many_site_reviews_without_external_id_allowed(self):
        make_review().save()
        make_review().save()  # two NULL external_ids must not clash
        self.assertEqual(Review.objects.count(), 2)
```

In `ReviewsApiTests`, replace `test_payload_has_exact_keys_no_personal_data` and add a source test:

```python
    def test_payload_has_exact_keys_no_personal_data(self):
        review = self.client.get(reverse("reviews:api")).json()["reviews"][0]
        self.assertEqual(set(review), {"name", "text", "stay_month", "stay_year", "source"})

    def test_payload_includes_source(self):
        make_review(text="מאירבנבי עם מקור", is_approved=True, source=Review.Source.AIRBNB, external_id="42").save()
        sources = {r["text"]: r["source"] for r in self.client.get(reverse("reviews:api")).json()["reviews"]}
        self.assertEqual(sources, {"מאושרת ומומלצת מאוד": "site", "מאירבנבי עם מקור": "airbnb"})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe manage.py test reviews.tests.ReviewModelTests reviews.tests.ReviewsApiTests`
Expected: FAIL / ERROR (`Review` has no attribute `Source`, payload keys missing `source`).

- [ ] **Step 3: Add the fields**

In `backend/reviews/models.py`, inside `class Review`, before `author_name`:

```python
    class Source(models.TextChoices):
        SITE = "site", "אתר"
        AIRBNB = "airbnb", "Airbnb"
```

After `created_at`:

```python
    source = models.CharField("מקור", max_length=10, choices=Source.choices, default=Source.SITE)
    # Airbnb review ID. NULL for site reviews; the unique index ignores NULLs.
    external_id = models.CharField("מזהה חיצוני", max_length=64, null=True, blank=True, unique=True)
```

- [ ] **Step 4: Generate the migration**

Run: `.venv/Scripts/python.exe manage.py makemigrations reviews --name review_source_external_id`
Expected: `reviews/migrations/0003_review_source_external_id.py` with two `AddField` operations. `source` has `default="site"`, so existing rows become `site`.

- [ ] **Step 5: Add `source` to the API**

In `backend/reviews/views.py`, in `reviews_api`, add to the dict:

```python
            "stay_year": r.stay_year,
            "source": r.source,
```

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe manage.py test reviews`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/reviews/models.py backend/reviews/migrations/0003_review_source_external_id.py backend/reviews/views.py backend/reviews/tests.py
git commit -m "Add review source and external ID, expose source in API"
```

---

### Task 3: `import_airbnb_reviews` command

**Files:**
- Create: `backend/reviews/management/__init__.py` (empty)
- Create: `backend/reviews/management/commands/__init__.py` (empty)
- Create: `backend/reviews/management/commands/import_airbnb_reviews.py`
- Test: `backend/reviews/tests.py`

**Interfaces:**
- Consumes: `Review.Source.AIRBNB`, `Review.external_id` (Task 2); fixture `backend/reviews/fixtures/apify_sample.json` and its keys (Task 1).
- Produces: command `import_airbnb_reviews` (no arguments). Env: `APIFY_TOKEN` (required), `AIRBNB_LISTING_URL` (optional). Module functions `fetch_reviews(token: str, listing_url: str) -> list` and `to_fields(item) -> dict | None`. Stdout last line: `fetched N, created X, skipped Y`. Failure: `CommandError` (exit code 1).

- [ ] **Step 1: Write the failing tests**

At the top of `backend/reviews/tests.py`, add imports:

```python
from io import StringIO
from unittest import mock
from urllib.error import URLError

from django.core.management import CommandError, call_command
```

At the bottom, add:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe manage.py test reviews.tests.ImportAirbnbReviewsTests`
Expected: ERROR, `Unknown command: 'import_airbnb_reviews'` / module not found for the patch target.

- [ ] **Step 3: Create the package markers**

Create empty files `backend/reviews/management/__init__.py` and `backend/reviews/management/commands/__init__.py`.

- [ ] **Step 4: Write the command**

Create `backend/reviews/management/commands/import_airbnb_reviews.py` (if Task 1 recorded different keys, use them in `to_fields`):

```python
import json
import os
from datetime import datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from reviews.models import Review

ACTOR = "tri_angle~airbnb-reviews-scraper"
DEFAULT_LISTING_URL = "https://www.airbnb.com/rooms/1771157482793114563"
TIMEOUT_SECONDS = 300  # Apify's cap for run-sync endpoints
MAX_TEXT = 1000
MAX_NAME = 100
FALLBACK_NAME = "אורח/ת"


def fetch_reviews(token, listing_url):
    """Run the Apify actor and return its dataset items. Raises CommandError on any failure."""
    request = Request(
        f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items",
        data=json.dumps({"startUrls": [{"url": listing_url}]}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            items = json.loads(response.read())
    except (URLError, TimeoutError, ValueError) as exc:  # ValueError covers bad JSON
        raise CommandError(f"Apify request failed: {exc}") from exc
    if not isinstance(items, list):
        raise CommandError(f"Apify returned {type(items).__name__}, expected a list")
    return items


def to_fields(item):
    """Map one Apify item to Review fields, or None if it can't be shown."""
    if not isinstance(item, dict):
        return None
    review_id = item.get("id")
    text = (item.get("text") or "").strip()
    if review_id in (None, "") or not text:
        return None
    try:
        created = datetime.fromisoformat(item["createdAt"])
    except (KeyError, TypeError, ValueError):
        return None
    if len(text) > MAX_TEXT:
        text = text[: MAX_TEXT - 1] + "…"
    reviewer = item.get("reviewer") if isinstance(item.get("reviewer"), dict) else {}
    name = (reviewer.get("firstName") or "").strip() or FALLBACK_NAME
    return {
        "author_name": name[:MAX_NAME],
        "text": text,
        # Airbnb hides the stay date; reviews come within 14 days of checkout, so the month is close enough.
        "stay_month": created.month,
        "stay_year": created.year,
        "source": Review.Source.AIRBNB,
        "external_id": str(review_id),
        "is_approved": True,
    }


class Command(BaseCommand):
    help = "Import new Airbnb reviews of the Alma listing through Apify."

    def handle(self, *args, **options):
        token = os.environ.get("APIFY_TOKEN")
        if not token:
            raise CommandError("APIFY_TOKEN is not set")
        listing_url = os.environ.get("AIRBNB_LISTING_URL") or DEFAULT_LISTING_URL

        items = fetch_reviews(token, listing_url)
        known = set(Review.objects.exclude(external_id=None).values_list("external_id", flat=True))
        created = skipped = 0
        with transaction.atomic():
            for index, item in enumerate(items):
                fields = to_fields(item)
                if fields is None:
                    self.stderr.write(f"skipped unusable item #{index}")
                    skipped += 1
                elif fields["external_id"] in known:
                    skipped += 1
                else:
                    Review.objects.create(**fields)
                    known.add(fields["external_id"])
                    created += 1
        self.stdout.write(f"fetched {len(items)}, created {created}, skipped {skipped}")
```

- [ ] **Step 5: Run the command tests**

Run: `.venv/Scripts/python.exe manage.py test reviews.tests.ImportAirbnbReviewsTests`
Expected: all PASS.

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe manage.py test reviews`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/reviews/management/__init__.py backend/reviews/management/commands/__init__.py backend/reviews/management/commands/import_airbnb_reviews.py backend/reviews/tests.py
git commit -m "Add import_airbnb_reviews command"
```

---

### Task 4: Owner panel and admin protect Airbnb reviews

**Files:**
- Modify: `backend/reviews/views.py` (`manage_action`)
- Modify: `backend/templates/reviews/manage.html`
- Modify: `backend/reviews/admin.py`
- Test: `backend/reviews/tests.py`

**Interfaces:**
- Consumes: `Review.Source.AIRBNB`, `Review.source` (Task 2).
- Produces: `manage_action` treats `delete` on an Airbnb row as `hide`. Panel shows "Airbnb" label and no delete button for those rows. Admin refuses delete for Airbnb rows.

- [ ] **Step 1: Write the failing tests**

Add to `ManagePanelTests`:

```python
    def make_airbnb(self):
        review = make_review(text="ייבוא מאירבנבי מאושר", is_approved=True, source=Review.Source.AIRBNB, external_id="77")
        review.save()
        return review

    def test_delete_on_airbnb_review_hides_it(self):
        review = self.make_airbnb()
        self.client.force_login(self.owner)
        self.client.post(reverse("reviews:manage_action", args=[review.pk]), {"action": "delete"})
        review.refresh_from_db()  # still exists, so the next import won't recreate it
        self.assertFalse(review.is_approved)

    def test_panel_labels_airbnb_and_offers_no_delete(self):
        review = self.make_airbnb()
        self.client.force_login(self.owner)
        html = self.client.get(reverse("reviews:manage")).content.decode()
        start = html.rindex("<article", 0, html.index(review.text))
        card = html[start : html.index("</article>", start)]
        self.assertIn("Airbnb", card)
        self.assertNotIn('value="delete"', card)
        self.assertIn('value="delete"', html)  # the site review still has its delete button
```

Add a new class:

```python
class ReviewAdminTests(TestCase):
    def test_admin_cannot_delete_airbnb_review(self):
        from django.contrib.admin.sites import site

        admin = site._registry[Review]
        owner = get_user_model().objects.create_superuser("root", password="pw-root-123")
        request = mock.Mock(user=owner)
        airbnb = make_review(source=Review.Source.AIRBNB, external_id="9")
        airbnb.save()
        site_review = make_review()
        site_review.save()
        self.assertFalse(admin.has_delete_permission(request, airbnb))
        self.assertTrue(admin.has_delete_permission(request, site_review))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe manage.py test reviews.tests.ManagePanelTests reviews.tests.ReviewAdminTests`
Expected: the three new tests FAIL (review deleted, delete button present, admin allows delete).

- [ ] **Step 3: Delete-as-hide in the view**

In `backend/reviews/views.py`, `manage_action`, after `action = request.POST.get("action")`:

```python
    if action == "delete" and review.source == Review.Source.AIRBNB:
        action = "hide"  # a deleted import would come back on the next daily run
```

- [ ] **Step 4: Panel template**

In `backend/templates/reviews/manage.html`, replace the meta line:

```html
        <p class="meta">{% if r.source == "airbnb" %}<strong>Airbnb</strong> · {% endif %}התארחו ב{{ r.stay_label }} · נשלח {{ r.created_at|date:"d.m.Y H:i" }}</p>
```

and wrap the delete button:

```html
          {% if r.source != "airbnb" %}
            <button class="btn btn-danger" name="action" value="delete" onclick="return confirm('למחוק את ההמלצה לצמיתות?')">מחיקה</button>
          {% endif %}
```

- [ ] **Step 5: Admin**

In `backend/reviews/admin.py`, replace the `list_display`, `list_filter` and `readonly_fields` lines, and add the delete guard:

```python
    list_display = ("author_name", "short_text", "source", "stay_month", "stay_year", "created_at", "is_approved")
    list_filter = ("is_approved", "source")
    readonly_fields = ("created_at", "source", "external_id")

    def has_delete_permission(self, request, obj=None):
        # A deleted Airbnb import would come back on the next run; hide it instead.
        if obj is not None and obj.source == Review.Source.AIRBNB:
            return False
        return super().has_delete_permission(request, obj)
```

- [ ] **Step 6: Run the whole suite**

Run: `.venv/Scripts/python.exe manage.py test reviews`
Expected: all PASS, including the old `test_approve_hide_delete` (site reviews still delete).

- [ ] **Step 7: Commit**

```bash
git add backend/reviews/views.py backend/templates/reviews/manage.html backend/reviews/admin.py backend/reviews/tests.py
git commit -m "Protect imported Airbnb reviews from deletion in panel and admin"
```

---

### Task 5: "מ-Airbnb" label on the site

No JS test setup exists in this repo; verification is manual.

**Files:**
- Modify: `site/reviews.js` (`card`)
- Modify: `site/styles.css` (after `.review-meta`, around line 357)

**Interfaces:**
- Consumes: API field `source` (Task 2). Missing `source` (old API) renders as a site review.

- [ ] **Step 1: Add the label in `card()`**

In `site/reviews.js`, replace the `card` function:

```js
  function card(review) {
    var article = el('article', 'review-card');
    article.append(
      el('span', 'review-initials', initials(review.name)),
      el('h3', 'review-name', review.name),
      el('p', 'review-meta', stayLabel(review.stay_month, review.stay_year))
    );
    if (review.source === 'airbnb') article.append(el('span', 'review-source', 'מ-Airbnb'));
    article.append(el('p', 'review-text', review.text));
    return article;
  }
```

- [ ] **Step 2: Style it**

In `site/styles.css`, right after the `.review-meta{...}` line:

```css
.review-source{display:inline-block;margin:-.6rem 0 .8rem;padding:.1rem .55rem;border:1px solid var(--muted);border-radius:999px;color:var(--muted);font-size:.72rem;letter-spacing:.02em;}
```

- [ ] **Step 3: Manual check**

From `backend/`, put one Airbnb review in the local DB and serve the API on a free port:

```bash
.venv/Scripts/python.exe manage.py shell -c "from reviews.models import Review; Review.objects.get_or_create(external_id='local-test', defaults=dict(author_name='Dana', text='Lovely apartment, spotless and quiet.', stay_month=8, stay_year=2026, source='airbnb', is_approved=True))"
.venv/Scripts/python.exe manage.py runserver 8001
```

In another shell: `curl -s http://localhost:8001/api/reviews/` shows `"source": "airbnb"` for Dana.

To see the label: port 8000 is normally taken by a Docker container on this machine, and `reviews.js` calls `localhost:8000` locally. Ask the user before stopping that container. If they agree, run `runserver 8000`, serve `site/` (for example `python -m http.server 5500 --directory ../site`) and open `http://localhost:5500/#reviews`. Otherwise, check the label after deploy (Task 7). Afterwards remove the test row:

```bash
.venv/Scripts/python.exe manage.py shell -c "from reviews.models import Review; Review.objects.filter(external_id='local-test').delete()"
```

- [ ] **Step 4: Commit**

```bash
git add site/reviews.js site/styles.css
git commit -m "Show Airbnb label on imported reviews"
```

---

### Task 6: Railway cron config and local rehearsal with real Apify

**Files:**
- Create: `backend/railway.cron.json`

**Interfaces:**
- Consumes: command `import_airbnb_reviews` (Task 3).
- Produces: config file the Railway service `airbnb-import` points to.

- [ ] **Step 1: Write the cron config**

Create `backend/railway.cron.json`:

```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "deploy": {
    "startCommand": "python manage.py import_airbnb_reviews",
    "cronSchedule": "0 4 * * *",
    "restartPolicyType": "NEVER"
  }
}
```

No `preDeployCommand` (migrations stay with the web service) and no `healthcheckPath` (cron jobs exit).

- [ ] **Step 2: Validate the JSON**

Run: `.venv/Scripts/python.exe -m json.tool railway.cron.json`
Expected: the file printed back, no error.

- [ ] **Step 3: Real import locally (user supplies the token in their shell)**

```bash
export APIFY_TOKEN=...   # user pastes token
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py import_airbnb_reviews
.venv/Scripts/python.exe manage.py import_airbnb_reviews
```

Expected: first run `fetched 5, created 5, skipped 0` (or the current review count). Second run `created 0, skipped 5`. Check names, texts and months look right:

```bash
.venv/Scripts/python.exe manage.py shell -c "from reviews.models import Review; [print(r.external_id, r.author_name, r.stay_month, r.stay_year, r.text[:50]) for r in Review.objects.filter(source='airbnb')]"
```

If any field is wrong, fix `to_fields` in Task 3's file plus the fixture, rerun the tests, and commit that fix before going on.

- [ ] **Step 4: Commit**

```bash
git add backend/railway.cron.json
git commit -m "Add Railway cron config for the Airbnb import"
```

---

### Task 7: Deploy (user-driven, only after the user approves)

- [ ] **Step 1: Full test run**

Run: `.venv/Scripts/python.exe manage.py test`
Expected: all PASS.

- [ ] **Step 2: User pushes**

Warn first: the push deploys the static site immediately and Railway redeploys the web service (runs migration `0003`). The user runs:

```bash
! git push origin master
```

Check `https://api.alma-hosting.co.il/api/reviews/` returns items with `"source"`.

- [ ] **Step 3: Create the cron service (Railway dashboard, or the Railway MCP/`use-railway` skill with the user watching)**

In the Alma project:
1. New service from the GitHub repo `Toxice/alma-beit-shean-site`, branch `master`, name `airbnb-import`.
2. Settings → Root directory: `backend`.
3. Settings → Config-as-code file path: `/backend/railway.cron.json` (Railway resolves this path from the repo root, not from the root directory).
4. Variables: `DATABASE_URL` = reference to the existing Postgres `DATABASE_URL`; `SECRET_KEY` = reference to the web service's `SECRET_KEY`; `APIFY_TOKEN` = the user's token; `AIRBNB_LISTING_URL` = `https://www.airbnb.com/rooms/1771157482793114563`.
5. No public domain.

- [ ] **Step 4: First run by hand**

Trigger the cron service once from the dashboard ("Run now" / deploy). In its logs expect `fetched 5, created 5, skipped 0`. Then open `https://alma-hosting.co.il/#reviews` and check the 5 Airbnb reviews show with the "מ-Airbnb" label, and `https://api.alma-hosting.co.il/manage` shows them with no delete button.

- [ ] **Step 5: Confirm the schedule**

The service settings show cron `0 4 * * *`. Next morning, its logs show `created 0, skipped 5` (or new reviews created).
