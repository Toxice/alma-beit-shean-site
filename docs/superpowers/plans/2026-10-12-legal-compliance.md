# Alma Legal Compliance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Israeli legal gaps on alma-hosting.co.il (accessibility statement, privacy policy, terms, review-form consent, Airbnb import moderation, accessibility fixes, self-hosted fonts) so the owner is not exposed to accessibility or privacy suits.

**Architecture:** The live site is static HTML in `site/` served by Cloudflare Workers (`wrangler.jsonc`, build gate `node check-links.js`). The review form and API are Django in `backend/` on Railway (`https://api.alma-hosting.co.il`). Legal pages are three new static HTML files in `site/` that reuse `site/styles.css`. Owner-specific facts go in as `{{OWNER_...}}` tokens, and the build gate refuses to deploy while any token remains.

**Tech Stack:** Django 5.2, plain HTML/CSS/JS (no build step), Node (only for `check-links.js`), Cloudflare Workers static assets, Railway.

**Spec:** There is no separate spec file. This plan comes from a read-only audit done on 2026-10-12 against three Israeli guides:
- https://divinesites.co.il/website-guides/מה-צריך-באתר-אינטרנט-כדי-לא-להתבע/
- https://maimonweb.com/תיקון-13-לחוק-הגנת-הפרטיות/
- https://www.y-law.co.il/blog/general/digital-business-guide/

The audit's findings are recorded under "Audit findings" below. Executors read that section in place of a spec.

## Audit findings (source of truth)

**Needs implementing**
- No footer links to terms, privacy or accessibility (`site/index.html:278-283`). `/accessibility` returns 404.
- No accessibility statement. The widget (`site/index.html:237-276`) is an extra and cannot be presented as compliance.
- No privacy policy. Data actually handled:
  - the review form: name, text, stay month and year, no email (`backend/reviews/forms.py:11`)
  - Google Fonts on both pages
  - Cloudflare and Railway hosting
  - the Apify scrape of Airbnb reviews
  - the `csrftoken` cookie on `/reviews/write/`
  - the `a11y-v2` localStorage key (`site/script.js:148`)
- No consent on the review form (`backend/templates/reviews/write.html`).
- No terms of use. `terms and conditions.md` in the repo root is Interspace's registrar terms. **Never publish it.**
- Google Fonts sends visitor IPs to Google.

**Needs improving**
- `--muted` `#787774` in `site/styles.css:11` is about 4.1:1 on `#F7F6F3`, below the 4.5:1 AA minimum.
- The a11y dialog does not trap focus.
- Carousel slides get `tabIndex=0` (`site/script.js:77-83`) but have no role or accessible name.
- The phone links have `target="_blank"` (`site/index.html:24`, `:220`).
- Form errors are not tied to their fields.
- There is no public way to report a review.
- Airbnb imports are auto-approved (`backend/reviews/management/commands/import_airbnb_reviews.py:70`).

**Not needed:** video captions (no video), VAT on prices (no prices), cookie banner (only the strictly-necessary `csrftoken`, no trackers), gallery alt text (already required).

**Owner decisions:** legal name, business number, address, turnover (accessibility exemption), accessibility coordinator, cancellation and refund policy, photo rights, the Johny Media to owner IP transfer, and whether to keep the Airbnb import.

## Global Constraints

- All user-facing text is Hebrew, RTL. Pages use `<html lang="he" dir="rtl">`.
- The words "אישור" and "מאושר" must not appear on `/reviews/write/` or `/reviews/thanks/`. Existing tests `test_form_open_without_login` and `test_thanks_page` assert this.
- The accessibility statement cites "תקן ישראלי ת"י 5568 חלק 1, ברמה AA". It never cites a WCAG version number, and never claims compliance because of the widget.
- Owner-specific values use exactly these tokens and nothing else: `{{OWNER_LEGAL_NAME}}`, `{{OWNER_BUSINESS_ID}}`, `{{OWNER_ADDRESS}}`, `{{OWNER_EMAIL}}`, `{{A11Y_COORDINATOR_NAME}}`, `{{A11Y_COORDINATOR_PHONE}}`, `{{A11Y_COORDINATOR_EMAIL}}`, `{{PHYSICAL_ACCESSIBILITY}}`, `{{CANCELLATION_POLICY}}`, `{{PAYMENT_METHODS}}`, `{{COURT_CITY}}`.
- Backend tests: run from `backend/` with `.venv/Scripts/python.exe manage.py test reviews`.
- Site gate: run from the repo root with `node check-links.js`.
- **Pushing `master` deploys instantly** (Cloudflare and Railway). Work on branch `feat/legal-compliance`. Never push or merge without the user's explicit go-ahead.
- No new Python or JS dependencies.

## Review Focus

1. **Legal pages are published with unfilled tokens.** The build gate must fail on any `{{` in `site/*.html` (Task 5 test).
2. **A guest submits the review form without ticking consent.** Nothing is saved and a Hebrew error is shown next to the checkbox (Task 2 test).
3. **Fonts break on the backend pages after self-hosting.** Cross-origin font loads need CORS. Without `site/_headers`, the review form silently falls back to Segoe UI (Task 3 Step 3, verified live in Task 7 Step 6).
4. **A keyboard user opens the a11y panel and presses Tab past the last control.** Focus must wrap and not escape behind the dialog (Task 4 Step 5 manual check).
5. **An Airbnb review the owner already approved is re-imported.** It must keep its state. Only *new* imports start pending (Task 1 adds `test_approved_review_stays_approved_after_reimport`).

