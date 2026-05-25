#!/usr/bin/env python3
"""Find images currently tagged spread:1 that are actually SINGLE pages.

A double-page spread bleeds content to at least one vertical edge. A single page
sits matted on a uniform (white/grey) canvas, so it has a wide uniform margin on
BOTH the left and right. We measure the contiguous uniform-bright margin from
each edge; if both are wide, it's a single that slipped through aspect-ratio
tagging.

Usage:
    python3 tools/detect-singles.py            # report candidates
    python3 tools/detect-singles.py --calibrate /abs/img1.jpg /abs/img2.jpg
"""
import sys, os, re, json, urllib.parse
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")

ANALYZE_W = 240          # downsample width for speed (margins are fractional)
STD_MAX = 14             # a column is "uniform" if its std is below this
MEAN_MIN = 185           # ...and "bright" (white/light-grey canvas) above this
MARGIN_MIN = 0.10        # single if BOTH side margins are >= 10% of width


def col_stats(px, W, H, x):
    vals = [px[x, y] for y in range(H)]
    m = sum(vals) / H
    var = sum((v - m) ** 2 for v in vals) / H
    return m, var ** 0.5


def margins(path):
    im = Image.open(path).convert("L")
    W0, H0 = im.size
    H = max(1, int(ANALYZE_W * H0 / W0))
    im = im.resize((ANALYZE_W, H))
    px = im.load()
    W = ANALYZE_W

    def is_bg(x):
        m, s = col_stats(px, W, H, x)
        return s < STD_MAX and m > MEAN_MIN

    left = 0
    while left < W and is_bg(left):
        left += 1
    right = 0
    while right < W and is_bg(W - 1 - right):
        right += 1
    return left / W, right / W


def verdict(lf, rf):
    return lf >= MARGIN_MIN and rf >= MARGIN_MIN


def decode(src):
    return os.path.join(ROOT, urllib.parse.unquote(src))


if "--calibrate" in sys.argv:
    for p in sys.argv[sys.argv.index("--calibrate") + 1:]:
        lf, rf = margins(p)
        print(f"L={lf:.2f} R={rf:.2f} -> {'SINGLE' if verdict(lf,rf) else 'spread'}  {p}")
    sys.exit(0)

html = open(HTML, encoding="utf-8").read()
m = re.search(r"const PROJECTS = (\[.*?\]);", html, re.S)
projects = json.loads(m.group(1))

candidates = []
checked = 0
for p in projects:
    for img in p.get("images", []):
        if img.get("spread") != 1:
            continue
        checked += 1
        path = decode(img["src"])
        if not os.path.exists(path):
            continue
        lf, rf = margins(path)
        if verdict(lf, rf):
            candidates.append((min(lf, rf), lf, rf, p["id"], img["src"]))

candidates.sort(reverse=True)
print(f"checked {checked} spread-tagged images; {len(candidates)} look like SINGLES:\n")
for mn, lf, rf, pid, src in candidates:
    print(f"  L={lf:.2f} R={rf:.2f}  {pid}  ::  {urllib.parse.unquote(src).split('/')[-1]}")
