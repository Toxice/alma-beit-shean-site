# Airbnb Reviews Import — Design

**Date:** 2026-10-03
**Status:** Design agreed in brainstorming, awaiting written-spec review.

## Goal

Show the Alma listing's Airbnb reviews on the site automatically, next to the reviews guests write on our own form, without anyone copying them by hand.

Success = a new Airbnb review appears on alma-hosting.co.il within about 24 hours of being posted on Airbnb, with no manual step.

## Background

- Airbnb has no public API. Its API is invite-only for software partners (channel managers, PMS).
- Checked on 2026-10-03 in the owner's Airbnb account: no channel manager or PMS connected, no calendar sync, professional hosting tools off. So there is no official route to the reviews.
- The listing (`https://www.airbnb.com/rooms/1771157482793114563`) has 5 reviews today, average 5.0.
- Chosen route: an Apify scraper reads the public reviews from the listing page. This is against Airbnb's terms of service. The risk sits with the scraper reading a public page, not with the owner's account, which is never logged into.

## Decisions (agreed)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Source of reviews | Apify actor `tri_angle/airbnb-reviews-scraper` (fallback: `cirkit/airbnb-reviews-scraper`). |
| 2 | Where it runs | Django management command `import_airbnb_reviews`, run by a separate Railway cron service. |
| 3 | Frequency | Once a day, `0 4 * * *` (04:00 UTC, about 07:00 Israel time). |
| 4 | Publishing | Imported reviews are published immediately (`is_approved=True`). The owner can hide them in the panel. |
| 5 | Look on the site | Same card as guest reviews, plus a small "מ-Airbnb" label. |
| 6 | Dedupe | By Airbnb review ID (`external_id`). Existing rows are never updated or deleted by the import. |
| 7 | Workflow | Build and test locally, run one real import locally, then deploy. The user runs `git push`. |

## Out of scope

- Booking.com reviews. Same approach could be added later as a second source.
- Star ratings, host responses and reviewer photos.
- Alerting when an import fails (Railway logs only for now).
- Translating reviews. They are shown in their original language.
- Syncing edits or deletions made on Airbnb after import.

## Architecture

```
Railway cron service "airbnb-import" (daily)
  └─ python manage.py import_airbnb_reviews
       ├─ POST Apify run-sync-get-dataset-items (listing URL) ──▶ list of reviews (JSON)
       └─ create new Review rows (source="airbnb", is_approved=True) ──▶ Postgres (shared with web service)

Visitor ──GET──▶ alma-hosting.co.il (static) ──fetch──▶ api.alma-hosting.co.il/api/reviews/  (now includes "source")
```

The web service is unchanged apart from the API field, the panel and the migration.

## Backend

### Model changes (`backend/reviews/models.py`)

Two new fields on `Review`:

- `source`: `CharField` with choices `site` / `airbnb`, default `site`. The migration sets every existing row to `site`.
- `external_id`: `CharField`, `null=True`, `blank=True`, `unique=True`. The Airbnb review ID. Null for site reviews (Postgres allows many nulls under a unique constraint).

### Field mapping (Airbnb item → `Review`)

| `Review` field | Value |
|---|---|
| `author_name` | Reviewer's first name as Airbnb shows it, cut to 100 characters. |
| `text` | Review text in its original language, stripped. If longer than 1000 characters, cut to 999 characters plus "…". |
| `stay_month`, `stay_year` | Month and year of the review's date. Airbnb does not publish the stay date, and reviews are written within 14 days of checkout, so the month is close enough. |
| `source` | `airbnb` |
| `external_id` | Airbnb review ID, as a string. |
| `is_approved` | `True` |

The exact JSON keys for the review ID, name, text and date are taken from a real sample (first plan task), not guessed. The import uses `Review.objects.create`, so the guest form's validation (minimum 10 characters, stay date not in the future) does not apply.

### Command `import_airbnb_reviews` (`backend/reviews/management/commands/`)

1. Read `APIFY_TOKEN` and `AIRBNB_LISTING_URL` from the environment. If `APIFY_TOKEN` is missing, raise `CommandError` with a clear message.
2. POST to `https://api.apify.com/v2/acts/<actor>/run-sync-get-dataset-items` with the listing URL as actor input, using `urllib` from the standard library (no new dependency). Timeout 300 seconds, which is Apify's limit for this endpoint.
3. For each item:
   - No review ID or empty text: skip and log one line.
   - `external_id` already in the database: skip.
   - Otherwise: map per the table above and create the row.