---

### Task 0: Branch + owner questions (non-code gate for Task 7)

**Files:**
- Create: `docs/legal/owner-answers.md`

- [ ] **Step 1: Create the branch**

```bash
cd "C:/Users/Mor/Documents/vscode projects/alma-beit-shean-site"
git checkout -b feat/legal-compliance
```

- [ ] **Step 2: Write the answers sheet** `docs/legal/owner-answers.md`:

```markdown
# Owner answers for legal pages (fill before Task 7)

| Token | Question for the owner | Answer |
|---|---|---|
| {{OWNER_LEGAL_NAME}} | Legal name of the business / owner | |
| {{OWNER_BUSINESS_ID}} | עוסק פטור / מורשה number or ח.פ | |
| {{OWNER_ADDRESS}} | Address for legal notices (city or PO box is fine if the home address stays private) | |
| {{OWNER_EMAIL}} | Email for privacy and content requests | |
| {{A11Y_COORDINATOR_NAME}} | Accessibility coordinator name (can be the owner) | |
| {{A11Y_COORDINATOR_PHONE}} | Coordinator phone | |
| {{A11Y_COORDINATOR_EMAIL}} | Coordinator email | |
| {{PHYSICAL_ACCESSIBILITY}} | Physical accessibility of the units (steps, parking, bathroom) in 1-2 Hebrew sentences | |
| {{CANCELLATION_POLICY}} | Cancellation and refund policy in Hebrew | |
| {{PAYMENT_METHODS}} | Accepted payment methods (bit, transfer, cash, card?) | |
| {{COURT_CITY}} | City for court venue (court nearest the business) | |

## Decisions (not tokens)
- Yearly turnover: under ₪100K / under ₪1M / above ₪1M. This affects the exemption only; the statement is published either way.
- Keep the daily Airbnb import? yes = Task 1 keeps it pending-by-default. no = the user disables the `airbnb-import` Railway cron service, and the Airbnb paragraph is removed from privacy.html.
- Does the owner hold rights to every photo in `site/images/`, especially gan-guru.jpg, gilboa.jpg, gan-hashlosha.jpg, beit-shean-park.jpg, ein-shokek.jpg?
- Has Johny Media signed a written transfer of design and code ownership to the owner (yes/no, date)?
```

- [ ] **Step 3:** Tell the user that Task 7 needs these answers and that Tasks 1–6 can run meanwhile.

- [ ] **Step 4: Commit**

```bash
git add docs/legal/owner-answers.md
git commit -m "docs: owner questions for legal pages"
```

---

### Task 1: Airbnb imports start pending

**Files:**
- Modify: `backend/reviews/management/commands/import_airbnb_reviews.py:70`
- Modify: `backend/reviews/tests.py` (class `ImportAirbnbReviewsTests`, around line 389)
- Modify: `docs/superpowers/specs/2026-10-03-airbnb-reviews-import-design.md` (lines 26, 45, 70 and 124 say `is_approved=True`)

**Interfaces:**
- Produces: imported `Review` rows with `is_approved=False`. The owner approves them in `/reviews/manage/`.

- [ ] **Step 1: Change the existing test so it expects pending, and add the re-import test.** In `backend/reviews/tests.py`, replace `test_imports_new_reviews_published_with_airbnb_source` with:

```python
    def test_imports_new_reviews_pending_with_airbnb_source(self):
        out, _ = self.run_import(sample_items())
        self.assertEqual(Review.objects.count(), 3)
        # Pending: the owner checks copied Airbnb content before it goes public.
        self.assertTrue(all(not r.is_approved and r.source == Review.Source.AIRBNB for r in Review.objects.all()))
        dana = Review.objects.get(external_id="1100000000000000001")
        self.assertEqual((dana.author_name, dana.stay_month, dana.stay_year), ("Dana", 8, 2026))
        self.assertIn("fetched 3, created 3, skipped 0", out)

    def test_approved_review_stays_approved_after_reimport(self):
        self.run_import(sample_items())
        Review.objects.filter(external_id="1100000000000000001").update(is_approved=True)
        self.run_import(sample_items())
        self.assertTrue(Review.objects.get(external_id="1100000000000000001").is_approved)
```

- [ ] **Step 2: Run and confirm the failure.** From `backend/`: `.venv/Scripts/python.exe manage.py test reviews.tests.ImportAirbnbReviewsTests`
Expected: `test_imports_new_reviews_pending_with_airbnb_source` FAILS.

- [ ] **Step 3: Implement.** In `import_airbnb_reviews.py`, replace `"is_approved": True,` with:

```python
        # Owner approves each import in the panel: copied third-party content is checked before publishing.
        "is_approved": False,
```

- [ ] **Step 4: Run the whole suite.** `.venv/Scripts/python.exe manage.py test reviews`. Expected: all PASS. If another test assumed imported reviews are public, make it approve them first.

- [ ] **Step 5: Update the spec doc.** In `docs/superpowers/specs/2026-10-03-airbnb-reviews-import-design.md`:
- line 26 becomes: "Imported reviews start hidden (`is_approved=False`). The owner approves each one in the panel (changed 2026-10-12 for legal review of copied content)."
- lines 45, 70 and 124: change `True` to `False`.

