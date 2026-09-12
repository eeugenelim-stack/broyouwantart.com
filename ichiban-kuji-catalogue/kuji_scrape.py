#!/usr/bin/env python3
"""Phase 1: scrape official Ichiban Kuji product pages into a prize manifest.

Visits each product URL, extracts every official prize image together with its
prize label (A/B/C..., Last One, Double Chance), downloads the image bytes, and
writes `manifest.json` for `kuji_build_pdf.py` to turn into the catalogue PDF.

Only images served from 1kuji.com (and its own asset hosts) are kept — anything
off-domain is dropped, so reseller/marketplace/fan images can never enter the
manifest.

Usage:
    python3 kuji_scrape.py --sources sources.txt --out build/
    python3 kuji_scrape.py --sources sources.txt --check-only
    python3 kuji_scrape.py --sources sources.txt --out build/ --dump-html
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from PIL import Image
except ImportError:  # Pillow is optional; it only powers size/aspect filtering.
    Image = None

# Hosts whose images count as "official". Everything else is rejected.
OFFICIAL_HOSTS = ("1kuji.com",)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# --- prize label recognition -------------------------------------------------
# The official pages are Japanese. These map the on-page label to the English
# label the catalogue must print.

JP_LETTER_PRIZE = re.compile(r"([A-Z])\s*賞")
EN_LETTER_PRIZE = re.compile(r"\bPrize\s+([A-Z])\b", re.I)
LAST_ONE = ("ラストワン賞", "ラストワン", "last one")
DOUBLE_CHANCE = ("ダブルチャンス賞", "ダブルチャンス", "double chance")

# Filename/path fragments that mark furniture rather than prize art.
JUNK_URL_PATTERNS = (
    "logo", "banner", "header", "footer", "icon", "btn", "button", "bg_",
    "/bg/", "common", "sns", "ogp", "share", "nav", "menu", "arrow", "spacer",
    "dummy", "noimage", "no_image", "placeholder", "favicon", "sprite",
)

MIN_IMAGE_PX = 200          # smaller than this in either axis => furniture
MAX_ASPECT_RATIO = 3.0      # wider/taller than 3:1 => almost certainly a banner


@dataclasses.dataclass
class Prize:
    label: str              # "Prize A", "Last One Prize", "Double Chance Prize"
    name_ja: str = ""       # official Japanese prize name, as printed on the page
    name_en: str = ""       # English name; filled from translations.json
    image_url: str = ""
    image_file: str = ""    # path relative to the manifest, "" if unavailable
    note: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def is_official(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in OFFICIAL_HOSTS)


def looks_like_junk(url: str) -> bool:
    low = url.lower()
    return any(p in low for p in JUNK_URL_PATTERNS)


def english_label(text: str) -> str | None:
    """Turn an on-page label into the catalogue's English label, or None."""
    if not text:
        return None
    low = text.lower()
    if any(k in text for k in LAST_ONE[:2]) or "last one" in low:
        return "Last One Prize"
    if any(k in text for k in DOUBLE_CHANCE[:2]) or "double chance" in low:
        return "Double Chance Prize"
    m = JP_LETTER_PRIZE.search(text) or EN_LETTER_PRIZE.search(text)
    if m:
        return f"Prize {m.group(1).upper()}"
    return None


def count_labels(text: str) -> int:
    """How many distinct prize labels appear in this block of text."""
    n = len(set(JP_LETTER_PRIZE.findall(text))) + len(set(EN_LETTER_PRIZE.findall(text)))
    low = text.lower()
    n += any(k in text for k in LAST_ONE[:2]) or "last one" in low
    n += any(k in text for k in DOUBLE_CHANCE[:2]) or "double chance" in low
    return n


