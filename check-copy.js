// Copy gate: site must say 4 identical units; no stale "2 units" / unit A/B wording.
const fs = require("fs");
const path = require("path");

const files = {
  "site/index.html": fs.readFileSync(path.join(__dirname, "site/index.html"), "utf8"),
  "backend/content/seed/content.json": fs.readFileSync(path.join(__dirname, "backend/content/seed/content.json"), "utf8"),
};
const stale = ["2 יחידות", "<strong>2</strong><span>יחידות", "יחידה א׳", "יחידה ב׳", "נפרדות"];
const errors = [];
for (const [name, text] of Object.entries(files)) {
  for (const s of stale) if (text.includes(s)) errors.push(`${name}: stale "${s}"`);
}
const html = files["site/index.html"];
if ((html.match(/4 יחידות אירוח/g) || []).length < 2) errors.push('index.html: need "4 יחידות אירוח" at least twice (meta + FAQ)');
if (!html.includes("<strong>4</strong>")) errors.push("index.html: facts band missing <strong>4</strong>");
if (!files["backend/content/seed/content.json"].includes("4 יחידות אירוח זהות")) errors.push("content.json: FAQ answer missing 4 units");

const bk = "https://www.booking.com/hotel/il/mtkhm-ykhydvt-yrvkh-lmh.he.html";
const bkLinks = html.match(new RegExp('<a [^>]*href="' + bk.replace(/[.]/g, "\.") + '"[^>]*>', "g")) || [];
if (bkLinks.length !== 1 || !/target="_blank"/.test(bkLinks[0]) || !/rel="noopener"/.test(bkLinks[0])) errors.push("index.html: need exactly one Booking.com link with target=_blank rel=noopener");
if (/class="btn[^"]*"[^>]*>[^<]*(Booking|Airbnb)/i.test(html)) errors.push("index.html: Booking/Airbnb must not be a .btn button");

// cancellation policy: FAQ item in page and seed, answer has intro + six numbered rules
const q = "מה מדיניות הביטול?";
if (!html.includes(q)) errors.push("index.html: missing cancellation FAQ question");
const seed = JSON.parse(files["backend/content/seed/content.json"]);
const cx = seed.faq.find((i) => i.q === q);
if (!cx) errors.push("content.json: missing cancellation FAQ item");
else {
  const rules = cx.a.split("\n").filter((l) => /^[1-6]\. /.test(l));
  if (rules.length !== 6) errors.push("content.json: cancellation answer needs six numbered rules, found " + rules.length);
  if (cx.a.length > 1000) errors.push("content.json: cancellation answer over 1000 chars");
}

if (errors.length) { console.error(errors.join("\n")); process.exit(1); }
console.log("OK: copy checks pass.");