- [ ] **Step 6: Commit**

```bash
git add backend/reviews docs/superpowers/specs/2026-10-03-airbnb-reviews-import-design.md
git commit -m "fix(reviews): imported Airbnb reviews wait for owner approval"
```

---

### Task 2: Review form consent + accessible errors

**Files:**
- Modify: `backend/reviews/forms.py`
- Modify: `backend/templates/reviews/write.html`
- Modify: `backend/templates/reviews/base.html` (`<style>` block)
- Modify: `backend/reviews/tests.py` (`VALID_POST` line 22, class `WriteReviewTests`)

**Interfaces:**
- Consumes: `site_url` template variable (existing context processor `reviews.views.site_url`, = `settings.SITE_ORIGIN`).
- Produces: `ReviewForm.consent`, a required `BooleanField` not stored on the model. It links to `{{ site_url }}/privacy.html`, which is created in Task 6.

- [ ] **Step 1: Write the failing tests.** Change `VALID_POST`:

```python
VALID_POST = {"author_name": "נועה לוי", "text": "חופשה נהדרת, המקום מאובזר ונקי.", "stay_month": 7, "stay_year": 2025, "consent": "on"}
```

Add to `WriteReviewTests`:

```python
    def test_without_consent_nothing_saved_and_hebrew_error(self):
        data = {k: v for k, v in VALID_POST.items() if k != "consent"}
        response = self.client.post(reverse("reviews:write"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "יש לסמן את התיבה כדי לשלוח את ההמלצה.")
        self.assertFalse(Review.objects.exists())

    def test_form_links_to_privacy_policy(self):
        response = self.client.get(reverse("reviews:write"))
        self.assertContains(response, 'name="consent"')
        self.assertContains(response, "/privacy.html")

    def test_field_error_is_inside_its_label(self):
        response = self.client.post(reverse("reviews:write"), {**VALID_POST, "author_name": ""})
        label = response.content.decode().split('for="id_author_name"', 1)[1].split("</label>", 1)[0]
        self.assertIn("errors", label)
```

- [ ] **Step 2: Run and confirm the failures.** `.venv/Scripts/python.exe manage.py test reviews.tests.WriteReviewTests`. Expected: the 3 new tests FAIL.

- [ ] **Step 3: Add the field.** In `backend/reviews/forms.py`, add under the honeypot `website` field:

```python
    # Not stored: every saved site review passed this box, so created_at is the consent time.
    consent = forms.BooleanField(
        required=True,
        error_messages={"required": "יש לסמן את התיבה כדי לשלוח את ההמלצה."},
    )
```

- [ ] **Step 4: Template.** Replace the whole `<form>…</form>` in `backend/templates/reviews/write.html` with the version below. Errors move inside their `<label>`, so screen readers read them with the field.

```html
  <form method="post">
    {% csrf_token %}
    {% if form.non_field_errors %}<div class="errors">{{ form.non_field_errors }}</div>{% endif %}
    <label for="{{ form.author_name.id_for_label }}">השם שיוצג
      {% if form.author_name.errors %}<span class="errors">{{ form.author_name.errors }}</span>{% endif %}</label>
    {{ form.author_name }}
    <label for="{{ form.text.id_for_label }}">ההמלצה שלכם
      {% if form.text.errors %}<span class="errors">{{ form.text.errors }}</span>{% endif %}</label>
    {{ form.text }}
    <div class="row">
      <div>
        <label for="{{ form.stay_month.id_for_label }}">חודש השהות
          {% if form.stay_month.errors %}<span class="errors">{{ form.stay_month.errors }}</span>{% endif %}</label>
        {{ form.stay_month }}
      </div>
      <div>
        <label for="{{ form.stay_year.id_for_label }}">שנה
          {% if form.stay_year.errors %}<span class="errors">{{ form.stay_year.errors }}</span>{% endif %}</label>
        {{ form.stay_year }}
      </div>
    </div>
    <div class="consent">
      {{ form.consent }}
      <label for="{{ form.consent.id_for_label }}">אני מסכים/ה שהשם וההמלצה יפורסמו באתר, ושהפרטים יישמרו לפי <a href="{{ site_url }}/privacy.html" target="_blank" rel="noopener">מדיניות הפרטיות</a>.
        {% if form.consent.errors %}<span class="errors">{{ form.consent.errors }}</span>{% endif %}</label>
    </div>
    <div class="hp" aria-hidden="true"><label for="id_website">אתר</label><input type="text" name="website" id="id_website" tabindex="-1" autocomplete="off"></div>
    <div class="actions"><button type="submit" class="btn btn-primary">שליחת ההמלצה</button></div>
  </form>
```

In the `<style>` block of `backend/templates/reviews/base.html`, add:

```css
    .consent{display:flex;gap:.6rem;align-items:flex-start;text-align:start;margin:1rem 0 .4rem}
    .consent input{margin-top:.35rem;width:1.1rem;height:1.1rem;flex:none}
    .consent label{font-weight:400;margin:0}
    label .errors{display:block}
```

- [ ] **Step 5: Run the whole suite.** `.venv/Scripts/python.exe manage.py test reviews`. Expected: all PASS. This includes `test_form_open_without_login`, which asserts "אישור" is absent; the consent text avoids that word on purpose.