def nearest_label(tag) -> tuple[str | None, str]:
    """Walk outward from an <img> looking for its prize label and name.

    1kuji.com groups each prize in a card; the label ("A賞") and the prize name
    live in sibling/ancestor text. Climb until a label turns up — but stop as
    soon as an ancestor holds more than one label, because that means we have
    climbed past this prize's own card into a container of several prizes and
    any label found there would belong to a different prize.
    """
    node = tag
    for _ in range(6):
        node = node.parent
        if node is None:
            break
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        if count_labels(text) > 1:
            break  # overshot the card — don't guess
        label = english_label(text)
        if label:
            # Strip the label itself off the front to leave the prize name.
            name = JP_LETTER_PRIZE.sub("", text, count=1)
            name = EN_LETTER_PRIZE.sub("", name, count=1)
            for kw in LAST_ONE[:2] + DOUBLE_CHANCE[:2]:
                name = name.replace(kw, "")
            return label, re.sub(r"\s+", " ", name).strip(" ：:-—|")[:120]
    # Fall back to the image's own alt text.
    alt = (tag.get("alt") or "").strip()
    return english_label(alt), alt[:120]


def candidate_image_urls(tag, page_url: str) -> list[str]:
    """All plausible sources for one <img>, best (largest) first."""
    urls: list[str] = []
    srcset = tag.get("srcset") or tag.get("data-srcset") or ""
    if srcset:
        parsed = []
        for part in srcset.split(","):
            bits = part.strip().split()
            if not bits:
                continue
            width = 0
            if len(bits) > 1 and bits[1].endswith("w"):
                try:
                    width = int(bits[1][:-1])
                except ValueError:
                    width = 0
            parsed.append((width, bits[0]))
        urls += [u for _, u in sorted(parsed, reverse=True)]
    for attr in ("data-original", "data-src", "data-lazy-src", "src"):
        val = tag.get(attr)
        if val:
            urls.append(val)
    seen, out = set(), []
    for u in urls:
        absolute = urljoin(page_url, u.strip())
        if absolute not in seen:
            seen.add(absolute)
            out.append(absolute)
    return out


def collection_title(soup: BeautifulSoup, url: str) -> str:
    for sel in ("h1", "meta[property='og:title']", "title"):
        node = soup.select_one(sel)
        if node is None:
            continue
        text = node.get("content") if node.name == "meta" else node.get_text(strip=True)
        if text:
            # Drop the site suffix the pages append after a full-width bar.
            return re.split(r"[｜|]", text)[0].strip()
    return urlparse(url).path.rsplit("/", 1)[-1]


def acceptable_image(data: bytes) -> tuple[bool, str]:
    """Reject furniture by pixel size and aspect ratio."""
    if Image is None:
        return True, ""
    try:
        img = Image.open(io.BytesIO(data))
        w, h = img.size
    except Exception as exc:
        return False, f"unreadable image ({exc})"
    if w < MIN_IMAGE_PX or h < MIN_IMAGE_PX:
        return False, f"too small ({w}x{h})"
    ratio = max(w / h, h / w)
    if ratio > MAX_ASPECT_RATIO:
        return False, f"banner-like aspect ratio ({w}x{h})"
    return True, ""


