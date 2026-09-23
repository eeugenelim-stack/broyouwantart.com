#!/usr/bin/env node
// Tags double-page-spread images in index.html's PROJECTS data.
// Also records each image's pixel size ("w","h") so the project book can size pages to the photo.
// Rule: an image whose pixel aspect ratio (w/h) >= SPREAD_RATIO is a spread
// (gets "spread":1); anything below is a single page (flag removed if present).
// Re-runnable: re-reads dimensions from disk and rewrites flags from scratch.
//
// Usage:  node tools/tag-spreads.mjs           (writes index.html in place)
//         node tools/tag-spreads.mjs --dry     (report only, no write)

import { readFileSync, writeFileSync } from 'node:fs';
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

// --- 3. Read pixel dimensions straight from the JPEG/PNG headers (pure Node, any OS).
const dims = new Map();      // src -> {w,h}
const missing = [];
const decode = (src) => join(ROOT, decodeURIComponent(src));
function readDims(file) {
  const b = readFileSync(file);
  if (b.readUInt32BE(0) === 0x89504e47) return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };   // PNG IHDR
  if (b[0] !== 0xff || b[1] !== 0xd8) return null;
  let i = 2;
  while (i + 9 < b.length) {                                   // walk JPEG segments to the SOFn frame header
    if (b[i] !== 0xff) { i++; continue; }
    const m = b[i + 1];
    if (m === 0xd8 || m === 0x01 || (m >= 0xd0 && m <= 0xd7)) { i += 2; continue; }
    if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) return { w: b.readUInt16BE(i + 7), h: b.readUInt16BE(i + 5) };
    i += 2 + b.readUInt16BE(i + 2);
  }
  return null;
}
for (const s of list) {
  try { const d = readDims(decode(s)); if (d && d.w && d.h) dims.set(s, d); } catch (e) { /* missing file */ }
}
for (const s of list) if (!dims.has(s)) missing.push(s);

// --- 4. Tag each image: spread:1 when landscape, drop flag otherwise.
let spreadN = 0, singleN = 0, unknownN = 0, forcedN = 0;
for (const p of projects) for (const img of (p.images || [])) {
  if (!img || !img.src) continue;
  const d = dims.get(img.src);
  if (isForcedSingle(img.src)) { delete img.spread; if (d) { img.w = d.w; img.h = d.h; } singleN++; forcedN++; continue; }   // manual override
  if (!d) { delete img.spread; delete img.w; delete img.h; unknownN++; continue; }
  img.w = d.w; img.h = d.h;   // true pixel size → the project book sizes each page to the photo, no cropping   // unknown -> treat as single (no flag)
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