- [ ] **Step 6: Visual check.** Run `.venv/Scripts/python.exe manage.py runserver`, open `http://localhost:8000/reviews/write/`, and submit with an empty name and no tick. Each error must sit under its own label, and the checkbox row must be aligned correctly in RTL.

- [ ] **Step 7: Commit**

```bash
git add backend/reviews/forms.py backend/reviews/tests.py backend/templates/reviews
git commit -m "feat(reviews): consent checkbox and errors inside labels"
```

---

### Task 3: Self-host fonts

**Files:**
- Create: `site/fonts/*.woff2`, `site/fonts/fonts.css`, `site/_headers`
- Modify: `site/index.html:6-8`, `backend/templates/reviews/base.html:9-11`

**Interfaces:**
- Produces: `site/fonts/fonts.css`, which declares the families `Rubik` (variable 400–900) and `Secular One`. The backend loads it through `{{ site_url }}/fonts/fonts.css`.

- [ ] **Step 1: Download** (bash, from the repo root):

```bash
mkdir -p site/fonts
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
curl -s -A "$UA" "https://fonts.googleapis.com/css2?family=Rubik:wght@400..900&family=Secular+One&display=swap" -o site/fonts/fonts.css
grep -o "https://fonts.gstatic.com[^)]*" site/fonts/fonts.css | sort -u | while read u; do curl -s "$u" -o "site/fonts/$(basename "$u")"; done
sed -i -E 's#url\(https://fonts\.gstatic\.com/[^)]*/([^/)]+)\)#url(\1)#' site/fonts/fonts.css
ls site/fonts
```

Expected: `fonts.css` plus one woff2 per subset.

- [ ] **Step 2: Trim the subsets.** Open `site/fonts/fonts.css` and keep only the `/* hebrew */`, `/* latin-ext */` and `/* latin */` blocks. Delete the other blocks (cyrillic, vietnamese, math, symbols) and their woff2 files. Each kept block looks like:

```css
/* hebrew */
@font-face {
  font-family: 'Rubik';
  font-style: normal;
  font-weight: 400 900;
  font-display: swap;
  src: url(<file>.woff2) format('woff2');
  unicode-range: U+0307-0308, U+0590-05FF, U+200C-2010, U+20AA, U+25CC, U+FB1D-FB4F;
}
```

- [ ] **Step 3: CORS for the API host.** Create `site/_headers`:

```
/fonts/*
  Access-Control-Allow-Origin: *
  Cache-Control: public, max-age=31536000, immutable
```

- [ ] **Step 4: Point both pages at the local CSS.**

In `site/index.html`, replace lines 6–8 (the two `preconnect` lines and the Google `css2` link) with:

```html
<link rel="stylesheet" href="fonts/fonts.css">
```

In `backend/templates/reviews/base.html`, replace lines 9–11 with:

```html
  <link rel="stylesheet" href="{{ site_url }}/fonts/fonts.css">
```

- [ ] **Step 5: Verify.**

Run `grep -rn "fonts.googleapis\|fonts.gstatic" site backend/templates`. Expected: no output.

Run `node check-links.js`. Expected: passes.

Run `npx wrangler dev` and open `http://localhost:8787`. DevTools → Network must show the woff2 files loading from localhost, and the headings must render in Secular One.

The backend form can only be fully checked after deploy (Task 7 Step 6), because `SITE_ORIGIN` points to the live site.

- [ ] **Step 6: Commit**

```bash
git add site/fonts site/_headers site/index.html backend/templates/reviews/base.html
git commit -m "feat(site): self-host Rubik and Secular One, stop calling Google Fonts"
```

---

### Task 4: Accessibility fixes in site code

**Files:**
- Modify: `site/styles.css:11`
- Modify: `site/index.html:24`, `:220`, and the `.a11y-panel` div (around line 241)
- Modify: `site/script.js` (the `slides.forEach` around lines 77–83, and the a11y keydown handler)

**Interfaces:**
- Consumes: the existing `window.initCarousel(car)` and the a11y IIFE variables `panel`, `toggle`, `closeBtn` and `openPanel`.

- [ ] **Step 1: Contrast.** In `site/styles.css:11`, change `--muted:#787774;` to `--muted:#6B6A67;`. Verify:

```bash
node -e "const L=h=>{const c=[1,3,5].map(i=>parseInt(h.slice(i,i+2),16)/255).map(v=>v<=.03928?v/12.92:((v+.055)/1.055)**2.4);return .2126*c[0]+.7152*c[1]+.0722*c[2]};const r=(a,b)=>((Math.max(L(a),L(b))+.05)/(Math.min(L(a),L(b))+.05)).toFixed(2);console.log(r('#6B6A67','#F7F6F3'),r('#6B6A67','#FFFFFF'),r('#6B6A67','#FBFBFA'))"
```

Expected: all three values ≥ 4.5.

- [ ] **Step 2: Phone links.** In `site/index.html` lines 24 and 220, remove `target="_blank"` from both `href="tel:+972506533940"` links.

- [ ] **Step 3: Name the slides.** In `site/script.js`, at the top of the `slides.forEach(function (el, i) { ... })` callback, add:

```js
      // Focusable slides need a role and a name for screen readers.
      var named = el.querySelector('h3') || el.querySelector('img[alt]:not([alt=""])');
      if (named) {
        el.setAttribute('role', 'group');
        el.setAttribute('aria-label', named.tagName === 'H3' ? named.textContent.trim() : named.alt);
      }
```