4. Print `fetched N, created X, skipped Y`.

The actor ID is a constant in the command. `AIRBNB_LISTING_URL` defaults to the Alma listing URL.

### API (`GET /api/reviews/`)

Each review gains `"source": "site" | "airbnb"`. Nothing else changes.

### Owner panel (`/reviews/manage/`)

- Airbnb reviews show an "Airbnb" label.
- Airbnb reviews get only the hide/approve buttons, no delete button. A deleted Airbnb review would come back on the next import, because its ID would no longer be known.
- In `manage_action`, a `delete` action on an Airbnb review is treated as `hide`, in case a stale page or crafted POST sends it.

## Site

### `site/reviews.js`

When `review.source === "airbnb"`, add a small "מ-Airbnb" label to the card. Styling goes in `site/styles.css`, in the existing editorial style (small, muted, no Airbnb logo).

## Railway

- New service `airbnb-import`, same GitHub repo, same branch (`master`), root directory `backend/`.
- `backend/railway.json` makes every service using it run `migrate` and start gunicorn. So the cron service uses its own config file, `backend/railway.cron.json`, set in the service's "Config file" setting. That file contains only the start command `python manage.py import_airbnb_reviews` and the cron schedule `0 4 * * *`. Migrations stay with the web service.
- Variables: `DATABASE_URL` (reference to the existing Postgres), `SECRET_KEY` and any other variables Django settings need to start, `APIFY_TOKEN`, `AIRBNB_LISTING_URL`.
- No domain and no healthcheck.

## Error handling summary

| Situation | Behaviour |
|---|---|
| Apify error, timeout or invalid JSON | Nothing is saved. `CommandError`, exit code 1. Railway shows the cron run as failed. The next day's run retries. |
| Apify returns an empty list | Nothing happens. The import never deletes. |
| Item without ID or text | Skipped, one log line. |
| Review already imported | Skipped, untouched, including its hidden/approved state. |
| `APIFY_TOKEN` missing | `CommandError` with a clear message, exit code 1. |
| Owner deletes an Airbnb review | Treated as hide, so it does not come back. |

## Testing

Tests go in `backend/reviews/tests.py`. Apify is faked by patching the HTTP call to return the saved real sample (`backend/reviews/fixtures/apify_sample.json`).

- Import creates new reviews with `source="airbnb"` and `is_approved=True`.
- A second run with the same data creates nothing.
- A review hidden by the owner stays hidden after a re-import.
- Text over 1000 characters is cut to 1000 including "…".
- An item without ID or text is skipped.
- An Apify HTTP error saves nothing and raises `CommandError`.
- Missing `APIFY_TOKEN` raises `CommandError`.
- `/api/reviews/` includes `source` for both kinds.
- Panel `delete` on an Airbnb review hides it instead of deleting it.
- After the migration, existing reviews have `source="site"`.

Manual check before deploy: one real import locally with a real token, then the site preview at 127.0.0.2:5500 shows the Airbnb reviews with their label.

## Deployment (after approval only)

1. User creates an Apify account (free plan) and an API token.
2. Push to `master` (user runs `git push`). The web service deploys and migrates.
3. Create the `airbnb-import` service in Railway, set its config file to `backend/railway.cron.json`, set the variables.
4. Trigger one run by hand from Railway, check the logs and the live site.

## Files touched

- `backend/reviews/models.py`: `source`, `external_id`.
- `backend/reviews/migrations/0003_review_source_external_id.py`: new.
- `backend/reviews/management/__init__.py`, `backend/reviews/management/commands/__init__.py`, `backend/reviews/management/commands/import_airbnb_reviews.py`: new.
- `backend/reviews/fixtures/apify_sample.json`: new (real sample, reviewer first names only).
- `backend/reviews/views.py`: `source` in the API, delete-as-hide for Airbnb rows.
- `backend/templates/reviews/manage.html`: label, no delete button for Airbnb rows.
- `backend/reviews/tests.py`: new tests.
- `backend/railway.cron.json`: new.
- `site/reviews.js`, `site/styles.css`: Airbnb label.
