# Guest Recommendations (המלצות אורחים) — Design

> **Amended 2026-09-26:** Google sign-in dropped. Guests submit name + text + stay date without login; the owner approves in a site-styled panel at `/reviews/manage/`. No avatar; the site shows initials. See the plan's "Amendment 2026-09-26" section. Google-related lines below are superseded.

**Date:** 2026-09-25
**Status:** Decisions agreed in brainstorming; visual details below marked *default* were not reviewed and may be changed during implementation review.

## Goal

Show recommendations from guests on the Alma site, each displaying the author's Google name and profile photo, to build trust with future guests.

## Decisions (agreed)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Sign-in method | **Google only** (via `django-allauth`). Facebook deferred; allauth makes it a config addition later. |
| 2 | Backend | **Python + Django**, hosted on **Railway**, at `https://api.alma-hosting.co.il`. |
| 3 | Database | **Railway Postgres** (same Railway project, linked via `DATABASE_URL` reference variable). Local dev uses SQLite automatically. |
| 4 | Review content | **Text + stay date** (month + year). Card meta line: "התארחו באוגוסט 2026". |
| 5 | Moderation | **Owner approval before publishing.** New reviews are saved as pending; owner approves in Django admin. Guest sees "תודה! ההמלצה תפורסם לאחר אישור". |
| 6 | Visual reference | `C:\Users\Mor\Pictures\Screenshots\gool.png` — 3-column card grid, round avatar, name, meta line, text; bottom row fades into a "show more". |

## Deferred (out of scope)

- **Guest verification** (proving the writer was a guest). Owner approval is the interim guard. Candidate approach discussed: one-time invite link sent by owner after checkout.
- Facebook login.
- Editing/deleting own review by the guest (owner can edit/delete in admin).

## Architecture

Two independent parts:

1. **Static site** (`site/`, Cloudflare Workers static assets, unchanged deploy). New section loads approved reviews with `fetch()` from the API and renders cards. If the API fails, the section hides itself — the rest of the site is unaffected.
2. **Django backend** (`backend/`, Railway):
   - `GET /api/reviews/` — public JSON list of approved reviews. CORS header allows only the site origin.
   - `/reviews/write/` — Django-rendered page (login required). Guest signs in with Google, fills text + stay month/year, submits.
   - `/reviews/thanks/` — confirmation page with link back to the site.
   - `/admin/` — owner approves/rejects reviews.

The write flow lives entirely on the API domain, so there are no cross-site cookies or cross-origin form posts. The static site only performs an anonymous GET.

## Data

`Review`: `user` (FK), `author_name`, `avatar_url` (both snapshotted from the Google account at submit time), `text` (10–1000 chars), `stay_month` (1–12), `stay_year` (2020–current), `is_approved` (default False), `created_at`.
Stay date may not be in the future. Public API returns only `is_approved=True`, ordered newest stay first.

## UI (*defaults*, not reviewed)

- Section placed between "עמק המעיינות בהישג יד" (attractions) and FAQ. Kicker "המלצות", title "מה האורחים שלנו מספרים".
- Cards use existing tokens: `--card`, `--radius`, `--shadow-card`, heading font Secular One. 3 columns desktop, 2 tablet, 1 mobile.
- First 6 cards shown; "עוד המלצות" button reveals the rest.
- Button "כתבו המלצה" links to `/reviews/write/` on the API domain.
- Zero approved reviews: section shows only the CTA "היו הראשונים להמליץ".
- Avatar load failure: initials circle.
- Write page tells the user: "השם והתמונה מחשבון Google שלכם יוצגו ליד ההמלצה".

## Security

- Review text rendered with `textContent` only (never `innerHTML`) — prevents stored XSS.
- Local username/password signup disabled; Google is the only way in.
- Secrets (`SECRET_KEY`, Google client secret) only in Railway variables, never committed.