- [ ] **Step 4: Trap focus in the a11y dialog.** In the a11y block of `site/script.js`, replace the existing handler `document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !panel.hidden) openPanel(false); });` with:

```js
  document.addEventListener('keydown', function (e) {
    if (panel.hidden) return;
    if (e.key === 'Escape') { openPanel(false); return; }
    if (e.key !== 'Tab') return;
    // Keep Tab inside the open dialog.
    var items = panel.querySelectorAll('button');
    var first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });
```

In `site/index.html`, add `aria-modal="true"` to `<div class="a11y-panel" id="a11yPanel" role="dialog" …>`.

- [ ] **Step 5: Manual keyboard check.** Run `npx wrangler dev` and open `http://localhost:8787`.
- Tab to the a11y button and press Enter. Focus goes to the close button.
- Tab repeatedly. Focus cycles inside the panel and never reaches the page.
- Shift+Tab from the close button goes to "איפוס הגדרות".
- Every chip shows a visible focus outline. The `.a11y-panel button:focus-visible` rule at `styles.css:326` provides it.
- Escape closes the panel and focus returns to the toggle.
- In the DevTools Accessibility pane, each attraction slide is named by its heading.

- [ ] **Step 6: Commit**

```bash
git add site/styles.css site/index.html site/script.js
git commit -m "fix(a11y): AA contrast, dialog focus trap, named slides, tel links"
```

---

### Task 5: Build gate checks every page and blocks unfilled tokens

**Files:**
- Modify: `check-links.js`

**Interfaces:**
- Produces: `node check-links.js` exits 1 if any `site/*.html` references a missing local file or contains `{{`.

- [ ] **Step 1: Reproduce the gap.**

```bash
printf '<!doctype html><html lang="he"><body>{{OWNER_EMAIL}}</body></html>' > site/zz-test.html
node check-links.js; echo "exit=$?"
```

Expected now: `exit=0`. That is the bug: the gate ignores other pages and tokens.

- [ ] **Step 2: Read the current `check-links.js` in full** (the excerpt shown at plan time ends at line 20). Replace it with the code below, and keep any extra behaviour the current file has after line 20.

```js
// Build gate for Cloudflare: fails the deploy if any site/*.html references a
// local file that doesn't exist, or still has an unfilled {{TOKEN}} (legal pages).
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "site");
const skipPrefixes = ["http://", "https://", "tel:", "mailto:", "#", "javascript:"];
const problems = [];

for (const page of fs.readdirSync(root).filter((f) => f.endsWith(".html"))) {
  const html = fs.readFileSync(path.join(root, page), "utf8");
  const tokens = html.match(/\{\{[^}]*\}\}/g);
  if (tokens) problems.push(`${page}: unfilled ${[...new Set(tokens)].join(", ")}`);

  for (const [, ref] of html.matchAll(/(?:src|href)="([^"]+)"/g)) {
    if (skipPrefixes.some((p) => ref.startsWith(p))) continue;
    const clean = ref.split("#")[0].split("?")[0];
    if (!clean) continue;
    if (!fs.existsSync(path.join(root, decodeURIComponent(clean)))) problems.push(`${page}: missing ${ref}`);
  }
}

if (problems.length) {
  console.error("Build gate failed:\n  " + problems.join("\n  "));
  process.exit(1);
}
console.log("All local references OK, no unfilled tokens.");
```

- [ ] **Step 3: Verify both directions.**

```bash
node check-links.js; echo "exit=$?"   # expect exit=1 and "zz-test.html: unfilled {{OWNER_EMAIL}}"
rm site/zz-test.html
node check-links.js; echo "exit=$?"   # expect exit=0
```

- [ ] **Step 4: Commit**

```bash
git add check-links.js
git commit -m "build: gate checks all pages and blocks unfilled legal tokens"
```

---

### Task 6: Legal pages + footer

The pages are written with tokens. The Task 5 gate blocks deploy until Task 7 fills them.

**Files:**
- Create: `site/accessibility.html`, `site/privacy.html`, `site/terms.html`
- Modify: `site/index.html` footer (lines 278–283)
- Modify: `site/styles.css` (append)

**Interfaces:**
- Consumes: the tokens from Global Constraints, `site/fonts/fonts.css` (Task 3), and the `site/styles.css` variables `--ink`, `--muted` and `--font-heading`.
- Produces: the URLs `/accessibility.html`, `/privacy.html` and `/terms.html`. Task 2 links `/privacy.html`.

- [ ] **Step 1: Shared shell.** All three pages use this shell. Replace `TITLE` and `BODY`; set the update date to the day the pages go live.

```html
<!doctype html><html lang="he" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TITLE – עלמה בית שאן</title>
<link rel="icon" href="images/alma-favicon-new.png" type="image/png">
<link rel="stylesheet" href="fonts/fonts.css">
<link rel="stylesheet" href="styles.css">
</head><body>
<main class="legal">
  <a class="legal-back" href="./">→ חזרה לעמוד הבית</a>
  <h1>TITLE</h1>
  <p class="legal-date">עודכן לאחרונה: 12 באוקטובר 2026</p>
  <article>
BODY
  </article>
</main>
</body></html>
```

- [ ] **Step 2: `site/accessibility.html`.** TITLE = `הצהרת נגישות`. BODY:

