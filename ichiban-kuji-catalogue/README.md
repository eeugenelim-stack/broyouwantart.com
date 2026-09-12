# Ichiban Kuji prize catalogue

Builds `ichiban_kuji_prize_catalogue.pdf` from the official 1kuji.com product
pages listed in `sources.txt`.

## Why the PDF isn't in this branch

The catalogue could not be generated in the Claude Code session that wrote these
scripts, for two independent reasons.

**1. No network access to 1kuji.com.** The session's egress proxy refuses all
outbound HTTP. `1kuji.com` returns `CONNECT tunnel failed, response 403`, and so
does every other host tested (`example.com`, `cdn.shopify.com`, Wikipedia). Both
`curl` and the agent's fetch tool are blocked identically. With no page HTML and
no image bytes, there is nothing to put in a PDF — and substituting reseller,
marketplace or search-engine images is explicitly out of scope.

**2. The supplied URLs look like the wrong slugs.** Spot checks against the live
site (via web search, which routes around the proxy) show real 1kuji.com product
slugs are short codes, not long descriptive ones:

| Supplied in `sources.txt` | Appears to actually be |
| --- | --- |
| `/products/sakamoto-days-vol2` | `/products/sakamotodays2` |
| `/products/chiikawa-chiikawas-public-bath` | `/products/chiikawa4` |
| `/products/pokemon-megaevolution` | `/products/pk_mega` |

Run `--check-only` (below) before a full scrape to see how many of the 53 resolve.

## Requirements

```
pip install requests beautifulsoup4 pillow reportlab
```

## Use

```bash
# 0. Which of the 53 URLs actually resolve?
python3 kuji_scrape.py --sources sources.txt --check-only

# 1. Scrape pages, download official images, write build/manifest.json
python3 kuji_scrape.py --sources sources.txt --out build --dump-html

# 2. Render the catalogue
python3 kuji_build_pdf.py --manifest build/manifest.json \
    --out ichiban_kuji_prize_catalogue.pdf
```

`--dump-html` saves each page's raw HTML to `build/html/`. Keep it on for the
first run: the extraction heuristics in `kuji_scrape.py` were written without
access to the live DOM, so the selectors will likely need one pass of tuning
against a real page.

## English prize names

The official pages are Japanese, so the scraper records `name_ja` for each prize
and leaves `name_en` blank. Fill `name_en` in `build/manifest.json` before step 2
to get fully English labels; the PDF falls back to the Japanese name where
`name_en` is empty, and `kuji_build_pdf.py` renders CJK correctly either way.

## What the scraper guarantees

- Images are kept only if served from `1kuji.com` — off-domain URLs are dropped,
  so reseller/fan images cannot enter the manifest.
- Banners, logos and UI furniture are filtered by URL keyword, by minimum pixel
  size (200px), and by aspect ratio (anything past 3:1).
- Duplicate images are rejected by SHA-256 of the image bytes.
- `A賞`/`ラストワン賞`/`ダブルチャンス賞` map to `Prize A` / `Last One Prize` /
  `Double Chance Prize`; multiple designs under one letter become `Prize F-1`,
  `Prize F-2`, ...

## Checking the layout without network

`make_fixture.py` builds a synthetic manifest covering every layout rule —
collection overflow, Last One and Double Chance prizes, F-1/F-2 variants,
extreme aspect ratios, Japanese names, and a missing image:

```bash
python3 make_fixture.py build-fixture
python3 kuji_build_pdf.py --manifest build-fixture/manifest.json --out sample.pdf
```

This path is verified working: 4 collections / 17 prizes / 2 missing → 7 pages.
