// Build gate for Cloudflare Pages: fails the deploy if index.html references
// a local file (image, etc.) that doesn't actually exist in the repo.
const fs = require("fs");
const path = require("path");

const root = __dirname;
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");

const refs = [...html.matchAll(/(?:src|href)="([^"]+)"/g)].map((m) => m[1]);
const skipPrefixes = ["http://", "https://", "tel:", "mailto:", "#", "javascript:"];

const missing = [];
for (const ref of refs) {
  if (skipPrefixes.some((p) => ref.startsWith(p))) continue;
  const clean = ref.split("#")[0].split("?")[0];
  if (!clean) continue;
  const filePath = path.join(root, decodeURIComponent(clean));
  if (!fs.existsSync(filePath)) missing.push(ref);
}

if (missing.length) {
  console.error("Broken local references in index.html:");
  for (const m of missing) console.error("  - " + m);
  process.exit(1);
}

console.log(`OK: all ${refs.length} local references resolve.`);