```html
<p>אנו ב"עלמה – בית שאן" רואים חשיבות רבה במתן שירות שוויוני לכלל הלקוחות, ופועלים כדי שהאתר והשירות יהיו נגישים לאנשים עם מוגבלות, בהתאם לחוק שוויון זכויות לאנשים עם מוגבלות, התשנ"ח-1998, ולתקנות שוויון זכויות לאנשים עם מוגבלות (התאמות נגישות לשירות), התשע"ג-2013.</p>

<h2>רמת הנגישות באתר</h2>
<p>האתר הותאם לדרישות תקן ישראלי ת"י 5568 חלק 1, ברמה AA. בין היתר:</p>
<ul>
  <li>האתר מוגדר בעברית ובכיוון מימין לשמאל, ומבנה הכותרות היררכי.</li>
  <li>לכל התמונות בעלות התוכן יש טקסט חלופי.</li>
  <li>ניתן לנווט בכל האתר באמצעות המקלדת, עם סימון פוקוס נראה.</li>
  <li>יחסי הניגודיות בין טקסט לרקע עומדים בדרישות רמה AA.</li>
  <li>לכל שדות הטופס יש תוויות, והודעות שגיאה מוצגות ליד השדה.</li>
  <li>האתר מכבד הגדרת "הפחתת תנועה" של מערכת ההפעלה.</li>
</ul>
<p>באתר קיים גם תפריט נגישות (ניגודיות, גודל טקסט, ריווח, עצירת אנימציות ועוד) ככלי עזר נוסף. התאמת הנגישות נעשתה בקוד האתר עצמו, ואינה נשענת על התפריט.</p>

<h2>מגבלות ידועות</h2>
<p>לא ידועות לנו כרגע מגבלות נגישות באתר. דף כתיבת ההמלצות מתארח בשרת נפרד ועוצב באותם עקרונות נגישות.</p>

<h2>נגישות פיזית של המתחם</h2>
<p>{{PHYSICAL_ACCESSIBILITY}}</p>

<h2>פנייה בנושא נגישות</h2>
<p>נתקלתם בבעיית נגישות? נשמח לשמוע ולתקן. רכז/ת הנגישות:</p>
<ul>
  <li>שם: {{A11Y_COORDINATOR_NAME}}</li>
  <li>טלפון: <a href="tel:{{A11Y_COORDINATOR_PHONE}}">{{A11Y_COORDINATOR_PHONE}}</a></li>
  <li>דוא"ל: <a href="mailto:{{A11Y_COORDINATOR_EMAIL}}">{{A11Y_COORDINATOR_EMAIL}}</a></li>
</ul>
<p>בפנייה, נא לציין את תיאור הבעיה, את הדף שבו נתקלתם בה, ואת סוג הדפדפן וטכנולוגיית העזר (אם יש).</p>
```

If the Step 7 audit finds issues that cannot be fixed now, replace the "מגבלות ידועות" paragraph with a `<ul>` listing each one and its fix date.

- [ ] **Step 3: `site/privacy.html`.** TITLE = `מדיניות פרטיות`. BODY:

```html
<p>מדיניות זו מסבירה איזה מידע נאסף באתר alma-hosting.co.il, לשם מה, ומה הזכויות שלכם, בהתאם לחוק הגנת הפרטיות, התשמ"א-1981 ותיקון 13 לחוק.</p>

<h2>מי אחראי על המידע</h2>
<p>{{OWNER_LEGAL_NAME}}, {{OWNER_BUSINESS_ID}}, {{OWNER_ADDRESS}}. פניות בנושא פרטיות: <a href="mailto:{{OWNER_EMAIL}}">{{OWNER_EMAIL}}</a>.</p>

<h2>איזה מידע נאסף ולמה</h2>
<ul>
  <li><strong>טופס כתיבת המלצה:</strong> השם שתבחרו להציג, תוכן ההמלצה, וחודש ושנת השהות. המטרה: פרסום ההמלצה באתר לאחר בדיקה של בעלי המקום. מסירת המידע אינה חובה לפי חוק, אך בלעדיו לא ניתן לפרסם המלצה. בטופס לא נאספים דוא"ל, טלפון או כתובת.</li>
  <li><strong>פנייה בוואטסאפ או בטלפון:</strong> המידע שתמסרו (שם, טלפון, תאריכים) משמש לתיאום האירוח בלבד. שיחות וואטסאפ כפופות גם למדיניות הפרטיות של WhatsApp (Meta).</li>
  <li><strong>המלצות מ-Airbnb:</strong> אנו מציגים המלצות שפורסמו בפומבי בדף המתחם ב-Airbnb: שם פרטי, תוכן ההמלצה וחודש הפרסום. ההמלצות מסומנות "מ-Airbnb" ומפורסמות רק לאחר בדיקה.</li>
  <li><strong>מידע טכני:</strong> ספקי האחסון שלנו רושמים באופן אוטומטי כתובת IP, סוג דפדפן ושעת הגישה, לצורכי אבטחה ותפעול בלבד.</li>
</ul>

<h2>עם מי המידע משותף</h2>
<p>איננו מוכרים מידע ואיננו מעבירים אותו לצורכי פרסום. המידע נשמר אצל ספקי שירות שמפעילים את האתר: Cloudflare (אחסון האתר), Railway (שרת טופס ההמלצות ומסד הנתונים) ו-Apify (שירות שאוסף את ההמלצות הפומביות מ-Airbnb). חלק מהספקים נמצאים מחוץ לישראל.</p>

<h2>עוגיות ואחסון בדפדפן</h2>
<p>האתר אינו משתמש בעוגיות פרסום או מעקב ואינו מפעיל כלי סטטיסטיקה. דף כתיבת ההמלצה יוצר עוגייה טכנית אחת (csrftoken) הדרושה לאבטחת הטופס. הגדרות תפריט הנגישות נשמרות בדפדפן שלכם בלבד ואינן נשלחות אלינו. ספק האחסון Cloudflare עשוי ליצור עוגייה טכנית לזיהוי תעבורה זדונית.</p>

<h2>הזכויות שלכם</h2>
<p>תוכלו לבקש לעיין במידע עליכם, לתקן אותו או למחוק אותו – כולל הסרת המלצה שפורסמה, בין אם נכתבה באתר ובין אם הגיעה מ-Airbnb. פנו אל <a href="mailto:{{OWNER_EMAIL}}">{{OWNER_EMAIL}}</a> ונטפל בבקשה תוך זמן סביר.</p>

<h2>שמירה ואבטחה</h2>
<p>המלצות נשמרות כל עוד הן מוצגות באתר או עד שתבקשו למחוק אותן. הגישה לניהול מוגבלת לבעלי המקום בלבד, בסיסמה ובחיבור מוצפן. אם יתרחש אירוע אבטחה שפוגע במידע, נפעל לפי הוראות הדין, כולל דיווח לרשות להגנת הפרטיות והודעה למי שנפגע, כשהדבר נדרש.</p>

<h2>שינויים במדיניות</h2>
<p>נעדכן מדיניות זו כשיחול שינוי באופן איסוף המידע, ולפחות פעם בשנה. תאריך העדכון האחרון מופיע בראש הדף.</p>
```

