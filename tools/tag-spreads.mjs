#!/usr/bin/env node
// Tags double-page-spread images in index.html's PROJECTS data.
// Rule: an image whose pixel aspect ratio (w/h) >= SPREAD_RATIO is a spread
// (gets "spread":1); anything below is a single page (flag removed if present).
// Re-runnable: re-reads dimensions from disk and rewrites flags from scratch.
//
// Usage:  node tools/tag-spreads.mjs           (writes index.html in place)
//         node tools/tag-spreads.mjs --dry     (report only, no write)

import { readFileSync, writeFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const HTML = join(ROOT, 'index.html');
const SPREAD_RATIO = 1.2;
const DRY = process.argv.includes('--dry');

// Manual overrides: landscape images that are actually SINGLE pages (e.g. a cover
// matted on a canvas), so aspect ratio wrongly reads them as spreads. Matched as a
// substring of the decoded src. Add an entry here when you spot a misclassified single.
const FORCE_SINGLE = [
  'LAWERENCE WONG COVER SHOOT/Screenshot 2026-05-11 at 2.02.28',
];
const isForcedSingle = (src) => FORCE_SINGLE.some(s => decodeURIComponent(src).includes(s));

const html = readFileSync(HTML, 'utf8');

// --- 1. Locate the `const PROJECTS = [ ... ]` array literal (string-aware brace match).
const marker = 'const PROJECTS = ';
const startKey = html.indexOf(marker);
if (startKey < 0) { console.error('Could not find `const PROJECTS = ` in index.html'); process.exit(1); }
const open = html.indexOf('[', startKey);
let depth = 0, inStr = false, esc = false, end = -1;
for (let i = open; i < html.length; i++) {
  const c = html[i];
  if (inStr) {
    if (esc) esc = false;
    else if (c === '\\') esc = true;
    else if (c === '"') inStr = false;
  } else {
    if (c === '"') inStr = true;
    else if (c === '[') depth++;
    else if (c === ']') { depth--; if (depth === 0) { end = i; break; } }
  }
}
if (end < 0) { console.error('Could not find end of PROJECTS array'); process.exit(1); }
const arrText = html.slice(open, end + 1);

let projects;
try { projects = JSON.parse(arrText); }
catch (e) { console.error('PROJECTS array is not valid JSON:', e.message); process.exit(1); }

// --- 2. Collect unique image file paths (decode the %-encoded srcs).
const srcs = new Set();
for (const p of projects) for (const img of (p.images || [])) if (img && img.src) srcs.add(img.src);
const list = [...srcs];

// --- 3. Read pixel dimensions in batches via macOS `sips`.
const dims = new Map();      // src -> {w,h}
const missing = [];
const decode = (src) => join(ROOT, decodeURIComponent(src));
const BATCH = 60;
for (let i = 0; i < list.length; i += BATCH) {
  const chunk = list.slice(i, i + BATCH);
  const paths = chunk.map(decode);
  let out = '';
  try {
    out = execFileSync('sips', ['-g', 'pixelWidth', '-g', 'pixelHeight', ...paths], { encoding: 'utf8' });
  } catch (e) { out = e.stdout ? String(e.stdout) : ''; }
  // sips prints: "<path>\n  pixelWidth: N\n  pixelHeight: N\n" per file.
  let cur = null, w = 0, h = 0;
  const commit = () => { if (cur && w && h) { const s = chunk.find(c => decode(c) === cur); if (s) dims.set(s, { w, h }); } };
  for (const line of out.split('\n')) {
    if (/^\s+pixelWidth:\s*(\d+)/.test(line)) w = +RegExp.$1;
    else if (/^\s+pixelHeight:\s*(\d+)/.test(line)) h = +RegExp.$1;
    else if (line.trim()) { commit(); cur = line.trim(); w = 0; h = 0; }
  }
  commit();
}
for (const s of list) if (!dims.has(s)) missing.push(s);

// --- 4. Tag each image: spread:1 when landscape, drop flag otherwise.
let spreadN = 0, singleN = 0, unknownN = 0, forcedN = 0;
for (const p of projects) for (const img of (p.images || [])) {
  if (!img || !img.src) continue;
  if (isForcedSingle(img.src)) { delete img.spread; singleN++; forcedN++; continue; }   // manual override
  const d = dims.get(img.src);
  if (!d) { delete img.spread; unknownN++; continue; }   // unknown -> treat as single (no flag)
  const ratio = d.w / d.h;
  if (ratio >= SPREAD_RATIO) { img.spread = 1; spreadN++; }
  else { delete img.spread; singleN++; }
}

// --- 5. Re-serialize (minified, key order preserved) and splice back in.
const newArr = JSON.stringify(projects);
const newHtml = html.slice(0, open) + newArr + html.slice(end + 1);

console.log(`images: ${list.length}  |  spreads: ${spreadN}  singles: ${singleN} (${forcedN} forced)  unknown(no file): ${unknownN}`);
if (missing.length) {
  console.log(`\n${missing.length} image(s) had no readable file (left untagged = single):`);
  for (const m of missing.slice(0, 20)) console.log('  - ' + decodeURIComponent(m));
  if (missing.length > 20) console.log(`  ...and ${missing.length - 20} more`);
}
if (DRY) { console.log('\n--dry: no changes written.'); process.exit(0); }
writeFileSync(HTML, newHtml);
console.log('\nindex.html updated.');