def scrape_page(session: requests.Session, url: str, image_dir: Path,
                seen_hashes: dict[str, str], dump_html: Path | None) -> dict:
    """Return one collection record, including any failure reason."""
    record = {"title": "", "source_url": url, "prizes": [], "error": ""}
    try:
        resp = session.get(url, timeout=30)
    except Exception as exc:
        record["error"] = f"request failed: {exc}"
        return record
    if resp.status_code != 200:
        record["error"] = f"HTTP {resp.status_code}"
        return record

    if dump_html is not None:
        slug = urlparse(url).path.rsplit("/", 1)[-1] or "page"
        (dump_html / f"{slug}.html").write_text(resp.text, encoding="utf-8")

    soup = BeautifulSoup(resp.text, "html.parser")
    record["title"] = collection_title(soup, url)

    # Collect one prize per (label, image) pair, in document order.
    by_label: dict[str, list[Prize]] = {}
    for tag in soup.find_all("img"):
        label, name = nearest_label(tag)
        if label is None:
            continue  # not tied to a prize — skip rather than guess
        for img_url in candidate_image_urls(tag, url):
            if not is_official(img_url) or looks_like_junk(img_url):
                continue
            try:
                img_resp = session.get(img_url, timeout=30)
                img_resp.raise_for_status()
            except Exception:
                continue
            data = img_resp.content
            ok, why = acceptable_image(data)
            if not ok:
                continue
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen_hashes:
                break  # duplicate image — requirement 10
            ext = Path(urlparse(img_url).path).suffix.lower() or ".jpg"
            if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
                ext = ".jpg"
            fname = f"{digest[:16]}{ext}"
            (image_dir / fname).write_bytes(data)
            seen_hashes[digest] = fname
            by_label.setdefault(label, []).append(
                Prize(label=label, name_ja=name, image_url=img_url,
                      image_file=f"images/{fname}")
            )
            break  # first acceptable candidate is the highest quality one

    # Requirement 11: multiple official designs under one letter become F-1/F-2.
    prizes: list[Prize] = []
    for label, group in by_label.items():
        if len(group) == 1:
            prizes.append(group[0])
        else:
            for i, prize in enumerate(group, 1):
                prize.label = f"{label}-{i}" if prize.label.startswith("Prize") \
                    else f"{label} ({i})"
                prizes.append(prize)

    prizes.sort(key=prize_sort_key)
    record["prizes"] = [p.to_dict() for p in prizes]
    if not prizes:
        record["error"] = "page fetched but no prize images matched"
    return record


def prize_sort_key(p: Prize) -> tuple:
    """A, B, C... then Last One, then Double Chance."""
    label = p.label
    if label.startswith("Prize"):
        m = re.match(r"Prize ([A-Z])(?:-(\d+))?", label)
        if m:
            return (0, m.group(1), int(m.group(2) or 0))
    if label.startswith("Last One"):
        return (1, "", 0)
    return (2, "", 0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", default="sources.txt")
    ap.add_argument("--out", default="build")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between page requests (be polite)")
    ap.add_argument("--check-only", action="store_true",
                    help="only report which URLs resolve; download nothing")
    ap.add_argument("--dump-html", action="store_true",
                    help="save each page's raw HTML for selector debugging")
    args = ap.parse_args()

    urls = [
        line.strip()
        for line in Path(args.sources).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    print(f"{len(urls)} source URLs", file=sys.stderr)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT,
                            "Accept-Language": "ja,en;q=0.8"})

    if args.check_only:
        bad = 0
        for url in urls:
            try:
                code = session.head(url, timeout=20, allow_redirects=True).status_code
            except Exception as exc:
                code = f"ERR {exc}"
            flag = "ok " if code == 200 else "BAD"
            if code != 200:
                bad += 1
            print(f"{flag} {code:<24} {url}")
            time.sleep(args.delay)
        print(f"\n{len(urls) - bad}/{len(urls)} reachable", file=sys.stderr)
        return 1 if bad else 0

    out = Path(args.out)
    image_dir = out / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    dump_dir = None
    if args.dump_html:
        dump_dir = out / "html"
        dump_dir.mkdir(parents=True, exist_ok=True)

    seen_hashes: dict[str, str] = {}
    collections = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}", file=sys.stderr)
        rec = scrape_page(session, url, image_dir, seen_hashes, dump_dir)
        if rec["error"]:
            print(f"    !! {rec['error']}", file=sys.stderr)
        else:
            print(f"    {len(rec['prizes'])} prizes", file=sys.stderr)
        collections.append(rec)
        time.sleep(args.delay)

    manifest = {"collections": collections}
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(c["prizes"]) for c in collections)
    failed = sum(1 for c in collections if c["error"])
    print(f"\nmanifest: {out/'manifest.json'}", file=sys.stderr)
    print(f"{len(collections)} collections, {total} prizes, "
          f"{failed} pages with problems", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