If the owner stops the Airbnb import (Task 0 decision), delete the "המלצות מ-Airbnb" `<li>` and "ו-Apify (…)" from the sharing paragraph. Keep the Airbnb mention in "הזכויות שלכם" while previously imported Airbnb reviews remain on the site.

- [ ] **Step 4: `site/terms.html`.** TITLE = `תנאי שימוש`. BODY:

```html
<p>השימוש באתר alma-hosting.co.il ("האתר") כפוף לתנאים אלה. האתר מופעל על ידי {{OWNER_LEGAL_NAME}}, {{OWNER_BUSINESS_ID}} ("עלמה"). הכתוב בלשון אחת מתייחס לכל המגדרים.</p>

<h2>השירות</h2>
<p>האתר מציג מידע על יחידות האירוח "עלמה" בבית שאן. הזמנת אירוח אינה מתבצעת באתר, אלא בתיאום ישיר בוואטסאפ או בטלפון, ותנאי כל הזמנה (תאריכים, מחיר, מקדמה) נקבעים בתיאום זה.</p>

<h2>תשלום</h2>
<p>אמצעי התשלום: {{PAYMENT_METHODS}}. האתר אינו גובה תשלום ואינו שומר פרטי אמצעי תשלום.</p>

<h2>ביטול הזמנה</h2>
<p>{{CANCELLATION_POLICY}}</p>
<p>אין באמור כדי לגרוע מזכויות הביטול הקבועות בחוק הגנת הצרכן, התשמ"א-1981 ובתקנותיו.</p>

<h2>המלצות אורחים</h2>
<p>המלצות מתפרסמות לאחר בדיקה של בעלי המקום, ועלמה רשאית שלא לפרסם או להסיר המלצה. ההמלצות משקפות את דעת כותביהן. מצאתם המלצה פוגענית, לא נכונה או כזו שפוגעת בפרטיות? דווחו לנו ב-<a href="mailto:{{OWNER_EMAIL}}">{{OWNER_EMAIL}}</a> או בוואטסאפ, ונבדוק ונסיר אותה במידת הצורך בהקדם.</p>

<h2>קניין רוחני</h2>
<p>התמונות, הטקסטים והעיצוב באתר שייכים לעלמה או משמשים ברשות בעליהם. אין להעתיק או לעשות בהם שימוש מסחרי ללא הסכמה בכתב.</p>

<h2>אחריות</h2>
<p>אנו משתדלים שהמידע באתר יהיה מדויק ועדכני, אך הוא מוצג כפי שהוא. מידע על אטרקציות בסביבה הוא כללי, ויש לבדוק שעות פתיחה ותנאים מול הגורם המפעיל.</p>

<h2>דין וסמכות שיפוט</h2>
<p>על תנאים אלה יחול הדין הישראלי. סמכות השיפוט הבלעדית נתונה לבתי המשפט המוסמכים ב{{COURT_CITY}}.</p>

<h2>יצירת קשר</h2>
<p>{{OWNER_LEGAL_NAME}}, {{OWNER_ADDRESS}}, <a href="mailto:{{OWNER_EMAIL}}">{{OWNER_EMAIL}}</a>, טלפון <a href="tel:+972506533940">050-653-3940</a>.</p>
```

- [ ] **Step 5: Footer.** Replace the `<footer>…</footer>` in `site/index.html` with:

