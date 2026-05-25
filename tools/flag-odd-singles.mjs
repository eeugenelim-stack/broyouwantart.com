#!/usr/bin/env node
// Lists every project that has an UNPAIRED single page.
//
// Singles are paired two-up (side by side). A single that has no adjacent single
// to pair with (because a spread/video follows it, or it's the last image) is left
// over and would render alone on the left page with a blank facing page. Those are
// the ones to curate — add/remove an image so singles pair up cleanly.
//
// Mirrors the pagination in showProject(): spread (spread===1) -> full leaf;
// video/embed -> its own leaf; single + adjacent single -> duo; lone single -> solo.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(ROOT, 'index.html'), 'utf8');
const m = html.match(/const PROJECTS = (\[.*?\]);/s);
const projects = JSON.parse(m[1]);

const isSpread = (it) => !!(it && it.spread === 1);
const isFramed = (it) => !!(it && (it.type === 'video' || it.type === 'embed'));
const fname = (src) => decodeURIComponent(src).split('/').pop();

const flagged = [];
for (const p of projects) {
  const media = [...(p.images || [])];
  if (p.video) media.push({ type: 'embed' });
  const singleCount = media.filter(it => !isSpread(it) && !isFramed(it)).length;
  const orphans = [];
  for (let k = 0; k < media.length;) {
    const it = media[k];
    if (isFramed(it)) { k += 1; continue; }
    if (isSpread(it)) { k += 1; continue; }
    const nx = media[k + 1];
    if (nx && !isFramed(nx) && !isSpread(nx)) { k += 2; }        // duo
    else { orphans.push({ index: k + 1, src: it.src }); k += 1; } // unpaired single
  }
  if (orphans.length) flagged.push({ id: p.id, title: p.title, singleCount, orphans });
}

if (!flagged.length) {
  console.log('No unpaired singles. Every single pairs cleanly.');
} else {
  console.log(`${flagged.length} project(s) have an unpaired single (renders left page + blank facing page):\n`);
  for (const f of flagged) {
    console.log(`• ${f.title}  [${f.id}]  — ${f.singleCount} single(s)`);
    for (const o of f.orphans) console.log(`    image ${o.index}: ${fname(o.src)}`);
  }
}