```html
<footer>
  <nav class="footer-links" aria-label="מידע משפטי">
    <a href="accessibility.html">הצהרת נגישות</a>
    <a href="privacy.html">מדיניות פרטיות</a>
    <a href="terms.html">תנאי שימוש</a>
  </nav>
  <p class="footer-owner">{{OWNER_LEGAL_NAME}} · {{OWNER_BUSINESS_ID}} · <a href="mailto:{{OWNER_EMAIL}}">{{OWNER_EMAIL}}</a></p>
  <div class="brand">
    <img class="jm-logo" src="images/johny-media-icon.png" alt="Johny Media" />
  </div>
  <div>סוכנות לבניית אתרים</div>
</footer>
```

- [ ] **Step 6: CSS.** Append to `site/styles.css`:

```css
/* ---------- legal pages + footer links ---------- */
.footer-links{display:flex;flex-wrap:wrap;justify-content:center;gap:.4rem 1.4rem;margin-bottom:.8rem;}
.footer-links a,.footer-owner a{color:var(--ink);text-underline-offset:3px;}
.footer-owner{margin:0 0 1.4rem;}
.legal{max-width:46rem;margin:0 auto;padding:3rem 20px 4rem;}
.legal h1{font-family:var(--font-heading);font-weight:400;font-size:2rem;margin:.8rem 0 .2rem;}
.legal h2{font-family:var(--font-heading);font-weight:400;font-size:1.3rem;margin:2rem 0 .5rem;}
.legal p,.legal li{line-height:1.75;color:var(--ink);}
.legal-date{color:var(--muted);font-size:.9rem;}
.legal-back{color:var(--ink);font-size:.95rem;}
```

- [ ] **Step 7: Accessibility audit.** Run `npx wrangler dev` and run Chrome DevTools Lighthouse → Accessibility on `/`, `/accessibility.html`, `/privacy.html` and `/terms.html`. Also run it on `http://localhost:8000/reviews/write/` with `runserver`. Fix every failing code item and commit those fixes separately. List any item that can't be fixed now in the statement's "מגבלות ידועות" section with a fix date.

- [ ] **Step 8: Gate check.** Run `node check-links.js; echo "exit=$?"`. Expected: `exit=1`, listing the tokens on accessibility, privacy, terms and index. This confirms production is protected.

- [ ] **Step 9: Commit**

```bash
git add site/accessibility.html site/privacy.html site/terms.html site/index.html site/styles.css
git commit -m "feat(site): accessibility statement, privacy policy, terms, footer links"
```

---

### Task 7: Fill tokens, review, deploy (needs the user)

**Files:**
- Modify: `site/accessibility.html`, `site/privacy.html`, `site/terms.html`, `site/index.html`
- Modify: `C:\Users\Mor\.claude\projects\C--Users-Mor-Documents-vscode-projects\memory\project_alma_guest_reviews.md`

- [ ] **Step 1: Replace every token** with the answers in `docs/legal/owner-answers.md`. Values inside `tel:` use `+972…` with no dashes. Then run `node check-links.js`. Expected: exit 0.

- [ ] **Step 2: Lawyer review.** Tell the user the three pages are ready for an Israeli lawyer. **Stop and wait** for the user's go-ahead, and apply any wording changes the lawyer asks for.

- [ ] **Step 3: Full run.** From `backend/`, run `.venv/Scripts/python.exe manage.py test`. From the repo root, run `node check-links.js`. Expected: all PASS and exit 0.

- [ ] **Step 4: Commit**

```bash
git add site docs/legal
git commit -m "feat(site): fill owner details in legal pages"
```

- [ ] **Step 5: Merge and push — only after the user explicitly says to.** Pushing `master` deploys Cloudflare and Railway.

```bash
git checkout master
git merge --no-ff feat/legal-compliance
git push origin master
```

- [ ] **Step 6: Live checks.**
- `curl -sI https://alma-hosting.co.il/accessibility.html`, `/privacy.html` and `/terms.html` all return 200.
- `curl -sI https://alma-hosting.co.il/fonts/fonts.css` shows `access-control-allow-origin: *`.
- At `https://api.alma-hosting.co.il/reviews/write/`, the fonts load from alma-hosting.co.il and nothing loads from fonts.googleapis.com. The consent checkbox shows, and submitting without it saves nothing.
- The home page footer shows the three links and the owner line.

- [ ] **Step 7: Railway.** If the owner chose to stop the Airbnb import, ask the user to disable the `airbnb-import` cron service in the Railway dashboard. That is a manual, outward-facing action.

- [ ] **Step 8: Memory + yearly reminder.** Update `project_alma_guest_reviews.md`: legal pages live (date), Airbnb imports pending by default, fonts self-hosted, legal pages due for review by the live date + 1 year. Offer the user a calendar reminder.

---

## Self-review notes

- Each audit finding maps to a task:
  - footer, statement, privacy, terms, business identity, review takedown channel: Task 6
  - consent and form errors: Task 2
  - Google Fonts: Task 3
  - contrast, focus trap, slide names, tel links: Task 4
  - Airbnb auto-approve: Task 1
  - unfilled-token safety: Task 5
  - owner decisions: Task 0
  - yearly review: Task 7 Step 8
- The audit said the a11y chips had no focus style. `site/styles.css:326` already has `.a11y-panel button:focus-visible`, so no task changes it; Task 4 Step 5 confirms it.
- Photo rights, the Johny Media IP transfer and the lawyer review are non-code. They are tracked in Task 0 and Task 7.
